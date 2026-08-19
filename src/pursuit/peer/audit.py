"""End-game mutual audit exchange (architecture §2 ``peer/audit.py``; rulings A6/A8/A9).

Runs on EVERY ending — capture, survival, timeout, crash, breach (D4; fixes reference
gap #5): we always push our own reveal (best-effort, the transport suppresses expiry),
then wait one bounded window for theirs. A missing opponent payload is legal (INTEROP
§2.3 — the winner may exit first) and is NOT forgery; a revealed record whose commit
does not recompute, or a step-0 declaration whose D14 Ed25519 signature fails against
the pubkey locked at the handshake, IS provable forgery → the caller adjudicates
``technical_loss`` 0/0 and both groups must report it (ruling A9a).
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from pursuit.constants import GameResult, Role
from pursuit.domain.protocol_audit import AuditPayload, AuditRecord
from pursuit.exceptions import DeadlineError, TransportError
from pursuit.peer.replay_audit import trajectory_mismatches
from pursuit.peer.sealing import SealedLog, verify_step0_signature


@dataclass(frozen=True)
class SubgameOutcome:
    """One finished, audit-adjudicated sub-game — everything the series driver needs."""

    result: GameResult
    winner: Role | None
    scores: dict[Role, int]  # straight from the signed scoring config (Table 17)
    audit: dict[str, Any]
    records: list[dict[str, Any]]  # my sealed chain, nonces revealed (post-audit)
    steps: int  # my OWN step counter (ruling A5)
    end_state_digest: str | None
    end_state_digest_preimage: str
    game_id: str
    game_uid: str
    opponent_group: str
    opponent_identity: dict[str, Any]
    started_at: str | None = None
    ended_at: str | None = None


def _reveal_mismatches(records: Any, live_commits: dict[int, str]) -> list[int]:
    """Steps whose REVEALED commit != the commit the opponent broadcast LIVE that turn.

    Without this, ``audit_verify`` only proves the revealed chain is self-consistent, so a
    peer could seal a fresh internally-valid chain at reveal and swap the move it played
    after seeing ours — defeating commit-reveal. A mismatch here is provable forgery.
    """
    bad: list[int] = []
    for rec in records:
        step = rec.payload.get("step") if isinstance(rec.payload, dict) else None
        if step in live_commits and live_commits[step] != rec.commit:
            bad.append(step)
    return bad


def exchange_audits(role: Role, result: GameResult, log: SealedLog, transport: Any,
                    audits_inbox: Any, deadlines: Any, audit_timeout: float,
                    opponent_pubkey: str | None,
                    live_commits: dict[int, str] | None = None,
                    board: Any = None) -> dict[str, Any]:
    """A8 stage 4: reveal every nonce both ways; verify theirs; report per-step results.

    Beyond recomputing each revealed commit, we BIND every revealed commit to the one the
    opponent broadcast live that turn (``live_commits``) — a mismatch is a move-swap forgery.
    Returns the audit dict: ``passed`` / ``forgery`` / ``opponent_received`` / ``steps`` /
    ``failed_steps`` (+ ``their_claim`` when the opponent's payload arrived).
    """
    mine = AuditPayload(sender=role.value, result_claim=result.value,
                        records=[AuditRecord(**rec) for rec in log.audit_reveal()])
    outbound = transport.submit_audit(mine.to_wire())
    audit: dict[str, Any] = {"passed": False, "forgery": False,
                             "opponent_received": False, "steps": [], "failed_steps": [],
                             "outbound_accepted": bool(outbound and outbound.get("ok")),
                             "ignored_payloads": 0}
    expected_sub_game = None
    if mine.records:
        expected_sub_game = mine.records[0].payload.get("sub_game_number")
    deadlines.arm("audit-exchange", audit_timeout)
    expires = time.monotonic() + audit_timeout
    try:
        while True:
            remaining = expires - time.monotonic()
            if remaining <= 0:
                raise DeadlineError("audit exchange deadline expired")
            try:
                candidate = AuditPayload.from_wire(audits_inbox.get(timeout=remaining))
            except TransportError:
                audit["ignored_payloads"] += 1
                continue
            candidate_sub_game = None
            if candidate.records:
                candidate_sub_game = candidate.records[0].payload.get("sub_game_number")
            if (candidate.sender != role.opponent.value or
                    candidate_sub_game != expected_sub_game):
                audit["ignored_payloads"] += 1
                continue
            theirs = candidate
            break
    except DeadlineError:
        return audit  # opponent may have exited (INTEROP §2.3) — absence != forgery
    finally:
        deadlines.disarm("audit-exchange")
    steps = SealedLog.audit_verify([rec.to_wire() for rec in theirs.records], log.dialect)
    failed = [step["step"] for step in steps if not step["ok"]]
    failed = sorted(set(failed) | set(_reveal_mismatches(theirs.records, live_commits or {})))
    if board is not None:  # semantic replay: the revealed trajectory must be physically legal
        failed = sorted(set(failed) | set(trajectory_mismatches(theirs.records, board)))
    if not failed and opponent_pubkey and theirs.records and not verify_step0_signature(
            theirs.records[0].payload, opponent_pubkey.encode("ascii")):
        failed = [0]  # forged D14 hardware/ledger declaration (rulings A7/A9b)
    audit.update(passed=not failed, forgery=bool(failed), opponent_received=True,
                 steps=steps, failed_steps=failed, their_claim=theirs.result_claim,
                 their_records=[rec.to_wire() for rec in theirs.records])  # E2 profiler intake
    return audit
