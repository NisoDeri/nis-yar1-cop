"""Reference scent dialect — byte-faithful to the reference simulator's smell.py.

reference_map.md §2.2: a 5x5 radial emission with falloff ``intensity/(half+1)``
per Chebyshev ring (0.9 / 0.6 / 0.3 at the Table 16 defaults), rounded to 3
decimals, MAX-MERGED into the field (not additive); decay is SUBTRACTIVE,
``max(0, v - rho)`` — NOT the book's multiplicative law. Selected only by
explicit negotiation with a stock-reference partner (ruling A2, DECISIONS.md
D3). Subtractive decay reaches zero exactly, so spent cells simply drop out of
the sparse grid.

Tactical note (STRATEGY.md §2.3): under this dialect a fresh center decayed
once reads 0.800 and no stale cell can exceed 0.700, so ``strongest()`` on an
absorbed snapshot IS the opponent's position — the inversion theorem our belief
engine exploits, and the leak our thief must manage when this dialect is live.
"""

from pursuit.domain.scent.base import ScentModel
from pursuit.domain.scent.params import STAMP_LAW


class ReferenceScent(ScentModel):
    """Max-merge deposit + subtractive decay (the reference simulator's law)."""

    dialect = "reference"
    formula = (
        f"{STAMP_LAW}; deposit: tau <- max(tau, F(d)) [max-merge]; "
        "decay: tau <- max(0, tau - rho), zero cells pruned"
    )

    def _merge(self, old: float, new: float) -> float:
        """Max-merge: a fresh stamp never sums with the trail, only eclipses it."""
        return max(old, new)

    def decay(self) -> None:
        """tau <- max(0, tau - rho); exhausted cells leave the sparse grid."""
        rho = self.params.decay_per_step
        self._grid = {cell: value - rho for cell, value in self._grid.items() if value - rho > 0}
