"""Signed pheromone terms + the rule-23 lock vocabulary shared by all dialects.

The scent trail is the only unfakeable evidence channel (brief §5), so its
arithmetic is LOCKED per series under rule 23: formula text + numeric worked
example + SHA-256 (DECISIONS.md D3). This module owns the pieces of that lock
common to both dialects — the validated parameter block (Appendix F Table 16),
the shared stamp-law text, and the fixed worked-example scenario.

Shared stamp law (STRATEGY.md §2.2, identical in both dialects)::

    F_x(d) = round(max(0, E0 - (E0 / (half + 1)) * cheb(x, d)), 3)

for in-bounds cells with cheb(x, d) <= half — at the Table 16 defaults
(E0=0.9, 5x5 window) that is the reference's documented 0.9/0.6/0.3 ring
profile (reference_map.md §2.2). Every value below arrives via the signed
shared config: zero hardcoded game parameters. The reference's anti-decoy floor
(deposit rejects intensity < min_center_intensity) is enforced at construction,
because here the emission intensity is itself a config term, not an argument.
"""

from dataclasses import dataclass

from pursuit.constants import Cell
from pursuit.exceptions import ConfigError

# Rule-23 lock fixture (NOT game parameters): every worked example runs this one
# fixed scenario so two peers can diff and hash the artifact byte-for-byte.
EXAMPLE_BOARD_SIZE = 7
EXAMPLE_CELL: Cell = (3, 3)

STAMP_LAW = (
    "F(d) = round(max(0, E0 - (E0 / (half + 1)) * cheb(center, d)), 3) "
    "for cheb(center, d) <= half and in-bounds; half = smell_grid_size // 2"
)


@dataclass(frozen=True)
class ScentParams:
    """Signed pheromone terms (Appendix F Table 16) — validated fail-fast."""

    board_size: int
    smell_grid_size: int
    emit_intensity: float
    decay_per_step: float
    min_center_intensity: float

    def __post_init__(self) -> None:
        for name in ("emit_intensity", "decay_per_step", "min_center_intensity"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int | float):
                raise ConfigError(f"{name} must be a number, got {value!r}")
        if not isinstance(self.board_size, int) or self.board_size < 1:
            raise ConfigError(f"board_size must be a positive int, got {self.board_size!r}")
        size = self.smell_grid_size
        if not isinstance(size, int) or size < 1 or size % 2 == 0:
            raise ConfigError(f"smell_grid_size must be a positive odd int, got {size!r}")
        if not 0.0 <= self.decay_per_step <= 1.0:
            raise ConfigError(f"decay_per_step must be in [0, 1], got {self.decay_per_step!r}")
        if self.emit_intensity <= 0:
            raise ConfigError(f"emit_intensity must be > 0, got {self.emit_intensity!r}")
        if self.emit_intensity < self.min_center_intensity:
            raise ConfigError(
                f"emit_intensity {self.emit_intensity!r} is below min_center_intensity "
                f"{self.min_center_intensity!r} — anti-decoy floor (reference_map §2.2)"
            )
