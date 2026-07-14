"""Unit tests for pursuit.domain.rules — the book-compliant physics referee (D4)."""

from __future__ import annotations

import pytest

from pursuit.constants import DIRECTION_DELTAS, Cell, Direction
from pursuit.domain.rules import (
    StepCounter,
    barrier_options,
    capture_by_barrier,
    capture_by_landing,
    jailed,
    survived,
    validate_barrier,
    validate_step,
)
from pursuit.exceptions import IllegalMoveError

# Test-local game parameters (in production these come from the signed game.json).
ROWS, COLS = 7, 7
MAX_BARRIERS = 14
SURVIVAL_THRESHOLD = 35


class StubBoard:
    """Minimal BoardLike: step() is the single physics primitive (reference_map §2.1)."""

    def __init__(
        self, rows: int = ROWS, cols: int = COLS, directions: tuple[Direction, ...] = ()
    ) -> None:
        self.rows, self.cols = rows, cols
        self.directions = directions or tuple(Direction)

    def step(self, origin: Cell, direction: Direction, barriers: frozenset[Cell]) -> Cell | None:
        if direction not in self.directions:
            return None
        d_row, d_col = DIRECTION_DELTAS[direction]
        dest = (origin[0] + d_row, origin[1] + d_col)
        in_bounds = 0 <= dest[0] < self.rows and 0 <= dest[1] < self.cols
        return dest if in_bounds and dest not in barriers else None

    def legal_moves(
        self, pos: Cell, barriers: frozenset[Cell]
    ) -> list[tuple[Direction, Cell]]:
        moves = [(d, self.step(pos, d, barriers)) for d in self.directions]
        return [(d, c) for d, c in moves if c is not None]


BOARD = StubBoard()
NONE: frozenset[Cell] = frozenset()


# --- validate_step -------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("direction", "expected"),
    [(Direction.N, (2, 3)), (Direction.S, (4, 3)), (Direction.E, (3, 4)),
     (Direction.W, (3, 2)), (Direction.STAY, (3, 3))],
)
def test_validate_step_orthogonal_and_stay(direction: Direction, expected: Cell) -> None:
    assert validate_step(BOARD, (3, 3), direction, NONE) == expected


def test_validate_step_accepts_wire_string() -> None:
    assert validate_step(BOARD, (3, 3), "N", NONE) == (2, 3)


@pytest.mark.parametrize("bad", ["NE", "SW", "up", "", 7])
def test_validate_step_rejects_diagonal_and_garbage(bad: object) -> None:
    with pytest.raises(IllegalMoveError, match="orthogonal move set"):
        validate_step(BOARD, (3, 3), bad, NONE)  # type: ignore[arg-type]


@pytest.mark.parametrize(("cell", "direction"), [((0, 0), Direction.N), ((6, 6), Direction.E)])
def test_validate_step_rejects_out_of_bounds(cell: Cell, direction: Direction) -> None:
    with pytest.raises(IllegalMoveError):
        validate_step(BOARD, cell, direction, NONE)


def test_validate_step_rejects_barrier_cell() -> None:
    with pytest.raises(IllegalMoveError):
        validate_step(BOARD, (3, 3), Direction.N, frozenset({(2, 3)}))


def test_validate_step_rejects_direction_outside_negotiated_move_set() -> None:
    narrow = StubBoard(directions=(Direction.N, Direction.S))
    with pytest.raises(IllegalMoveError):
        validate_step(narrow, (3, 3), Direction.E, NONE)


# --- barrier options + validation (ruling A3) ----------------------------------------------
def test_barrier_options_center_has_five() -> None:
    assert barrier_options(BOARD, (3, 3), NONE) == [(3, 3), (2, 3), (4, 3), (3, 4), (3, 2)]


def test_barrier_options_corner_has_three() -> None:
    assert set(barrier_options(BOARD, (0, 0), NONE)) == {(0, 0), (1, 0), (0, 1)}


def test_barrier_options_excludes_existing_barriers() -> None:
    options = barrier_options(BOARD, (3, 3), frozenset({(2, 3), (3, 4)}))
    assert set(options) == {(3, 3), (4, 3), (3, 2)}


def test_barrier_options_excludes_own_cell_when_already_barrier() -> None:
    assert (3, 3) not in barrier_options(BOARD, (3, 3), frozenset({(3, 3)}))


def test_validate_barrier_own_cell_ok() -> None:
    assert validate_barrier(BOARD, (3, 3), (3, 3), NONE, 0, MAX_BARRIERS) == (3, 3)


def test_validate_barrier_quota_exhausted() -> None:
    with pytest.raises(IllegalMoveError, match="quota exhausted"):
        validate_barrier(BOARD, (3, 3), (2, 3), NONE, MAX_BARRIERS, MAX_BARRIERS)


@pytest.mark.parametrize("target", [(2, 2), (5, 3), (-1, 0)])
def test_validate_barrier_rejects_out_of_reach(target: Cell) -> None:
    with pytest.raises(IllegalMoveError, match="5-option reach"):
        validate_barrier(BOARD, (3, 3), target, NONE, 0, MAX_BARRIERS)


def test_validate_barrier_rejects_occupied_cell() -> None:
    with pytest.raises(IllegalMoveError):
        validate_barrier(BOARD, (3, 3), (2, 3), frozenset({(2, 3)}), 0, MAX_BARRIERS)


# --- captures (rules 46-47) -----------------------------------------------------------------
def test_capture_by_landing() -> None:
    assert capture_by_landing((2, 2), (2, 2)) and not capture_by_landing((2, 2), (2, 3))


def test_capture_by_barrier_on_thief() -> None:
    assert capture_by_barrier((4, 4), (4, 4)) and not capture_by_barrier((4, 4), (4, 5))


def test_jailed_center_by_four_barriers() -> None:
    walls = frozenset({(2, 3), (4, 3), (3, 4), (3, 2)})
    assert jailed(BOARD, (3, 3), walls)


def test_jailed_flag_false_stay_keeps_thief_alive() -> None:
    walls = frozenset({(2, 3), (4, 3), (3, 4), (3, 2)})
    assert not jailed(BOARD, (3, 3), walls, jailed_includes_stay=False)


def test_jailed_corner_two_barriers_two_edges() -> None:
    assert jailed(BOARD, (0, 0), frozenset({(1, 0), (0, 1)}))


def test_not_jailed_with_one_open_neighbor() -> None:
    assert not jailed(BOARD, (3, 3), frozenset({(2, 3), (4, 3), (3, 4)}))


def test_jailed_without_stay_in_move_set_regardless_of_flag() -> None:
    no_stay = StubBoard(directions=(Direction.N, Direction.S, Direction.E, Direction.W))
    walls = frozenset({(2, 3), (4, 3), (3, 4), (3, 2)})
    assert jailed(no_stay, (3, 3), walls, jailed_includes_stay=False)


# --- survival clock (ruling A5) --------------------------------------------------------------
def test_step_counter_counts_stay_toward_threshold() -> None:
    counter = StepCounter()
    for _ in range(SURVIVAL_THRESHOLD):  # a mix of MOVEs and STAYs — all valid thief actions
        counter.record_valid_move()
    assert counter.count == SURVIVAL_THRESHOLD
    assert survived(counter, SURVIVAL_THRESHOLD)


def test_step_counter_below_threshold_not_survived() -> None:
    counter = StepCounter(count=SURVIVAL_THRESHOLD - 1)
    assert not survived(counter, SURVIVAL_THRESHOLD)


def test_opponent_barrier_turns_do_not_advance_the_clock() -> None:
    counter = StepCounter(count=10)
    assert counter.record_opponent_barrier_turn() == 10
    assert counter.count == 10
