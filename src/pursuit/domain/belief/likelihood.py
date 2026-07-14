"""Emission likelihoods for BeliefV2 — the UPDATE step (STRATEGY.md §2.2-2.4).

Forward model: replay the LOCKED scent dialect — the very ``ScentModel`` class
both peers hashed under rule 23 — in the sender's exact order (absorb the
prior trail, deposit at the candidate, decay, wire-round) and score the
observed snapshot by its Gaussian residual. Cells a candidate predicts
fragrant while the wire reads 0.000 carry ``zero_scent_weight`` (lambda_zero
>= 1): zero scent is *negative evidence* (D6) — the brief §5 lie-detection
arithmetic (expected ~0.81 vs measured 0.00) run for every cell, every turn.
``sigma_obs`` absorbs partner rounding drift so a 1-ulp mismatch degrades
gracefully instead of zeroing the filter.

``absolute_*`` is the lost/duplicated-message resync fit (§2.4): the trail is
self-contained, so one clean snapshot restores the filter. It penalizes only
*deficits* against a fresh once-decayed stamp, because stale trail may
lawfully sit on top of the fresh profile — but never below it.
"""

from collections.abc import Iterable

from pursuit.constants import Cell
from pursuit.domain.scent import ScentModel


def parse_wire(model: ScentModel, cells: dict[str, float]) -> dict[str, float]:
    """Validate + normalize an incoming snapshot via the dialect's own absorb.

    Malformed keys / off-board cells raise ValueError (that data cannot be
    honest); non-positive cells drop; values re-round to the wire contract.
    """
    probe = type(model)(model.params)
    probe.absorb(cells)
    return probe.snapshot()


def forward_snapshot(
    model: ScentModel, s_prev: dict[str, float], center: Cell
) -> dict[str, float]:
    """S_hat_c: the snapshot the locked law emits if the opponent stands at ``center``.

    Replays the sender's order — absorb S_{t-1}, deposit, decay, wire-round —
    on a scratch instance of the SAME dialect class, so merge/decay/rounding
    are byte-faithful to the rule-23 lock by construction.
    """
    probe = type(model)(model.params)
    probe.absorb(s_prev)
    probe.deposit(center)
    probe.decay()
    return probe.snapshot()


def residual_log_likelihood(
    observed: dict[str, float],
    predicted: dict[str, float],
    sigma_obs: float,
    zero_scent_weight: float,
) -> float:
    """log L(S_t | x_t=c) = -sum w(d)*(S_t(d)-S_hat_c(d))^2 / (2*sigma^2).

    Support union of both snapshots; w(d) = lambda_zero on cells predicted
    fragrant but observed silent (zero-scent negative evidence), else 1.
    """
    denom = 2.0 * sigma_obs * sigma_obs
    total = 0.0
    for key in observed.keys() | predicted.keys():
        seen, expected = observed.get(key, 0.0), predicted.get(key, 0.0)
        weight = zero_scent_weight if seen == 0.0 and expected > 0.0 else 1.0
        total -= weight * (seen - expected) ** 2 / denom
    return total


def absolute_log_likelihood(
    observed: dict[str, float],
    fresh: dict[str, float],
    sigma_obs: float,
    zero_scent_weight: float,
) -> float:
    """Resync fit: one-sided — penalize only cells reading BELOW a fresh stamp.

    ``fresh`` is the candidate's deposit-then-decay profile from an EMPTY
    trail; observed values above it are stale-trail surplus (lawful under both
    dialects), values below it are impossible at the true cell.
    """
    denom = 2.0 * sigma_obs * sigma_obs
    total = 0.0
    for key, expected in fresh.items():
        seen = observed.get(key, 0.0)
        deficit = expected - seen
        if deficit <= 0.0:
            continue
        weight = zero_scent_weight if seen == 0.0 else 1.0
        total -= weight * deficit**2 / denom
    return total


def scent_log_likelihoods(
    model: ScentModel,
    observed: dict[str, float],
    s_prev: dict[str, float],
    candidates: Iterable[Cell],
    sigma_obs: float,
    zero_scent_weight: float,
) -> dict[Cell, float]:
    """log L per candidate cell — the emission-profile inversion of §2.4."""
    return {
        cell: residual_log_likelihood(
            observed, forward_snapshot(model, s_prev, cell), sigma_obs, zero_scent_weight
        )
        for cell in candidates
    }


def absolute_log_likelihoods(
    model: ScentModel,
    observed: dict[str, float],
    candidates: Iterable[Cell],
    sigma_obs: float,
    zero_scent_weight: float,
) -> dict[Cell, float]:
    """Resync scores: each candidate vs a fresh once-decayed stamp, deficits only."""
    return {
        cell: absolute_log_likelihood(
            observed, forward_snapshot(model, {}, cell), sigma_obs, zero_scent_weight
        )
        for cell in candidates
    }
