"""`ScentModel` — the dialect-agnostic scent field (D3 seam base class).

Every turn an agent leaks a 5x5 "smell" stamp (brief §5). Dialects (book vs
reference, reference_map.md §2.2, §10 landmine 4) subclass this base and differ
ONLY in merge law + decay law; stamp geometry (``params.STAMP_LAW``), wire
serialization, absorption, and the rule-23 worked example all live here.

ROUNDING CONTRACT (wire format, reference_map.md §3.2): ``snapshot()`` emits
sparse ``{"r,c": round(v, 3)}`` (Python half-even rounding), positive cells
only — anything rounding to 0.000 is omitted. Internal state keeps
full-precision floats; only the wire and the lock artifact are rounded.
"""

from abc import ABC, abstractmethod
from dataclasses import asdict, replace
from typing import ClassVar

from pursuit.constants import Cell
from pursuit.domain.scent.params import EXAMPLE_BOARD_SIZE, EXAMPLE_CELL, ScentParams


class ScentModel(ABC):
    """One peer's scent field under a single locked dialect (D3 seam).

    Subclasses supply the dialect id, formula text (the rule-23 lock payload),
    the deposit merge law, and the decay law.
    """

    dialect: ClassVar[str]
    formula: ClassVar[str]

    def __init__(self, params: ScentParams) -> None:
        self.params = params
        self._grid: dict[Cell, float] = {}

    def _in_bounds(self, cell: Cell) -> bool:
        row, col = cell
        return 0 <= row < self.params.board_size and 0 <= col < self.params.board_size

    def emission_stamp(self, center: Cell) -> dict[Cell, float]:
        """Fresh deposit profile around ``center`` (the shared forward law).

        Raises ValueError off-board: that is a caller bug, never game data.
        """
        if not self._in_bounds(center):
            raise ValueError(f"deposit center {center} is outside the board")
        e0 = self.params.emit_intensity
        half = self.params.smell_grid_size // 2
        stamp: dict[Cell, float] = {}
        for d_row in range(-half, half + 1):
            for d_col in range(-half, half + 1):
                cell = (center[0] + d_row, center[1] + d_col)
                ring = max(abs(d_row), abs(d_col))
                value = round(max(0.0, e0 - (e0 / (half + 1)) * ring), 3)
                if self._in_bounds(cell) and value > 0:
                    stamp[cell] = value
        return stamp

    def deposit(self, center: Cell) -> None:
        """Stamp one emission at ``center``, merging per the dialect law."""
        for cell, value in self.emission_stamp(center).items():
            self._grid[cell] = self._merge(self._grid.get(cell, 0.0), value)

    @abstractmethod
    def _merge(self, old: float, new: float) -> float:
        """Dialect merge law: combine an existing value with a fresh stamp cell."""

    @abstractmethod
    def decay(self) -> None:
        """Dialect decay law — called exactly once per full turn (message-driven)."""

    def snapshot(self) -> dict[str, float]:
        """Wire grid ``{"r,c": round(v, 3)}`` — positive cells, row-major key order."""
        rounded = ((cell, round(self._grid[cell], 3)) for cell in sorted(self._grid))
        return {f"{row},{col}": value for (row, col), value in rounded if value > 0}

    def absorb(self, cells: dict[str, float]) -> None:
        """Replace the field with an opponent snapshot (authoritative full trail).

        Replacement, not merging: absorption stays idempotent, so the wire's
        legal duplicate deliveries (reference_map §3) are harmless. Malformed
        keys / off-board cells raise ValueError — that data cannot be honest.
        """
        grid: dict[Cell, float] = {}
        for key, value in cells.items():
            try:
                row_text, col_text = key.split(",")
                cell = (int(row_text), int(col_text))
            except ValueError:
                raise ValueError(f"malformed scent key {key!r} (expected 'r,c')") from None
            if not self._in_bounds(cell):
                n = self.params.board_size
                raise ValueError(f"scent cell {cell} is outside the {n}x{n} board")
            if value > 0:
                grid[cell] = float(value)
        self._grid = grid

    def strongest(self) -> Cell | None:
        """Cell with the highest intensity; ties break row-major; None when empty."""
        if not self._grid:
            return None
        return min(self._grid, key=lambda cell: (-self._grid[cell], cell))

    def worked_example(self) -> dict:
        """Rule-23 lock artifact: fixed 7x7 board, one deposit at (3, 3), one decay.

        Deterministic + dialect-labeled; peers canonical-hash this dict (the
        ``pheromones.formula_sha256`` term) to prove byte-identical scent law
        pre-series (D3). The grid is wire-rounded, so rounding is locked too.
        """
        probe = type(self)(replace(self.params, board_size=EXAMPLE_BOARD_SIZE))
        probe.deposit(EXAMPLE_CELL)
        probe.decay()
        return {
            "dialect": self.dialect,
            "formula": self.formula,
            "rounding": "wire values are round(v, 3) (half-even); 0.000 cells omitted",
            "params": asdict(probe.params),
            "operations": [f"deposit({EXAMPLE_CELL})", "decay()"],
            "grid": probe.snapshot(),
        }
