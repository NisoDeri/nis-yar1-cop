"""SurvivorThiefBrain — composite flee score + hard jail-risk ban (STRATEGY §4.1-4.2 v1).

score(cell) = w_dist * BFS-true-distance(cell, threat)
            + w_mob  * |reachable_cells(cell, barriers, mobility_k)|
            - jail ban (a penalty larger than any achievable score) on risky cells

Jail rule (rule 47 is the thief's death clause): while the cop still owns barrier
charges, a cell whose post-move non-STAY exit count is below ``jail_min_mobility``
is banned — it is only ever entered when EVERY legal move is jail-risky (survival
over aesthetics; the runtime HOLD backstop never becomes the plan). The cop's
remaining charges are observable: every placement is truthfully declared (rule 14)
and the thief never places barriers itself, so charges = barriers_max - |barriers|.
When charges hit zero, corners become legal terrain again (STRATEGY §4.2).

Weight/k DEFAULTS live here, in one place (the constructor); production values come
from the private ``[thief]`` table in game.toml via ``resolve_brain``.
"""

from __future__ import annotations

from typing import Any

from pursuit.constants import Cell, Direction, MoveType, Role
from pursuit.strategy.base import BeliefLike, BrainBase, TalkLike
from pursuit.strategy.decoy import propose_decoy


class SurvivorThiefBrain(BrainBase):
    """Deterministic survivor: true-distance flee, mobility bonus, jail-risk ban."""

    role = Role.THIEF

    def __init__(
        self,
        talk: TalkLike,
        rng: Any,
        *,
        w_dist: float = 1.0,  # STRATEGY §7 thief.w_safety default
        w_mob: float = 0.4,  # STRATEGY §7 thief.w_mobility default
        mobility_k: int = 3,  # STRATEGY §7 thief.mobility_k default
        jail_min_mobility: int = 2,  # STRATEGY §4.2: exits(c) < 2 is banned terrain
        decoy_enabled: bool = False,  # CREATIVITY-DESIGN E3 — DEFAULT OFF
        decoy_margin: int = 4,  # min flee distance before we spend tempo on misdirection
    ) -> None:
        super().__init__(talk, rng)
        self.w_dist = float(w_dist)
        self.w_mob = float(w_mob)
        self.mobility_k = int(mobility_k)
        self.jail_min_mobility = int(jail_min_mobility)
        self.decoy_enabled = bool(decoy_enabled)
        self.decoy_margin = int(decoy_margin)
        self._opponent_charges = 0  # refreshed every _decide_move from barriers_max

    def _decide_move(
        self, state: Any, belief: BeliefLike, barriers_max: int
    ) -> tuple[MoveType, Direction | None]:
        """Observe the cop's remaining charges, then defer to the base move pipeline."""
        self._opponent_charges = max(0, int(barriers_max) - len(state.barriers))
        return super()._decide_move(state, belief, barriers_max)

    def _pick_move(
        self, moves: list[tuple[Direction, Cell]], state: Any, belief: BeliefLike
    ) -> tuple[Direction, Cell]:
        board, barriers = state.board, state.barriers
        threat = belief.most_likely()
        if self.decoy_enabled:  # E3: shape the scent only when far enough to spare tempo
            decoy = propose_decoy(
                board, state.position, threat, barriers, moves,
                margin=self.decoy_margin,
                opponent_charges=self._opponent_charges,
                jail_min_mobility=self.jail_min_mobility,
            )
            if decoy is not None:
                return decoy
        far = board.size * board.size  # exceeds any BFS distance; also the unreachable bonus
        ban = (self.w_dist + self.w_mob) * far + 1.0  # dominates any achievable score

        def score(cell: Cell) -> float:
            distance = board.bfs_distance(cell, threat, barriers)
            value = self.w_dist * (far if distance is None else distance)
            value += self.w_mob * len(board.reachable_cells(cell, barriers, self.mobility_k))
            if self._opponent_charges > 0 and self._exits(board, cell, barriers) < (
                self.jail_min_mobility
            ):
                value -= ban
            return value

        return max(moves, key=lambda move: score(move[1]))  # ties -> move_set order

    @staticmethod
    def _exits(board: Any, cell: Cell, barriers: set[Cell]) -> int:
        """Post-move mobility: how many real (non-STAY) steps remain from ``cell``."""
        return sum(1 for d, _c in board.legal_moves(cell, barriers) if d is not Direction.STAY)
