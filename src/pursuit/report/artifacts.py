"""Pure builders for the four standardized game JSON artifacts (book Appendix F):
declaration, config, log, result — dicts in, dicts out (the writer lives in
:mod:`pursuit.report.artifacts_io`, re-exported here). Real data replaces the reference
placeholders (true ``github_commit``, repo links, summed per-group tokens, agreed
``config_sha256``); the App. F table-20 join keys (game_id, game_uid, groups,
num_sub_games, sub_game_number) ride every kind so the four files join by one game_uid.
Nothing is hardcoded — all read from the passed dicts.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pursuit.report.artifacts_io import write_artifacts
from pursuit.report.consensus import mutual_agreement_signature
from pursuit.report.schema import (
    DEFAULT_TIMEZONE,
    SCHEMA_CONFIG,
    SCHEMA_DECLARATION,
    SCHEMA_LOG,
    SCHEMA_RESULT,
    SCHEMA_VERSION,
    hardware_spec,
    links,
    sub_result_row,
)

__all__ = [
    "build_config_artifact",
    "build_declaration",
    "build_log_artifact",
    "build_result_artifact",
    "write_artifacts",
]


def build_declaration(sysinfo: Mapping[str, Any], group_id: str,
                      members: Sequence[str], github_commit: str, counted_games: int,
                      public_key_b64: str, repos: Mapping[str, str],
                      opponent_group_id: str = "", game_id: str = "",
                      game_uid: str = "", num_sub_games: int = 0,
                      opponent_identity: Mapping[str, Any] | None = None,
                      mcp_servers: Mapping[str, str] | None = None) -> dict[str, Any]:
    """Template 1: static pre-game declaration for the whole series (both group blocks)."""
    model = sysinfo.get("model") or sysinfo.get("llm_model") or sysinfo.get("trash_talk_model")
    group_1 = {"group_id": group_id, "members": list(members), "repos": dict(repos)}
    if mcp_servers:
        group_1["mcp_servers"] = dict(mcp_servers)
    if model:
        group_1["llm_model"] = model
    group_2 = _opponent_group(opponent_group_id, opponent_identity)
    return {
        "_schema": SCHEMA_DECLARATION,
        "schema_version": SCHEMA_VERSION,
        "declaration_type": "pre_game_declaration",
        "game_id": game_id,
        "game_uid": game_uid,
        "num_sub_games": num_sub_games,
        "groups": {"group_1": group_1, "group_2": group_2},
        "links": links(game_id),
        "group_id": group_id,
        "members": list(members),
        "github_commit": github_commit,
        "counted_games": counted_games,
        "public_key_b64": public_key_b64,
        "repos": dict(repos),
        "llm_model": model,
        "llm_provider": sysinfo.get("llm_provider"),
        "os": sysinfo.get("os"),
        "hardware_spec": hardware_spec(sysinfo),
    }


def _opponent_group(group_id: str, identity: Mapping[str, Any] | None) -> dict[str, Any]:
    """Declaration-safe projection of the peer's handshake identity block."""
    allowed = (
        "group_id", "group_name", "members", "repos", "mcp_servers", "llm_model",
        "ed25519_public_key", "counted_games_so_far",
    )
    group = {key: identity[key] for key in allowed if identity and key in identity}
    group["group_id"] = str(group.get("group_id") or group_id)
    return group


def build_config_artifact(config_sha256: str, terms: Mapping[str, Any], game_id: str = "",
                          game_uid: str = "", sub_game_number: int = 1) -> dict[str, Any]:
    """Template 2: one PER-SUB-GAME agreed config plus its canonical sha256 lock."""
    return {
        "_schema": SCHEMA_CONFIG,
        **dict(terms),
        "game_id": game_id,
        "game_uid": game_uid,
        "sub_game_number": sub_game_number,
        "links": links(game_id),
        "schema_version": SCHEMA_VERSION,
        "config_sha256": config_sha256,
    }


def build_log_artifact(subgame_log: Mapping[str, Any]) -> dict[str, Any]:
    """Template 3: normalize one peer's ``{summary, records}`` sub-game log."""
    summary = dict(subgame_log.get("summary", {}))
    game_id = str(summary.get("game_id", ""))
    return {
        "_schema": SCHEMA_LOG,
        "schema_version": SCHEMA_VERSION,
        "game_id": game_id,
        "game_uid": summary.get("game_uid", ""),
        "links": links(game_id),
        "summary": summary,
        "records": list(subgame_log.get("records", [])),
    }


def build_result_artifact(series_summary: Mapping[str, Any], group_id: str,
                          opponent_group_id: str,
                          repos_by_group: Mapping[str, Mapping[str, str]] | None = None,
                          counted_games_by_group: Mapping[str, int] | None = None,
                          counted: bool = False) -> dict[str, Any]:
    """Template 4: per-sub-game rows + totals + tie + winner over the whole series.

    ``counted`` marks this as an OFFICIAL counted series (not a friendly): it adds +1 to
    each group's ``games_played_including_this`` (this game counts) and, on a counted FIRST
    meeting, applies the App. F diversity reward (+10) to the winner. Friendlies leave both
    untouched (raw counts, no reward) — verified against the friendlies that reconciled 3/0.
    """
    group_ids = sorted([group_id, opponent_group_id])
    game_id = str(series_summary.get("game_id", ""))
    subs = list(series_summary.get("sub_games", []))
    rows = [sub_result_row(sub, game_id, group_ids) for sub in subs]
    wins: dict[str, int] = dict.fromkeys(group_ids, 0)
    ties = 0
    for row in rows:
        if row["result"] == "tie":
            ties += 1
        elif row["winner_group"] in wins:
            wins[row["winner_group"]] += 1
    tokens_total = {gid: sum(row["tokens"].get(gid, 0) for row in rows)
                    for gid in group_ids}
    winner = series_summary.get("winner")
    first_meeting = bool(series_summary.get("first_meeting_between_groups", True))
    artifact = {
        "_schema": SCHEMA_RESULT,
        "schema_version": SCHEMA_VERSION,
        "report_type": "final_game_result",
        "game_id": game_id,
        "game_uid": subs[0].get("game_uid", "") if subs else "",
        "links": links(game_id, repos_by_group, include_remark=True),
        "timezone": DEFAULT_TIMEZONE,
        "groups": list(group_ids),
        "num_sub_games": len(rows),
        "sub_games": rows,
        "final_result": {
            "total_score": dict(series_summary.get("totals", {})),
            "sub_games_won": wins,
            "ties": ties,
            "winner_group": series_summary.get("winner"),
            "series_tie": bool(series_summary.get("tie", False)),
            "tokens_total_series": tokens_total,
            "games_played_including_this": {
                gid: int((counted_games_by_group or {}).get(gid, 0)) + (1 if counted else 0)
                for gid in group_ids
            },
            "first_meeting_between_groups": first_meeting,
            "diversity_reward_applied": {
                gid: bool(counted and first_meeting and gid == winner) for gid in group_ids
            },
        },
        "mutual_agreement": {
            "sha256": "",
            "confirmed": all(row["audit"]["log_verified"] for row in rows),
        },
    }
    artifact["mutual_agreement"]["sha256"] = mutual_agreement_signature(artifact)
    # Reconciliation rides mutual_agreement.sha256 alone — the symmetric-scope hash both teams
    # derive identically (proven byte-equal vs imreeyal). No separate settlement block: the
    # course result template is authoritative, and extra keys beyond it are not emitted (§3.17).
    return artifact
