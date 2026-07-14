"""Reference-default baseline brains — the lab's opponents (ref-map §2.2, STRATEGY §1.1).

Faithful to the DOCUMENTED reference policies, weaknesses included on purpose:

- ``GreedyThiefBrain``: maximize Manhattan distance from ``belief.most_likely()``,
  tiebreak prefer-unvisited.
- ``GreedyPoliceBrain``: minimize Manhattan distance; ``barrier_coin_p`` (reference
  constant 0.15) random chance to BARRIER the cell it would have stepped onto —
  the W4 self-walling coin, reproduced verbatim so lab experiment E1 replicates
  the reference baseline before E2/E3 measure our edge against it.

Manhattan-through-walls (W1) is intentional here — the reference board is
barrier-blind for distance. These brains are lab opponents, never league brains.
"""

from __future__ import annotations

from typing import Any

from pursuit.constants import Cell, Direction, MoveType, Role
from pursuit.strategy.base import BeliefLike, BrainBase, TalkLike


def _manhattan(a: Cell, b: Cell) -> int:
    """The reference's barrier-blind distance (W1) — kept local to the baselines."""
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


class GreedyThiefBrain(BrainBase):
    """Reference thief: max Manhattan distance from the mode, prefer unvisited cells."""

    role = Role.THIEF

    def _pick_move(
        self, moves: list[tuple[Direction, Cell]], state: Any, belief: BeliefLike
    ) -> tuple[Direction, Cell]:
        target = belief.most_likely()

        def rank(move: tuple[Direction, Cell]) -> tuple[int, bool]:
            _direction, cell = move
            return (_manhattan(cell, target), cell not in state.visited)

        return max(moves, key=rank)  # final tie -> move_set order (deterministic)


class GreedyPoliceBrain(BrainBase):
    """Reference cop: min Manhattan distance + the 15% own-step barrier coin (W4)."""

    role = Role.POLICE

    def __init__(self, talk: TalkLike, rng: Any, *, barrier_coin_p: float = 0.15) -> None:
        super().__init__(talk, rng)
        self.barrier_coin_p = float(barrier_coin_p)  # ref-map §2.2 documented constant

    def _decide_move(
        self, state: Any, belief: BeliefLike, barriers_max: int
    ) -> tuple[MoveType, Direction | None]:
        board, pos = state.board, state.position
        moves = board.legal_moves(pos, state.barriers)
        if not moves:
            return (MoveType.HOLD, None)
        direction, cell = self._pick_move(moves, state, belief)
        if (
            state.my_barriers < barriers_max
            and cell != pos  # a STAY pick has no "cell it would have stepped onto"
            and self.rng.random() < self.barrier_coin_p
        ):
            self._random_move = True  # the coin, not a plan — flagged for the audit record
            return (MoveType.BARRIER, direction)
        return (MoveType.MOVE, direction)

    def _pick_move(
        self, moves: list[tuple[Direction, Cell]], state: Any, belief: BeliefLike
    ) -> tuple[Direction, Cell]:
        target = belief.most_likely()
        return min(moves, key=lambda move: _manhattan(move[1], target))
