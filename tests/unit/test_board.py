"""Unit tests for pursuit.domain.board — geometry, BFS, and strict move_set gates."""

import pytest

from pursuit.constants import Direction
from pursuit.domain.board import Board
from pursuit.exceptions import ConfigError

FULL_SET = ["N", "S", "E", "W", "STAY"]


@pytest.fixture
def board() -> Board:
    return Board(7, FULL_SET)


class TestConstruction:
    def test_rejects_unknown_direction(self) -> None:
        with pytest.raises(ConfigError, match="NE"):
            Board(7, ["N", "NE"])

    def test_rejects_king_move_set_no_silent_fallback(self) -> None:
        king = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
        with pytest.raises(ConfigError):
            Board(7, king)

    def test_rejects_empty_move_set(self) -> None:
        with pytest.raises(ConfigError, match="empty"):
            Board(7, [])

    @pytest.mark.parametrize("size", [0, -3])
    def test_rejects_non_positive_size(self, size: int) -> None:
        with pytest.raises(ConfigError, match="size"):
            Board(size, FULL_SET)

    def test_stay_excluded_from_step_directions(self, board: Board) -> None:
        assert Direction.STAY not in board.step_directions
        assert board.allows_stay is True
        assert set(board.step_directions) == {
            Direction.N,
            Direction.S,
            Direction.E,
            Direction.W,
        }

    def test_duplicates_deduped(self) -> None:
        b = Board(5, ["N", "N", "STAY"])
        assert b.move_set == (Direction.N, Direction.STAY)


class TestBoundsAndNeighbors:
    def test_in_bounds_corners_and_outside(self, board: Board) -> None:
        assert board.in_bounds((0, 0)) and board.in_bounds((6, 6))
        for bad in [(-1, 0), (0, -1), (7, 0), (0, 7)]:
            assert not board.in_bounds(bad)

    def test_center_has_four_orthogonal_neighbors(self, board: Board) -> None:
        assert sorted(board.neighbors((3, 3))) == [(2, 3), (3, 2), (3, 4), (4, 3)]

    def test_corner_clipped_to_two(self, board: Board) -> None:
        assert sorted(board.neighbors((0, 0))) == [(0, 1), (1, 0)]

    def test_edge_clipped_to_three(self, board: Board) -> None:
        assert sorted(board.neighbors((0, 3))) == [(0, 2), (0, 4), (1, 3)]

    def test_no_diagonals_ever(self, board: Board) -> None:
        for cell in board.neighbors((3, 3)):
            assert Board.manhattan((3, 3), cell) == 1


class TestLegalMoves:
    def test_includes_stay_at_own_cell(self, board: Board) -> None:
        assert (Direction.STAY, (3, 3)) in board.legal_moves((3, 3), set())

    def test_no_stay_when_not_in_move_set(self) -> None:
        b = Board(7, ["N", "S", "E", "W"])
        moves = b.legal_moves((3, 3), set())
        assert all(d is not Direction.STAY for d, _ in moves)

    def test_barriers_excluded(self, board: Board) -> None:
        moves = board.legal_moves((3, 3), {(2, 3), (3, 4)})
        dests = {cell for _, cell in moves}
        assert (2, 3) not in dests and (3, 4) not in dests
        assert (3, 3) in dests  # STAY survives

    def test_fully_jailed_cell_yields_empty_list(self) -> None:
        b = Board(3, ["N", "S", "E", "W"])  # no STAY
        walls = {(0, 1), (2, 1), (1, 0), (1, 2)}
        assert b.legal_moves((1, 1), walls) == []

    def test_corner_with_barriers(self, board: Board) -> None:
        moves = board.legal_moves((0, 0), {(0, 1)})
        assert moves == [(Direction.S, (1, 0)), (Direction.STAY, (0, 0))]


class TestDistances:
    def test_manhattan(self) -> None:
        assert Board.manhattan((0, 0), (3, 4)) == 7

    def test_bfs_equals_manhattan_on_open_board(self, board: Board) -> None:
        assert board.bfs_distance((0, 0), (3, 4), set()) == 7

    def test_bfs_diverges_from_manhattan_around_wall(self, board: Board) -> None:
        # Vertical wall through column 3, gap only at row 6.
        wall = {(r, 3) for r in range(6)}
        a, b = (0, 0), (0, 6)
        assert Board.manhattan(a, b) == 6
        assert board.bfs_distance(a, b, wall) == 18  # down, around the gap, back up

    def test_bfs_unreachable_returns_none(self, board: Board) -> None:
        wall = {(r, 3) for r in range(7)}  # full split
        assert board.bfs_distance((0, 0), (0, 6), wall) is None

    def test_bfs_same_cell_is_zero(self, board: Board) -> None:
        assert board.bfs_distance((2, 2), (2, 2), set()) == 0

    def test_bfs_target_on_barrier_is_none(self, board: Board) -> None:
        assert board.bfs_distance((0, 0), (2, 2), {(2, 2)}) is None

    def test_bfs_out_of_bounds_is_none(self, board: Board) -> None:
        assert board.bfs_distance((0, 0), (9, 9), set()) is None
        assert board.bfs_distance((-1, 0), (0, 0), set()) is None


class TestReachableCells:
    def test_open_board_diamond_counts(self, board: Board) -> None:
        assert board.reachable_cells((3, 3), set(), 0) == {(3, 3)}
        assert len(board.reachable_cells((3, 3), set(), 1)) == 5  # von Neumann
        assert len(board.reachable_cells((3, 3), set(), 2)) == 13  # L1 diamond

    def test_corner_clipping_reduces_count(self, board: Board) -> None:
        assert len(board.reachable_cells((0, 0), set(), 2)) == 6

    def test_barriers_block_flow(self, board: Board) -> None:
        walls = {(2, 3), (4, 3), (3, 2), (3, 4)}  # jail the center
        assert board.reachable_cells((3, 3), walls, 5) == {(3, 3)}

    def test_negative_k_raises(self, board: Board) -> None:
        with pytest.raises(ConfigError, match="k"):
            board.reachable_cells((3, 3), set(), -1)

    def test_off_board_pos_is_empty(self, board: Board) -> None:
        assert board.reachable_cells((9, 9), set(), 3) == set()
