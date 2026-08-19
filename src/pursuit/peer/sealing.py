"""SealedLog — the per-step commit-reveal chain (book rule 18; 4-stage ruling A8).

Each step's true position/move/intent is SEALED: only the sha256 ``commit`` travels in the
TurnMessage; the nonce stays local until the single end-of-game reveal (ruling A8 stage 4 =
``audit_reveal``). ``records[0]`` is the Ed25519-signed hardware/spec declaration (D14,
rules 24/37/53) carrying the REAL github commit (fixing the reference's literal
``"unknown"``, INTEROP §5.5 item 1) and the counted-games ledger INSIDE the signed payload
(rule 37, A9b). A record failing the cross-audit is provable forgery: the sub-game is
adjudicated ``technical_loss`` 0/0 and BOTH groups must report it (ruling A9a). The commit
dialect comes from the SIGNED shared ``crypto`` config block (rule-23 lock, D3).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pursuit.domain.crypto import (
    HashDialect,
    generate_nonce,
    make_hash_dialect,
    sign,
    verify_signature,
)
from pursuit.shared.config import ConfigManager

#: Sealed-payload keys that reveal position/strategy (INTEROP §2.2 seal semantics) —
#: stripped from any pre-audit view; they exist in cleartext ONLY at the final reveal.
SECRET_PAYLOAD_KEYS: tuple[str, ...] = (
    "state", "position", "move", "intent", "verdict", "prompt_discussion", "random_move",
)  # fmt: skip

STEP0_SIGNATURE_KEY = "signature"


def verify_step0_signature(step0_payload: Mapping[str, Any], public_pem: bytes) -> bool:
    """True iff the step-0 payload carries a valid Ed25519 signature by ``public_pem``.

    The signature covers the payload SANS its own ``signature`` key (D14). Total over
    adversarial input — malformed material is False, never a crash.
    """
    signature = step0_payload.get(STEP0_SIGNATURE_KEY)
    if not isinstance(signature, str):
        return False
    unsigned = {k: v for k, v in step0_payload.items() if k != STEP0_SIGNATURE_KEY}
    return verify_signature(public_pem, unsigned, signature)


class SealedLog:
    """Ordered sealed records for one sub-game — commit now, reveal nonces at audit."""

    def __init__(self, crypto_cfg: Mapping[str, Any] | None) -> None:
        """Build with the negotiated ``crypto`` config block (D3; ruling A1 default)."""
        self._dialect: HashDialect = make_hash_dialect(crypto_cfg)
        self._records: list[dict[str, Any]] = []

    @property
    def dialect(self) -> HashDialect:
        """The negotiated commit dialect instance (shared with audit/replay)."""
        return self._dialect

    def seal_step(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        """Seal one step: fresh secret nonce + commit; append to the local chain.

        The returned record CONTAINS the nonce — a LOCAL artifact (rule 18/A8); only
        ``wire_view`` material may hit the wire before the final audit.
        """
        nonce = generate_nonce()
        record = {
            "payload": dict(payload),
            "nonce": nonce,
            "commit": self._dialect.commit(payload, nonce),
        }
        self._records.append(record)
        return record

    @staticmethod
    def wire_view(record: Mapping[str, Any]) -> dict[str, Any]:
        """Pre-audit projection: NO nonce, NO position/strategy keys — feeds the
        TurnMessage (``commit``) and the live UI without leaking what the commit hides."""
        payload: Mapping[str, Any] = record["payload"]
        public = {k: v for k, v in payload.items() if k not in SECRET_PAYLOAD_KEYS}
        return {"payload": public, "commit": record["commit"]}

    def step0_record(
        self,
        config: ConfigManager,
        sysinfo: Mapping[str, Any],
        github_commit: str,
        counted_games: int,
        keypair: tuple[bytes, bytes],
        sub_game_number: int | None = None,
    ) -> dict[str, Any]:
        """Seal ``records[0]`` — the Ed25519-signed system_spec declaration (D14).

        Extra payload keys (``github_commit``, ``counted_games``, ``public_key``,
        ``signature``) are audit-safe: a reference auditor recomputes the commit from the
        self-describing payload (INTEROP §2.3). ``counted_games`` sits INSIDE the signed
        blob so the rule-37 ledger cannot be reset mid-series (ruling A9b).
        """
        private_pem, public_pem = keypair
        payload: dict[str, Any] = {
            "step": 0,
            "type": "system_spec",
            "spec": dict(sysinfo),
            "model": config.private("trash_talk.model"),
            "code_version": config.private("version"),
            "group_name": config.private("game.group_name"),
            "sub_game_number": (
                int(sub_game_number) if sub_game_number is not None
                else config.private("game.sub_game_number")
            ),
            "github_commit": github_commit,
            "counted_games": counted_games,
            "public_key": public_pem.decode("ascii"),
        }
        payload[STEP0_SIGNATURE_KEY] = sign(private_pem, payload)
        return self.seal_step(payload)

    def audit_reveal(self) -> list[dict[str, Any]]:
        """All sealed records WITH nonces — the ``records[]`` of our AuditPayload
        (A8 stage 4: the ONE moment nonces leave the process, end of sub-game)."""
        return [
            {"payload": dict(r["payload"]), "nonce": r["nonce"], "commit": r["commit"]}
            for r in self._records
        ]

    @staticmethod
    def audit_verify(
        their_records: Sequence[Any], their_dialect: HashDialect
    ) -> list[dict[str, Any]]:
        """Recompute every revealed record's commit — per-step pass/fail list.

        ANY ``ok: False`` entry is provable forgery: adjudicate ``technical_loss`` 0/0
        and report it (ruling A9a). Total over adversarial input: malformed records
        fail, never crash our audit.
        """
        results: list[dict[str, Any]] = []
        for index, record in enumerate(their_records):
            fields = record if isinstance(record, Mapping) else {}
            payload, nonce, commit = (fields.get(k) for k in ("payload", "nonce", "commit"))
            step = payload.get("step", index) if isinstance(payload, Mapping) else index
            well_formed = (
                isinstance(payload, Mapping) and isinstance(nonce, str) and isinstance(commit, str)
            )
            if not well_formed:
                reason = "malformed record"
            elif their_dialect.verify(payload, nonce, commit):
                reason = ""
            else:
                reason = "revealed payload+nonce != commit"
            results.append({"step": step, "ok": reason == "", "reason": reason})
        return results
