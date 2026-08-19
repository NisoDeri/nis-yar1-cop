"""``multiplicative_book_v1`` — the book ch.4 / figure-4 scent model (kit PROMOTED).

Byte-faithful to the league conformance kit's ``vectors/scent_book_v3.json``
(contributed + clean-room validated by anrbj666): a verbatim 5x5 figure-4
Gaussian kernel, multiplicative decay, clamp-after-add at E0, **decay-then-deposit**
once per full turn, and NO wire rounding (``rounding_decimals: null``), from an
empty start. Distinct from the ``book`` dialect, which is a Chebyshev falloff —
this one pins the printed Gaussian kernel the league locks under rule 23.

Update law, per full turn (kit ``model.update``)::

    tau' = clamp((1 - rho) * tau + kernel_delta, 0, E0)   # (1-rho)*tau + delta, THEN clamp

realized as :meth:`decay` (``(1-rho)*tau``) then :meth:`deposit` (``min(E0, tau+delta)``,
clamp-after-add) in :meth:`full_turn` — the pinned evaluation order, bit-for-bit.
"""

from pursuit.constants import Cell
from pursuit.domain.scent.base import ScentModel
from pursuit.domain.scent.params import ScentParams
from pursuit.exceptions import ConfigError

#: The book figure-4 kernel is pinned verbatim at centre 0.9 (kit center_intensity), so this
#: dialect is only self-consistent at E0 == 0.9 — clamp-after-add uses E0, and a different E0
#: would silently distort the pinned kernel and diverge byte-for-byte from a conforming partner.
_PINNED_CENTRE = 0.9

# book v3.0.0 figure 4 — printed values, verbatim lookup (kit scent_book_v3.json).
# Indexed [dr + 2][dc + 2] for offset (dr, dc) in [-2, 2]^2 from the emitter cell.
_KERNEL: tuple[tuple[float, ...], ...] = (
    (0.04, 0.14, 0.20, 0.14, 0.04),
    (0.14, 0.42, 0.62, 0.42, 0.14),
    (0.20, 0.62, 0.90, 0.62, 0.20),
    (0.14, 0.42, 0.62, 0.42, 0.14),
    (0.04, 0.14, 0.20, 0.14, 0.04),
)


class MultiplicativeBookV1Scent(ScentModel):
    """Figure-4 Gaussian kernel, multiplicative decay, decay-then-deposit, unrounded wire."""

    dialect = "multiplicative_book_v1"
    formula = (
        "kernel: book v3.0.0 figure 4 verbatim 5x5 (centre 0.9); per full turn "
        "tau' = clamp((1 - rho) * tau + kernel_delta, 0, E0), evaluation (1-rho)*tau + delta "
        "then clamp; order decay_then_deposit; no wire rounding"
    )

    def __init__(self, params: ScentParams) -> None:
        super().__init__(params)
        if params.emit_intensity != _PINNED_CENTRE:
            raise ConfigError(
                "multiplicative_book_v1 pins the book figure-4 kernel at centre "
                f"{_PINNED_CENTRE} (kit scent_book_v3.json); pheromones.pheromone_center_intensity "
                f"must be {_PINNED_CENTRE}, got {params.emit_intensity!r}")

    def emission_stamp(self, center: Cell) -> dict[Cell, float]:
        """The pinned figure-4 kernel around ``center``, clipped to the board bounds."""
        if not self._in_bounds(center):
            raise ValueError(f"deposit center {center} is outside the board")
        stamp: dict[Cell, float] = {}
        for d_row in range(-2, 3):
            for d_col in range(-2, 3):
                value = _KERNEL[d_row + 2][d_col + 2]
                cell = (center[0] + d_row, center[1] + d_col)
                if value > 0.0 and self._in_bounds(cell):
                    stamp[cell] = value
        return stamp

    def _merge(self, old: float, new: float) -> float:
        """Additive deposit, clamped AFTER the add at E0 (clamp-after-add)."""
        return min(self.params.emit_intensity, old + new)

    def decay(self) -> None:
        """tau <- (1 - rho) * tau; strictly-positive cells kept (no rounding, no prune floor)."""
        keep = 1.0 - self.params.decay_per_step
        self._grid = {cell: value * keep for cell, value in self._grid.items()
                      if value * keep > 0.0}

    def full_turn(self, center: Cell) -> None:
        """Decay THEN deposit — the book's pinned per-full-turn evaluation order."""
        self.decay()
        self.deposit(center)

    def snapshot(self) -> dict[str, float]:
        """Unrounded wire grid ``{"r,c": tau}`` (rounding_decimals is null), positive cells."""
        return {f"{row},{col}": self._grid[(row, col)]
                for (row, col) in sorted(self._grid) if self._grid[(row, col)] > 0.0}
