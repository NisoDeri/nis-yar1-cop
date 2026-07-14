"""Paired-seed match runner — the promotion-rule series driver (STRATEGY.md §6.3).

Each seed is played TWICE, once per role assignment ("A as police" then "B as
police"), with the same arena seed and the same role-derived brain seeds — so
board luck cancels and only brain quality separates the agents, exactly the
role-alternating structure of a real league series. Rows are plain dicts,
ready for :mod:`pursuit.lab.stats` and the D7 markdown artifacts.
"""

from __future__ import annotations

import random
from collections.abc import Callable
from typing import Any

from pursuit.constants import Role
from pursuit.lab.arena import BrainLike, play_subgame

#: A brain spec builds a fresh brain per game: spec(role, rng, terms) -> brain.
BrainSpec = Callable[[Role, random.Random, dict], BrainLike]


def _play_one(pair: int, seed: int, police_agent: str, specs: dict[str, BrainSpec],
              terms: dict, belief_factory: Any) -> dict[str, Any]:
    """One sub-game with a fixed role assignment; brains get role-derived rngs."""
    thief_agent = "B" if police_agent == "A" else "A"
    police = specs[police_agent](Role.POLICE, random.Random(f"{seed}:police"), terms)
    thief = specs[thief_agent](Role.THIEF, random.Random(f"{seed}:thief"), terms)
    outcome = play_subgame(police, thief, terms, random.Random(seed),
                           belief_factory=belief_factory)
    winner = None
    if outcome.winner_role is Role.POLICE:
        winner = police_agent
    elif outcome.winner_role is Role.THIEF:
        winner = thief_agent
    return {
        "pair": pair,
        "seed": seed,
        "police": police_agent,
        "thief": thief_agent,
        "result": outcome.result.value,
        "winner_role": None if outcome.winner_role is None else outcome.winner_role.value,
        "winner": winner,
        "steps": outcome.steps,
        "cop_steps": outcome.cop_steps,
        "capture_kind": outcome.capture_kind,
        "trajectory": outcome.trajectory,
    }


def run_match(brain_spec_a: BrainSpec, brain_spec_b: BrainSpec, n_games: int, base_seed: int,
              terms: dict, belief_factory: Any = None) -> list[dict[str, Any]]:
    """``n_games`` paired seeds → ``2 * n_games`` rows (both role assignments per seed).

    Fully deterministic: rerunning with the same arguments reproduces every
    trajectory byte-for-byte (the reproducibility clause of the §6.3 rule).
    """
    specs = {"A": brain_spec_a, "B": brain_spec_b}
    rows: list[dict[str, Any]] = []
    for pair in range(n_games):
        seed = base_seed + pair
        rows.append(_play_one(pair, seed, "A", specs, terms, belief_factory))
        rows.append(_play_one(pair, seed, "B", specs, terms, belief_factory))
    return rows
