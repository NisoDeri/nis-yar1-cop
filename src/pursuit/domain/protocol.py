"""Wire envelopes — TurnMessage & ControlMessage, byte-faithful to INTEROP §2.

This module owns the two ``message``-keyed tool bodies (§2.2 turn, §2.4 control).
The ``payload``-keyed audit envelope, the sealed-step builder and the move-string
codec live in :mod:`pursuit.domain.protocol_audit` (150-line split).

Strictness contract (which keys are extension-tolerant, per INTEROP):

- **TurnMessage** — STRICT both ways: ``step/sender/hint/smell_grid/commit/timestamp``
  required, the four claim fields optional (``null``), unknown TOP-LEVEL keys REJECTED
  (the reference parses via ``TurnMessage(**data)``, so an extra key breaks a stock
  peer) → TransportError. True position/move/intent are NEVER here — they travel
  sealed inside ``commit`` (nonce withheld until audit).
- **ControlMessage** — only ``kind``/``sender`` enforced; unknown keys are SILENTLY
  DROPPED. This is the one forward-compatible envelope we may extend freely (§2.4).
"""

from __future__ import annotations

from collections.abc import Container
from dataclasses import dataclass
from typing import Any

from pursuit.constants import Role
from pursuit.exceptions import TransportError

# Fixed hint literals a partner sends/expects verbatim (§2.2; landmine 8).
CAPTURE_CONCESSION_HINT = "You got me."
SILENCE_HINT = "(silence)"
FALLBACK_HINT = "I keep moving through the streets."

CONTROL_KINDS = frozenset({"enable", "status", "restart", "quit"})

_ROLES = frozenset(role.value for role in Role)
# Required turn fields with their shallow JSON types (§2.2 field contract).
_TURN_REQUIRED: dict[str, type] = {
    "step": int,
    "sender": str,
    "hint": str,
    "smell_grid": dict,
    "commit": str,
    "timestamp": str,
}
_TURN_OPTIONAL = ("barrier_placed", "capture_claim", "claim_response", "win_claim")
_CONTROL_OPTIONAL = ("sub_game_number", "status", "step_budget", "payload")


def validate_envelope(
    data: Any, spec: dict[str, type], known: Container[str] | None, envelope: str
) -> None:
    """One strict wire gate: dict-shaped, required keys present and typed, no unknowns.

    ``known=None`` skips the unknown-key rejection — the tolerant ControlMessage path.
    A bool masquerading as int is rejected (JSON booleans are never wire counters).
    Every failure is a TransportError naming the offending field(s) (rule 4).
    """
    if not isinstance(data, dict):
        raise TransportError(f"{envelope} body must be a dict, got {type(data).__name__}")
    if missing := [key for key in spec if key not in data]:
        raise TransportError(f"{envelope} missing required field(s): {missing}")
    if known is not None and (unknown := [key for key in data if key not in known]):
        raise TransportError(f"{envelope} unknown field(s): {unknown}")
    for key, typ in spec.items():
        value = data[key]
        if not isinstance(value, typ) or (typ is int and isinstance(value, bool)):
            raise TransportError(f"{envelope} field {key!r} must be {typ.__name__}")


def require_role(sender: Any, envelope: str) -> None:
    """``sender`` must be one of the two wire role strings."""
    if sender not in _ROLES:
        raise TransportError(f"{envelope} sender must be one of {sorted(_ROLES)}: {sender!r}")


@dataclass(frozen=True)
class TurnMessage:
    """§2.2 body of ``receive_turn`` — possession of it IS the turn token."""

    step: int  # sender's OWN 1-based counter; MOVE/BARRIER/HOLD all increment (A5)
    sender: str  # "thief" | "police"
    hint: str  # free NL, <= hint_max_words, MAY lie; never coordinates (rule 27)
    smell_grid: dict[str, float]  # decaying scent {"r,c": intensity}, no spaces, >0 only
    commit: str  # sha256 hex of the sealed step payload (protocol_audit.sealed_payload)
    timestamp: str  # ISO-8601 UTC
    barrier_placed: list[int] | None = None  # cop's mandatory truthful [r, c] declaration
    capture_claim: list[int] | None = None  # cop, EVERY MOVE turn: own landing cell
    claim_response: dict[str, Any] | None = None  # thief: {"claim": [r, c], "caught": bool}
    win_claim: dict[str, Any] | None = None  # thief: {"type": "survival"} at max_steps

    def to_wire(self) -> dict[str, Any]:
        """The full 10-key wire dict; nullable fields emitted as null (reference shape)."""
        return {
            "step": self.step,
            "sender": self.sender,
            "hint": self.hint,
            "smell_grid": dict(self.smell_grid),
            "commit": self.commit,
            "timestamp": self.timestamp,
            "barrier_placed": self.barrier_placed,
            "capture_claim": self.capture_claim,
            "claim_response": self.claim_response,
            "win_claim": self.win_claim,
        }

    @classmethod
    def from_wire(cls, data: dict[str, Any]) -> TurnMessage:
        """Strict parse: missing required, unknown key, or bad type → TransportError."""
        all_keys = (*_TURN_REQUIRED, *_TURN_OPTIONAL)
        validate_envelope(data, _TURN_REQUIRED, all_keys, "TurnMessage")
        require_role(data["sender"], "TurnMessage")
        return cls(**{key: data.get(key) for key in all_keys})


@dataclass(frozen=True)
class ControlMessage:
    """§2.4 advisory channel body — never part of the sealed record."""

    kind: str  # enable | status | restart | quit
    sender: str
    sub_game_number: int | None = None
    status: str | None = None  # one of the reference's 7 labels (peer/fsm.WIRE_LABELS)
    step_budget: float | None = None
    payload: dict[str, Any] | None = None

    def to_wire(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "sender": self.sender,
            "sub_game_number": self.sub_game_number,
            "status": self.status,
            "step_budget": self.step_budget,
            "payload": self.payload,
        }

    @classmethod
    def from_wire(cls, data: dict[str, Any]) -> ControlMessage:
        """Tolerant parse: only kind/sender enforced; unknown keys silently dropped."""
        validate_envelope(data, {"kind": str, "sender": str}, None, "ControlMessage")
        if data["kind"] not in CONTROL_KINDS:
            raise TransportError(f"ControlMessage kind must be one of {sorted(CONTROL_KINDS)}")
        require_role(data["sender"], "ControlMessage")
        optional = {key: data.get(key) for key in _CONTROL_OPTIONAL}
        return cls(kind=data["kind"], sender=data["sender"], **optional)
