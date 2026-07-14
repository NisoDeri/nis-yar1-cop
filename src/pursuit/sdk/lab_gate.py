"""SDK gateway into the simulation lab (D7) — keeps the Table-5 gate airtight.

The CLI never imports :mod:`pursuit.lab` or :mod:`pursuit.strategy` directly; the
``lab`` subcommand routes through :func:`run_lab` here, so the SDK remains the single
entry for every way to play. Brains are selected by ``'module:Class'`` (the same
``[strategy]`` selector grammar as game.toml) and adapted onto the lab's view seam;
terms come from the signed game.json of ``config_dir`` — zero hardcoded parameters.
:func:`run_lab_versus` extends this to a real agent-vs-agent series (A's brain-set
against B's), and belief is the real :class:`BeliefV2` filter (ScentBelief fallback).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pursuit.constants import DIRECTION_DELTAS, MoveType, Role
from pursuit.lab.arena import LabDecision
from pursuit.lab.runner import run_match
from pursuit.lab.stats import a_beats_b_p_value, points_per_scoring_table, win_rate
from pursuit.sdk.lab_belief import belief_v2_factory
from pursuit.sdk.series import ScentBelief
from pursuit.shared.config import ConfigManager
from pursuit.strategy.resolve import load_brain_cls
from pursuit.strategy.talk import TemplateTalk

_TERMS_BLOCKS = ("board_and_agents", "movement_and_barriers", "scoring", "pheromones")


class _LabBrain:
    """Adapt a BrainBase brain onto the lab's view seam (LabView -> LabDecision)."""

    def __init__(self, brain: Any, barriers_max: int) -> None:
        self.brain, self.barriers_max = brain, int(barriers_max)

    def decide(self, view: Any) -> LabDecision:
        decision = self.brain.decide(view.state, view.belief, view.opponent_hint or "",
                                     "", self.barriers_max, None)
        if decision.move_type is MoveType.BARRIER:
            delta = DIRECTION_DELTAS[decision.direction]
            position = view.state.position
            return LabDecision(MoveType.BARRIER, hint=decision.hint,
                               barrier_cell=(position[0] + delta[0], position[1] + delta[1]))
        return LabDecision(decision.move_type, direction=decision.direction,
                           hint=decision.hint)


def _belief_factory(role: Role, terms: dict[str, Any]) -> ScentBelief:
    """Crude wire-mode fallback belief seeded on the opponent's start cell."""
    agents = terms["board_and_agents"]
    start = agents["thief_start"] if role is Role.POLICE else agents["cop_start"]
    return ScentBelief(tuple(start))


def _belief_or_scent(role: Role, terms: dict[str, Any]) -> Any:
    """Real BeliefV2 when it constructs; never crash the lab — fall back to ScentBelief."""
    try:
        return belief_v2_factory(role, terms)
    except Exception:
        return _belief_factory(role, terms)


def _load(config_dir: str | Path) -> tuple[dict[str, Any], str, int, int]:
    """Signed terms + world settings from ``config_dir`` — zero hardcoded parameters."""
    config = ConfigManager.load(config_dir)
    config.validate_agreement()
    terms = {block: config.game(block) for block in _TERMS_BLOCKS}
    setting = str(config.game("world.map_area"))
    hint_cap = int(config.game("world.hint_max_words"))
    barriers_max = int(terms["movement_and_barriers"]["max_barriers"])
    return terms, setting, hint_cap, barriers_max


def _spec_for(classes: dict[Role, Any], setting: str, hint_cap: int, barriers_max: int) -> Any:
    """A per-game brain spec: build the role's class fresh with its role-derived rng."""
    def spec(role: Any, rng: Any, _terms: dict) -> _LabBrain:
        talk = TemplateTalk(rng, setting, hint_cap)
        return _LabBrain(classes[Role(role)](talk, rng), barriers_max)
    return spec


def _summary(rows: list[dict[str, Any]], terms: dict[str, Any]) -> dict[str, Any]:
    return {"games": len(rows), "win_rate_A": win_rate(rows),
            "p_value_A": a_beats_b_p_value(rows),
            "points": points_per_scoring_table(rows, terms["scoring"])}


def run_lab(games: int, seed: int, police: str, thief: str,
            config_dir: str | Path) -> dict[str, Any]:
    """Paired-seed self-play match: ``games`` seeds x both role assignments (§6.3).

    ``police``/``thief`` are ``'module:Class'`` BrainBase selectors; agent A plays the
    named class for whichever role it draws, so the promotion stats stay role-balanced.
    Belief is the real :class:`BeliefV2` filter (ScentBelief fallback if it can't build).
    """
    terms, setting, hint_cap, barriers_max = _load(config_dir)
    classes = {Role.POLICE: load_brain_cls(police), Role.THIEF: load_brain_cls(thief)}
    spec = _spec_for(classes, setting, hint_cap, barriers_max)
    rows = run_match(spec, spec, int(games), int(seed), terms, belief_factory=_belief_or_scent)
    return _summary(rows, terms)


def run_lab_versus(games: int, seed: int, police_a: str, thief_a: str, police_b: str,
                   thief_b: str, config_dir: str | Path,
                   use_belief_v2: bool = True) -> dict[str, Any]:
    """Agent-vs-agent series: A's brain-set (``police_a``/``thief_a``) against B's.

    Each seed is played twice with the roles swapped, so ``win_rate_A``/``p_value_A``
    measure A's brains against B's on identical boards. Belief is the real BeliefV2
    filter unless ``use_belief_v2`` is off, in which case the ScentBelief stand-in runs.
    """
    terms, setting, hint_cap, barriers_max = _load(config_dir)
    classes_a = {Role.POLICE: load_brain_cls(police_a), Role.THIEF: load_brain_cls(thief_a)}
    classes_b = {Role.POLICE: load_brain_cls(police_b), Role.THIEF: load_brain_cls(thief_b)}
    spec_a = _spec_for(classes_a, setting, hint_cap, barriers_max)
    spec_b = _spec_for(classes_b, setting, hint_cap, barriers_max)
    factory = _belief_or_scent if use_belief_v2 else _belief_factory
    rows = run_match(spec_a, spec_b, int(games), int(seed), terms, belief_factory=factory)
    return _summary(rows, terms)
