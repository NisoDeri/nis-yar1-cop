"""InterceptorPoliceBrain — BFS true-distance chase + deterministic barrier doctrine v1.

Replaces the reference policy "minimize Manhattan distance; 15% coin to BARRIER the
cell it would have stepped onto" (ref-map §2.2 — weaknesses W1/W4/W6). There is NO
random coin here: every barrier must pass a deterministic value test (STRATEGY §3.5
— "the 14-charge budget replaces the 15% coin").

v1 scope (STRATEGY §3.1 chase + §3.5 finisher/tempo; the T* solver and the cage
planner arrive with belief v2):

- MOVE: argmin BFS true distance to ``belief.most_likely()``; ties break toward
  higher own mobility (non-STAY exit count), then move_set order — all deterministic.
- BARRIER finisher: mode inside the 5-option reach AND mode probability >=
  ``barrier_finisher_p`` -> barrier ON the thief = capture (rule 46, ruling A3).
- BARRIER tempo: within ``cage_radius`` of the mode, wall the best WALLABLE escape
  lane, guarded against self-harm (never lengthen our own route — contrast W4).
"""

from __future__ import annotations

from typing import Any

from pursuit.constants import DIRECTION_DELTAS, Cell, Direction, MoveType, Role
from pursuit.domain.rules import barrier_options
from pursuit.strategy.base import BeliefLike, BrainBase, TalkLike, mode_probability

_DELTA_TO_DIRECTION = {delta: d for d, delta in DIRECTION_DELTAS.items()}


def _direction_toward(origin: Cell, dest: Cell) -> Direction:
    """Direction whose delta maps origin -> dest; own cell encodes as STAY."""
    return _DELTA_TO_DIRECTION[(dest[0] - origin[0], dest[1] - origin[1])]


class InterceptorPoliceBrain(BrainBase):
    """Deterministic interceptor: true-distance chase, value-tested barriers."""

    role = Role.POLICE

    def __init__(
        self,
        talk: TalkLike,
        rng: Any,
        *,
        barrier_finisher_p: float = 0.8,  # STRATEGY §7 police.finisher_threshold default
        cage_radius: int = 2,  # tempo test trigger distance (v1 stand-in for the cage planner)
    ) -> None:
        super().__init__(talk, rng)
        self.barrier_finisher_p = float(barrier_finisher_p)
        self.cage_radius = int(cage_radius)

    def _decide_move(
        self, state: Any, belief: BeliefLike, barriers_max: int
    ) -> tuple[MoveType, Direction | None]:
        board, pos, barriers = state.board, state.position, state.barriers
        target = belief.most_likely()
        moves = board.legal_moves(pos, barriers)
        confident = mode_probability(belief) >= self.barrier_finisher_p
        # LANDING capture (rule 46 half-one) is UNIVERSALLY honored — a reference peer
        # rejects a barrier-on-thief (rule 46 half-two) it never implemented, so stepping
        # ONTO the mode always beats walling it when both are available (review fix).
        if confident:
            for direction, cell in moves:
                if cell == target and direction is not Direction.STAY:
                    return (MoveType.MOVE, direction)  # step onto the thief = capture
        if state.my_barriers < barriers_max:
            options = barrier_options(board, pos, barriers)
            if target in options and confident:  # can't land it -> wall it (book-peer capture)
                return (MoveType.BARRIER, _direction_toward(pos, target))
            lane = self._tempo_lane(board, pos, target, barriers, options)
            if lane is not None:
                return (MoveType.BARRIER, _direction_toward(pos, lane))
        if not moves:
            return (MoveType.HOLD, None)
        return (MoveType.MOVE, self._pick_move(moves, state, belief)[0])

    def _tempo_lane(
        self, board: Any, pos: Cell, target: Cell, barriers: set[Cell], options: list[Cell]
    ) -> Cell | None:
        """STRATEGY §3.5 tempo test, v1: wall the thief's best wallable escape lane.

        Fires only when the chase is already close (BFS distance <= cage_radius) and
        never places a wall that lengthens our own route to the mode (the reference's
        W4 self-walling blunder is structurally impossible here).
        """
        distance = board.bfs_distance(pos, target, barriers)
        if distance is None or distance == 0 or distance > self.cage_radius:
            return None
        reach = set(options)
        lanes = sorted(
            cell
            for _direction, cell in board.legal_moves(target, barriers)
            if cell in reach and cell not in (pos, target)
        )
        safe = [c for c in lanes if not self._self_harming(board, pos, target, barriers, c)]
        if not safe:
            return None
        far = board.size * board.size

        def flee_value(cell: Cell) -> int:
            d = board.bfs_distance(cell, pos, barriers)
            return far if d is None else d

        return max(safe, key=flee_value)  # ties -> first in sorted cell order (deterministic)

    @staticmethod
    def _self_harming(
        board: Any, pos: Cell, target: Cell, barriers: set[Cell], wall: Cell
    ) -> bool:
        """True when the candidate wall lengthens (or severs) our own route to the mode."""
        before = board.bfs_distance(pos, target, barriers)
        after = board.bfs_distance(pos, target, barriers | {wall})
        return after is None or (before is not None and after > before)

    def _pick_move(
        self, moves: list[tuple[Direction, Cell]], state: Any, belief: BeliefLike
    ) -> tuple[Direction, Cell]:
        """Argmin BFS true distance to the mode; tie-break toward higher own mobility."""
        board, barriers = state.board, state.barriers
        target = belief.most_likely()
        far = board.size * board.size

        def rank(move: tuple[Direction, Cell]) -> tuple[int, int]:
            _direction, cell = move
            distance = board.bfs_distance(cell, target, barriers)
            mobility = sum(
                1 for d, _c in board.legal_moves(cell, barriers) if d is not Direction.STAY
            )
            return (far if distance is None else distance, -mobility)

        return min(moves, key=rank)  # final tie -> move_set order (deterministic)
