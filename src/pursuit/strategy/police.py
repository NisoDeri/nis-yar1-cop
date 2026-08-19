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
        herd_k: int = 4,  # horizon of the thief-escape region we collapse on distance ties
        close_barrier_p: float = 0.35,
        jitter_epsilon: float = 0.0,  # >0 randomizes among near-best chases (anti-scouting)
    ) -> None:
        super().__init__(talk, rng)
        self.barrier_finisher_p = float(barrier_finisher_p)
        self.cage_radius = int(cage_radius)
        self.herd_k = int(herd_k)
        self.close_barrier_p = float(close_barrier_p)
        self.jitter_epsilon = max(0.0, float(jitter_epsilon))

    def _decide_move(
        self, state: Any, belief: BeliefLike, barriers_max: int
    ) -> tuple[MoveType, Direction | None]:
        board, pos, barriers = state.board, state.position, state.barriers
        target = belief.most_likely()
        moves = board.legal_moves(pos, barriers)
        confident = mode_probability(belief) >= self.barrier_finisher_p
        if target == pos and not confident:
            patrol = self._uncertain_mode_patrol(board, moves, state)
            if patrol is not None:
                return (MoveType.MOVE, patrol[0])
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
            if target in options and mode_probability(belief) >= self.close_barrier_p:
                if self._edge_or_corner(board, target):
                    return (MoveType.BARRIER, _direction_toward(pos, target))
            jail = self._jail_completion(board, pos, target, barriers, options, belief)
            if jail is not None:
                return (MoveType.BARRIER, _direction_toward(pos, jail))
            staging = self._jail_staging_move(board, moves, target, barriers, belief)
            if staging is not None:
                return (MoveType.MOVE, staging)
            lane = self._tempo_lane(board, pos, target, barriers, options)
            if lane is not None:
                return (MoveType.BARRIER, _direction_toward(pos, lane))
        if not moves:
            return (MoveType.HOLD, None)
        picked = self._pick_move(moves, state, belief)
        if picked[0] is Direction.STAY:
            patrol = self._uncertain_mode_patrol(board, moves, state)
            if patrol is not None:
                picked = patrol
        return (MoveType.MOVE, picked[0])

    def _uncertain_mode_patrol(
        self, board: Any, moves: list[tuple[Direction, Cell]], state: Any
    ) -> tuple[Direction, Cell] | None:
        """When belief says "here" but confidence is low, keep searching instead of holding."""
        candidates = [(direction, cell) for direction, cell in moves if direction is not Direction.STAY]
        if not candidates:
            return None

        center = ((board.size - 1) / 2.0, (board.size - 1) / 2.0)

        def rank(move: tuple[Direction, Cell]) -> tuple[int, int, float]:
            _direction, cell = move
            fresh = 1 if cell not in state.visited else 0
            mobility = len(board.reachable_cells(cell, state.barriers, self.herd_k))
            center_pull = -abs(cell[0] - center[0]) - abs(cell[1] - center[1])
            return (fresh, mobility, center_pull)

        return max(candidates, key=rank)

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

    @staticmethod
    def _edge_or_corner(board: Any, cell: Cell) -> bool:
        return cell[0] in (0, board.size - 1) or cell[1] in (0, board.size - 1)

    def _jail_completion(
        self, board: Any, pos: Cell, target: Cell, barriers: set[Cell],
        options: list[Cell], belief: BeliefLike
    ) -> Cell | None:
        """Finish a corner/edge cage by walling the target's last real exit."""
        if mode_probability(belief) < self.close_barrier_p or not self._edge_or_corner(board, target):
            return None
        reach = set(options)
        exits = sorted(
            cell for direction, cell in board.legal_moves(target, barriers)
            if direction is not Direction.STAY
        )
        for cell in exits:
            if cell in reach:
                remaining = [
                    c for direction, c in board.legal_moves(target, barriers | {cell})
                    if direction is not Direction.STAY
                ]
                if not remaining:
                    return cell
        return None

    def _jail_staging_move(
        self, board: Any, moves: list[tuple[Direction, Cell]], target: Cell,
        barriers: set[Cell], belief: BeliefLike
    ) -> Direction | None:
        """Move beside the last exit of a corner camper so next turn can seal it."""
        if mode_probability(belief) < self.close_barrier_p or not self._edge_or_corner(board, target):
            return None
        exits = [
            cell for direction, cell in board.legal_moves(target, barriers)
            if direction is not Direction.STAY
        ]
        if len(exits) != 1:
            return None
        last_exit = exits[0]
        candidates = [
            (direction, cell) for direction, cell in moves
            if direction is not Direction.STAY and last_exit in barrier_options(board, cell, barriers)
        ]
        if not candidates:
            return None
        dr = target[0] - last_exit[0]
        dc = target[1] - last_exit[1]
        line_cell = (last_exit[0] - dr, last_exit[1] - dc)

        def rank(move: tuple[Direction, Cell]) -> tuple[int, int, int, Cell]:
            _direction, cell = move
            exit_distance = board.bfs_distance(cell, last_exit, barriers)
            target_distance = board.bfs_distance(cell, target, barriers)
            return (
                0 if cell == line_cell else 1,
                exit_distance if exit_distance is not None else board.size * board.size,
                target_distance if target_distance is not None else board.size * board.size,
                cell,
            )

        return min(candidates, key=rank)[0]

    def _pick_move(
        self, moves: list[tuple[Direction, Cell]], state: Any, belief: BeliefLike
    ) -> tuple[Direction, Cell]:
        """Argmin BFS distance to the mode; HERD tie-break (shrink the thief's escape
        region — cells it reaches strictly before us), then own mobility. Herding as a
        distance TIE-break (never the primary key) converts survivals into captures the
        pure chaser misses, with no greedy regression (lab: beats the chaser 1.0)."""
        board, barriers = state.board, state.barriers
        target = belief.most_likely()
        far = board.size * board.size
        region = board.reachable_cells(target, barriers, self.herd_k)
        thief_dist = {x: (board.bfs_distance(target, x, barriers) or 0) for x in region}

        def rank(move: tuple[Direction, Cell]) -> tuple[int, int, int]:
            _direction, cell = move
            distance = board.bfs_distance(cell, target, barriers)
            escape = sum(1 for x, dt in thief_dist.items()
                         if (dc := board.bfs_distance(cell, x, barriers)) is None or dt < dc)
            mobility = sum(
                1 for d, _c in board.legal_moves(cell, barriers) if d is not Direction.STAY
            )
            return (far if distance is None else distance, escape, -mobility)

        if self.jitter_epsilon > 0:  # anti-scouting: randomize among near-best chases so an
            ranked = [(rank(m), m) for m in moves]  # opponent can't learn a hard counter
            best = min(r for r, _m in ranked)
            near = [m for r, m in ranked if r[0] <= best[0] + self.jitter_epsilon]
            if len(near) > 1:
                self._random_move = True
                return near[int(self.rng.random() * len(near)) % len(near)]
        return min(moves, key=rank)  # final tie -> move_set order (deterministic)
