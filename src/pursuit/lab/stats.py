"""Lab statistics — win rates, league points, exact binomial promotion test (§6.3).

"Nothing ships on vibes": a candidate brain beats the incumbent only when the
one-sided exact binomial tail over the decisive paired games clears the
promotion alpha. Pure python (``math.comb``) — no scipy, no network, no rng.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from typing import Any

from pursuit.domain.scoring import ScoreTable

Row = Mapping[str, Any]

_COLUMNS = ("pair", "seed", "police", "thief", "result", "winner", "steps", "capture_kind")


def decisive_wins(rows: Iterable[Row], agent: str = "A") -> tuple[int, int]:
    """``(wins, decisive)`` for ``agent`` — undecided rows dropped (§6.3 tie rule)."""
    decided = [row for row in rows if row.get("winner") is not None]
    wins = sum(1 for row in decided if row["winner"] == agent)
    return wins, len(decided)


def win_rate(rows: Iterable[Row], agent: str = "A") -> float:
    """Fraction of decisive games won by ``agent``; 0.0 when nothing was decisive."""
    wins, decisive = decisive_wins(rows, agent)
    return wins / decisive if decisive else 0.0


def points_per_scoring_table(rows: Iterable[Row], scoring: Mapping[str, int]) -> dict[str, int]:
    """League points per agent, straight from the signed scoring terms (Table 17).

    Reuses :class:`ScoreTable` — the same code that scores real sub-games — so
    lab points can never drift from league points.
    """
    table = ScoreTable(scoring)
    totals: dict[str, int] = {}
    for row in rows:
        for role, points in table.score_subgame(row["result"], row["winner_role"]).items():
            agent = row[role.value]  # row["police"] / row["thief"] name the agent
            totals[agent] = totals.get(agent, 0) + points
    return totals


def binomial_p_value(wins: int, n: int, p: float = 0.5) -> float:
    """One-sided exact binomial tail ``P(W >= wins | n, p)`` — pure python.

    The §6.3 promotion test: 60 wins of 100 decisive vs p=0.5 → ~0.028 < 0.05.
    ``n = 0`` returns 1.0 (no evidence is never significant).
    """
    if n < 0 or not 0 <= wins <= n:
        raise ValueError(f"need 0 <= wins <= n, got wins={wins}, n={n}")
    if not 0.0 <= p <= 1.0:
        raise ValueError(f"p must be a probability, got {p!r}")
    tail = sum(math.comb(n, k) * p**k * (1.0 - p) ** (n - k) for k in range(wins, n + 1))
    return min(1.0, tail)  # guard float summation drift above exactly 1


def a_beats_b_p_value(rows: Iterable[Row], p: float = 0.5) -> float:
    """Promotion-rule p-value that agent A beats agent B over a run_match series."""
    wins, decisive = decisive_wins(rows, "A")
    return binomial_p_value(wins, decisive, p)


def format_table(rows: Iterable[Row]) -> str:
    """Per-game rows as a markdown table — the body of every D7 lab artifact."""
    lines = [
        "| " + " | ".join(_COLUMNS) + " |",
        "| " + " | ".join("---" for _ in _COLUMNS) + " |",
    ]
    for row in rows:
        cells = ("" if row.get(col) is None else str(row[col]) for col in _COLUMNS)
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)
