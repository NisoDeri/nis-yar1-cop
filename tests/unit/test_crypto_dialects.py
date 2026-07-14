"""Behavior tests for pursuit.domain.crypto dialects — tamper detection, nonces, factory.

Byte-level golden vectors live in test_crypto.py; this file covers the commit/verify
contract (any change flips verify to False), unicode stability, nonce hygiene and the
make_hash_dialect factory (default `book` per NotebookLM ruling A1).
"""

from __future__ import annotations

import json

import pytest

from pursuit.domain.crypto import (
    DEFAULT_DIALECT,
    BookDialect,
    HashDialect,
    ReferenceDialect,
    generate_nonce,
    make_hash_dialect,
)
from pursuit.exceptions import ConfigError, CryptoError

# Same worked example as test_crypto.py (INTEROP §3.1) — kept local: test modules are
# not importable from each other without a tests package.
WORKED_PAYLOAD = {
    "step": 1,
    "move": "MOVE:S",
    "intent": "truth",
    "state": "grid=7x7;self=[4, 3];barriers=[]",
}
WORKED_NONCE = "22fdde9fd1571e88dfe922d6190dffcc"
DIGEST_B = "93a63dddf6d1ac3a02d5f641aa123dfd8aa9f0519bad55dd77ea916b92efeeea"

DIALECTS = [BookDialect(), ReferenceDialect()]
_IDS = [d.name for d in DIALECTS]


@pytest.mark.parametrize("dialect", DIALECTS, ids=_IDS)
def test_commit_verify_roundtrip(dialect: HashDialect) -> None:
    nonce = generate_nonce()
    digest = dialect.commit(WORKED_PAYLOAD, nonce)
    assert dialect.verify(WORKED_PAYLOAD, nonce, digest)


@pytest.mark.parametrize("dialect", DIALECTS, ids=_IDS)
def test_any_tampering_flips_verify_to_false(dialect: HashDialect) -> None:
    digest = dialect.commit(WORKED_PAYLOAD, WORKED_NONCE)
    for mutated in (
        {**WORKED_PAYLOAD, "step": 2},  # changed field
        {**WORKED_PAYLOAD, "move": "MOVE:N"},  # changed field
        {**WORKED_PAYLOAD, "extra": True},  # smuggled field
        {k: v for k, v in WORKED_PAYLOAD.items() if k != "intent"},  # dropped field
    ):
        assert not dialect.verify(mutated, WORKED_NONCE, digest)
    assert not dialect.verify(WORKED_PAYLOAD, "0" * 32, digest)  # wrong nonce
    assert not dialect.verify(WORKED_PAYLOAD, WORKED_NONCE, "0" * 64)  # wrong digest


@pytest.mark.parametrize("dialect", DIALECTS, ids=_IDS)
def test_hebrew_hint_payload_hashes_stably(dialect: HashDialect) -> None:
    payload = {**WORKED_PAYLOAD, "hint": "אני מסתתר ליד הים בחיפה"}
    digest = dialect.commit(payload, WORKED_NONCE)
    rewired = json.loads(json.dumps(payload, ensure_ascii=False))  # wire round-trip
    assert dialect.commit(rewired, WORKED_NONCE) == digest
    assert dialect.verify(rewired, WORKED_NONCE, digest)


def test_book_dialect_rejects_reserved_nonce_key() -> None:
    smuggled = {**WORKED_PAYLOAD, "nonce": "beef"}
    with pytest.raises(CryptoError):
        BookDialect().commit(smuggled, WORKED_NONCE)
    assert not BookDialect().verify(smuggled, WORKED_NONCE, DIGEST_B)  # no crash at audit


def test_generate_nonce_is_32_lowercase_hex_and_fresh() -> None:
    nonces = {generate_nonce() for _ in range(64)}
    assert len(nonces) == 64
    assert all(len(n) == 32 and set(n) <= set("0123456789abcdef") for n in nonces)


def test_base_dialect_commit_is_abstract() -> None:
    with pytest.raises(NotImplementedError):
        HashDialect().commit(WORKED_PAYLOAD, WORKED_NONCE)


def test_factory_defaults_to_reference_and_honors_explicit_choice() -> None:
    assert DEFAULT_DIALECT == "reference"  # league CORE form; a partial crypto block
    assert isinstance(make_hash_dialect({}), ReferenceDialect)  # must not fall back to book
    assert isinstance(make_hash_dialect(None), ReferenceDialect)
    assert isinstance(make_hash_dialect({"dialect": "book"}), BookDialect)
    assert isinstance(make_hash_dialect({"dialect": "reference"}), ReferenceDialect)


@pytest.mark.parametrize("bad", [{"dialect": "md5"}, {"dialect": ""}, {"dialect": 3}])
def test_factory_rejects_unknown_dialects(bad: dict) -> None:
    with pytest.raises(ConfigError):
        make_hash_dialect(bad)
