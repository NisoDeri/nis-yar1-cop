"""TurnHandler unit tests — direct handler calls over in-memory messages.

No sockets, no processes, no LLMs: opponent messages are hand-built wire dicts whose
smell grids come from a REAL ScentModel trail, so the belief fold is exercised against
the byte-faithful locked law. Rule 21 (truthful capture answers), rules 46-47 (barrier /
jailed captures) and the rule-5 breach paths are all driven through ``process()``.
"""

from __future__ import annotations

import pytest

from pursuit.constants import Cell, Role
from pursuit.domain.belief import BeliefV2
from pursuit.domain.board import Board
from pursuit.domain.own_state import OwnGameState
from pursuit.domain.scent import make_scent_model
from pursuit.peer.fsm import GameStateMachine, State
from pursuit.peer.turn_handler import BREACH, DUPLICATE, TURN, ProcessedTurn, TurnHandler

# Test-local game parameters (production values come from the signed game.json).
GRID = 7
MOVES = ["N", "S", "E", "W", "STAY"]
PHEROMONES = {"dialect": "reference", "board_size": GRID, "smell_grid_size": 5,
              "emit_intensity": 0.9, "decay_per_step": 0.10, "min_center_intensity": 0.5}
BELIEF_CFG = {"move_set": MOVES, "sigma_obs": 0.02, "zero_scent_weight": 2.0,
              "resync_floor": 1e-9, "motion_eta_thief": 2.0, "motion_eta_police": 2.0,
              "kernel_mobility_mu": 0.3, "kernel_mobility_k": 3,
              "lie_inversion": False, "lie_inversion_below": 0.25}
SURVIVAL, BARRIERS_MAX = 35, 14


class SpyBelief:
    """Duck-typed belief that records the fold order instead of doing math."""

    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def diffuse(self, role, reference=None) -> None:
        self.calls.append(("diffuse", Role(role), reference))

    def observe_smell(self, cells) -> None:
        self.calls.append(("observe", dict(cells)))

    def note_barrier(self, cell) -> None:
        self.calls.append(("barrier", cell))


class Opponent:
    """Honest opponent trail simulator: real scent physics + hand-built envelopes."""

    def __init__(self, role: Role, start: Cell) -> None:
        self.role, self.position, self.step = role, start, 0
        self.scent = make_scent_model(PHEROMONES)

    def message(self, move_to: Cell | None = None, **overrides) -> dict:
        if move_to is not None:
            self.position = move_to
        self.scent.deposit(self.position)
        self.scent.decay()
        self.step += 1
        body = {"step": self.step, "sender": self.role.value, "hint": "watching the shadows",
                "smell_grid": self.scent.snapshot(), "commit": "a" * 64,
                "timestamp": "2026-07-13T10:00:00+00:00", "barrier_placed": None,
                "capture_claim": None, "claim_response": None, "win_claim": None}
        body.update(overrides)
        return body


def fsm_in_opp_turn() -> GameStateMachine:
    fsm = GameStateMachine()
    fsm.advance(State.NEGOTIATING)
    fsm.advance(State.OPP_TURN)
    return fsm


def back_to_waiting(fsm: GameStateMachine) -> None:
    """My reply happened: MY_TURN -> SENDING -> OPP_TURN (the only legal route back)."""
    fsm.advance(State.SENDING)
    fsm.advance(State.OPP_TURN)


def make_rig(role: Role = Role.THIEF, position: Cell = (3, 3), barriers: set | None = None,
             belief=None, **limits):
    kwargs = {"survival_threshold": SURVIVAL, "barriers_max": BARRIERS_MAX,
              "max_breaches": 3, **limits}
    handler = TurnHandler(role, **kwargs)
    state = OwnGameState(Board(GRID, MOVES), position, barriers=set(barriers or ()))
    belief = SpyBelief() if belief is None else belief
    return handler, state, belief, make_scent_model(PHEROMONES), fsm_in_opp_turn()


def process(rig, message) -> ProcessedTurn:
    handler, state, belief, reader, fsm = rig
    return handler.process(message, state, belief, reader, fsm)


# --- valid turns fold local truth ------------------------------------------------------------
def test_valid_turn_folds_belief_scent_and_fsm() -> None:
    rig = make_rig(Role.THIEF, position=(3, 3), belief=BeliefV2(GRID, BELIEF_CFG, PHEROMONES))
    handler, state, belief, reader, fsm = rig
    cop = Opponent(Role.POLICE, (0, 0))
    result = process(rig, cop.message())
    assert (result.kind, result.step, result.game_over) == (TURN, 1, False)
    assert result.hint == handler.last_hint == "watching the shadows"
    assert belief.most_likely() == (0, 0)  # emission inversion found the cop's true cell
    assert reader.strongest() == (0, 0)  # authoritative trail mirrored locally
    assert fsm.state is State.MY_TURN


def test_fold_order_is_barrier_then_predict_then_update() -> None:
    rig = make_rig(Role.THIEF)
    handler, state, belief, _reader, _fsm = rig
    cop = Opponent(Role.POLICE, (1, 1))
    process(rig, cop.message(barrier_placed=[1, 2]))
    kinds = [call[0] for call in belief.calls]
    assert kinds == ["barrier", "diffuse", "observe"]  # STRATEGY §2.4 seam order
    assert belief.calls[0][1] == (1, 2)
    assert belief.calls[1][1:] == (Role.POLICE, (3, 3))  # PREDICT anchored on MY cell


def test_capture_claim_answered_truthfully_when_missed() -> None:
    rig = make_rig(Role.THIEF, position=(3, 3))
    result = process(rig, Opponent(Role.POLICE, (2, 3)).message(capture_claim=[2, 3]))
    assert result.claim_response_due == {"claim": [2, 3], "caught": False}  # rule 21
    assert result.captured is None and not result.game_over


def test_capture_claim_answered_truthfully_when_caught() -> None:
    rig = make_rig(Role.THIEF, position=(3, 3))
    _handler, _state, _belief, _reader, fsm = rig
    result = process(rig, Opponent(Role.POLICE, (3, 3)).message(capture_claim=[3, 3]))
    assert result.claim_response_due == {"claim": [3, 3], "caught": True}  # rule 21
    assert result.captured == "landing"
    assert fsm.state is State.MY_TURN  # the concession reply is still owed


def test_barrier_declaration_folds_into_shared_map() -> None:
    rig = make_rig(Role.THIEF, position=(3, 3))
    handler, state, _belief, _reader, _fsm = rig
    result = process(rig, Opponent(Role.POLICE, (2, 5)).message(barrier_placed=[2, 4]))
    assert result.barrier_cell == (2, 4)
    assert (2, 4) in state.barriers  # truthful declaration (rule 14) merged
    assert handler.opponent_barriers == 1


def test_barrier_on_my_cell_is_capture() -> None:
    rig = make_rig(Role.THIEF, position=(3, 3))
    result = process(rig, Opponent(Role.POLICE, (3, 4)).message(barrier_placed=[3, 3]))
    assert result.captured == "barrier"  # rule 46 half two (ruling A3)
    assert result.claim_response_due == {"claim": [3, 3], "caught": True}


def test_jailing_barrier_is_capture() -> None:
    rig = make_rig(Role.THIEF, position=(0, 0), barriers={(0, 1)})
    result = process(rig, Opponent(Role.POLICE, (2, 0)).message(barrier_placed=[1, 0]))
    assert result.captured == "jailed"  # rule 47: all orthogonal exits blocked
    assert result.claim_response_due == {"claim": [0, 0], "caught": True}


def test_police_side_never_self_detects_capture() -> None:
    rig = make_rig(Role.POLICE, position=(3, 3))
    result = process(rig, Opponent(Role.THIEF, (3, 3)).message())
    assert result.captured is None and result.kind == TURN


def test_opponent_claim_response_ends_the_game_for_the_cop() -> None:
    rig = make_rig(Role.POLICE, position=(3, 4))
    _handler, _state, _belief, _reader, fsm = rig
    thief = Opponent(Role.THIEF, (3, 4))
    result = process(rig, thief.message(claim_response={"claim": [3, 4], "caught": True}))
    assert result.opponent_caught and result.game_over
    assert fsm.state is State.GAME_OVER


def test_false_claim_response_keeps_playing() -> None:
    rig = make_rig(Role.POLICE)
    result = process(rig, Opponent(Role.THIEF, (5, 5)).message(
        claim_response={"claim": [1, 1], "caught": False}))
    assert not result.opponent_caught and not result.game_over


def test_valid_win_claim_ends_the_game() -> None:
    rig = make_rig(Role.POLICE, survival_threshold=1)
    _handler, _state, _belief, _reader, fsm = rig
    result = process(rig, Opponent(Role.THIEF, (6, 6)).message(win_claim={"type": "survival"}))
    assert result.survival_claimed and result.game_over
    assert fsm.state is State.GAME_OVER


# --- duplicates are idempotent ----------------------------------------------------------------
def test_duplicate_delivery_is_dropped_idempotently() -> None:
    rig = make_rig(Role.THIEF)
    handler, state, belief, _reader, fsm = rig
    message = Opponent(Role.POLICE, (1, 1)).message(barrier_placed=[1, 2])
    assert process(rig, message).kind == TURN
    folds = len(belief.calls)
    duplicate = process(rig, message)  # a legal wire retry (INTEROP §1)
    assert duplicate.kind == DUPLICATE and not duplicate.game_over
    assert len(belief.calls) == folds  # no re-fold
    assert handler.opponent_barriers == 1  # quota not double-counted
    assert fsm.state is State.MY_TURN  # no double advance


# --- breach paths (rule 5 / D4) ---------------------------------------------------------------
BREACH_CASES = [
    ("wrong_sender", Role.THIEF, {"sender": "thief"}),
    ("step_gap", Role.THIEF, {"step": 3}),
    ("cop_claiming_survival", Role.THIEF, {"win_claim": {"type": "survival"}}),
    ("cop_sending_claim_response", Role.THIEF,
     {"claim_response": {"claim": [1, 1], "caught": True}}),
    ("barrier_off_board", Role.THIEF, {"barrier_placed": [9, 9]}),
    ("barrier_not_ints", Role.THIEF, {"barrier_placed": [1.5, 2]}),
    ("capture_claim_off_board", Role.THIEF, {"capture_claim": [-1, 0]}),
    ("malformed_smell_key", Role.THIEF, {"smell_grid": {"2;3": 0.5}}),
    ("off_board_smell_cell", Role.THIEF, {"smell_grid": {"9,9": 0.5}}),
    ("premature_win_claim", Role.POLICE, {"win_claim": {"type": "survival"}}),
    ("unknown_win_claim", Role.POLICE, {"win_claim": {"type": "teleport"}}),
    ("boolean_free_claim_response", Role.POLICE, {"claim_response": {"claim": [1, 1]}}),
    ("thief_placing_barrier", Role.POLICE, {"barrier_placed": [1, 1]}),
    ("thief_claiming_capture", Role.POLICE, {"capture_claim": [1, 1]}),
]


@pytest.mark.parametrize(("label", "my_role", "overrides"),
                         BREACH_CASES, ids=[c[0] for c in BREACH_CASES])
def test_illegal_opponent_move_takes_the_breach_path(label, my_role, overrides) -> None:
    rig = make_rig(my_role)
    handler, state, belief, _reader, fsm = rig
    message = Opponent(my_role.opponent, (1, 1)).message(**overrides)
    result = process(rig, message)
    assert result.kind == BREACH and result.breach_reason
    assert belief.calls == [] and not state.barriers  # nothing was folded
    assert handler.last_step == 0  # the message was never accepted
    assert fsm.state is State.OPP_TURN  # non-fatal: keep waiting (max_breaches=3)


def test_envelope_violation_is_a_breach() -> None:
    rig = make_rig(Role.THIEF)
    message = Opponent(Role.POLICE, (1, 1)).message()
    del message["commit"]
    result = process(rig, message)
    assert result.kind == BREACH and "envelope" in result.breach_reason
    unknown_key = Opponent(Role.POLICE, (1, 1)).message(surprise=True)
    assert process(rig, unknown_key).kind == BREACH  # strict TurnMessage (INTEROP §2.2)


def test_barrier_quota_exhaustion_is_a_breach() -> None:
    rig = make_rig(Role.THIEF, barriers_max=1)
    cop = Opponent(Role.POLICE, (1, 1))
    assert process(rig, cop.message(barrier_placed=[1, 2])).kind == TURN
    back_to_waiting(rig[4])
    result = process(rig, cop.message(barrier_placed=[2, 2]))
    assert result.kind == BREACH and "quota" in result.breach_reason


def test_duplicate_barrier_cell_is_a_breach() -> None:
    rig = make_rig(Role.THIEF, barriers={(2, 2)})
    result = process(rig, Opponent(Role.POLICE, (2, 1)).message(barrier_placed=[2, 2]))
    assert result.kind == BREACH and "already" in result.breach_reason


def test_message_outside_opp_turn_is_a_breach() -> None:
    rig = make_rig(Role.THIEF)
    cop = Opponent(Role.POLICE, (1, 1))
    assert process(rig, cop.message()).kind == TURN  # FSM is now MY_TURN
    result = process(rig, cop.message())  # a NEW step while it is my turn
    assert result.kind == BREACH and "FSM" in result.breach_reason


def test_consecutive_breaches_end_the_sub_game() -> None:
    rig = make_rig(Role.THIEF, max_breaches=2)
    handler, _state, _belief, _reader, fsm = rig
    bad = Opponent(Role.POLICE, (1, 1)).message(step=9)
    first = process(rig, bad)
    assert (first.kind, first.game_over, fsm.state) == (BREACH, False, State.OPP_TURN)
    second = process(rig, dict(bad, step=10))
    assert second.game_over and fsm.state is State.GAME_OVER  # technical_loss path (D4)
    assert handler.breaches == 2


def test_valid_turn_resets_the_consecutive_breach_counter() -> None:
    rig = make_rig(Role.THIEF, max_breaches=2)
    handler, _state, _belief, _reader, fsm = rig
    cop = Opponent(Role.POLICE, (1, 1))
    assert process(rig, cop.message(step=9)).kind == BREACH
    assert process(rig, cop.message(step=1)).kind == TURN  # step 1 arrives correctly
    assert handler.breaches == 0
    back_to_waiting(fsm)
    assert not process(rig, cop.message(step=9)).game_over  # counter restarted
