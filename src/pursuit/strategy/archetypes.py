"""Diverse LAB opponents — distinct playstyles to stress-test our brains beyond greedy.

These are NOT league brains; they exist so the fitness harness can ask the real question:
does our agent beat a RANGE of opponents (a random floor, a distinct fleer, a distinct
chaser), or only the one greedy baseline? Each is pure Python, reads geometry from state,
and takes an injected ``rng`` (BrainBase contract). Deliberately simple/suboptimal.
"""

from __future__ import annotations

from typing import Any

from pursuit.constants import Cell, Direction, Role
from pursuit.strategy.base import BeliefLike, BrainBase


def _manhattan(a: Cell, b: Cell) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


class RandomThief(BrainBase):
    """Sanity floor: a legal random move every turn (rng-driven)."""

    role = Role.THIEF

    def _pick_move(self, moves: list[tuple[Direction, Cell]], state: Any,
                   belief: BeliefLike) -> tuple[Direction, Cell]:
        return moves[self.rng.randrange(len(moves))]


class RandomPolice(BrainBase):
    """Sanity floor cop: a legal random move every turn."""

    role = Role.POLICE

    def _pick_move(self, moves: list[tuple[Direction, Cell]], state: Any,
                   belief: BeliefLike) -> tuple[Direction, Cell]:
        return moves[self.rng.randrange(len(moves))]


class WallHuggerThief(BrainBase):
    """A distinct (bad) fleer: maximizes distance-to-edge-minimizing... i.e. hugs the border,
    the classic trap our herding cop should punish. Ties break to max flee distance."""

    role = Role.THIEF

    def _pick_move(self, moves: list[tuple[Direction, Cell]], state: Any,
                   belief: BeliefLike) -> tuple[Direction, Cell]:
        board, threat = state.board, belief.most_likely()
        edge = board.size - 1

        def rank(move: tuple[Direction, Cell]) -> tuple[int, int]:
            _d, cell = move
            to_edge = min(cell[0], cell[1], edge - cell[0], edge - cell[1])  # 0 == on the wall
            return (to_edge, -_manhattan(cell, threat))  # prefer walls, then far from cop

        return min(moves, key=rank)


class CornerAmbushPolice(BrainBase):
    """A distinct chaser: closes Manhattan distance but always heads for the thief's nearest
    corner first (herds toward corners without the barrier machinery). No barriers."""

    role = Role.POLICE

    def _pick_move(self, moves: list[tuple[Direction, Cell]], state: Any,
                   belief: BeliefLike) -> tuple[Direction, Cell]:
        board, mode = state.board, belief.most_likely()
        edge = board.size - 1
        corner = (0 if mode[0] < board.size / 2 else edge,
                  0 if mode[1] < board.size / 2 else edge)
        aim = mode if _manhattan(state.position, mode) <= 2 else corner
        return min(moves, key=lambda m: _manhattan(m[1], aim))
