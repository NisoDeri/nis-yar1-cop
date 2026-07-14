"""Unit tests for pursuit.domain.scoring — Appendix F Table 17, rulings A6/A9a."""

from __future__ import annotations

import pytest

from pursuit.constants import GameResult, Role
from pursuit.domain.scoring import ScoreTable
from pursuit.exceptions import ConfigError

# Table 17 values, injected as config (production asserts them in shared_terms, not here).
SCORING = {
    "capture_cop": 20,
    "capture_thief": 5,
    "survival_cop": 5,
    "survival_thief": 10,
    "technical_loss": 0,
    "tie_score": 2,
}


@pytest.fixture
def table() -> ScoreTable:
    return ScoreTable(SCORING)


# --- construction / config validation --------------------------------------------------------
@pytest.mark.parametrize("missing", sorted(SCORING))
def test_missing_key_rejected(missing: str) -> None:
    broken = {key: value for key, value in SCORING.items() if key != missing}
    with pytest.raises(ConfigError, match=missing):
        ScoreTable(broken)


@pytest.mark.parametrize("bad_value", ["20", 20.0, None, True])
def test_non_int_value_rejected(bad_value: object) -> None:
    with pytest.raises(ConfigError, match="capture_cop"):
        ScoreTable({**SCORING, "capture_cop": bad_value})


# --- sub-game rows ----------------------------------------------------------------------------
def test_capture_scores_cop_20_thief_5(table: ScoreTable) -> None:
    scores = table.score_subgame(GameResult.CAPTURE, Role.POLICE)
    assert scores == {Role.POLICE: 20, Role.THIEF: 5}


def test_survival_scores_cop_5_thief_10(table: ScoreTable) -> None:
    scores = table.score_subgame(GameResult.SURVIVAL, Role.THIEF)
    assert scores == {Role.POLICE: 5, Role.THIEF: 10}


@pytest.mark.parametrize("winner", [None, Role.POLICE, Role.THIEF])
def test_technical_loss_always_zero_zero(table: ScoreTable, winner: Role | None) -> None:
    """Ruling A9a: audit-caught forgery keeps no points, whoever 'won' on the board."""
    scores = table.score_subgame(GameResult.TECHNICAL_LOSS, winner)
    assert scores == {Role.POLICE: 0, Role.THIEF: 0}


def test_stopped_scores_technical(table: ScoreTable) -> None:
    assert table.score_subgame(GameResult.STOPPED, None) == {Role.POLICE: 0, Role.THIEF: 0}


def test_unknown_result_string_scores_technical(table: ScoreTable) -> None:
    assert table.score_subgame("weird_ending", Role.POLICE) == {Role.POLICE: 0, Role.THIEF: 0}


@pytest.mark.parametrize(
    ("result", "claimed_winner"),
    [(GameResult.CAPTURE, Role.THIEF), (GameResult.CAPTURE, None),
     (GameResult.SURVIVAL, Role.POLICE), (GameResult.SURVIVAL, None)],
)
def test_forged_winner_claim_degrades_to_technical(
    table: ScoreTable, result: GameResult, claimed_winner: Role | None
) -> None:
    assert table.score_subgame(result, claimed_winner) == {Role.POLICE: 0, Role.THIEF: 0}


# --- series aggregation -----------------------------------------------------------------------
def test_series_totals_clear_winner(table: ScoreTable) -> None:
    rows = [
        table.score_subgame(GameResult.CAPTURE, Role.POLICE),
        table.score_subgame(GameResult.CAPTURE, Role.POLICE),
        table.score_subgame(GameResult.SURVIVAL, Role.THIEF),
    ]
    outcome = table.series_totals(rows)
    assert outcome["totals"] == {Role.POLICE: 45, Role.THIEF: 20}
    assert outcome["winner"] is Role.POLICE
    assert outcome["tie"] is False


def test_series_tie_adds_bonus_to_both(table: ScoreTable) -> None:
    rows = [{"nis-yar1": 25, "opp-grp2": 25}]
    outcome = table.series_totals(rows)
    assert outcome["tie"] is True
    assert outcome["winner"] is None
    assert outcome["totals"] == {"nis-yar1": 27, "opp-grp2": 27}  # +2 each (Table 17)


def test_series_totals_group_keyed_rows(table: ScoreTable) -> None:
    rows = [{"nis-yar1": 20, "opp-grp2": 5}, {"nis-yar1": 5, "opp-grp2": 10}]
    outcome = table.series_totals(rows)
    assert outcome["totals"] == {"nis-yar1": 25, "opp-grp2": 15}
    assert outcome["winner"] == "nis-yar1"


def test_series_totals_empty_rows(table: ScoreTable) -> None:
    assert table.series_totals([]) == {"totals": {}, "tie": False, "winner": None}
