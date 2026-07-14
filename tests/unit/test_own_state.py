"""Unit tests for pursuit.domain.own_state — private state, sealed state_string bytes."""

from __future__ import annotations

import pytest

from pursuit.constants import Direction
from pursuit.domain.board import Board
from pursuit.domain.own_state import OwnGameState
from pursuit.exceptions import IllegalMoveError

MOVE_SET = ["N", "S", "E", "W", "STAY"]  # Appendix F default, injected — never hardcoded in src


def make_board(size: int = 7) -> Board:
    return Board(size=size, move_set=MOVE_SET)


@pytest.fixture()
def state() -> OwnGameState:
    return OwnGameState(board=make_board(), position=(3, 3))


def test_start_cell_is_visited_and_counters_zero(state: OwnGameState) -> None:
    assert state.visited == {(3, 3)}
    assert state.step_number == 0
    assert state.my_barriers == 0
    assert state.barriers == set()


def test_apply_step_moves_and_counts(state: OwnGameState) -> None:
    dest = state.apply_step(Direction.S)
    assert dest == (4, 3) == state.position
    assert state.visited == {(3, 3), (4, 3)}
    assert state.step_number == 1


def test_stay_counts_a_step_without_moving(state: OwnGameState) -> None:
    assert state.apply_step(Direction.STAY) == (3, 3)
    assert state.step_number == 1
    assert state.visited == {(3, 3)}


def test_revisit_does_not_regrow_visited(state: OwnGameState) -> None:
    state.apply_step(Direction.N)
    state.apply_step(Direction.S)
    assert state.visited == {(3, 3), (2, 3)}
    assert state.step_number == 2


def test_illegal_step_off_grid_leaves_state_untouched() -> None:
    st = OwnGameState(board=make_board(), position=(0, 0))
    with pytest.raises(IllegalMoveError):
        st.apply_step(Direction.N)
    assert st.position == (0, 0)
    assert st.step_number == 0
    assert st.visited == {(0, 0)}


def test_step_into_barrier_is_illegal(state: OwnGameState) -> None:
    state.note_opponent_barrier((2, 3))
    with pytest.raises(IllegalMoveError):
        state.apply_step(Direction.N)
    assert state.position == (3, 3)
    assert state.step_number == 0


def test_direction_outside_negotiated_move_set_is_illegal() -> None:
    no_stay = Board(size=7, move_set=["N", "S", "E", "W"])
    st = OwnGameState(board=no_stay, position=(3, 3))
    with pytest.raises(IllegalMoveError):
        st.apply_step(Direction.STAY)
    assert st.step_number == 0


def test_apply_barrier_counts_only_mine(state: OwnGameState) -> None:
    state.apply_barrier((2, 5))
    state.note_opponent_barrier((6, 6))
    assert state.barriers == {(2, 5), (6, 6)}
    assert state.my_barriers == 1


def test_apply_barrier_rejects_duplicate_cell(state: OwnGameState) -> None:
    state.apply_barrier((2, 5))
    with pytest.raises(IllegalMoveError):
        state.apply_barrier((2, 5))
    assert state.my_barriers == 1
    st2 = OwnGameState(board=make_board(), position=(3, 3))
    st2.note_opponent_barrier((1, 1))
    with pytest.raises(IllegalMoveError):
        st2.apply_barrier((1, 1))


def test_note_opponent_barrier_is_idempotent(state: OwnGameState) -> None:
    state.note_opponent_barrier((2, 5))
    state.note_opponent_barrier((2, 5))
    assert state.barriers == {(2, 5)}
    assert state.my_barriers == 0


# --- state_string golden bytes (INTEROP §2.2 sample-run forms) -------------------------


def test_state_string_golden_no_barriers() -> None:
    st = OwnGameState(board=make_board(7), position=(4, 3))
    assert st.state_string() == "grid=7x7;self=[4, 3];barriers=[]"


def test_state_string_golden_one_barrier() -> None:
    st = OwnGameState(board=make_board(7), position=(4, 3))
    st.note_opponent_barrier((2, 5))
    assert st.state_string() == "grid=7x7;self=[4, 3];barriers=[[2, 5]]"


def test_state_string_barriers_sorted_regardless_of_insertion() -> None:
    st = OwnGameState(board=make_board(7), position=(0, 0))
    st.apply_barrier((3, 1))
    st.apply_barrier((2, 5))
    st.note_opponent_barrier((2, 4))
    assert st.state_string() == "grid=7x7;self=[0, 0];barriers=[[2, 4], [2, 5], [3, 1]]"


def test_state_string_tracks_board_size_and_position() -> None:
    st = OwnGameState(board=make_board(9), position=(8, 0))
    assert st.state_string() == "grid=9x9;self=[8, 0];barriers=[]"
    st.apply_step(Direction.E)
    assert st.state_string() == "grid=9x9;self=[8, 1];barriers=[]"
