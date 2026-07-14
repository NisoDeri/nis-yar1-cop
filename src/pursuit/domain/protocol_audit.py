"""AuditPayload envelope, sealed-step builder, move-string codec (INTEROP §2.2-§2.3).

``submit_audit`` is the ONE tool keyed ``payload`` — not ``message`` (landmine 2).
Strictness is asymmetric BY DESIGN: the AuditPayload top level and each record's
``payload/nonce/commit`` triple are STRICT (reference ``Cls(**data)`` semantics), while
keys INSIDE a record's ``payload`` are extension-tolerant — the auditor recomputes each
commit from the payload+nonce, so extras (D9 ``github_commit``) are interop-safe.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from pursuit.constants import Direction, MoveType
from pursuit.domain.protocol import require_role, validate_envelope
from pursuit.exceptions import TransportError

#: The EXACT sealed key set of the per-step commit preimage (§2.2 seal semantics).
SEALED_STEP_KEYS: tuple[str, ...] = (
    "step", "state", "position", "move", "intent", "verdict", "hint",
    "prompt_discussion", "model", "tokens_step", "tokens_total",
    "response_seconds", "random_move",
)
INTENTS = frozenset({"truth", "lie"})
#: §2.3 claims plus our negotiated "technical_loss" ending (rulings A6/A9a, D9 fix 4).
RESULT_CLAIMS = frozenset({"capture", "survival", "timeout", "technical_loss"})
HOLD_WIRE = "HOLD:-"  # staying put always travels as this exact string (§2.2)

# Keys extra= may NEVER override: they define WHAT happened, not telemetry about it.
_IDENTITY_KEYS = frozenset({"step", "state", "position", "move", "intent", "verdict", "hint"})
_RECORD_SPEC: dict[str, type] = {"payload": dict, "nonce": str, "commit": str}
_AUDIT_SPEC: dict[str, type] = {"sender": str, "result_claim": str, "records": list}
_SELF_RE = re.compile(r";self=\[(-?\d+), (-?\d+)\]")  # the state string's own-cell field


def format_move_string(move_type: MoveType, direction: Direction | None = None) -> str:
    """Sealed move form: ``MOVE:S`` / ``BARRIER:E`` / ``HOLD:-``. ``BARRIER:STAY`` is
    legal (own-cell placement, book 5-option rule); ``MOVE:STAY`` is not — that's HOLD."""
    if move_type is MoveType.HOLD:
        return HOLD_WIRE
    if direction is None or (move_type is MoveType.MOVE and direction is Direction.STAY):
        raise TransportError(f"{move_type.value} needs a direction (staying put is HOLD)")
    return f"{move_type.value}:{direction.value}"


def parse_move_string(text: object) -> tuple[MoveType, Direction | None]:
    """Inverse of :func:`format_move_string`; bare ``"HOLD"`` also accepted, holds
    always parse to ``(HOLD, None)``. Anything malformed → TransportError."""
    if not isinstance(text, str):
        raise TransportError(f"move string must be str, got {type(text).__name__}")
    kind, _, tail = text.partition(":")
    try:
        move_type = MoveType(kind)
    except ValueError:
        raise TransportError(f"unknown move type in {text!r}") from None
    if move_type is MoveType.HOLD:
        if tail not in ("", "-"):
            raise TransportError(f"HOLD carries no direction: {text!r}")
        return MoveType.HOLD, None
    try:
        direction = Direction(tail)
    except ValueError:
        raise TransportError(f"unknown direction in {text!r}") from None
    if move_type is MoveType.MOVE and direction is Direction.STAY:
        raise TransportError(f"staying put travels as {HOLD_WIRE!r}, not {text!r}")
    return move_type, direction


def _position_from_state(state_string: str) -> list[int]:
    """Derive ``position`` from the sealed state string so the two can never disagree."""
    match = _SELF_RE.search(state_string)
    if match is None:
        raise TransportError(f"state string has no parsable self cell: {state_string!r}")
    return [int(match.group(1)), int(match.group(2))]


def sealed_payload(
    state_string: str, move_string: str, intent: str, hint: str,
    step: int, role: str, extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the EXACT §2.2 sealed key set — the commit preimage, byte-frozen.

    ``verdict`` duplicates ``intent`` (BOTH keys must be present or hashes break).
    ``role`` is validated but deliberately NOT sealed: sender identity travels in the
    TurnMessage envelope, never in the preimage. ``extra`` may override telemetry keys
    (model/tokens/prompt_discussion/...) and add audit-safe extension keys — never the
    identity keys. Defaults mirror the reference stub-LLM run (§2.3 sample).
    """
    fields = {"step": step, "hint": hint, "state": state_string}
    validate_envelope(fields, {"step": int, "hint": str, "state": str}, None, "sealed payload")
    if intent not in INTENTS:
        raise TransportError(f"sealed payload intent must be one of {sorted(INTENTS)}: {intent!r}")
    require_role(role, "sealed payload")
    parse_move_string(move_string)  # reject a malformed move before it gets hashed
    payload: dict[str, Any] = {
        "step": step, "state": state_string,
        "position": _position_from_state(state_string),
        "move": move_string, "intent": intent, "verdict": intent, "hint": hint,
        "prompt_discussion": {"llm_prompt": "", "llm_reasoning": "",
                              "bluff_classification": intent},
        "model": "stub", "tokens_step": 0, "tokens_total": 0,
        "response_seconds": 0.0, "random_move": False,
    }
    if extra:
        if clashes := sorted(_IDENTITY_KEYS & set(extra)):
            raise TransportError(f"extra may not override sealed identity keys: {clashes}")
        payload.update(extra)
    return payload


@dataclass(frozen=True)
class AuditRecord:
    """One reveal: a sealed payload with its nonce now disclosed (§2.3 records[])."""

    payload: dict[str, Any]  # interior keys are extension-tolerant (self-describing)
    nonce: str
    commit: str

    def to_wire(self) -> dict[str, Any]:
        return {"payload": dict(self.payload), "nonce": self.nonce, "commit": self.commit}

    @classmethod
    def from_wire(cls, data: dict[str, Any]) -> AuditRecord:
        validate_envelope(data, _RECORD_SPEC, _RECORD_SPEC, "AuditRecord")
        return cls(payload=data["payload"], nonce=data["nonce"], commit=data["commit"])


@dataclass(frozen=True)
class AuditPayload:
    """§2.3 body of ``submit_audit``; records[0] is the sealed step-0 system_spec.
    Top level STRICT: only sender/result_claim/records, ever (reference TypeErrors)."""

    sender: str
    result_claim: str
    records: list[AuditRecord]

    def to_wire(self) -> dict[str, Any]:
        return {"sender": self.sender, "result_claim": self.result_claim,
                "records": [record.to_wire() for record in self.records]}

    @classmethod
    def from_wire(cls, data: dict[str, Any]) -> AuditPayload:
        validate_envelope(data, _AUDIT_SPEC, _AUDIT_SPEC, "AuditPayload")
        require_role(data["sender"], "AuditPayload")
        if data["result_claim"] not in RESULT_CLAIMS:
            raise TransportError(f"AuditPayload result_claim not in {sorted(RESULT_CLAIMS)}")
        records = [AuditRecord.from_wire(record) for record in data["records"]]
        return cls(sender=data["sender"], result_claim=data["result_claim"], records=records)
