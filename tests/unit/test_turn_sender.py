"""TurnSender unit tests + the full fake-wire exchange (sender <-> handler, two sides).

No sockets, no processes, no LLMs: FakeTransport pairs deliver straight into in-memory
inboxes; sealing, scent, rules, FSM and (in the exchange) brains + BeliefV2 are all real.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any

import pytest

from pursuit.constants import Cell, Direction, MoveType, Role
from pursuit.domain.belief import BeliefV2
from pursuit.domain.board import Board
from pursuit.domain.own_state import OwnGameState
from pursuit.domain.protocol import CAPTURE_CONCESSION_HINT, SILENCE_HINT
from pursuit.domain.scent import make_scent_model
from pursuit.exceptions import IllegalTransitionError
from pursuit.infra.transport import FakeTransport
from pursuit.peer.fsm import GameStateMachine, State
from pursuit.peer.inboxes import PeerInboxes
from pursuit.peer.sealing import SealedLog
from pursuit.peer.turn_handler import TURN, TurnHandler
from pursuit.peer.turn_sender import SentTurn, TurnSender, lint_hint
from pursuit.strategy.base import Decision
from pursuit.strategy.police import InterceptorPoliceBrain
from pursuit.strategy.talk import TemplateTalk
from pursuit.strategy.thief import SurvivorThiefBrain

# Test-local game parameters (production values come from the signed game.json).
GRID = 7
MOVES = ["N", "S", "E", "W", "STAY"]
PHEROMONES = {"dialect": "reference", "board_size": GRID, "smell_grid_size": 5,
              "emit_intensity": 0.9, "decay_per_step": 0.10, "min_center_intensity": 0.5}
BELIEF_CFG = {"move_set": MOVES, "sigma_obs": 0.02, "zero_scent_weight": 2.0,
              "resync_floor": 1e-9, "motion_eta_thief": 2.0, "motion_eta_police": 2.0,
              "kernel_mobility_mu": 0.3, "kernel_mobility_k": 3,
              "lie_inversion": False, "lie_inversion_below": 0.25}
LIMITS = {"barriers_max": 14, "survival_threshold": 35, "hint_max_words": 15}


class FakeBrain:
    """Scripted decisions; raises IndexError if consulted more often than scripted."""

    def __init__(self, *decisions: Decision) -> None:
        self.queue, self.calls = list(decisions), []

    def decide(self, state, belief, opponent_hint, setting, barriers_max, deadline=None):
        self.calls.append((opponent_hint, setting, barriers_max, deadline))
        return self.queue.pop(0)


def move(direction: Direction, **kw) -> Decision:
    return Decision(move_type=MoveType.MOVE, direction=direction,
                    hint=kw.pop("hint", "slipping between doorways"),
                    verdict=kw.pop("verdict", "truth"), **kw)


def decision(move_type: MoveType, direction: Direction | None = None, **kw) -> Decision:
    return Decision(move_type=move_type, direction=direction,
                    hint=kw.pop("hint", "slipping between doorways"),
                    verdict=kw.pop("verdict", "truth"), **kw)


@dataclass
class Rig:
    sender: TurnSender
    state: OwnGameState
    scent: Any
    sealer: SealedLog
    transport: FakeTransport
    inboxes: PeerInboxes  # the OPPONENT's inboxes this rig's transport delivers into
    fsm: GameStateMachine
    belief: Any = None

    def take(self, brain, **kwargs) -> SentTurn:
        return self.sender.take_turn(brain, self.state, self.belief, self.scent, self.sealer,
                                     self.transport, self.fsm, kwargs.pop("opponent_hint", ""),
                                     **kwargs)


def make_rig(role: Role, position: Cell = (3, 3), barriers: set | None = None,
             move_set: list | None = None, **overrides) -> Rig:
    fsm = GameStateMachine()
    fsm.advance(State.NEGOTIATING)
    fsm.advance(State.MY_TURN)
    inboxes = PeerInboxes()
    state = OwnGameState(Board(GRID, move_set or MOVES), position, barriers=set(barriers or ()))
    sender = TurnSender(role, **{**LIMITS, "setting": "New York", **overrides})
    return Rig(sender, state, make_scent_model(PHEROMONES), SealedLog({"dialect": "book"}),
               FakeTransport(inboxes), inboxes, fsm)


# --- happy path -------------------------------------------------------------------------------
def test_legal_move_is_applied_sealed_and_sent() -> None:
    rig = make_rig(Role.POLICE, position=(0, 0))
    sent = rig.take(FakeBrain(move(Direction.S)))
    assert rig.state.position == (1, 0) and rig.state.step_number == 1
    assert (sent.step, sent.terminal, sent.random_move) == (1, False, False)
    message = sent.message
    assert message.sender == "police" and message.step == 1
    assert message.capture_claim == [1, 0]  # cop declares its landing cell on EVERY MOVE
    assert message.barrier_placed is None and message.win_claim is None
    assert message.commit == sent.record["commit"]
    assert message.smell_grid == rig.scent.snapshot()  # deposit+decay ran before send
    assert sent.record["payload"]["move"] == "MOVE:S"
    assert sent.record["payload"]["state"] == rig.state.state_string()
    assert rig.inboxes.turns.get_nowait() == message.to_wire()  # delivered on the fake wire
    assert rig.fsm.state is State.OPP_TURN


def test_thief_move_carries_no_capture_claim() -> None:
    rig = make_rig(Role.THIEF)
    sent = rig.take(FakeBrain(move(Direction.N)))
    assert sent.message.capture_claim is None


def test_brain_bug_degrades_to_first_legal_move_flagged_random() -> None:
    rig = make_rig(Role.POLICE, position=(0, 0))
    sent = rig.take(FakeBrain(move(Direction.N)))  # N from (0,0) is off the board
    assert (sent.move_type, sent.direction) == (MoveType.MOVE, Direction.S)  # move_set order
    assert sent.random_move and sent.record["payload"]["random_move"] is True
    assert rig.state.position == (1, 0)  # the applied move IS the sent move


def test_move_stay_normalizes_to_hold_wire_form() -> None:
    rig = make_rig(Role.THIEF)
    sent = rig.take(FakeBrain(move(Direction.STAY)))
    assert sent.move_type is MoveType.HOLD and sent.direction is None
    assert sent.record["payload"]["move"] == "HOLD:-"  # never "MOVE:STAY" (INTEROP §2.2)
    assert rig.state.position == (3, 3) and rig.state.step_number == 1  # STAY counts (A5)
    assert sent.message.capture_claim is None  # HOLD is not a MOVE turn


def test_barrier_turn_increments_my_step_counter() -> None:
    rig = make_rig(Role.POLICE, position=(3, 3))
    sent = rig.take(FakeBrain(decision(MoveType.BARRIER, Direction.E)))
    assert sent.barrier_cell == (3, 4) and sent.message.barrier_placed == [3, 4]
    assert (3, 4) in rig.state.barriers and rig.state.my_barriers == 1
    assert sent.step == 1 and rig.state.step_number == 1  # ruling A5: barrier = MY step
    assert sent.record["payload"]["move"] == "BARRIER:E"
    assert sent.message.capture_claim is None  # a barrier turn claims nothing
    rig.fsm.advance(State.MY_TURN)
    follow_up = rig.take(FakeBrain(move(Direction.S)))
    assert follow_up.step == 2 and rig.state.step_number == 2  # the clock never skipped


def test_barrier_on_own_cell_travels_as_barrier_stay() -> None:
    rig = make_rig(Role.POLICE, position=(2, 2))
    sent = rig.take(FakeBrain(decision(MoveType.BARRIER, Direction.STAY)))
    assert sent.barrier_cell == (2, 2)  # own-cell placement: the book's 5th option (A3)
    assert sent.record["payload"]["move"] == "BARRIER:STAY"


def test_thief_barrier_decision_degrades_to_a_legal_move() -> None:
    rig = make_rig(Role.THIEF)
    sent = rig.take(FakeBrain(decision(MoveType.BARRIER, Direction.E)))
    assert sent.move_type is MoveType.MOVE and sent.random_move  # only the cop builds
    assert not rig.state.barriers


def test_barrier_over_quota_degrades_to_a_legal_move() -> None:
    rig = make_rig(Role.POLICE, barriers_max=0)
    sent = rig.take(FakeBrain(decision(MoveType.BARRIER, Direction.E)))
    assert sent.move_type is MoveType.MOVE and sent.random_move
    assert rig.state.my_barriers == 0


def test_jailed_hold_backstop_still_counts_my_step() -> None:
    rig = make_rig(Role.THIEF, position=(0, 0), barriers={(0, 1), (1, 0)},
                   move_set=["N", "S", "E", "W"])  # no STAY -> literally no legal move
    sent = rig.take(FakeBrain(move(Direction.E)))
    assert sent.move_type is MoveType.HOLD and sent.random_move
    assert rig.state.position == (0, 0) and rig.state.step_number == 1  # A5: turn consumed
    assert sent.record["payload"]["move"] == "HOLD:-"


# --- hint lint (rules 26-27) BEFORE sealing ---------------------------------------------------
def test_hint_with_digits_is_linted_before_sealing() -> None:
    rig = make_rig(Role.THIEF)
    sent = rig.take(FakeBrain(move(Direction.N, hint="meet me at 3,4 by the docks")))
    assert sent.message.hint == "meet me at by the docks"
    assert not any(ch.isdigit() for ch in sent.message.hint)
    assert sent.record["payload"]["hint"] == sent.message.hint  # audited bytes == wire bytes


def test_hint_word_cap_is_enforced_mechanically() -> None:
    rig = make_rig(Role.THIEF, hint_max_words=3)
    sent = rig.take(FakeBrain(move(Direction.N, hint="one two three four five")))
    assert sent.message.hint == "one two three"


def test_all_digit_hint_becomes_the_silence_literal() -> None:
    assert lint_hint("3 4 5", 15) == SILENCE_HINT
    rig = make_rig(Role.THIEF)
    sent = rig.take(FakeBrain(move(Direction.N, hint="1 2 3")))
    assert sent.message.hint == SILENCE_HINT


def test_garbage_verdict_is_sealed_as_truth() -> None:
    rig = make_rig(Role.THIEF)
    sent = rig.take(FakeBrain(move(Direction.N, verdict="maybe")))
    assert sent.record["payload"]["intent"] == sent.record["payload"]["verdict"] == "truth"


# --- claims and endings -----------------------------------------------------------------------
def test_false_claim_response_passes_through_and_play_continues() -> None:
    rig = make_rig(Role.THIEF)
    brain = FakeBrain(move(Direction.N))
    sent = rig.take(brain, claim_response={"claim": [1, 1], "caught": False})
    assert sent.message.claim_response == {"claim": [1, 1], "caught": False}
    assert not sent.terminal and brain.calls  # the brain still played this turn
    assert rig.fsm.state is State.OPP_TURN


def test_caught_claim_response_turns_into_the_concession() -> None:
    rig = make_rig(Role.THIEF)
    brain = FakeBrain()  # empty script: consulting the brain would raise IndexError
    sent = rig.take(brain, claim_response={"claim": [3, 3], "caught": True})
    assert sent.message.hint == CAPTURE_CONCESSION_HINT  # the fixed "You got me." literal
    assert sent.move_type is MoveType.HOLD and sent.terminal
    assert sent.message.claim_response == {"claim": [3, 3], "caught": True}  # rule 21
    assert sent.record["payload"]["intent"] == "truth"
    assert rig.fsm.state is State.GAME_OVER and brain.calls == []


def test_thief_win_claim_fires_exactly_at_the_survival_threshold() -> None:
    rig = make_rig(Role.THIEF, survival_threshold=2)
    first = rig.take(FakeBrain(move(Direction.N)))
    assert first.message.win_claim is None and not first.terminal
    rig.fsm.advance(State.MY_TURN)
    second = rig.take(FakeBrain(move(Direction.S)))
    assert second.message.win_claim == {"type": "survival"}  # my OWN counter hit max (A5)
    assert second.terminal and rig.fsm.state is State.GAME_OVER


def test_police_never_claims_survival() -> None:
    rig = make_rig(Role.POLICE, survival_threshold=1)
    sent = rig.take(FakeBrain(move(Direction.S)))
    assert sent.message.win_claim is None and not sent.terminal


def test_take_turn_outside_my_turn_fails_before_any_mutation() -> None:
    rig = make_rig(Role.THIEF)
    rig.fsm.advance(State.SENDING)  # wrong phase
    brain = FakeBrain(move(Direction.N))
    with pytest.raises(IllegalTransitionError, match="MY_TURN"):
        rig.take(brain)
    assert rig.state.step_number == 0 and brain.calls == []  # nothing happened


def test_injected_now_pins_the_timestamp() -> None:
    rig = make_rig(Role.THIEF, now=lambda: "2026-07-13T10:00:00+00:00")
    sent = rig.take(FakeBrain(move(Direction.N)))
    assert sent.message.timestamp == "2026-07-13T10:00:00+00:00"


# --- the full fake-wire exchange (sender <-> handler, both sides real) ------------------------
@dataclass
class Peer:
    role: Role
    state: OwnGameState
    belief: Any
    scent_mine: Any
    scent_reader: Any
    sealer: SealedLog
    sender: TurnSender
    handler: TurnHandler
    fsm: GameStateMachine
    inboxes: PeerInboxes
    brain: Any
    transport: FakeTransport | None = None
    opp_hint: str = ""
    response_due: dict | None = field(default=None)


def make_peer(role: Role, start: Cell, brain: Any, first_mover: bool) -> Peer:
    fsm = GameStateMachine()
    fsm.advance(State.NEGOTIATING)
    fsm.advance(State.MY_TURN if first_mover else State.OPP_TURN)
    return Peer(role=role, state=OwnGameState(Board(GRID, MOVES), start),
                belief=BeliefV2(GRID, BELIEF_CFG, PHEROMONES),
                scent_mine=make_scent_model(PHEROMONES),
                scent_reader=make_scent_model(PHEROMONES),
                sealer=SealedLog({"dialect": "book"}),
                sender=TurnSender(role, **LIMITS, setting="New York"),
                handler=TurnHandler(role, survival_threshold=LIMITS["survival_threshold"],
                                    barriers_max=LIMITS["barriers_max"], max_breaches=1),
                fsm=fsm, inboxes=PeerInboxes(), brain=brain)


def wire_pair(thief: Peer, police: Peer) -> None:
    thief.transport, police.transport = FakeTransport.pair(thief.inboxes, police.inboxes)


def exchange(mover: Peer, waiter: Peer):
    """One half-ply over the fake wire: mover sends, waiter folds the delivered dict."""
    sent = mover.sender.take_turn(mover.brain, mover.state, mover.belief, mover.scent_mine,
                                  mover.sealer, mover.transport, mover.fsm, mover.opp_hint,
                                  claim_response=mover.response_due)
    mover.response_due = None
    processed = waiter.handler.process(waiter.inboxes.turns.get_nowait(), waiter.state,
                                       waiter.belief, waiter.scent_reader, waiter.fsm)
    waiter.opp_hint, waiter.response_due = processed.hint, processed.claim_response_due
    return sent, processed


def test_three_ply_exchange_with_real_brains_and_belief() -> None:
    talk = TemplateTalk(random.Random(11), "New York", LIMITS["hint_max_words"])
    thief = make_peer(Role.THIEF, (3, 3), SurvivorThiefBrain(talk, random.Random(1)), True)
    police = make_peer(Role.POLICE, (0, 0), InterceptorPoliceBrain(talk, random.Random(2)),
                       False)
    wire_pair(thief, police)
    for ply in (1, 2, 3):  # thief moves first, unconditionally (INTEROP §4)
        t_sent, p_processed = exchange(thief, police)
        assert p_processed.kind == TURN and t_sent.step == ply
        assert police.belief.most_likely() == thief.state.position  # belief tracks truth
        p_sent, t_processed = exchange(police, thief)
        assert t_processed.kind == TURN and p_sent.step == ply
        assert p_sent.move_type is MoveType.MOVE  # too far for barriers in 3 plies
        assert thief.belief.most_likely() == police.state.position
        assert not (t_processed.game_over or p_processed.game_over)
        for message in (t_sent.message, p_sent.message):
            words = message.hint.split()
            assert len(words) <= LIMITS["hint_max_words"]
            assert not any(ch.isdigit() for word in words for ch in word)  # rule 27
        assert t_processed.claim_response_due is not None  # cop claimed; answer owed next ply
    # thief just folded the cop's 3rd message (reply owed); the cop is waiting again
    assert thief.fsm.state is State.MY_TURN and police.fsm.state is State.OPP_TURN
    for own, other in ((thief, police), (police, thief)):
        results = SealedLog.audit_verify(own.sealer.audit_reveal(), other.sealer.dialect)
        assert [r["ok"] for r in results] == [True, True, True]  # cross-audit passes


def test_wire_capture_claim_answered_truthfully_and_conceded() -> None:
    thief = make_peer(Role.THIEF, (3, 4), FakeBrain(decision(MoveType.HOLD)), True)
    police = make_peer(Role.POLICE, (3, 3), FakeBrain(move(Direction.E)), False)
    wire_pair(thief, police)
    _t_sent, p_processed = exchange(thief, police)  # thief holds at (3, 4)
    assert p_processed.claim_response_due is None  # a thief never claims capture
    p_sent, t_processed = exchange(police, thief)  # cop lands exactly on the thief
    assert p_sent.message.capture_claim == [3, 4]
    assert t_processed.captured == "landing"
    assert t_processed.claim_response_due == {"claim": [3, 4], "caught": True}  # rule 21
    t_sent, p_final = exchange(thief, police)  # the concession turn
    assert t_sent.terminal and t_sent.message.hint == CAPTURE_CONCESSION_HINT
    assert p_final.opponent_caught and p_final.game_over
    assert thief.fsm.state is State.GAME_OVER and police.fsm.state is State.GAME_OVER


def test_wire_missed_claim_is_answered_caught_false() -> None:
    thief = make_peer(Role.THIEF, (5, 5), FakeBrain(decision(MoveType.HOLD),
                                                    move(Direction.N)), True)
    police = make_peer(Role.POLICE, (0, 0), FakeBrain(move(Direction.S)), False)
    wire_pair(thief, police)
    exchange(thief, police)
    _p_sent, t_processed = exchange(police, thief)  # cop lands (1,0), thief sits (5,5)
    assert t_processed.claim_response_due == {"claim": [1, 0], "caught": False}
    t_sent, p_processed = exchange(thief, police)  # truthful "not caught" travels back
    assert t_sent.message.claim_response == {"claim": [1, 0], "caught": False}
    assert not p_processed.opponent_caught and not p_processed.game_over
