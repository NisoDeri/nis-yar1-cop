"""Outcome → points, straight from the signed scoring config (Appendix F Table 17).

Table 17 fixes the values — capture 20/5 (cop/thief), survival 5/10, series tie 2 each,
technical loss 0/0 — but this module never hardcodes them: every number arrives via the
scoring block of the negotiated ``game.json`` (D4 "zero hardcoded parameters"; the fixed-value
assertion against Appendix F happens once at config load in ``shared/shared_terms.py``).

Technical-loss semantics (rulings A6 / A9a): timeout, crash, audit-caught forgery, an unknown
result string, AND a result row whose claimed ``winner_role`` contradicts the outcome (a forged
row) all score ``technical_loss`` to BOTH sides — never waiting-peer-wins, never
cheater-keeps-points. The series tie bonus is additive: on an equal cumulative series score
every tied side gains ``tie_score`` (2-group series in league play).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any, TypeVar

from pursuit.constants import GameResult, Role
from pursuit.exceptions import ConfigError

K = TypeVar("K")  # series rows may be keyed by Role (one sub-game) or group_id (a series)

_REQUIRED_KEYS = (
    "capture_cop",
    "capture_thief",
    "survival_cop",
    "survival_thief",
    "technical_loss",
    "tie_score",
)


class ScoreTable:
    """Pure points table bound to one signed scoring config dict (Table 17 keys)."""

    def __init__(self, scoring: Mapping[str, Any]) -> None:
        missing = [key for key in _REQUIRED_KEYS if key not in scoring]
        if missing:
            raise ConfigError(f"scoring config missing keys: {missing}")
        for key in _REQUIRED_KEYS:
            value = scoring[key]
            if isinstance(value, bool) or not isinstance(value, int):
                raise ConfigError(f"scoring[{key!r}] must be an int, got {value!r}")
        self._cfg: dict[str, int] = {key: scoring[key] for key in _REQUIRED_KEYS}

    def score_subgame(
        self, result: GameResult | str, winner_role: Role | None
    ) -> dict[Role, int]:
        """Points for one sub-game; anything inconsistent degrades to technical 0/0 (A9a)."""
        if result == GameResult.CAPTURE and winner_role == Role.POLICE:
            return {
                Role.POLICE: self._cfg["capture_cop"],
                Role.THIEF: self._cfg["capture_thief"],
            }
        if result == GameResult.SURVIVAL and winner_role == Role.THIEF:
            return {
                Role.POLICE: self._cfg["survival_cop"],
                Role.THIEF: self._cfg["survival_thief"],
            }
        # technical_loss, stopped, unknown result strings, and forged winner claims (A6/A9a).
        technical = self._cfg["technical_loss"]
        return {Role.POLICE: technical, Role.THIEF: technical}

    def series_totals(self, rows: Iterable[Mapping[K, int]]) -> dict[str, Any]:
        """Additive series aggregate with tie detection (+``tie_score`` each on a tie)."""
        totals: dict[K, int] = {}
        for row in rows:
            for key, points in row.items():
                totals[key] = totals.get(key, 0) + points
        winner: K | None = None
        tie = False
        if totals:
            top = max(totals.values())
            leaders = [key for key, total in totals.items() if total == top]
            if len(leaders) == 1:
                winner = leaders[0]
            else:
                tie = True
                for key in leaders:
                    totals[key] += self._cfg["tie_score"]
        return {"totals": totals, "tie": tie, "winner": winner}
