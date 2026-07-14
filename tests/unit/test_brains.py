"""Unit tests for the v1 heuristic brains (STRATEGY §3/§4 v1 scope + §8 guardrails).

No sockets, no processes, no LLM: real Board/OwnGameState domain objects, fake
belief/talk/rng — the brains are exercised through direct ``decide()`` calls.
"""

from __future__ import annotations

import random

import pytest

from pursuit.constants import Cell, Direction, MoveType
from pursuit.domain.board import Board
from pursuit.domain.own_state import OwnGameState
from pursuit.strategy.base import BrainBase, Decision, mode_probability
from pursuit.strategy.greedy import GreedyPoliceBrain, GreedyThiefBrain
from pursuit.strategy.police import InterceptorPoliceBrain
from pursuit.strategy.thief import SurvivorThiefBrain

# Test-local game parameters (in production these come from the signed game.json).
GRID = 7
MOVE_SET = ["N", "S", "E", "W", "STAY"]
MAX_BARRIERS = 14


class FakeBelief:
    """Duck-typed belief: most_likely_p() returns a bare float."""

    def __init__(self, cell: Cell, p: float = 1.0) -> None:
        self.cell, self.p = cell, p

    def most_likely(self) -> Cell:
        return self.cell

    def most_likely_p(self) -> float:
        return self.p


class TupleBelief(FakeBelief):
    """The STRATEGY §2.6 shape: most_likely_p() returns (cell, prob)."""

    def most_likely_p(self) -> tuple[Cell, float]:
        return (self.cell, self.p)


class FakeTalk:
    def say(self, role, state, belief, setting, opponent_hint, deadline):
        return ("watching the shadows", "truth", "test stub", "")


class ScriptedRng:
    """Deterministic random() stream — asserts exactly how much entropy is consumed."""

    def __init__(self, values: list[float]) -> None:
        self.values = list(values)

    def random(self) -> float:
        return self.values.pop(0)


def make_state(position: Cell, barriers: set[Cell] | None = None) -> OwnGameState:
    return OwnGameState(board=Board(GRID, MOVE_SET), position=position,
                        barriers=set(barriers or ()))


def police(**kwargs) -> InterceptorPoliceBrain:
    return InterceptorPoliceBrain(FakeTalk(), random.Random(0), **kwargs)


def thief(**kwargs) -> SurvivorThiefBrain:
    return SurvivorThiefBrain(FakeTalk(), random.Random(0), **kwargs)


# --- contract (base.py) ----------------------------------------------------------------------
def test_brainbase_is_abstract() -> None:
    with pytest.raises(TypeError):
        BrainBase(FakeTalk(), random.Random(0))  # type: ignore[abstract]


def test_mode_probability_handles_both_duck_shapes() -> None:
    assert mode_probability(FakeBelief((1, 1), 0.7)) == pytest.approx(0.7)
    assert mode_probability(TupleBelief((1, 1), 0.9)) == pytest.approx(0.9)


def test_decide_wires_talk_fields_into_decision() -> None:
    decision = police().decide(make_state((0, 0)), FakeBelief((6, 6)), "", "New York", 0)
    assert isinstance(decision, Decision)
    assert (decision.hint, decision.verdict) == ("watching the shadows", "truth")
    assert decision.prompt_text == "" and decision.reasoning == "test stub"
    assert decision.response_seconds >= 0.0 and decision.random_move is False


def test_default_decide_move_holds_when_jailed() -> None:
    state = OwnGameState(board=Board(GRID, ["N", "S", "E", "W"]), position=(0, 0),
                         barriers={(0, 1), (1, 0)})  # no STAY in move_set -> truly jailed
    decision = thief().decide(state, FakeBelief((6, 6)), "", "", 0)
    assert (decision.move_type, decision.direction) == (MoveType.HOLD, None)


# --- police (STRATEGY §3 v1) ------------------------------------------------------------------
def test_police_closes_bfs_distance_every_turn_on_open_board() -> None:
    brain, state, target = police(), make_state((0, 0)), (6, 6)
    belief = FakeBelief(target)
    distance = state.board.bfs_distance(state.position, target, state.barriers)
    for _ in range(distance - 1):
        decision = brain.decide(state, belief, "", "", 0)  # barriers_max=0 -> pure chase
        assert decision.move_type is MoveType.MOVE
        state.apply_step(decision.direction)
        new_distance = state.board.bfs_distance(state.position, target, state.barriers)
        assert new_distance == distance - 1  # STRICTLY closes every single turn
        distance = new_distance
    assert distance == 1


@pytest.mark.parametrize(
    ("target", "expected"),
    [((3, 4), (MoveType.MOVE, Direction.E)),        # adjacent mode -> LAND on it (universal
     ((2, 3), (MoveType.MOVE, Direction.N)),        # capture; a reference peer rejects a
     ((3, 3), (MoveType.BARRIER, Direction.STAY))],  # barrier-on-thief). own cell -> wall it.
)
def test_police_finisher_lands_else_walls_own_cell(target: Cell, expected: tuple) -> None:
    decision = police().decide(make_state((3, 3)), FakeBelief(target, p=0.9), "", "",
                               MAX_BARRIERS)
    assert (decision.move_type, decision.direction) == expected


def test_police_finisher_accepts_tuple_belief_shape() -> None:
    decision = police().decide(make_state((3, 3)), TupleBelief((3, 4), p=0.9), "", "",
                               MAX_BARRIERS)
    assert (decision.move_type, decision.direction) == (MoveType.MOVE, Direction.E)  # land it


def test_police_finisher_needs_mode_probability() -> None:
    # p below barrier_finisher_p (0.8 default): pounce by MOVE onto the mode instead.
    decision = police().decide(make_state((3, 3)), FakeBelief((3, 4), p=0.5), "", "",
                               MAX_BARRIERS)
    assert (decision.move_type, decision.direction) == (MoveType.MOVE, Direction.E)


def test_police_finisher_respects_barrier_quota() -> None:
    state = make_state((3, 3))
    state.my_barriers = MAX_BARRIERS  # quota spent -> finisher impossible, keep chasing
    decision = police().decide(state, FakeBelief((3, 4), p=1.0), "", "", MAX_BARRIERS)
    assert decision.move_type is MoveType.MOVE


def test_police_tempo_walls_best_wallable_escape_lane() -> None:
    # Mode 2 away (diagonal): both common neighbours are wallable without self-harm.
    decision = police().decide(make_state((3, 3)), FakeBelief((2, 4), p=0.5), "", "",
                               MAX_BARRIERS)
    assert (decision.move_type, decision.direction) == (MoveType.BARRIER, Direction.N)


def test_police_tempo_never_walls_its_own_only_path() -> None:
    # (0,1) is the only short route to the mode at (0,2); walling it would self-harm (W4).
    decision = police().decide(make_state((0, 0), barriers={(1, 1)}),
                               FakeBelief((0, 2), p=0.5), "", "", MAX_BARRIERS)
    assert (decision.move_type, decision.direction) == (MoveType.MOVE, Direction.E)


def test_police_is_deterministic_no_random_coin() -> None:
    rng = ScriptedRng([])  # any rng consumption would raise IndexError (STRATEGY §3.5)
    brain = InterceptorPoliceBrain(FakeTalk(), rng)
    decision = brain.decide(make_state((0, 0)), FakeBelief((6, 6)), "", "", MAX_BARRIERS)
    assert decision.move_type is MoveType.MOVE and rng.values == []


# --- thief (STRATEGY §4 v1) -------------------------------------------------------------------
def test_thief_never_enters_jail_risk_cell_while_cop_has_charges() -> None:
    # (0,0) is a dead-end (single non-STAY exit) but maximizes distance from the threat.
    state = make_state((0, 1), barriers={(1, 0)})
    decision = thief(w_mob=0.0).decide(state, FakeBelief((6, 6)), "", "", MAX_BARRIERS)
    assert decision.direction is Direction.STAY  # next-best distance, never the tomb


def test_thief_enters_risky_cell_once_cop_charges_exhausted() -> None:
    state = make_state((0, 1), barriers={(1, 0)})  # cop placed its only charge already
    decision = thief(w_mob=0.0).decide(state, FakeBelief((6, 6)), "", "", 1)
    assert decision.direction is Direction.W  # jail_risk == 0 -> corners are terrain again


def test_thief_increases_distance_vs_greedy_chaser() -> None:
    # Start under pressure (distance 4): every flee move must strictly buy a step back.
    # (From far away the default brain may prefer a T-safe STAY — that is by design.)
    state, cop = make_state((2, 2)), (0, 0)
    brain, board = thief(), state.board
    initial = board.bfs_distance(cop, state.position, state.barriers)
    for _ in range(3):
        before = board.bfs_distance(cop, state.position, state.barriers)
        decision = brain.decide(state, FakeBelief(cop), "", "", MAX_BARRIERS)
        assert decision.move_type is MoveType.MOVE
        state.apply_step(decision.direction)
        assert board.bfs_distance(cop, state.position, state.barriers) == before + 1
        cop = min(  # greedy chaser closes one BFS step after every thief move
            (c for _d, c in board.legal_moves(cop, state.barriers)),
            key=lambda c: (board.bfs_distance(c, state.position, state.barriers), c),
        )
    assert board.bfs_distance(cop, state.position, state.barriers) >= initial


def test_thief_survives_unreachable_threat_cell() -> None:
    state = make_state((3, 3), barriers={(0, 1), (1, 0)})
    decision = thief().decide(state, FakeBelief((0, 0)), "", "", MAX_BARRIERS)
    assert decision.move_type is MoveType.MOVE  # walled-off mode never crashes the score


# --- greedy reference baselines (ref-map §2.2) ------------------------------------------------
def test_greedy_thief_maximizes_manhattan_and_prefers_unvisited() -> None:
    state = make_state((3, 3))
    state.visited.update({(2, 3), (3, 4)})  # two of the three max-distance cells visited
    brain = GreedyThiefBrain(FakeTalk(), random.Random(0))
    decision = brain.decide(state, FakeBelief((3, 0)), "", "", MAX_BARRIERS)
    assert decision.direction is Direction.S  # (4,3): same distance, only unvisited one


def test_greedy_thief_falls_back_to_move_order_when_all_visited() -> None:
    state = make_state((3, 3))
    state.visited.update({(2, 3), (3, 4), (4, 3)})
    brain = GreedyThiefBrain(FakeTalk(), random.Random(0))
    decision = brain.decide(state, FakeBelief((3, 0)), "", "", MAX_BARRIERS)
    assert decision.direction is Direction.N  # first max in move_set order


def test_greedy_police_steps_toward_target_without_coin() -> None:
    brain = GreedyPoliceBrain(FakeTalk(), ScriptedRng([0.99]))
    decision = brain.decide(make_state((0, 0)), FakeBelief((3, 0)), "", "", MAX_BARRIERS)
    assert (decision.move_type, decision.direction) == (MoveType.MOVE, Direction.S)
    assert decision.random_move is False


def test_greedy_police_15_percent_coin_walls_its_own_step_cell() -> None:
    brain = GreedyPoliceBrain(FakeTalk(), ScriptedRng([0.10]))  # coin fires (< 0.15)
    decision = brain.decide(make_state((0, 0)), FakeBelief((3, 0)), "", "", MAX_BARRIERS)
    assert (decision.move_type, decision.direction) == (MoveType.BARRIER, Direction.S)
    assert decision.random_move is True  # flagged for the sealed audit record


def test_greedy_police_coin_respects_quota_and_stay() -> None:
    rng = ScriptedRng([0.0])
    brain = GreedyPoliceBrain(FakeTalk(), rng)
    quota_out = brain.decide(make_state((0, 0)), FakeBelief((3, 0)), "", "", 0)
    assert quota_out.move_type is MoveType.MOVE and rng.values == [0.0]  # coin never rolled
    on_target = brain.decide(make_state((3, 3)), FakeBelief((3, 3)), "", "", MAX_BARRIERS)
    assert (on_target.move_type, on_target.direction) == (MoveType.MOVE, Direction.STAY)
