"""E2 cross-sub-game opponent lie-profiler (CREATIVITY-DESIGN.md E2, STRATEGY §5.5).

Between sub-games there is no turn deadline, so we mine the *revealed* transcript for
the opponent's verbal tells and seed the NEXT sub-game's reliability prior r_0. Pure
Python, zero tokens: every signal comes from the revealed fields ``intent`` (the
mover's own truthful label of THEIR hint), ``hint`` (their words) and
``position``/``state`` (ground truth the liar cannot suppress). Tells: overall
lie-rate, per-direction lie bias (N/S/E/W), truthfulness near barriers, and
phrasing-repetition. ``trust_prior`` is the Beta-posterior mean — a chronic liar
seeds a low r_0, so E1's fusion distrusts them from turn one of the next game. An
optional local-LLM enrichment (phrasing clusters, tone) is a documented TODO; the
graded core stays deterministic and free of any I/O or model.
"""

from __future__ import annotations

import random
import re
from collections import Counter
from typing import Any

from pursuit.exceptions import ConfigError

_DIR_WORDS = {"N": "north", "S": "south", "E": "east", "W": "west"}
_BARRIER_RE = re.compile(r"\[(\d+),\s*(\d+)\]")


def _parse_barriers(state: str) -> list[tuple[int, int]]:
    """Pull barrier cells out of a ``...;barriers=[[r,c],...]`` state string."""
    section = re.search(r"barriers=\[(.*)\]", state)
    if not section:
        return []
    return [(int(r), int(c)) for r, c in _BARRIER_RE.findall(section.group(1))]


def _is_near(position: Any, barriers: list[tuple[int, int]]) -> bool:
    """True when the mover sits within one cell (Chebyshev) of any placed barrier."""
    if not position or len(position) < 2 or not barriers:
        return False
    row, col = int(position[0]), int(position[1])
    return any(abs(row - br) <= 1 and abs(col - bc) <= 1 for br, bc in barriers)


class OpponentProfiler:
    """Accumulates one opponent's verbal tells across sub-games; seeds the next r_0."""

    def __init__(self, cfg: dict, rng: random.Random | None = None) -> None:
        for key in ("hint_alpha0", "hint_beta0", "move_set"):
            if key not in cfg:
                raise ConfigError(f"profiler config missing required term: {key!r}")
        self._alpha0, self._beta0 = float(cfg["hint_alpha0"]), float(cfg["hint_beta0"])
        if self._alpha0 <= 0.0 or self._beta0 <= 0.0:
            raise ConfigError(f"Beta priors must be > 0, got {self._alpha0!r}/{self._beta0!r}")
        self._dirs = {d: w for d, w in _DIR_WORDS.items() if d in cfg["move_set"]}
        # Profiler tuning knobs (statistical, not game terms) — overridable via cfg.
        self._min_samples = int(cfg.get("profile_min_samples", 3))
        self._flag_ratio = float(cfg.get("profile_bias_ratio", 1.25))
        self._flag_floor = float(cfg.get("profile_bias_floor", 0.5))
        self._rng = rng  # injected for any future tie-break; core stays deterministic
        self._truths = self._lies = self._subgames = 0
        self._near_truth = self._near_total = self._far_truth = self._far_total = 0
        self._dir_lies, self._dir_total = Counter(), Counter()
        self._phrases, self._roles = Counter(), Counter()

    def _claimed_direction(self, hint: str) -> str | None:
        """Best-effort direction the hint talks about (full word, then bare letter)."""
        low = hint.lower()
        for direction, word in self._dirs.items():
            if re.search(rf"\b{word}\b", low):
                return direction
        for direction in self._dirs:
            if re.search(rf"\b{direction}\b", hint):
                return direction
        return None

    def ingest_subgame(self, revealed_records: list, opponent_role: str) -> None:
        """Fold one finished game's revealed records (the opponent's own moves)."""
        for record in revealed_records:
            payload = record.get("payload", record)
            intent = payload.get("intent")
            if intent not in ("truth", "lie"):
                continue  # step-0 system rows / unlabelled hints carry no tell
            is_lie = intent == "lie"
            self._lies += is_lie
            self._truths += not is_lie
            self._roles[opponent_role] += 1
            hint = payload.get("hint") or ""
            self._phrases[hint] += 1
            direction = self._claimed_direction(hint)
            if direction is not None:
                self._dir_total[direction] += 1
                self._dir_lies[direction] += is_lie
            barriers = _parse_barriers(payload.get("state") or "")
            if _is_near(payload.get("position"), barriers):
                self._near_total += 1
                self._near_truth += not is_lie
            elif barriers:
                self._far_total += 1
                self._far_truth += not is_lie
        self._subgames += 1

    @property
    def _samples(self) -> int:
        return self._truths + self._lies

    def lie_rate(self) -> float:
        """Fraction of the opponent's own hints they labelled as lies (0 when unseen)."""
        return self._lies / self._samples if self._samples else 0.0

    def per_direction_bias(self) -> dict[str, float]:
        """Per-direction lie-rate over hints that named that direction."""
        return {d: self._dir_lies[d] / n for d, n in self._dir_total.items() if n}

    def flagged_directions(self) -> list[str]:
        """Directions the opponent lies about far more than their baseline."""
        overall = self.lie_rate()
        bias = self.per_direction_bias()
        return sorted(
            d
            for d, rate in bias.items()
            if self._dir_total[d] >= self._min_samples
            and rate >= self._flag_floor
            and rate >= overall * self._flag_ratio
        )

    def trust_prior(self) -> float:
        """Beta-posterior mean r_0 in (0, 1) to seed the next sub-game's ledger."""
        alpha, beta = self._alpha0 + self._truths, self._beta0 + self._lies
        return alpha / (alpha + beta)

    def _rate(self, hits: int, total: int) -> float | None:
        return hits / total if total else None

    def profile(self) -> dict:
        """Deterministic summary dict — seeds E1 and documents the opponent's tells."""
        return {
            "subgames": self._subgames,
            "samples": self._samples,
            "lie_rate": self.lie_rate(),
            "trust_prior": self.trust_prior(),
            "per_direction_bias": self.per_direction_bias(),
            "flagged_directions": self.flagged_directions(),
            "near_barrier_truth_rate": self._rate(self._near_truth, self._near_total),
            "far_barrier_truth_rate": self._rate(self._far_truth, self._far_total),
            "phrasing_repetition_rate": self._rate(
                sum(c - 1 for c in self._phrases.values() if c > 1), self._samples
            ),
            "top_phrase": (self._phrases.most_common(1)[0][0] if self._phrases else None),
            "roles_seen": dict(self._roles),
        }
