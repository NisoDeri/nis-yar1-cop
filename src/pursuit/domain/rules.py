"""Book-compliant physics referee — every peer enforces these rules locally (Zero-Trust).

There is no central referee (brief §0): each peer validates its OWN moves before sending and
its opponent's declared effects on arrival. This module is the pure rulebook (D4, no I/O):

- **Stepping** (rules 41-45): 4-orthogonal + STAY only; diagonal, out-of-bounds and
  barrier-blocked steps are illegal. The negotiated ``move_set`` lives in the injected board.
- **Barriers** (ruling A3): the cop may place on its OWN cell or the 4 orthogonal in-bounds,
  non-barrier neighbours — exactly 5 options at most, bounded by the negotiated quota.
- **Captures** (rules 46-47, ruling A3 — MANDATORY in league play): landing on the thief,
  dropping a barrier on the thief, and jailing the thief all end the sub-game as a capture.
- **Jailed nuance with STAY** (rule 47's intent): if STAY is in the move_set a thief boxed on
  all 4 orthogonal sides could "legally" STAY forever. Per ruling A3 we treat *all 4 orthogonal
  neighbours blocked* as jailed EVEN with STAY available. Because the semantic is negotiable,
  the flag ``jailed_includes_stay`` (default True) selects it; False demands literally no legal
  move at all. (A barrier ON the thief's cell is never "jailed" — it is capture_by_barrier.)
- **Survival** (ruling A5): adjudicated on the thief's OWN valid-move counter — STAY/HOLD
  count, the opponent's barrier turns do NOT. Threshold comes from the signed config.
"""

from __future__ import annotations

from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from typing import Protocol

from pursuit.constants import Cell, Direction
from pursuit.exceptions import IllegalMoveError

#: Barrier reach per ruling A3 is structurally orthogonal (independent of the move_set).
_ORTHOGONALS = (Direction.N, Direction.S, Direction.E, Direction.W)


class BoardLike(Protocol):
    """The single physics primitive this referee relies on (see ``domain/board.py``)."""

    def step(
        self, origin: Cell, direction: Direction, barriers: AbstractSet[Cell]
    ) -> Cell | None:
        """Destination cell, or None when out-of-bounds / blocked / outside the move_set."""
        ...

    def legal_moves(
        self, pos: Cell, barriers: AbstractSet[Cell]
    ) -> list[tuple[Direction, Cell]]:
        """All (direction, destination) pairs legal from ``pos``."""
        ...


def validate_step(
    board: BoardLike, from_cell: Cell, direction: Direction | str, barriers: AbstractSet[Cell]
) -> Cell:
    """Validated destination of one step; raises IllegalMoveError otherwise (rules 41-45)."""
    try:
        direction = Direction(direction)
    except ValueError as exc:  # diagonal ("NE") or garbage — no king fallback (D4)
        raise IllegalMoveError(f"direction {direction!r} not in the orthogonal move set") from exc
    destination = board.step(from_cell, direction, barriers)
    if destination is None:
        raise IllegalMoveError(
            f"step {direction.value} from {from_cell} is out of bounds, blocked by a barrier, "
            "or outside the negotiated move_set"
        )
    return destination


def barrier_options(
    board: BoardLike, cop_cell: Cell, barriers: AbstractSet[Cell]
) -> list[Cell]:
    """The cop's legal barrier cells: own cell + 4 orthogonal, in-bounds, non-barrier (A3)."""
    options: list[Cell] = [] if cop_cell in barriers else [cop_cell]
    for direction in _ORTHOGONALS:
        destination = board.step(cop_cell, direction, barriers)
        if destination is not None:
            options.append(destination)
    return options


def validate_barrier(
    board: BoardLike,
    cop_cell: Cell,
    target: Cell,
    barriers: AbstractSet[Cell],
    barriers_used: int,
    max_barriers: int,
) -> Cell:
    """Validated barrier placement; raises IllegalMoveError on quota/reach violations."""
    if barriers_used >= max_barriers:
        raise IllegalMoveError(
            f"barrier quota exhausted: {barriers_used} used of max_barriers={max_barriers}"
        )
    if target not in barrier_options(board, cop_cell, barriers):
        raise IllegalMoveError(
            f"barrier at {target} is outside the 5-option reach from {cop_cell} "
            "(own cell + 4 orthogonal, in-bounds, non-barrier — ruling A3)"
        )
    return target


def capture_by_landing(cop: Cell, thief: Cell) -> bool:
    """Rule 46 half one: the cop steps onto the thief's cell."""
    return cop == thief


def capture_by_barrier(barrier_cell: Cell, thief: Cell) -> bool:
    """Rule 46 half two (ruling A3): a barrier dropped on the thief's cell captures it."""
    return barrier_cell == thief


def jailed(
    board: BoardLike,
    thief: Cell,
    barriers: AbstractSet[Cell],
    jailed_includes_stay: bool = True,
) -> bool:
    """Rule 47 (ruling A3): thief with no legal move is captured — see STAY nuance above."""
    moves = board.legal_moves(thief, barriers)
    if jailed_includes_stay:
        moves = [(d, c) for d, c in moves if d is not Direction.STAY]
    return not moves


@dataclass
class StepCounter:
    """The thief's OWN valid-move counter — the sole survival clock (ruling A5)."""

    count: int = 0

    def record_valid_move(self) -> int:
        """One validated thief action — MOVE and STAY/HOLD alike count (ruling A5)."""
        self.count += 1
        return self.count

    def record_opponent_barrier_turn(self) -> int:
        """Explicit no-op: the cop's barrier turns never advance the clock (ruling A5)."""
        return self.count


def survived(counter: StepCounter, survival_threshold: int) -> bool:
    """True once the thief logged ``survival_threshold`` valid moves (35 min, Table 15)."""
    return counter.count >= survival_threshold
