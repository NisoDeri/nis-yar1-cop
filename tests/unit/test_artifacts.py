"""Unit tests for the four-artifact report builder (pure dicts in -> dicts out).

Fakes a minimal series summary + sysinfo, builds all four artifacts, and asserts the
required keys, ``schema_version`` propagation, result-total consistency, the reference
filenames, and a Hebrew field surviving an ``ensure_ascii=False`` round-trip.
"""

from __future__ import annotations

import json

import pytest

from pursuit.report.artifacts import (
    build_config_artifact,
    build_declaration,
    build_log_artifact,
    build_result_artifact,
    write_artifacts,
)

GAME_ID = "nis-yar1-vs-seg-team"
HEBREW = "קבוצת ירדן"


@pytest.fixture
def sysinfo() -> dict:
    return {
        "os": "Windows 11 (10.0.26200)", "cpu_type": "22-core", "cpu_freq_mhz": 2400,
        "cpu_cores": 22, "ram_gb": 63.5, "gpu_model": "RTX 3500 Ada", "vram_gb": 12.0,
        "model": "qwen2.5:7b",
    }


@pytest.fixture
def series_summary() -> dict:
    return {
        "game_id": GAME_ID, "group_id": "nis-yar1", "num_sub_games": 2,
        "config_sha256": "abc123", "tie": False, "winner": "nis-yar1",
        "totals": {"nis-yar1": 25, "seg-team": 5},
        "sub_games": [
            {"sub_game_number": 1, "roles": {"nis-yar1": "police", "seg-team": "thief"},
             "result": "capture", "winner_role": "police", "game_uid": "uid-1",
             "score": {"nis-yar1": 20, "seg-team": 5}, "tokens": {"nis-yar1": 120},
             "audit": {"passed": True, "forgery": False}},
            {"sub_game_number": 2, "roles": {"nis-yar1": "thief", "seg-team": "police"},
             "result": "survival", "winner_role": "thief", "game_uid": "uid-2",
             "score": {"nis-yar1": 5, "seg-team": 5}, "tokens": {"seg-team": 30},
             "audit": {"passed": True, "forgery": False}},
        ],
    }


def test_declaration_required_keys(sysinfo: dict) -> None:
    decl = build_declaration(sysinfo, "nis-yar1", ["id-1", "id-2"], "deadbeef", 3,
                             "PUBKEY==", {"cop": "https://gh/x", "thief": "https://gh/x"})
    assert decl["schema_version"] == "1.1"
    assert decl["github_commit"] == "deadbeef"
    assert decl["github_commit"] != "unknown"
    assert decl["counted_games"] == 3
    assert decl["repos"]["cop"] == "https://gh/x"
    assert decl["hardware_spec"]["gpu_model"] == "RTX 3500 Ada"
    assert decl["public_key_b64"] == "PUBKEY=="


def test_config_artifact_lock_and_terms() -> None:
    terms = {"game_id": GAME_ID, "scoring": {"capture_cop": 20}, "note": HEBREW}
    art = build_config_artifact("SHA256LOCK", terms)
    assert art["schema_version"] == "1.1"
    assert art["config_sha256"] == "SHA256LOCK"
    assert art["scoring"]["capture_cop"] == 20
    assert art["note"] == HEBREW


def test_result_totals_match(series_summary: dict) -> None:
    result = build_result_artifact(series_summary, "nis-yar1", "seg-team")
    assert result["schema_version"] == "1.1"
    final = result["final_result"]
    assert final["total_score"] == {"nis-yar1": 25, "seg-team": 5}
    assert final["sub_games_won"] == {"nis-yar1": 2, "seg-team": 0}
    assert final["winner_group"] == "nis-yar1"
    # real token totals summed per group (reference emitted 0) -> fixed
    assert final["tokens_total_series"] == {"nis-yar1": 120, "seg-team": 30}
    # mutual-agreement SHA is the agreed config lock
    assert result["mutual_agreement"]["sha256"] == "abc123"
    assert result["mutual_agreement"]["confirmed"] is True
    rows = result["sub_games"]
    assert [r["result"] for r in rows] == ["capture", "survival"]
    assert rows[0]["winner_group"] == "nis-yar1"
    assert rows[0]["audit"] == {"log_verified": True, "tampered": False}


def test_result_technical_loss_mapping(series_summary: dict) -> None:
    series_summary["sub_games"][0]["result"] = "stopped"
    series_summary["sub_games"][0]["winner_role"] = None
    result = build_result_artifact(series_summary, "nis-yar1", "seg-team")
    assert result["sub_games"][0]["result"] == "technical_loss"
    assert result["sub_games"][0]["winner_group"] is None


def test_log_artifact_passthrough() -> None:
    subgame_log = {
        "summary": {"sub_game_number": 1, "game_id": GAME_ID, "game_uid": "uid-1",
                    "group_id": "nis-yar1", "role": "police", "hint": HEBREW},
        "records": [{"payload": {"step": 0}, "commit": "c0"}],
    }
    log = build_log_artifact(subgame_log)
    assert log["schema_version"] == "1.1"
    assert log["game_id"] == GAME_ID
    assert log["summary"]["hint"] == HEBREW
    assert log["records"][0]["commit"] == "c0"
    assert "declaration" in log["links"]


def test_write_artifacts_filenames(tmp_path, sysinfo: dict, series_summary: dict) -> None:
    decl = build_declaration(sysinfo, "nis-yar1", ["id-1"], "deadbeef", 0, "PK", {})
    config_art = build_config_artifact("LOCK", {"game_id": GAME_ID, "note": HEBREW})
    result = build_result_artifact(series_summary, "nis-yar1", "seg-team")
    logs = [build_log_artifact({"summary": {"sub_game_number": 1, "game_id": GAME_ID},
                                "records": []})]
    paths = write_artifacts(tmp_path, decl, config_art, result, logs)
    names = {p.rsplit("\\", 1)[-1].rsplit("/", 1)[-1] for p in paths}
    assert names == {
        f"declaration_{GAME_ID}.json", f"config_{GAME_ID}.json",
        f"result_{GAME_ID}.json", f"log_{GAME_ID}_g01.json",
    }


def test_hebrew_round_trips(tmp_path, sysinfo: dict, series_summary: dict) -> None:
    config_art = build_config_artifact("LOCK", {"game_id": GAME_ID, "note": HEBREW})
    blob = json.dumps(config_art, ensure_ascii=False, indent=2)
    assert HEBREW in blob  # not \\u-escaped
    assert json.loads(blob)["note"] == HEBREW
