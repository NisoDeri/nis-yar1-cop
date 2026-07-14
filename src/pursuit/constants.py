"""Core enums and wire literals — the single vocabulary every module shares.

Wire string values are pinned by the reference protocol (planning/INTEROP.md):
moves travel as "MOVE:N" / "HOLD" / "BARRIER:E"; roles as "police"/"thief".
"""

from enum import StrEnum


class Role(StrEnum):
    POLICE = "police"
    THIEF = "thief"

    @property
    def opponent(self) -> "Role":
        return Role.THIEF if self is Role.POLICE else Role.POLICE


class Direction(StrEnum):
    N = "N"
    S = "S"
    E = "E"
    W = "W"
    STAY = "STAY"


# (row, col) deltas — origin top-left, row grows downward (book Table 13 defaults).
DIRECTION_DELTAS: dict[Direction, tuple[int, int]] = {
    Direction.N: (-1, 0),
    Direction.S: (1, 0),
    Direction.E: (0, 1),
    Direction.W: (0, -1),
    Direction.STAY: (0, 0),
}


class MoveType(StrEnum):
    MOVE = "MOVE"
    HOLD = "HOLD"
    BARRIER = "BARRIER"


class GameResult(StrEnum):
    """Sub-game ending strings as they appear in the result artifact."""

    CAPTURE = "capture"
    SURVIVAL = "survival"
    TECHNICAL_LOSS = "technical_loss"  # timeout / crash / forgery -> 0/0 (rulings A6, A9a)
    STOPPED = "stopped"


Cell = tuple[int, int]
