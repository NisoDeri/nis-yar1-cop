"""Log/document emission for the series driver (arch §sdk): the report-row :func:`sub_row`,
the replayable :func:`log_document`, the :func:`write_json` sink and :func:`emit_artifacts`.
No game params hardcoded — all derived from the passed ``outcome``/``config``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pursuit.constants import GameResult, Role
from pursuit.domain.scoring import ScoreTable
from pursuit.peer.audit import SubgameOutcome
from pursuit.exceptions import ConfigError
from pursuit.strategy.profiler import OpponentProfiler


class LieProfiler:
    """E2 cross-sub-game lie-profiler bridge — gated, non-fatal. Off unless private
    ``strategy.profile_opponent`` is truthy (``None`` on any build error). :meth:`observe`
    folds each sub-game's revealed opponent records into :attr:`prior` — the Beta r_0 the
    next sub-game seeds via :meth:`belief_cfg`; wrapped so it never crashes.
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
    turns = _turns_completed(role, outcome)
    roles = {my_gid: role.value, opp_gid: role.opponent.value}
    return {"sub_game_number": number,
            "roles": roles,
            "started_at": _outcome_attr(outcome, "started_at", None),
            "ended_at": _outcome_attr(outcome, "ended_at", None),
            "result": outcome.result.value,
            "winner_role": None if outcome.winner is None else outcome.winner.value,
            "github_commit": _github_commit_map(roles, role, outcome.records,
                                                outcome.audit.get("their_records")),
            "score": {my_gid: outcome.scores[role], opp_gid: outcome.scores[role.opponent]},
            "steps": outcome.steps, "turns_completed": turns,
            "step_count_convention": _STEP_COUNT_CONVENTION,
            "end_state_digest": _outcome_attr(outcome, "end_state_digest", None),
            "end_state_digest_preimage": _outcome_attr(
                outcome, "end_state_digest_preimage", None),
            "digest_match": _digest_match(outcome),
            "game_uid": outcome.game_uid,
            "opponent_identity": dict(_outcome_attr(outcome, "opponent_identity", {}) or {}),
            "audit": {key: outcome.audit[key] for key in
                      ("passed", "forgery", "opponent_received", "failed_steps")}}


def log_document(number: int, role: Role, my_gid: str,
                 outcome: SubgameOutcome) -> dict[str, Any]:
    """Minimal replayable per-sub-game log: summary + the revealed sealed chain."""
    turns = _turns_completed(role, outcome)
    return {"summary": {"sub_game_number": number, "group_id": my_gid, "role": role.value,
                        "opponent_group_id": outcome.opponent_group,
                        "opponent_identity": dict(_outcome_attr(outcome, "opponent_identity", {}) or {}),
                        "game_id": outcome.game_id, "game_uid": outcome.game_uid,
                        "started_at": _outcome_attr(outcome, "started_at", None),
                        "ended_at": _outcome_attr(outcome, "ended_at", None),
                        "result": outcome.result.value,
                        "winner_role": None if outcome.winner is None else outcome.winner.value,
                        "steps": outcome.steps, "turns_completed": turns,
                        "step_count_convention": _STEP_COUNT_CONVENTION,
                        "end_state_digest": _outcome_attr(outcome, "end_state_digest", None),
                        "end_state_digest_preimage": _outcome_attr(
                            outcome, "end_state_digest_preimage", None),
                        "digest_match": _digest_match(outcome),
                        "audit": outcome.audit},
            "records": outcome.records}


def write_json(path: Path, data: dict[str, Any]) -> None:
    """Emit ``data`` as pretty UTF-8 JSON, creating parent dirs as needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


_STEP_COUNT_CONVENTION = (
    "steps is this peer's own valid-turn counter, including terminal concession/survival "
    "records when this peer emits them. turns_completed is the last step number emitted by "
    "the winning role; on technical/tie outcomes it is the max revealed step."
)


def _outcome_attr(outcome: Any, name: str, default: Any) -> Any:
    return getattr(outcome, name, default)


def _last_step(records: Any) -> int:
    values: list[int] = []
    for record in records or []:
        payload = record.get("payload", {}) if isinstance(record, dict) else {}
        try:
            values.append(int(payload.get("step", 0) or 0))
        except Exception:  # noqa: BLE001
            pass
    return max(values, default=0)


def _turns_completed(role: Role, outcome: Any) -> int:
    own_last = _last_step(_outcome_attr(outcome, "records", [])) or int(
        _outcome_attr(outcome, "steps", 0) or 0)
    their_records = (_outcome_attr(outcome, "audit", {}) or {}).get("their_records", [])
    their_last = _last_step(their_records)
    winner = _outcome_attr(outcome, "winner", None)
    if winner is role:
        return own_last
    if winner is role.opponent:
        return their_last or max(0, own_last - (1 if role is Role.THIEF else 0))
    return max(own_last, their_last)


def _digest_match(outcome: Any) -> bool | None:
    digest = _outcome_attr(outcome, "end_state_digest", None)
    their = (_outcome_attr(outcome, "audit", {}) or {}).get("their_end_state_digest")
    if digest and their:
        return digest == their
    return None


def _step0_commit(records: Any) -> str | None:
    for record in records or []:
        payload = record.get("payload", {}) if isinstance(record, dict) else {}
        try:
            step = int(payload.get("step", -1))
        except Exception:  # noqa: BLE001
            step = -1
        if step == 0:
            commit = payload.get("github_commit")
            return str(commit) if commit else None
    return None


def _github_commit_map(
    roles: dict[str, str],
    my_role: Role,
    my_records: Any,
    their_records: Any,
) -> dict[str, str]:
    by_role = {
        my_role.value: _step0_commit(my_records),
        my_role.opponent.value: _step0_commit(their_records),
    }
    return {gid: by_role[role] for gid, role in roles.items() if by_role.get(role)}


def _opponent(summary: dict[str, Any], my_gid: str) -> str:
    return next((g for g in summary.get("totals", {}) if g != my_gid), "opponent")


def _log_number(doc: dict[str, Any]) -> int:
    return int(doc.get("summary", {}).get("sub_game_number", 0) or 0)


def _read_sibling_logs(out_dir: Path, game_id: str) -> list[dict[str, Any]]:
    docs: list[dict[str, Any]] = []
    for path in out_dir.glob(f"log_{game_id}_g*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                docs.append(data)
        except Exception:  # noqa: BLE001 - a corrupt side artifact must not stop reporting
            pass
    return docs


def _role(value: Any) -> Role | None:
    try:
        return Role(value)
    except Exception:  # noqa: BLE001
        return None


def _row_from_log(config: Any, doc: dict[str, Any], my_gid: str, opp_gid: str) -> dict[str, Any]:
    summary = dict(doc.get("summary", {}))
    role = _role(summary.get("role")) or Role.POLICE
    opponent = str(summary.get("opponent_group_id") or opp_gid)
    winner = _role(summary.get("winner_role"))
    result = summary.get("result")
    try:
        game_result = GameResult(result)
    except Exception:  # noqa: BLE001
        game_result = str(result or GameResult.TECHNICAL_LOSS.value)
    by_role = ScoreTable(config.game("scoring")).score_subgame(game_result, winner)
    roles = {my_gid: role.value, opponent: role.opponent.value}
    return {
        "sub_game_number": _log_number(doc),
        "roles": roles,
        "started_at": summary.get("started_at"),
        "ended_at": summary.get("ended_at"),
        "result": str(result or GameResult.TECHNICAL_LOSS.value),
        "winner_role": None if winner is None else winner.value,
        "github_commit": _github_commit_map(
            roles,
            role,
            doc.get("records", []),
            (summary.get("audit") or {}).get("their_records", []),
        ),
        "score": {my_gid: by_role[role], opponent: by_role[role.opponent]},
        "steps": int(summary.get("steps", 0) or 0),
        "turns_completed": int(summary.get("turns_completed", summary.get("steps", 0)) or 0),
        "step_count_convention": summary.get("step_count_convention", _STEP_COUNT_CONVENTION),
        "end_state_digest": summary.get("end_state_digest"),
        "digest_match": summary.get("digest_match"),
        "game_uid": str(summary.get("game_uid", "")),
        "opponent_identity": dict(summary.get("opponent_identity", {}) or {}),
        "audit": {
            "passed": bool((summary.get("audit") or {}).get("passed", False)),
            "forgery": bool((summary.get("audit") or {}).get("forgery", False)),
            "opponent_received": bool((summary.get("audit") or {}).get("opponent_received", False)),
            "failed_steps": list((summary.get("audit") or {}).get("failed_steps", [])),
        },
    }


def _merged_summary(config: Any, summary: dict[str, Any], logs: list[dict[str, Any]],
                    out_dir: Path, my_gid: str, opp_gid: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    game_id = str(summary.get("game_id", ""))
    by_number = {_log_number(doc): doc for doc in _read_sibling_logs(out_dir, game_id)}
    by_number.update({_log_number(doc): doc for doc in logs})
    merged_logs = [by_number[n] for n in sorted(by_number) if n > 0]
    if len(merged_logs) <= len(logs):
        return summary, logs
    rows = [_row_from_log(config, doc, my_gid, opp_gid) for doc in merged_logs]
    scores = [dict(row.get("score", {})) for row in rows]
    return {
        **summary,
        "num_sub_games": len(rows),
        "sub_games": rows,
        **ScoreTable(config.game("scoring")).series_totals(scores),
    }, merged_logs


def emit_artifacts(config: Any, summary: dict[str, Any], logs: list[dict[str, Any]],
                   sysinfo: dict[str, Any], github_commit: str,
                   keypair: tuple[bytes, bytes], out_dir: Path) -> list[str]:
    """Build + write the FOUR artifacts; best-effort, never aborts a finished series."""
    import base64

    from pursuit.domain.negotiation import build_terms
    from pursuit.report.artifacts import (
        build_config_artifact,
        build_declaration,
        build_log_artifact,
        build_result_artifact,
        write_artifacts,
    )
    try:
        my_gid = str(summary.get("group_id", ""))
        try:
            counted = int(config.private("game.counted_games_so_far"))
        except Exception:  # noqa: BLE001
            counted = 0
        is_counted_game = _game_mode(config) == "counted"  # +1 counter + App.F diversity
        opp = _opponent(summary, my_gid)
        # SINGLE-EMITTER GUARD: capture THIS peer's own windows BEFORE the sibling merge.
        # In a two-process fixed-role run both peers build the full merged report, but only
        # the one that played the FINAL window (num_games) may email it — otherwise the
        # opponent (and the lecturer, on a counted game) receives duplicate reports.
        try:
            _num_games = int(config.game("network_and_league.num_games"))
        except Exception:  # noqa: BLE001
            _num_games = len(summary.get("sub_games", []))
        _own_windows = {int(s.get("sub_game_number", 0)) for s in summary.get("sub_games", [])}
        is_report_emitter = _num_games in _own_windows
        summary, logs = _merged_summary(config, summary, logs, out_dir, my_gid, opp)
        artifact_sysinfo = dict(sysinfo)
        try:
            artifact_sysinfo.setdefault("llm_model", config.private("trash_talk.model"))
            artifact_sysinfo.setdefault("llm_provider", config.private("trash_talk.provider"))
        except ConfigError:
            pass
        subs = list(summary.get("sub_games", []))
        opponent_identity = next((dict(sub.get("opponent_identity", {}) or {})
                                  for sub in subs if sub.get("opponent_identity")), {})
        counted_by_group = {
            my_gid: counted,
            opp: int(opponent_identity.get("counted_games_played",
                                           opponent_identity.get("counted_games_so_far", 0)) or 0),
        }
        try:
            mcp_servers = config.private("game.mcp_servers")
        except ConfigError:
            mcp_servers = {}
        repos_by_group = {my_gid: config.private("game.repos")}
        if opponent_identity.get("repos"):
            repos_by_group[opp] = dict(opponent_identity.get("repos", {}))
        result = build_result_artifact(summary, my_gid, opp, repos_by_group, counted_by_group,
                                       counted=is_counted_game)
        game_id, game_uid = result["game_id"], result["game_uid"]
        declaration = build_declaration(
            artifact_sysinfo, my_gid, config.private("game.members"), github_commit, counted,
            base64.b64encode(keypair[1]).decode("ascii"), config.private("game.repos"),
            opp, game_id, game_uid, len(subs), opponent_identity, mcp_servers)
        sha, terms = config.config_sha256(), build_terms(config)
        configs = [build_config_artifact(sha, terms, game_id, game_uid,
                                         int(sub.get("sub_game_number", i + 1)))
                   for i, sub in enumerate(subs)]
        log_arts = [build_log_artifact(doc) for doc in logs]
        paths = write_artifacts(out_dir, declaration, configs, result, log_arts)
        maybe_email(config, summary, result, is_emitter=is_report_emitter)
        return paths
    except Exception:  # noqa: BLE001 — reporting must never crash a completed series
        return []


def _game_mode(config: Any) -> str:
    """The friendly/counted mode (private ``game.mode``, default ``friendly``).

    ONE switch drives everything counted-vs-friendly: the report recipient and the
    +1 counter / diversity reward. Default friendly is the SAFE default — a report can
    only reach the lecturer when mode is explicitly ``counted``.
    """
    mode = str(_private_default(config, "game.mode", "friendly")).strip().lower()
    return "counted" if mode == "counted" else "friendly"


def _mode_recipient(config: Any) -> Any:
    """Report recipient for the current mode: friendly -> both teams' inboxes; counted ->
    the lecturer alone. Mode-specific keys win; ``email.recipient`` is the legacy fallback."""
    if _game_mode(config) == "counted":
        return _private_default(config, "email.recipient_counted",
                                _private_default(config, "email.recipient", None))
    return _private_default(config, "email.recipient_friendly",
                            _private_default(config, "email.recipient", None))


def maybe_email(config: Any, summary: dict[str, Any], result: dict[str, Any],
                is_emitter: bool = True) -> None:
    """Opt-in (private ``email.enabled``): send the result artifact via the email Gatekeeper.

    ``is_emitter`` is the single-emitter guard: a two-process fixed-role run passes False on
    every peer except the one that played the final window, so exactly ONE report is filed
    (critical at the lecturer address on a counted game). Single-process runs pass True.
    """
    try:
        if not is_emitter or not bool(config.private("email.enabled")):
            return
        try:
            expected = int(config.game("network_and_league.num_games"))
        except Exception:  # noqa: BLE001
            expected = int(summary.get("num_sub_games", 0) or 0)
        if int(result.get("num_sub_games", 0) or 0) < expected:
            return
        from pursuit.infra.email import GmailSender
        from pursuit.infra.gatekeeper import Gatekeeper

        subject = _report_subject(result)
        recipient = _mode_recipient(config)
        sender = _private_default(config, "email.sender", None)
        credentials_dir = _private_default(config, "email.credentials_dir", "secrets")
        Gatekeeper.from_config(config, "email").execute(
            GmailSender(Path(credentials_dir) / "token.json",
                        Path(credentials_dir) / "smtp.json").send_result,
            subject, result, recipient, sender)  # result = the canonical artifact dict
    except Exception:  # noqa: BLE001 — a send failure must NEVER crash the series
        pass


def _private_default(config: Any, key_path: str, default: Any) -> Any:
    try:
        return config.private(key_path)
    except Exception:  # noqa: BLE001
        return default


def _report_subject(result: dict[str, Any]) -> str:
    game_id = str(result.get("game_id", ""))
    final = dict(result.get("final_result", {}) or {})
    totals = dict(final.get("total_score", {}) or {})
    verdict = "series_tie" if final.get("series_tie") else f"winner={final.get('winner_group')}"
    score = " ".join(f"{gid}:{totals[gid]}" for gid in sorted(totals))
    return f"P2P league SERIES result - {game_id} - {verdict} - {score}"
