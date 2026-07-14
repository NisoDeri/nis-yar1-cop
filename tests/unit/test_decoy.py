"""Unit tests for E3 active scent-decoy routing (CREATIVITY-DESIGN.md E3, DEFAULT OFF).

Pure domain objects (real Board/OwnGameState), fake belief/talk, injected
``random.Random`` — no sockets, processes or LLM. Three guarantees are pinned:
disabled reproduces the shipped v1 flight exactly (regression guard), an enabled
brain with a FAR cop takes a safe non-jail misdirection step, and an enabled brain
with a NEAR cop falls straight back to pure flight.
"""

from __future__ import annotations

import random

from pursuit.constants import Cell, Direction, MoveType
from pursuit.domain.board import Board
from pursuit.domain.own_state import OwnGameState
from pursuit.strategy.decoy import propose_decoy
from pursuit.strategy.thief import SurvivorThiefBrain

GRID = 7
MOVE_SET = ["N", "S", "E", "W", "STAY"]
MAX_BARRIERS = 14


class FakeBelief:
    """Duck-typed belief: ``most_likely()`` is the thief's estimate of the cop cell."""

    def __init__(self, cell: Cell) -> None:
        self.cell = cell

    def most_likely(self) -> Cell:
        return self.cell

    def most_likely_p(self) -> float:
        return 1.0


class FakeTalk:
    def say(self, role, state, belief, setting, opponent_hint, deadline):
        return ("scentless", "truth", "stub", "")


def make_state(position: Cell, barriers: set[Cell] | None = None) -> OwnGameState:
    return OwnGameState(board=Board(GRID, MOVE_SET), position=position,
                        barriers=set(barriers or ()))


def thief(**kwargs) -> SurvivorThiefBrain:
    return SurvivorThiefBrain(FakeTalk(), random.Random(0), **kwargs)


# --- regression guard: disabled == shipped v1 flight -----------------------------------------
def test_decoy_disabled_reproduces_v1_flight() -> None:
    # Fixed board + seed: (3,3) fleeing a far cop at (0,0). The shipped brain flees S.
    baseline = thief().decide(make_state((3, 3)), FakeBelief((0, 0)), "", "", MAX_BARRIERS)
    disabled = thief(decoy_enabled=False).decide(
        make_state((3, 3)), FakeBelief((0, 0)), "", "", MAX_BARRIERS
    )
    assert (baseline.move_type, baseline.direction) == (MoveType.MOVE, Direction.S)
    assert (disabled.move_type, disabled.direction) == (baseline.move_type, baseline.direction)


# --- enabled + FAR cop: a safe, legal, non-jail decoy step -----------------------------------
def test_decoy_far_cop_takes_safe_non_jail_step() -> None:
    board = Board(GRID, MOVE_SET)
    position, threat = (3, 3), (0, 0)
    moves = board.legal_moves(position, set())
    step = propose_decoy(board, position, threat, set(), moves,
                         margin=4, opponent_charges=MAX_BARRIERS, jail_min_mobility=2)
    assert step is not None
    direction, cell = step
    assert (direction, cell) in moves and direction is not Direction.STAY
    # Safe: never a jail-risk cell, and flee-distance held at or above the floor.
    exits = sum(1 for d, _c in board.legal_moves(cell, set()) if d is not Direction.STAY)
    assert exits >= 2
    flee = board.bfs_distance(position, threat, set())
    assert board.bfs_distance(cell, threat, set()) >= flee - 1


def test_decoy_far_cop_diverts_from_pure_flight() -> None:
    # Same board: disabled flees S, the decoy-enabled brain diverts to lay scent elsewhere.
    disabled = thief().decide(make_state((3, 3)), FakeBelief((0, 0)), "", "", MAX_BARRIERS)
    enabled = thief(decoy_enabled=True).decide(
        make_state((3, 3)), FakeBelief((0, 0)), "", "", MAX_BARRIERS
    )
    assert enabled.move_type is MoveType.MOVE
    assert enabled.direction is not disabled.direction  # scent shaped, not straight flight


# --- enabled + NEAR cop: pure-flight fallback ------------------------------------------------
def test_decoy_near_cop_returns_none() -> None:
    board = Board(GRID, MOVE_SET)
    moves = board.legal_moves((3, 3), set())
    step = propose_decoy(board, (3, 3), (3, 4), set(), moves,
                         margin=4, opponent_charges=MAX_BARRIERS, jail_min_mobility=2)
    assert step is None  # flee distance 1 < margin 4 -> no misdirection


def test_decoy_near_cop_matches_pure_flight() -> None:
    disabled = thief().decide(make_state((3, 3)), FakeBelief((3, 4)), "", "", MAX_BARRIERS)
    enabled = thief(decoy_enabled=True).decide(
        make_state((3, 3)), FakeBelief((3, 4)), "", "", MAX_BARRIERS
    )
    assert (enabled.move_type, enabled.direction) == (disabled.move_type, disabled.direction)
