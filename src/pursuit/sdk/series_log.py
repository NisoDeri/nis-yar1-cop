"""Log/document emission helpers for the series driver (arch §sdk).

The MINIMAL writer surface pulled out of :mod:`pursuit.sdk.series`: the report-row
shape (:func:`sub_row`), the replayable sealed per-sub-game log document
(:func:`log_document`) and the JSON sink (:func:`write_json`). Kept pure — no game
parameters are hardcoded here; everything is derived from the passed ``outcome``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pursuit.constants import Role
from pursuit.peer.audit import SubgameOutcome
from pursuit.strategy.profiler import OpponentProfiler


class LieProfiler:
    """E2 cross-sub-game lie-profiler bridge — LOW-RISK, gated, and non-fatal by design.

    Off unless private ``strategy.profile_opponent`` is truthy; ``None`` on ANY build error.
    :meth:`observe` folds each finished sub-game's revealed opponent records (read defensively
    from ``outcome.audit['their_records']``) and exposes :attr:`prior` — the Beta-posterior r_0
    the NEXT sub-game's belief seeds via :meth:`belief_cfg`. Every step is wrapped so a bad
    transcript can never crash the series (STRATEGY §5.5, CREATIVITY-DESIGN E2).
    """

    def __init__(self, config: Any) -> None:
        self.prior: float | None = None
        self._profiler = self._build(config)

    @staticmethod
    def _build(config: Any) -> OpponentProfiler | None:
        try:
            if not bool(config.private("strategy.profile_opponent")):
                return None
            belief = config.private("belief")
            r0 = float(belief.get("hint_trust_prior", 0.5))
            strength = float(belief.get("hint_prior_strength", 2.0))
            moves = list(config.game("movement_and_barriers.move_set"))
            return OpponentProfiler({"hint_alpha0": max(1e-6, r0 * strength),
                                     "hint_beta0": max(1e-6, (1.0 - r0) * strength),
                                     "move_set": moves})
        except Exception:  # noqa: BLE001 — a best-effort creativity hook is never fatal
            return None

    def observe(self, outcome: SubgameOutcome, opponent_role: Role) -> None:
        """Fold the opponent's revealed records; refresh :attr:`prior` for the next sub-game."""
        if self._profiler is None:
            return
        try:
            self._profiler.ingest_subgame(outcome.audit.get("their_records") or [],
                                          opponent_role.value)
            self.prior = self._profiler.trust_prior()
        except Exception:  # noqa: BLE001 — a malformed transcript must never crash the series
            pass

    @staticmethod
    def belief_cfg(config: Any, cfg: dict[str, Any], trust_prior: float | None) -> dict[str, Any]:
        """BeliefV2 cfg with r_0 seeded from a cross-sub-game profile (else the config value)."""
        prior = trust_prior if trust_prior is not None else cfg.get("hint_trust_prior")
        return {"move_set": list(config.game("movement_and_barriers.move_set")),
                "hint_trust_prior": prior,
                **{k: cfg[k] for k in cfg if k not in ("smell_trust_weight", "hint_trust_prior")}}


def sub_row(number: int, role: Role, my_gid: str, opp_gid: str,
            outcome: SubgameOutcome) -> dict[str, Any]:
    """One result row (the shape the report-stage result artifact will consume)."""
    return {"sub_game_number": number,
            "roles": {my_gid: role.value, opp_gid: role.opponent.value},
            "result": outcome.result.value,
            "winner_role": None if outcome.winner is None else outcome.winner.value,
            "score": {my_gid: outcome.scores[role], opp_gid: outcome.scores[role.opponent]},
            "steps": outcome.steps, "game_uid": outcome.game_uid,
            "audit": {key: outcome.audit[key] for key in
                      ("passed", "forgery", "opponent_received", "failed_steps")}}


def log_document(number: int, role: Role, my_gid: str,
                 outcome: SubgameOutcome) -> dict[str, Any]:
    """Minimal replayable per-sub-game log: summary + the revealed sealed chain."""
    return {"summary": {"sub_game_number": number, "group_id": my_gid, "role": role.value,
                        "opponent_group_id": outcome.opponent_group,
                        "game_id": outcome.game_id, "game_uid": outcome.game_uid,
                        "result": outcome.result.value,
                        "winner_role": None if outcome.winner is None else outcome.winner.value,
                        "steps": outcome.steps, "audit": outcome.audit},
            "records": outcome.records}


def write_json(path: Path, data: dict[str, Any]) -> None:
    """Emit ``data`` as pretty UTF-8 JSON, creating parent dirs as needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
