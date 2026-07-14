"""Simulation lab — the evidence machine (DECISIONS.md D7, STRATEGY.md §6).

In-process, network-free self-play: :mod:`arena` referees single sub-games
under the real domain rules with a faithful information partition,
:mod:`runner` drives paired-seed series, :mod:`stats` turns the rows into
win rates, league points, and the §6.3 exact-binomial promotion verdict.
Unit-test safe by construction: no sockets, no subprocesses, no LLMs.
"""

from pursuit.lab.arena import play_subgame
from pursuit.lab.protocol import (
    BrainLike,
    LabDecision,
    LabView,
    NullBelief,
    SubgameResult,
)
from pursuit.lab.runner import BrainSpec, run_match
from pursuit.lab.stats import (
    a_beats_b_p_value,
    binomial_p_value,
    decisive_wins,
    format_table,
    points_per_scoring_table,
    win_rate,
)

__all__ = [
    "BrainLike",
    "BrainSpec",
    "LabDecision",
    "LabView",
    "NullBelief",
    "SubgameResult",
    "a_beats_b_p_value",
    "binomial_p_value",
    "decisive_wins",
    "format_table",
    "play_subgame",
    "points_per_scoring_table",
    "run_match",
    "win_rate",
]
