"""Pure builders for the four standardized game JSON artifacts (book Appendix F):
declaration, config, log, result — dicts in, dicts out, no I/O except the optional
:func:`write_artifacts` writer. Wired from the report stage over a completed series.

These fix the reference's known emission bugs by CONSUMING real data instead of
placeholders: the real ``github_commit`` (never the literal ``"unknown"``), every repo
link, real per-group token totals summed from the sub-games, and a mutual-agreement
SHA that is the agreed ``config_sha256`` (byte-identical config lock) rather than an
ad-hoc digest. Everything is read from the passed dicts — no hardcoded game parameters.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from pursuit.report.schema import (
    DEFAULT_TIMEZONE,
    SCHEMA_CONFIG,
    SCHEMA_DECLARATION,
    SCHEMA_LOG,
    SCHEMA_RESULT,
    SCHEMA_VERSION,
    config_filename,
    declaration_filename,
    hardware_spec,
    links,
    log_filename,
    result_filename,
    sub_result_row,
)


def build_declaration(sysinfo: Mapping[str, Any], group_id: str,
                      members: Sequence[str], github_commit: str, counted_games: int,
                      public_key_b64: str, repos: Mapping[str, str]) -> dict[str, Any]:
    """Template 1: static pre-game declaration for the whole series (our group block)."""
    return {
        "_schema": SCHEMA_DECLARATION,
        "schema_version": SCHEMA_VERSION,
        "declaration_type": "pre_game_declaration",
        "group_id": group_id,
        "members": list(members),
        "github_commit": github_commit,
        "counted_games": counted_games,
        "public_key_b64": public_key_b64,
        "repos": dict(repos),
        "llm_model": sysinfo.get("model") or sysinfo.get("llm_model"),
        "os": sysinfo.get("os"),
        "hardware_spec": hardware_spec(sysinfo),
    }


def build_config_artifact(config_sha256: str, terms: Mapping[str, Any]) -> dict[str, Any]:
    """Template 2: the agreed, byte-identical config plus its canonical sha256 lock."""
    return {
        "_schema": SCHEMA_CONFIG,
        **dict(terms),
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
                          opponent_group_id: str) -> dict[str, Any]:
    """Template 4: per-sub-game rows + totals + tie + winner over the whole series."""
    group_ids = [group_id, opponent_group_id]
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
    mutual_sha = str(series_summary.get("config_sha256", ""))
    return {
        "_schema": SCHEMA_RESULT,
        "schema_version": SCHEMA_VERSION,
        "report_type": "final_game_result",
        "game_id": game_id,
        "game_uid": subs[0].get("game_uid", "") if subs else "",
        "links": links(game_id),
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
        },
        "mutual_agreement": {
            "sha256": mutual_sha,
            "confirmed": all(row["audit"]["log_verified"] for row in rows),
        },
    }


def _dump(path: Path, data: Mapping[str, Any]) -> str:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)


def write_artifacts(out_dir: str | Path, declaration: Mapping[str, Any],
                    config_art: Mapping[str, Any], result: Mapping[str, Any],
                    logs: Sequence[Mapping[str, Any]]) -> list[str]:
    """Write all four artifact kinds under ``out_dir``; return the written paths."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    game_id = str(result.get("game_id") or config_art.get("game_id", ""))
    paths = [
        _dump(out / declaration_filename(game_id), declaration),
        _dump(out / config_filename(game_id), config_art),
        _dump(out / result_filename(game_id), result),
    ]
    for log in logs:
        number = int(log.get("summary", {}).get("sub_game_number", 0) or 0)
        paths.append(_dump(out / log_filename(game_id, number), log))
    return paths
