"""SealedLog behavior — seal/reveal round-trip, wire hygiene, forgery detection, step-0.

No sockets, no processes, no LLM: everything is direct calls over in-memory dicts;
the config is a hand-built ConfigManager (no file I/O).
"""

from __future__ import annotations

import json

import pytest

from pursuit.domain.crypto import make_hash_dialect, verify_signature
from pursuit.domain.crypto.signing import generate_keypair
from pursuit.peer.sealing import (
    SECRET_PAYLOAD_KEYS,
    SealedLog,
    verify_step0_signature,
)
from pursuit.shared.config import ConfigManager

DIALECT_IDS = ["book", "reference"]

FAKE_SPEC = {
    "os": "TestOS 1.0 (0.0.1)", "cpu_type": "TestCPU", "cpu_freq_mhz": 2400,
    "cpu_cores": 8, "ram_gb": 16.0, "gpu_model": "Test GPU", "vram_gb": 4.0,
}  # fmt: skip

STEP_PAYLOADS = [
    {"step": 1, "state": "grid=7x7;self=[4, 3];barriers=[]", "position": [4, 3],
     "move": "MOVE:S", "intent": "truth", "verdict": "truth",
     "hint": "I keep moving through the streets."},
    {"step": 2, "state": "grid=7x7;self=[5, 3];barriers=[]", "position": [5, 3],
     "move": "MOVE:E", "intent": "lie", "verdict": "lie",
     "hint": "רואים אותי ליד הפארק"},
]  # fmt: skip


def make_config(dialect: str) -> ConfigManager:
    return ConfigManager(
        game_terms={"crypto": {"dialect": dialect}},
        private_terms={
            "version": "0.1.0",
            "game": {"group_name": "nis-yar1", "sub_game_number": 3},
            "trash_talk": {"model": "qwen2.5:7b"},
        },
        rate_limits={},
    )


def make_log(dialect: str) -> SealedLog:
    return SealedLog({"dialect": dialect})


@pytest.mark.parametrize("dialect", DIALECT_IDS)
def test_seal_reveal_audit_roundtrip_passes_every_step(dialect: str) -> None:
    log = make_log(dialect)
    for payload in STEP_PAYLOADS:
        log.seal_step(payload)
    revealed = log.audit_reveal()
    results = SealedLog.audit_verify(revealed, make_hash_dialect({"dialect": dialect}))
    assert [r["ok"] for r in results] == [True, True]
    assert [r["step"] for r in results] == [1, 2]
    assert all(r["reason"] == "" for r in results)


@pytest.mark.parametrize("dialect", DIALECT_IDS)
def test_wire_view_carries_no_nonce_and_no_secret_keys(dialect: str) -> None:
    log = make_log(dialect)
    record = log.seal_step(STEP_PAYLOADS[0])
    view = SealedLog.wire_view(record)
    assert set(view) == {"payload", "commit"}
    assert view["commit"] == record["commit"]
    assert record["nonce"] not in json.dumps(view)  # rule 18/A8: nonce never pre-audit
    assert not set(view["payload"]) & set(SECRET_PAYLOAD_KEYS)
    assert view["payload"]["step"] == 1  # non-secret keys survive
    assert view["payload"]["hint"] == STEP_PAYLOADS[0]["hint"]


def test_dialect_mismatch_fails_every_step() -> None:
    log = make_log("book")
    for payload in STEP_PAYLOADS:
        log.seal_step(payload)
    other_dialect = make_hash_dialect({"dialect": "reference"})
    results = SealedLog.audit_verify(log.audit_reveal(), other_dialect)
    assert all(not r["ok"] for r in results)  # INTEROP M5: unnegotiated dialect = all fail


@pytest.mark.parametrize("dialect", DIALECT_IDS)
@pytest.mark.parametrize("field,value", [("move", "MOVE:N"), ("hint", "doctored"),
                                         ("intent", "truth"), ("position", [0, 0])])  # fmt: skip
def test_audit_catches_a_tampered_field(dialect: str, field: str, value: object) -> None:
    log = make_log(dialect)
    for payload in STEP_PAYLOADS:
        log.seal_step(payload)
    revealed = log.audit_reveal()
    revealed[1]["payload"][field] = value  # forge step 2 after the commit went out
    results = SealedLog.audit_verify(revealed, make_hash_dialect({"dialect": dialect}))
    assert [r["ok"] for r in results] == [True, False]
    assert results[1]["reason"] != ""  # documented forgery -> technical_loss 0/0 (A9a)


def test_audit_is_total_over_malformed_records() -> None:
    dialect = make_hash_dialect({"dialect": "book"})
    junk = ["not-a-record", {"payload": "not-a-dict", "nonce": "aa", "commit": "bb"},
            {"payload": {"step": 9}, "nonce": None, "commit": "bb"}, {}]  # fmt: skip
    results = SealedLog.audit_verify(junk, dialect)
    assert len(results) == 4
    assert all(not r["ok"] and r["reason"] == "malformed record" for r in results)


@pytest.mark.parametrize("dialect", DIALECT_IDS)
def test_step0_record_is_signed_first_and_commit_verifies(dialect: str) -> None:
    keypair = generate_keypair()
    log = make_log(dialect)
    record = log.step0_record(make_config(dialect), FAKE_SPEC, "abc1234", 2, keypair)
    payload = record["payload"]
    assert payload["step"] == 0
    assert payload["type"] == "system_spec"
    assert payload["spec"] == FAKE_SPEC
    assert payload["model"] == "qwen2.5:7b"
    assert payload["code_version"] == "0.1.0"
    assert payload["group_name"] == "nis-yar1"
    assert payload["sub_game_number"] == 3
    assert payload["github_commit"] == "abc1234"  # real hash, not the reference's "unknown"
    assert payload["counted_games"] == 2  # rule 37 ledger INSIDE the signed blob (A9b)
    assert log.audit_reveal()[0] is not record  # reveal returns copies
    assert log.audit_reveal()[0]["payload"]["step"] == 0  # records[0] = step-0
    results = SealedLog.audit_verify(log.audit_reveal(), make_hash_dialect({"dialect": dialect}))
    assert results[0]["ok"]


def test_step0_signature_verifies_with_right_key_and_fails_with_wrong_key() -> None:
    keypair = generate_keypair()
    _, wrong_public = generate_keypair()
    log = make_log("book")
    payload = log.step0_record(make_config("book"), FAKE_SPEC, "abc1234", 0, keypair)["payload"]
    assert payload["public_key"] == keypair[1].decode("ascii")
    assert verify_step0_signature(payload, keypair[1])
    assert not verify_step0_signature(payload, wrong_public)
    unsigned = {k: v for k, v in payload.items() if k != "signature"}
    assert verify_signature(keypair[1], unsigned, payload["signature"])  # D14 wire form


def test_step0_signature_breaks_if_counted_games_ledger_is_altered() -> None:
    keypair = generate_keypair()
    log = make_log("book")
    payload = log.step0_record(make_config("book"), FAKE_SPEC, "abc1234", 5, keypair)["payload"]
    forged = {**payload, "counted_games": 0}  # try to reset the rule-37 ledger
    assert not verify_step0_signature(forged, keypair[1])
    assert not verify_step0_signature({**payload, "signature": 42}, keypair[1])  # no crash


def test_sealed_log_dialect_comes_from_config_block() -> None:
    assert SealedLog({"dialect": "book"}).dialect.name == "book"
    assert SealedLog({"dialect": "reference"}).dialect.name == "reference"
    assert SealedLog(None).dialect.name == "reference"  # CORE-form default (review fix)
