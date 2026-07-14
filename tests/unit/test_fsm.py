"""Unit tests for pursuit.peer.fsm — the guarded turn state machine (rules 4-5)."""

import pytest

from pursuit.exceptions import IllegalTransitionError
from pursuit.peer.fsm import (
    ALLOWED,
    TERMINAL_STATES,
    WIRE_LABELS,
    WIRE_PROJECTION,
    GameStateMachine,
    State,
)


def _machine_at(*path: State) -> GameStateMachine:
    """Drive a fresh machine along ``path`` (must be legal)."""
    fsm = GameStateMachine()
    for state in path:
        fsm.advance(state)
    return fsm


TO_MY_TURN = (State.NEGOTIATING, State.OPP_TURN, State.MY_TURN)
FULL_PATH = (
    State.NEGOTIATING,
    State.OPP_TURN,
    State.MY_TURN,
    State.SENDING,
    State.OPP_TURN,
    State.MY_TURN,
    State.GAME_OVER,
    State.AUDITING,
    State.DONE,
)


class TestLegalPaths:
    def test_full_legal_path_boot_to_done(self):
        fsm = GameStateMachine()
        assert fsm.state is State.BOOT
        for state in FULL_PATH:
            assert fsm.advance(state) is state
        assert fsm.state is State.DONE
        assert fsm.is_terminal

    def test_history_records_every_transition_in_order(self):
        fsm = _machine_at(*FULL_PATH)
        assert fsm.history == list(zip((State.BOOT, *FULL_PATH[:-1]), FULL_PATH, strict=True))

    def test_history_is_a_defensive_copy(self):
        fsm = _machine_at(State.NEGOTIATING)
        fsm.history.clear()
        assert fsm.history == [(State.BOOT, State.NEGOTIATING)]

    def test_thief_first_variant_negotiating_to_my_turn(self):
        fsm = _machine_at(State.NEGOTIATING, State.MY_TURN)
        assert fsm.state is State.MY_TURN

    @pytest.mark.parametrize(
        "path",
        [
            (State.NEGOTIATING, State.GAME_OVER),  # stop during negotiation
            (State.NEGOTIATING, State.OPP_TURN, State.GAME_OVER),  # deadline_expired
            TO_MY_TURN + (State.SENDING, State.GAME_OVER),  # send failure -> stop
            (State.GAME_OVER,),  # stop from BOOT
        ],
    )
    def test_game_over_reachable_and_audit_always_runs(self, path):
        fsm = _machine_at(*path)
        assert fsm.state is State.GAME_OVER
        fsm.advance(State.AUDITING)
        fsm.advance(State.DONE)
        assert fsm.is_terminal

    @pytest.mark.parametrize(
        "path",
        [(), (State.NEGOTIATING,), TO_MY_TURN, TO_MY_TURN + (State.SENDING,),
         (State.NEGOTIATING, State.OPP_TURN, State.GAME_OVER, State.AUDITING)],
    )
    def test_abort_reachable_from_any_non_terminal(self, path):
        fsm = _machine_at(*path)
        fsm.advance(State.ABORTED)
        assert fsm.is_terminal


class TestPauseResume:
    @pytest.mark.parametrize("turn_state", [State.OPP_TURN, State.MY_TURN])
    def test_resume_returns_to_exact_prior_state(self, turn_state):
        path = TO_MY_TURN if turn_state is State.MY_TURN else TO_MY_TURN[:-1]
        fsm = _machine_at(*path)
        fsm.advance(State.PAUSED)
        assert fsm.advance(turn_state) is turn_state

    def test_resume_to_wrong_turn_state_rejected(self):
        fsm = _machine_at(State.NEGOTIATING, State.OPP_TURN, State.PAUSED)
        with pytest.raises(IllegalTransitionError, match="resume"):
            fsm.advance(State.MY_TURN)
        assert fsm.state is State.PAUSED

    def test_stop_while_paused_allowed(self):
        fsm = _machine_at(*TO_MY_TURN, State.PAUSED)
        assert fsm.advance(State.GAME_OVER) is State.GAME_OVER


ILLEGAL_EDGES = [
    ((), State.OPP_TURN),  # BOOT cannot skip negotiation
    ((), State.AUDITING),
    ((), State.DONE),
    ((State.NEGOTIATING,), State.SENDING),
    ((State.NEGOTIATING,), State.PAUSED),  # pause only from turn states
    ((State.NEGOTIATING, State.OPP_TURN), State.SENDING),  # opp turn can't send
    (TO_MY_TURN, State.OPP_TURN),  # must go through SENDING
    (TO_MY_TURN + (State.SENDING,), State.MY_TURN),
    (TO_MY_TURN + (State.SENDING,), State.PAUSED),
    ((State.GAME_OVER,), State.DONE),  # audit may not be skipped (D4)
    ((State.GAME_OVER,), State.OPP_TURN),
    ((State.GAME_OVER,), State.PAUSED),
    ((State.GAME_OVER, State.AUDITING), State.GAME_OVER),
    ((State.GAME_OVER, State.AUDITING, State.DONE), State.NEGOTIATING),  # terminal
    ((State.GAME_OVER, State.AUDITING, State.DONE), State.ABORTED),
    ((State.ABORTED,), State.GAME_OVER),  # terminal
]


class TestIllegalTransitions:
    @pytest.mark.parametrize("path,bad", ILLEGAL_EDGES)
    def test_documented_illegal_edges_rejected(self, path, bad):
        fsm = _machine_at(*path)
        before_state, before_history = fsm.state, fsm.history
        with pytest.raises(IllegalTransitionError) as exc:
            fsm.advance(bad)
        assert before_state.value in str(exc.value)
        assert bad.value in str(exc.value)
        # rejected transition leaves state and audit trail untouched
        assert fsm.state is before_state
        assert fsm.history == before_history

    def test_terminal_states_allow_nothing(self):
        for terminal in TERMINAL_STATES:
            assert ALLOWED[terminal] == frozenset()


class TestWireProjection:
    def test_every_state_projects_onto_the_seven_labels(self):
        assert set(WIRE_PROJECTION) == set(State)
        assert set(WIRE_PROJECTION.values()) == WIRE_LABELS
        assert len(WIRE_LABELS) == 7

    @pytest.mark.parametrize(
        "path,label",
        [
            ((), "WAITING"),
            ((State.NEGOTIATING,), "WAITING"),
            ((State.NEGOTIATING, State.OPP_TURN), "WAITING"),
            (TO_MY_TURN, "THINKING"),
            (TO_MY_TURN + (State.SENDING,), "PLAYING"),
            (TO_MY_TURN + (State.PAUSED,), "PAUSED"),
            ((State.GAME_OVER,), "GAME_OVER"),
            ((State.GAME_OVER, State.AUDITING), "GAME_OVER"),
            ((State.GAME_OVER, State.AUDITING, State.DONE), "STOPPED"),
            ((State.ABORTED,), "QUIT"),
        ],
    )
    def test_wire_status_per_state(self, path, label):
        assert _machine_at(*path).wire_status() == label
