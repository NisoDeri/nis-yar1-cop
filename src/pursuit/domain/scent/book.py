"""Book scent dialect — additive deposit, multiplicative decay (the DEFAULT).

The book law (brief §5; NotebookLM ruling A2, DECISIONS.md D3)::

    tau(t+1) = max(0, (1 - rho) * tau(t) + delta_tau)

``delta_tau`` is the shared stamp profile ADDED into the field, and the sum is
clamped AFTER the add at the center intensity E0 (clamp-after-add). That clamp
makes two overlapping fresh stamps saturate a *plateau* of cells at E0 — the
"cap-plateau" effect (STRATEGY.md §2.3) that breaks argmax uniqueness, which is
exactly why rule 23 forces the dialect choice into the hashed lock: under the
reference dialect the strongest cell decodes the opponent position, under this
one it need not.

Multiplicative decay never reaches zero exactly, so cells that can no longer
serialize above 0.000 (``round(v, 3) <= 0``) are pruned from the sparse grid —
a documented clause of the locked formula text below.
"""

from pursuit.domain.scent.base import ScentModel
from pursuit.domain.scent.params import STAMP_LAW


class BookScent(ScentModel):
    """Additive deposit + multiplicative decay, clamped after add at E0."""

    dialect = "book"
    formula = (
        f"{STAMP_LAW}; deposit: tau <- min(E0, tau + F(d)) [clamp-after-add, cap-plateau]; "
        "decay: tau <- (1 - rho) * tau, cells with round(tau, 3) <= 0 pruned"
    )

    def _merge(self, old: float, new: float) -> float:
        """tau + delta_tau, clamped after the add at the configured E0 cap."""
        return min(self.params.emit_intensity, old + new)

    def decay(self) -> None:
        """tau <- (1 - rho) * tau; sub-wire residues (round to 0.000) pruned."""
        keep = 1.0 - self.params.decay_per_step
        decayed = {cell: value * keep for cell, value in self._grid.items()}
        self._grid = {cell: value for cell, value in decayed.items() if round(value, 3) > 0}
