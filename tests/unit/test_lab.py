"""Unit tests for pursuit.lab — in-process arena, paired-seed runner, promotion stats."""

from __future__ import annotations

import dataclasses
import random

import pytest

from pursuit.constants import Direction, GameResult, MoveType, Role
from pursuit.exceptions import IllegalMoveError
from pursuit.lab.arena import LabDecision, LabView, play_subgame
from pursuit.lab.runner import run_match
from pursuit.lab.stats import (
    a_beats_b_p_value,
    binomial_p_value,
    decisive_wins,
    format_table,
    points_per_scoring_table,
    win_rate,
)

# Test-local game parameters (in production these come from the signed game.json).
SCORING = {"capture_cop": 20, "capture_thief": 5, "survival_cop": 5,
           "survival_thief": 10, "tie_score": 2, "technical_loss": 0}


def make_terms(cop_start=(0, 0), thief_start=(3, 3), grid=7, max_moves=35,
               survival=35, max_barriers=14, dialect="reference") -> dict:
    return {
        "board_and_agents": {"grid_size": grid, "cop_start": list(cop_start),
                             "thief_start": list(thief_start)},
        "movement_and_barriers": {"move_set": ["N", "S", "E", "W", "STAY"],
                                  "max_barriers": max_barriers, "max_moves": max_moves,
                                  "survival_threshold": survival},
        "scoring": dict(SCORING),
        "pheromones": {"dialect": dialect, "pheromone_center_intensity": 0.9,
                       "pheromone_decay": 0.1, "pheromone_grid_size": 5,
                       "pheromone_min_center_intensity": 0.5},
    }


def move(letter: str) -> LabDecision:
    return LabDecision(MoveType.MOVE, direction=Direction(letter))


def barrier(cell) -> LabDecision:
    return LabDecision(MoveType.BARRIER, barrier_cell=cell)


class ScriptedBrain:
    """Fixed decision list, then HOLD forever; records every view (partition probe)."""

    def __init__(self, decisions=()) -> None:
        self.script = list(decisions)
        self.views: list[LabView] = []

    def decide(self, view: LabView) -> LabDecision:
        self.views.append(view)
        return self.script.pop(0) if self.script else LabDecision(MoveType.HOLD)


class RandomWalkBrain:
    """Legal random walk driven ONLY by the injected rng (determinism probe)."""

    def decide(self, view: LabView) -> LabDecision:
        moves = view.state.board.legal_moves(view.state.position, view.state.barriers)
        return LabDecision(MoveType.MOVE, direction=view.rng.choice([d for d, _ in moves]))


# --- arena: documented endings ---------------------------------------------------------------
class TestArenaEndings:
    def test_capture_by_landing(self) -> None:
        cop = ScriptedBrain([move("S"), move("S"), move("S"), move("E"), move("E"), move("E")])
        outcome = play_subgame(cop, ScriptedBrain(), make_terms(), random.Random(0))
        assert outcome.result is GameResult.CAPTURE
        assert outcome.winner_role is Role.POLICE
        assert outcome.capture_kind == "landing"
        assert (outcome.steps, outcome.cop_steps) == (6, 6)
        assert outcome.trajectory[0].startswith("thief:")  # the thief moves first
        assert outcome.trajectory[-1] == "police:MOVE:E"

    def test_capture_by_barrier_on_thief_cell(self) -> None:
        cop = ScriptedBrain([barrier((3, 3))])
        terms = make_terms(cop_start=(2, 3))
        outcome = play_subgame(cop, ScriptedBrain(), terms, random.Random(0))
        assert outcome.result is GameResult.CAPTURE
        assert outcome.capture_kind == "barrier"
        assert (outcome.steps, outcome.cop_steps) == (1, 1)
        assert outcome.trajectory[-1] == "police:BARRIER:3,3"

    def test_capture_by_jailing_and_a5_clock(self) -> None:
        cop = ScriptedBrain([barrier((0, 1)), barrier((1, 0))])
        terms = make_terms(cop_start=(1, 1), thief_start=(0, 0))
        outcome = play_subgame(cop, ScriptedBrain(), terms, random.Random(0))
        assert outcome.result is GameResult.CAPTURE
        assert outcome.capture_kind == "jailed"
        # Ruling A5: barrier turns consumed cop moves but never advanced the thief clock.
        assert (outcome.steps, outcome.cop_steps) == (2, 2)

    def test_thief_survival_on_own_counter(self) -> None:
        terms = make_terms(cop_start=(6, 6), survival=5)
        outcome = play_subgame(ScriptedBrain(), ScriptedBrain(), terms, random.Random(0))
        assert outcome.result is GameResult.SURVIVAL
        assert outcome.winner_role is Role.THIEF
        assert outcome.capture_kind is None
        assert (outcome.steps, outcome.cop_steps) == (5, 4)  # thief's 5th move ends it

    def test_move_ceiling_ends_as_survival(self) -> None:
        terms = make_terms(cop_start=(6, 6), survival=10, max_moves=3)
        outcome = play_subgame(ScriptedBrain(), ScriptedBrain(), terms, random.Random(0))
        assert outcome.result is GameResult.SURVIVAL
        assert (outcome.steps, outcome.cop_steps) == (4, 3)

    def test_thief_barrier_is_illegal(self) -> None:
        with pytest.raises(IllegalMoveError, match="only the cop"):
            play_subgame(ScriptedBrain(), ScriptedBrain([barrier((3, 4))]),
                         make_terms(), random.Random(0))

    def test_barrier_outside_reach_is_rejected(self) -> None:
        with pytest.raises(IllegalMoveError, match="5-option reach"):
            play_subgame(ScriptedBrain([barrier((5, 5))]), ScriptedBrain(),
                         make_terms(), random.Random(0))


# --- arena: information partition -------------------------------------------------------------
class TestInformationPartition:
    def test_thief_view_carries_no_cop_position_object(self) -> None:
        thief = ScriptedBrain()
        cop = ScriptedBrain([move("S"), move("S"), move("S"), move("E"), move("E"), move("E")])
        play_subgame(cop, thief, make_terms(), random.Random(0))
        field_names = {f.name for f in dataclasses.fields(LabView)}
        assert field_names == {"role", "state", "belief", "opponent_scent",
                               "opponent_hint", "moves_left", "rng"}
        assert thief.views  # the probe actually ran
        for view in thief.views:
            assert view.role is Role.THIEF
            assert view.state.position == (3, 3)  # own position only — the thief never moved
            assert set(vars(view.state)) <= {"board", "position", "visited", "barriers",
                                             "my_barriers", "step_number"}
            assert all(isinstance(k, str) and isinstance(v, float)
                       for k, v in view.opponent_scent.items())

    def test_opponent_scent_snapshot_is_the_position_channel(self) -> None:
        thief = ScriptedBrain()
        outcome = play_subgame(ScriptedBrain([move("S")]), thief,
                               make_terms(survival=3), random.Random(0))
        assert outcome.result is GameResult.SURVIVAL
        assert thief.views[0].opponent_scent == {}  # nothing broadcast before the first cop turn
        second = thief.views[1].opponent_scent
        # Reference dialect: fresh center 0.9 minus one decay = 0.800 at the cop's real cell.
        assert max(second, key=second.get) == "1,0"
        assert second["1,0"] == pytest.approx(0.8)

    def test_hints_travel_to_the_opponent_view(self) -> None:
        thief = ScriptedBrain([LabDecision(MoveType.HOLD, hint="north of the park")])
        cop = ScriptedBrain([move("S")])
        play_subgame(cop, thief, make_terms(survival=3), random.Random(0))
        assert cop.views[0].opponent_hint == "north of the park"
        assert thief.views[0].opponent_hint is None


# --- runner: paired seeds ---------------------------------------------------------------------
class TestPairedSeeds:
    @staticmethod
    def spec(role, rng, terms) -> RandomWalkBrain:
        return RandomWalkBrain()

    def test_rerun_reproduces_identical_games(self) -> None:
        terms = make_terms(survival=8)
        rows_1 = run_match(self.spec, self.spec, 3, 42, terms)
        rows_2 = run_match(self.spec, self.spec, 3, 42, terms)
        assert rows_1 == rows_2
        assert len(rows_1) == 6  # 3 paired seeds x both role assignments

    def test_pair_shares_seed_and_swaps_roles(self) -> None:
        rows = run_match(self.spec, self.spec, 2, 7, make_terms(survival=6))
        for first, second in zip(rows[::2], rows[1::2], strict=True):
            assert first["seed"] == second["seed"]
            assert (first["police"], first["thief"]) == ("A", "B")
            assert (second["police"], second["thief"]) == ("B", "A")
            # Same seed + same brain spec both ways -> byte-identical game trajectory.
            assert first["trajectory"] == second["trajectory"]


# --- stats ------------------------------------------------------------------------------------
class TestStats:
    def test_binomial_known_value_60_of_100(self) -> None:
        assert binomial_p_value(60, 100) == pytest.approx(0.028444, abs=1e-4)

    def test_binomial_edges(self) -> None:
        assert binomial_p_value(0, 10) == 1.0
        assert binomial_p_value(10, 10) == pytest.approx(0.5**10)
        assert binomial_p_value(0, 0) == 1.0

    @pytest.mark.parametrize(("wins", "n", "p"), [(-1, 10, 0.5), (11, 10, 0.5), (5, 10, 1.5)])
    def test_binomial_rejects_bad_arguments(self, wins: int, n: int, p: float) -> None:
        with pytest.raises(ValueError):
            binomial_p_value(wins, n, p)

    def test_win_rate_drops_undecided_rows(self) -> None:
        rows = [{"winner": "A"}, {"winner": "A"}, {"winner": "B"}, {"winner": None}]
        assert decisive_wins(rows) == (2, 3)
        assert win_rate(rows) == pytest.approx(2 / 3)
        assert win_rate(rows, agent="B") == pytest.approx(1 / 3)
        assert win_rate([]) == 0.0

    def test_a_beats_b_matches_binomial_on_decisive(self) -> None:
        rows = [{"winner": "A"}] * 60 + [{"winner": "B"}] * 40 + [{"winner": None}] * 5
        assert a_beats_b_p_value(rows) == pytest.approx(binomial_p_value(60, 100))

    def test_points_per_scoring_table(self) -> None:
        rows = [
            {"police": "A", "thief": "B", "result": "capture", "winner_role": "police"},
            {"police": "B", "thief": "A", "result": "survival", "winner_role": "thief"},
            {"police": "A", "thief": "B", "result": "technical_loss", "winner_role": None},
        ]
        assert points_per_scoring_table(rows, SCORING) == {"A": 30, "B": 10}

    def test_format_table_is_markdown(self) -> None:
        rows = run_match(TestPairedSeeds.spec, TestPairedSeeds.spec, 1, 3,
                         make_terms(survival=4))
        table = format_table(rows)
        lines = table.splitlines()
        assert lines[0] == "| pair | seed | police | thief | result | winner | steps |" \
                           " capture_kind |"
        assert set(lines[1].replace("|", "").split()) == {"---"}
        assert len(lines) == 2 + len(rows)
        assert "survival" in table
