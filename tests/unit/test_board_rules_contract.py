"""Contract tests: the REAL Board satisfies rules.py's BoardLike physics primitive.

reference_map.md pins ``step(origin, direction, barriers) -> Cell | None`` as the
SINGLE physics primitive shared by movement and barrier legality; rules.py codes
against that protocol via a stub. These tests wire the real Board into rules.py so
a signature or semantics drift between the two modules fails loudly here.
"""

import pytest

from pursuit.constants import Direction
from pursuit.domain.board import Board
from pursuit.domain.rules import barrier_options, validate_step
from pursuit.exceptions import IllegalMoveError

FULL_SET = ["N", "S", "E", "W", "STAY"]


@pytest.fixture
def board() -> Board:
    return Board(7, FULL_SET)


class TestStepPrimitive:
    def test_legal_step_returns_destination(self, board: Board) -> None:
        assert board.step((3, 3), Direction.N, frozenset()) == (2, 3)

    def test_stay_returns_origin(self, board: Board) -> None:
        assert board.step((3, 3), Direction.STAY, frozenset()) == (3, 3)

    def test_off_board_returns_none(self, board: Board) -> None:
        assert board.step((0, 0), Direction.N, frozenset()) is None

    def test_barrier_returns_none(self, board: Board) -> None:
        assert board.step((3, 3), Direction.E, frozenset({(3, 4)})) is None

    def test_direction_outside_move_set_returns_none(self) -> None:
        no_stay = Board(7, ["N", "S", "E", "W"])
        assert no_stay.step((3, 3), Direction.STAY, frozenset()) is None


class TestRulesAgainstRealBoard:
    def test_validate_step_accepts_legal_move(self, board: Board) -> None:
        assert validate_step(board, (3, 3), "S", frozenset()) == (4, 3)

    def test_validate_step_rejects_barriered_destination(self, board: Board) -> None:
        with pytest.raises(IllegalMoveError):
            validate_step(board, (3, 3), Direction.W, frozenset({(3, 2)}))

    def test_validate_step_rejects_diagonal_no_king_fallback(self, board: Board) -> None:
        with pytest.raises(IllegalMoveError):
            validate_step(board, (3, 3), "NE", frozenset())

    def test_barrier_options_center_is_own_cell_plus_orthogonals(self, board: Board) -> None:
        assert barrier_options(board, (3, 3), frozenset()) == [
            (3, 3),
            (2, 3),
            (4, 3),
            (3, 4),
            (3, 2),
        ]

    def test_barrier_options_clipped_at_corner(self, board: Board) -> None:
        assert barrier_options(board, (0, 0), frozenset()) == [(0, 0), (1, 0), (0, 1)]
