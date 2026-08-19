"""Lab brain contract — the decision/view seam of the arena (STRATEGY.md §6, D7).

Faithful information partition (STRATEGY §1.2): a brain's whole world is its
:class:`LabView` — own state, own belief, the opponent's broadcast scent
snapshot and hint. The opponent's position object never crosses this seam;
the referee in :mod:`pursuit.lab.arena` is the only holder of both truths.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any, Protocol

from pursuit.constants import Cell, Direction, GameResult, MoveType, Role
from pursuit.domain.own_state import OwnGameState


@dataclass(frozen=True)
class LabDecision:
    """One brain decision: MOVE/HOLD with a direction, or BARRIER with a cell."""

    move_type: MoveType
    direction: Direction | None = None
    barrier_cell: Cell | None = None
    hint: str | None = None


@dataclass(frozen=True)
class LabView:
    """Everything one brain may legally see on its turn — nothing else exists."""

    role: Role
    state: OwnGameState  # own truth only — never contains the opponent's position
    belief: Any
    opponent_scent: dict[str, float]  # opponent's broadcast snapshot, wire form
    opponent_hint: str | None
    moves_left: int
    rng: random.Random


class BrainLike(Protocol):
    def decide(self, view: LabView) -> LabDecision: ...


class NullBelief:
    """No-op belief — the default when no belief_factory is injected."""

    def diffuse(self) -> None: ...

    def observe_smell(self, cells: dict[str, float]) -> None: ...


@dataclass(frozen=True)
class SubgameResult:
    result: GameResult
    winner_role: Role | None
    steps: int  # the thief's OWN valid-move count (ruling A5)
    cop_steps: int  # cop turns consumed — barrier turns included
    capture_kind: str | None  # "landing" | "barrier" | "jailed" | None
    trajectory: tuple[str, ...]


@dataclass
class Side:
    """One peer's full private stack: brain + own state + own scent + belief."""

    role: Role
    brain: BrainLike
    state: OwnGameState
    belief: Any
    scent: Any
    snapshot: dict[str, float] = field(default_factory=dict)
    hint: str | None = None

    def emit(self, decision: LabDecision) -> None:
        """Sender order per STRATEGY §1.2: one dialect-pinned full turn → snapshot."""
        self.scent.full_turn(self.state.position)
        self.snapshot = self.scent.snapshot()
        self.hint = decision.hint

    def decide(self, opponent: Side, moves_left: int, rng: random.Random) -> LabDecision:
        self.belief.diffuse()  # the TurnHandler seam order: diffuse → observe (STRATEGY §2)
        self.belief.observe_smell(opponent.snapshot)
        view = LabView(self.role, self.state, self.belief, dict(opponent.snapshot),
                       opponent.hint, moves_left, rng)
        return self.brain.decide(view)
