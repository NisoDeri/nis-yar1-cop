"""BeliefV2 — recursive Bayes filter over the opponent position (STRATEGY.md §2, D6).

Superset of the reference ``BeliefGrid`` surface (``most_likely / as_matrix /
exclude / diffuse / observe_smell``) so brains duck-type either implementation;
v2 adds ``fuse_hint / note_barrier / most_likely_p / entropy``. Turn order at
the TurnHandler seam: predict -> update -> fuse -> mask. Every number arrives
via ``cfg`` / the signed pheromones terms; never-NaN lives in ``_renormalize``.
"""

import math

from pursuit.constants import Cell, Role
from pursuit.domain.belief.kernel import apply_kernel
from pursuit.domain.belief.likelihood import (
    absolute_log_likelihoods,
    parse_wire,
    scent_log_likelihoods,
)
from pursuit.domain.belief.reliability import hint_footprint
from pursuit.domain.board import Board
from pursuit.domain.scent import ScentModel, make_scent_model
from pursuit.exceptions import ConfigError

_REQUIRED = (
    "move_set", "sigma_obs", "zero_scent_weight", "resync_floor", "motion_eta_thief",
    "motion_eta_police", "kernel_mobility_mu", "kernel_mobility_k", "lie_inversion",
    "lie_inversion_below")


class BeliefV2:
    """Probability grid over the opponent position under the LOCKED scent dialect."""

    def __init__(self, board_size: int, cfg: dict, scent_params: dict | ScentModel) -> None:
        missing = sorted(key for key in _REQUIRED if key not in cfg)
        if missing:
            raise ConfigError(f"belief config missing required terms: {missing}")
        if not cfg["resync_floor"] > 0:
            raise ConfigError(f"resync_floor must be > 0, got {cfg['resync_floor']!r}")
        self._cfg = cfg
        self._board = Board(board_size, list(cfg["move_set"]))
        self._scent = (
            scent_params if isinstance(scent_params, ScentModel) else make_scent_model(scent_params)
        )
        scent_n = self._scent.params.board_size
        if scent_n != board_size:
            raise ConfigError(f"scent board_size {scent_n} != belief board_size {board_size}")
        self._cells = tuple((r, c) for r in range(board_size) for c in range(board_size))
        self._belief: dict[Cell, float] = dict.fromkeys(self._cells, 1.0 / len(self._cells))
        self._barriers: set[Cell] = set()
        self._s_prev: dict[str, float] = {}

    # ---- reference-compatible surface (reference_map §4.1) ----
    def most_likely(self) -> Cell:
        """Argmax cell; ties break row-major (matches ScentModel.strongest)."""
        return min(self._belief, key=lambda cell: (-self._belief[cell], cell))

    def most_likely_p(self) -> float:
        """Posterior mass at the argmax — drives pounce/finisher thresholds (§3.3/§3.6)."""
        return max(self._belief.values())

    def as_matrix(self) -> list[list[float]]:
        n = self._board.size
        return [[self._belief[(row, col)] for col in range(n)] for row in range(n)]

    def entropy(self) -> float:
        """Shannon entropy in bits — the §3.4 information-gathering trigger."""
        return -sum(p * math.log2(p) for p in self._belief.values() if p > 0.0)

    def exclude(self, cell: Cell) -> None:
        """Hard-zero one cell (e.g. our own — we would see the opponent here)."""
        self._belief[cell] = 0.0
        self._renormalize()

    def diffuse(self, opponent_role: Role | str, reference: Cell | None = None) -> None:
        """PREDICT via the role-conditioned kernel (§2.4); eta=0 = reference diffuse.

        ``reference`` defaults to the current argmax; brains pass their own
        position explicitly when known (the opponent flees/chases *us*)."""
        role = Role(opponent_role)
        eta = self._cfg["motion_eta_thief" if role is Role.THIEF else "motion_eta_police"]
        anchor = reference if reference is not None else self.most_likely()
        self._belief = apply_kernel(
            self._board, self._barriers, self._belief, anchor, role, eta,
            self._cfg["kernel_mobility_mu"], self._cfg["kernel_mobility_k"],
        )
        self._renormalize()

    def observe_smell(self, cells: dict[str, float]) -> None:
        """UPDATE: emission-profile inversion + zero-scent negative evidence (§2.4).

        If no candidate explains the snapshot (lost/duplicated message), refit
        from the absolute snapshot alone — the trail is self-contained."""
        observed = parse_wire(self._scent, cells)
        candidates = [cell for cell in self._cells if cell not in self._barriers]
        sigma, lam = self._cfg["sigma_obs"], self._cfg["zero_scent_weight"]
        lls = scent_log_likelihoods(self._scent, observed, self._s_prev, candidates, sigma, lam)
        if max(lls.values()) < math.log(self._cfg["resync_floor"]):
            lls = absolute_log_likelihoods(self._scent, observed, candidates, sigma, lam)
            # Resync: drop the stale prior, refit from the snapshot alone.
            self._belief = {cell: float(cell not in self._barriers) for cell in self._cells}
        top = max(lls.values())
        for cell, ll in lls.items():
            self._belief[cell] *= math.exp(ll - top)
        self._s_prev = observed
        self._renormalize()

    # ---- v2 extensions (same handler seam) ----
    def note_barrier(self, cell: Cell) -> None:
        """Mask a declared barrier (truthful by rule 14) out of the posterior."""
        self._barriers.add(cell)
        self._renormalize()

    def fuse_hint(self, claim: dict | None, reliability: float) -> float | None:
        """FUSE: mixture likelihood L_h = r*g_h + (1-r)*q (§2.5, book p.63).

        Returns q_consist = scent-posterior mass inside G_h (feed it to
        ``ReliabilityLedger.update``); None when the claim has no geometry
        (a structural no-op). Lie-inversion (config-gated) turns a caught
        liar's words into negative evidence."""
        footprint = hint_footprint(
            claim, self._s_prev, self._belief, self._board.size, self._cfg.get("zones", {})
        ) - self._barriers
        if not footprint:
            return None
        consistency = min(1.0, sum(self._belief[cell] for cell in footprint))
        confidence = claim.get("confidence")
        weight = min(1.0, max(0.0, reliability * (1.0 if confidence is None else confidence)))
        n2 = len(self._cells)
        invert = (self._cfg["lie_inversion"] and len(footprint) < n2
                  and reliability < self._cfg["lie_inversion_below"])
        inside, base_q = 1.0 / len(footprint), 1.0 / n2
        inverted_q = 1.0 / (n2 - len(footprint)) if invert else 0.0
        for cell in self._cells:
            in_g = cell in footprint
            q = (0.0 if in_g else inverted_q) if invert else base_q
            self._belief[cell] *= weight * (inside if in_g else 0.0) + (1.0 - weight) * q
        self._renormalize()
        return consistency

    def _renormalize(self) -> None:
        """Mask barriers; never-NaN: degenerate totals reset to uniform over free cells."""
        for cell in self._barriers:
            self._belief[cell] = 0.0
        total = sum(self._belief.values())
        if not math.isfinite(total) or total <= 0.0:
            free = [cell for cell in self._cells if cell not in self._barriers] or list(self._cells)
            self._belief = dict.fromkeys(self._cells, 0.0)
            self._belief.update(dict.fromkeys(free, 1.0 / len(free)))
            return
        self._belief = {cell: value / total for cell, value in self._belief.items()}
