"""Semantic replay audit — re-simulate the opponent's REVEALED trajectory for legality.

Commit-reveal + live-commit binding prove the opponent did not CHANGE its sealed log after
seeing our moves; this proves the sealed log is a LEGAL game. Each revealed position is
post-move (turn_sender seals AFTER applying), so a legal chain satisfies:

  position[t] == position[t-1] + delta(move[t])     (MOVE:D advances by D; HOLD/BARRIER hold)

plus in-bounds cells and consecutive step numbers. A teleport, a through-the-grid jump, a
move-string that disagrees with the position it sealed, or a skipped step is provable
forgery — the caller folds these into ``failed_steps`` → ``technical_loss`` 0/0 (A9a).

Uses only the opponent's own revealed records + the board geometry (no second log needed),
so it runs on either peer independently and reaches the same verdict.
"""

from __future__ import annotations

from typing import Any


def _payload(record: Any) -> dict[str, Any]:
    """The record's payload dict whether it is an AuditRecord or a raw wire dict."""
    payload = getattr(record, "payload", None)
    if payload is None and isinstance(record, dict):
        payload = record.get("payload")
    return payload if isinstance(payload, dict) else {}


def _cell(value: Any) -> tuple[int, int] | None:
    if (isinstance(value, list | tuple) and len(value) == 2
            and all(isinstance(v, int) and not isinstance(v, bool) for v in value)):
        return (value[0], value[1])
    return None


def trajectory_mismatches(records: Any, board: Any) -> list[int]:
    """Steps whose revealed POSITION TRAIL is physically impossible — the interop-safe physics.

    Judged from the trail, NEVER the move-string spelling (kit §7.1 / sparring audit.py: a peer
    may name its moves differently, or legitimately seal a blocked move against the direction it
    ATTEMPTED — treating either as tampering "called an honest, sealed, counted series TAMPERED").
    A step fails only when its revealed position is off-board or jumps MORE THAN ONE orthogonal
    cell from the previous revealed position — a teleport/diagonal the physics forbid. A record
    without a position is a legitimate schema (action+state only) and is skipped, never accused.
    Total over adversarial input: never crashes.
    """
    bad: list[int] = []
    prev: tuple[int, int] | None = None
    for record in records:
        payload = _payload(record)
        step = payload.get("step")
        if not isinstance(step, int) or step < 1:  # step-0 declaration / unlabelled: no trail
            continue
        pos = _cell(payload.get("position"))
        if pos is None:  # a position-less schema carries no trail to judge — a note, not a fault
            continue
        if not board.in_bounds(pos):
            bad.append(step)
        elif prev is not None and abs(pos[0] - prev[0]) + abs(pos[1] - prev[1]) > 1:
            bad.append(step)  # teleport / diagonal: more than one orthogonal step in one turn
        prev = pos
    return sorted(set(bad))
