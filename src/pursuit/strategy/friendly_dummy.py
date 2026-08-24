"""Deliberately uninformative brains used only for friendly transport rehearsals."""

from __future__ import annotations

from typing import Any

from pursuit.constants import Cell, Direction, Role
from pursuit.strategy.base import BeliefLike, BrainBase


class NeutralFriendlyTalk:
    """Emit a fixed, non-positional message and ignore every opponent hint."""

    def say(self, role: Role, state: Any, belief: Any, setting: str,
            opponent_hint: str, deadline: float | None) -> tuple[str, str, str, str]:
        return ("Friendly systems test in progress.", "truth", "neutral friendly", "")


class _FriendlyDummyBrain(BrainBase):
    """Always select STAY when legal; never consult belief or opponent messages."""

    def __init__(self, talk: Any, rng: Any) -> None:
        super().__init__(NeutralFriendlyTalk(), rng)

    def _pick_move(
        self, moves: list[tuple[Direction, Cell]], state: Any, belief: BeliefLike
    ) -> tuple[Direction, Cell]:
        return next((move for move in moves if move[0] is Direction.STAY), moves[0])


class FriendlyDummyPoliceBrain(_FriendlyDummyBrain):
    role = Role.POLICE


class FriendlyDummyThiefBrain(_FriendlyDummyBrain):
    role = Role.THIEF


def friendly_dummy_brain(role: Role | str, rng: Any) -> BrainBase:
    """Build the role-correct friendly-only dummy brain."""
    cls = FriendlyDummyPoliceBrain if Role(role) is Role.POLICE else FriendlyDummyThiefBrain
    return cls(NeutralFriendlyTalk(), rng)
