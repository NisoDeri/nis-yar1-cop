"""Replay auditor tests — seal real records, then verify (and detect tampering).

Records are produced by the production :class:`SealedLog`, so the test exercises the
exact commit-reveal chain the series writer emits (no hand-rolled hashes). No Tk window
is ever opened here — only the headless :func:`verify_log` / :func:`parse_state` path.
"""

from __future__ import annotations

import json
from pathlib import Path

from pursuit.interface.replay_verify import parse_state, verify_log
from pursuit.peer.sealing import SealedLog

_SUMMARY = {"game_id": "t-vs-t", "result": "capture"}


def _make_records(dialect: str) -> list[dict]:
    log = SealedLog({"dialect": dialect})
    log.seal_step({"step": 0, "type": "system_spec", "spec": {}})
    log.seal_step(
        {"step": 1, "state": "grid=7x7;self=[1, 0];barriers=[]",
         "position": [1, 0], "move": "MOVE:S"}
    )
    log.seal_step(
        {"step": 2, "state": "grid=7x7;self=[2, 0];barriers=[[3, 3]]",
         "position": [2, 0], "move": "MOVE:S"}
    )
    return log.audit_reveal()


def _write(tmp_path: Path, records: list[dict]) -> Path:
    path = tmp_path / "log.json"
    path.write_text(
        json.dumps({"summary": _SUMMARY, "records": records}, ensure_ascii=False),
        encoding="utf-8",
    )
    return path


def test_verify_log_passes_for_reference_sealed_records(tmp_path: Path) -> None:
    result = verify_log(_write(tmp_path, _make_records("reference")))
    assert result["passed"] is True
    assert result["n_records"] == 3
    assert result["failed_steps"] == []
    assert result["dialect"] == "reference"
    assert result["game_id"] == "t-vs-t"
    assert result["result"] == "capture"


def test_verify_log_detects_book_dialect(tmp_path: Path) -> None:
    result = verify_log(_write(tmp_path, _make_records("book")))
    assert result["passed"] is True
    assert result["dialect"] == "book"


def test_tampered_payload_field_fails_that_step(tmp_path: Path) -> None:
    records = _make_records("reference")
    records[1]["payload"]["position"] = [5, 5]  # flip a field AFTER sealing
    result = verify_log(_write(tmp_path, records))
    assert result["passed"] is False
    assert 1 in result["failed_steps"]
    assert result["n_records"] == 3


def test_parse_state_extracts_position_and_barriers() -> None:
    pos, barriers = parse_state("grid=7x7;self=[4, 3];barriers=[[2, 5], [1, 0]]")
    assert pos == (4, 3)
    assert set(barriers) == {(2, 5), (1, 0)}
    assert parse_state("grid=7x7;self=[0, 0];barriers=[]") == ((0, 0), [])
    assert parse_state("garbage") == (None, [])
    assert parse_state(None) == (None, [])
