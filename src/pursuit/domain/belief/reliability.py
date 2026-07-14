"""The book p.63 hint machinery: Beta-ledger reliability + claim geometry (§2.5).

``ReliabilityLedger`` keeps r_t = alpha/(alpha+beta) per opponent. After each
hint the caller cross-checks words against unfakeable scent
(``BeliefV2.fuse_hint`` returns q_consist — the scent-posterior mass inside
the claimed footprint) and feeds it to ``update``: consistent hints raise
alpha, contradictions raise beta, and the forgetting factor lambda_r <= 1
tracks liars who change policy mid-series. ``injection_detected`` is the
prompt-injection penalty hook — a detected attack burns beta immediately,
without waiting for geometric contradiction. Priors come from config (or a
cross-sub-game profile, STRATEGY §5.5) — nothing is hardcoded.

``hint_footprint`` maps a parsed claim to its geometry mask G_h: a direction
half-plane relative to the opponent-trail centroid (STRATEGY §5.4), an
arena-landmark zone from the config table, or their intersection; anything
unparseable yields the empty set — fusing an uninformative hint is a
structural no-op by construction.
"""

from pursuit.constants import Cell
from pursuit.exceptions import ConfigError

# Direction -> (axis, beyond-centroid sign); row grows south (constants.DIRECTION_DELTAS).
_HALF_PLANES: dict[str, tuple[int, int]] = {
    "N": (0, -1),
    "S": (0, 1),
    "W": (1, -1),
    "E": (1, 1),
}
_REQUIRED = ("hint_alpha0", "hint_beta0", "reliability_forget", "injection_penalty")


class ReliabilityLedger:
    """Beta ledger for one opponent; priors may come from a cross-sub-game profile."""

    def __init__(self, cfg: dict) -> None:
        missing = sorted(key for key in _REQUIRED if key not in cfg)
        if missing:
            raise ConfigError(f"reliability config missing required terms: {missing}")
        alpha0, beta0 = float(cfg["hint_alpha0"]), float(cfg["hint_beta0"])
        forget, penalty = float(cfg["reliability_forget"]), float(cfg["injection_penalty"])
        if alpha0 <= 0.0 or beta0 <= 0.0:
            raise ConfigError(f"Beta priors must be > 0, got alpha0={alpha0!r} beta0={beta0!r}")
        if not 0.0 < forget <= 1.0:
            raise ConfigError(f"reliability_forget must be in (0, 1], got {forget!r}")
        if penalty < 0.0:
            raise ConfigError(f"injection_penalty must be >= 0, got {penalty!r}")
        self._alpha, self._beta = alpha0, beta0
        self._forget, self._penalty = forget, penalty

    def value(self) -> float:
        """r_t = alpha/(alpha+beta) in (0, 1) — the mixture weight fuse_hint consumes."""
        return self._alpha / (self._alpha + self._beta)

    def update(self, consistency: float) -> float:
        """Fold one scent-vs-hint cross-check (q_consist in [0, 1]); returns new r_t."""
        if not 0.0 <= consistency <= 1.0:
            raise ValueError(f"consistency must be in [0, 1], got {consistency!r}")
        self._alpha = self._forget * self._alpha + consistency
        self._beta = self._forget * self._beta + (1.0 - consistency)
        return self.value()

    def injection_detected(self) -> float:
        """Penalty hook: a detected prompt-injection attempt burns beta hard."""
        self._beta += self._penalty
        return self.value()


def trail_centroid(trail: dict[str, float], belief: dict[Cell, float]) -> tuple[float, float]:
    """Intensity-weighted centroid of the opponent trail (belief-weighted when empty)."""
    if trail:
        points = [
            ((int(key.split(",")[0]), int(key.split(",")[1])), value)
            for key, value in trail.items()
        ]
    else:
        points = list(belief.items())
    total = sum(value for _, value in points) or 1.0
    row = sum(cell[0] * value for cell, value in points) / total
    col = sum(cell[1] * value for cell, value in points) / total
    return (row, col)


def hint_footprint(
    claim: dict | None,
    trail: dict[str, float],
    belief: dict[Cell, float],
    board_size: int,
    zones: dict,
) -> set[Cell]:
    """Geometry mask G_h of a parsed hint claim: landmark zone ∩ direction half-plane."""
    if not claim:
        return set()
    cells = {
        (int(row), int(col))
        for row, col in zones.get(claim.get("claimed_zone") or "", ())
        if 0 <= int(row) < board_size and 0 <= int(col) < board_size
    }
    plane = _HALF_PLANES.get(claim.get("claimed_direction") or "")
    if plane is not None:
        axis, sign = plane
        centroid = trail_centroid(trail, belief)
        half = {
            cell
            for cell in ((row, col) for row in range(board_size) for col in range(board_size))
            if (cell[axis] - centroid[axis]) * sign > 0
        }
        cells = (cells & half) if cells else half
    return cells
