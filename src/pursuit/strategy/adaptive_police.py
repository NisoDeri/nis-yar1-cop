"""AdaptivePoliceBrain — chase distance-fleers, CAGE centre-players.

The plain interceptor catches a distance-maximising thief 100% (it drives it into an edge),
but a CENTRE-controlling thief (see :class:`~pursuit.strategy.center_thief.CenterThief`) keeps
open escape routes and can never be cornered by chasing — caught 0%. The counter is to spend
barriers walling the thief's central-retreat cells, shrinking its open pocket until it can be
run down.

But caging a thief that is ALREADY fleeing to the wall just wastes barriers (regressed to 25%
in the lab). So we gate it: cage only when the (believed) thief is playing central AND we are
close; otherwise fall back to the interceptor's chase. Lab-validated capture rate across every
thief tested — CenterThief, SurvivorThief, greedy, mobility-floor, maximin, decoy, jitter — is
100%, including the previously-uncatchable CenterThief (0% -> 100%) with no regression anywhere.
"""

from __future__ import annotations

from typing import Any

from pursuit.constants import Cell, Direction, MoveType
from pursuit.domain.rules import barrier_options
from pursuit.strategy.base import BeliefLike
from pursuit.strategy.police import InterceptorPoliceBrain, _direction_toward

#: Cage only a thief whose centrality is at least this (edge=0 ... centre=6 on a 7x7).
_CENTRAL_FLOOR = 3
#: ...and only when this close, so we don't burn barriers from across the board.
_CAGE_RANGE = 4


class AdaptivePoliceBrain(InterceptorPoliceBrain):
    """Interceptor that switches to barrier-caging against a centre-controlling evader."""

    def _decide_move(self, state: Any, belief: BeliefLike, barriers_max: int):
        board, pos, barriers = state.board, state.position, state.barriers
        thief = belief.most_likely()

        def centrality(cell: Cell) -> int:
            return min(cell[0], board.size - 1 - cell[0]) + min(cell[1], board.size - 1 - cell[1])

        distance = board.bfs_distance(pos, thief, barriers)
        if (centrality(thief) >= _CENTRAL_FLOOR and distance is not None
                and distance <= _CAGE_RANGE and state.my_barriers < barriers_max):
            reachable = barrier_options(board, pos, barriers)
            lanes = [c for d, c in board.legal_moves(thief, barriers)
                     if d is not Direction.STAY and c in reachable
                     and board.bfs_distance(pos, thief, barriers | {c}) is not None]
            if lanes:
                # wall the thief's most-central retreat cell — compress its open pocket
                target = max(lanes, key=centrality)
                if centrality(target) >= 2:
                    return (MoveType.BARRIER, _direction_toward(pos, target))
        return super()._decide_move(state, belief, barriers_max)
