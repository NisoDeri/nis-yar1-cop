"""Commit-binding audit (review fix): a revealed commit must equal the LIVE wire commit.

Without this bind, ``SealedLog.audit_verify`` only proves the revealed chain is internally
self-consistent — a peer could reveal a fresh, valid chain and swap the move it actually
played after seeing ours. ``_reveal_mismatches`` catches that as provable forgery (0/0).
"""

from __future__ import annotations

from types import SimpleNamespace

from pursuit.peer.audit import _reveal_mismatches


def _rec(step: int, commit: str) -> SimpleNamespace:
    """A minimal revealed-record stand-in: ``.payload['step']`` + ``.commit``."""
    return SimpleNamespace(payload={"step": step}, commit=commit)


def test_honest_reveal_binds_clean() -> None:
    records = [_rec(0, "declaration"), _rec(1, "cA"), _rec(2, "cB")]
    live = {1: "cA", 2: "cB"}  # step 0 is the signed declaration — no live turn commit
    assert _reveal_mismatches(records, live) == []


def test_move_swap_is_caught() -> None:
    # The opponent broadcast cB on turn 2, then revealed a different sealed record.
    records = [_rec(1, "cA"), _rec(2, "SWAPPED_AFTER_SEEING_OUR_MOVE")]
    live = {1: "cA", 2: "cB"}
    assert _reveal_mismatches(records, live) == [2]


def test_no_live_commits_is_a_noop() -> None:
    # Backward-compatible: absent live commits (e.g. a 0-turn game) never false-positive.
    assert _reveal_mismatches([_rec(1, "cA")], {}) == []


def test_malformed_payload_never_crashes() -> None:
    records = [_rec(1, "cA"), SimpleNamespace(payload="not-a-dict", commit="x")]
    assert _reveal_mismatches(records, {1: "cA"}) == []
