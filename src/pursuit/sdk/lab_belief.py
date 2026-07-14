"""BeliefV2 factory for the self-play lab — the real recursive-Bayes filter (D6).

Builds a :class:`BeliefV2` straight from the signed terms (board size, move_set,
pheromones) plus the belief defaults that mirror ``config/police/game.toml``
``[belief]``, then seeds it with the opponent's start cell — the same prior the
crude :class:`ScentBelief` stand-in carries — so even the very first decision has
real evidence. Construction is deliberately total-facing: any failure surfaces as
an exception the lab catches and downgrades to ScentBelief, never a crash.
"""

from __future__ import annotations

from typing import Any

from pursuit.constants import Role
from pursuit.domain.belief.engine import BeliefV2
from pursuit.domain.scent import make_scent_model

#: Belief defaults mirroring config/police/game.toml [belief] (STRATEGY.md §2, D6).
_BELIEF_DEFAULTS: dict[str, Any] = {
    "sigma_obs": 0.1,
    "zero_scent_weight": 0.6,
    "resync_floor": 1e-8,
    "motion_eta_thief": 2.0,
    "motion_eta_police": 1.5,
    "kernel_mobility_mu": 0.6,
    "kernel_mobility_k": 3,
    "lie_inversion": True,
    "lie_inversion_below": 0.3,
}


class _V2Adapter:
    """Bridge BeliefV2 onto the arena's belief seam (STRATEGY.md §2 turn order).

    The arena calls ``belief.diffuse()`` with no argument, but BeliefV2 needs the
    tracked opponent's role to pick its motion kernel — so we bind it here (the
    holder tracks its *opponent*). Every other call delegates unchanged, so the v1
    brains keep reading ``most_likely`` / ``most_likely_p`` off the real posterior.
    """

    def __init__(self, belief: BeliefV2, opponent_role: Role) -> None:
        self._belief = belief
        self._opponent_role = opponent_role

    def diffuse(self, *args: Any, **kwargs: Any) -> None:
        if args or kwargs:
            self._belief.diffuse(*args, **kwargs)
        else:
            self._belief.diffuse(self._opponent_role)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._belief, name)


def _scent_cfg(terms: dict[str, Any], board_size: int) -> dict[str, Any]:
    """Adapt the signed ``pheromones`` block to the ScentParams vocabulary."""
    pheromones = terms["pheromones"]
    return {
        "dialect": pheromones["dialect"],
        "board_size": board_size,
        "smell_grid_size": int(pheromones["pheromone_grid_size"]),
        "emit_intensity": float(pheromones["pheromone_center_intensity"]),
        "decay_per_step": float(pheromones["pheromone_decay"]),
        "min_center_intensity": float(pheromones["pheromone_min_center_intensity"]),
    }


def belief_v2_factory(role: Role, terms: dict[str, Any]) -> _V2Adapter:
    """``factory(role, terms) -> belief`` seeded on the opponent's start cell.

    Every number is read from the signed terms (grid size, move_set, pheromones)
    or the mirrored ``[belief]`` defaults — zero hardcoded game parameters. The
    seed is applied through the real UPDATE pipeline: a synthetic scent stamp at
    the opponent's start cell, absorbed via ``observe_smell`` so the posterior
    peaks there exactly as ScentBelief's mode does.
    """
    agents = terms["board_and_agents"]
    board_size = int(agents["grid_size"])
    cfg = {"move_set": list(terms["movement_and_barriers"]["move_set"]), **_BELIEF_DEFAULTS}
    scent_cfg = _scent_cfg(terms, board_size)
    belief = BeliefV2(board_size, cfg, scent_cfg)
    start = agents["thief_start"] if role is Role.POLICE else agents["cop_start"]
    seed_model = make_scent_model(scent_cfg)
    seed_model.deposit((int(start[0]), int(start[1])))
    belief.observe_smell(seed_model.snapshot())
    return _V2Adapter(belief, role.opponent)
