"""Golden-vector tests for pursuit.domain.crypto — INTEROP §2.1/§3.1 pinned bytes.

Vectors come from planning/INTEROP.md's worked examples and from the professor's
sample-run log (reference/Game-P2P-Cop-Chase/docs/sample-run/), machine-verified
2026-07-13. If any of these ever fail, interop with the league is broken — fix the
code, never the vector.
"""

from __future__ import annotations

from pursuit.domain.crypto import BookDialect, ReferenceDialect, canonical_bytes, sha256_hex

# --- INTEROP §3.1 worked byte-level example (same payload, both dialect digests) ------
WORKED_PAYLOAD = {
    "step": 1,
    "move": "MOVE:S",
    "intent": "truth",
    "state": "grid=7x7;self=[4, 3];barriers=[]",
}
WORKED_NONCE = "22fdde9fd1571e88dfe922d6190dffcc"
WORKED_CANONICAL = (
    b'{"intent":"truth","move":"MOVE:S","state":"grid=7x7;self=[4, 3];barriers=[]","step":1}'
)
DIGEST_A = "b578bc307517f62029449e9fa845e6e981b8c802779713072324af02a722624b"
DIGEST_B = "93a63dddf6d1ac3a02d5f641aa123dfd8aa9f0519bad55dd77ea916b92efeeea"

# --- Sample-run step-0 system_spec record (dialect A, INTEROP §2.3/§3.1) --------------
SAMPLE_SPEC_PAYLOAD = {
    "step": 0,
    "type": "system_spec",
    "spec": {
        "os": "Windows 11 (10.0.26200)",
        "cpu_type": "Intel(R) Core(TM) i9-9980HK CPU @ 2.40GHz",
        "cpu_cores": 8,
        "cpu_freq_mhz": 2400,
        "ram_gb": 31.8,
        "gpu_type": "NVIDIA GeForce RTX 2060",
        "gpu_cores_or_cuda": "CUDA (core count not exposed by driver)",
        "vram_gb": 6.0,
    },
    "model": "claude-opus-4-8[1m]",
    "code_version": "1.12",
    "group_name": "Segal-Thief-Team",
    "sub_game_number": 1,
}
SAMPLE_SPEC_NONCE = "5f72978b482c02eeb3d8a20b01e619b9"
SAMPLE_SPEC_COMMIT = "78a31c516536350bfdb8a3ee4ba3e131ae0676d7b4b95d02ff94b1aa84b85e65"

# --- INTEROP §2.1 agreement-signature vector (always the reference construction) ------
AGREEMENT_TERMS = {
    "board_size": 7,
    "smell_grid_size": 5,
    "decay_per_step": 0.1,
    "emit_intensity": 0.9,
    "min_center_intensity": 0.5,
    "max_steps": 35,
    "barriers_max": 14,
    "setting": "New York",
    "hint_max_words": 15,
    "axis_origin_corner": "top-left",
    "axis_start_index": 0,
    "thief_start": [3, 3],
    "cop_start": [0, 0],
    "num_games": 1,
}
AGREEMENT_NONCE = "0f0e0d0c0b0a09080706050403020100"
AGREEMENT_SIGNATURE = "167fef4e1881492a35297832f78a550e3ffd909e69a21f259cf09c58b887472d"


def test_canonical_bytes_matches_interop_worked_bytes() -> None:
    assert canonical_bytes(WORKED_PAYLOAD) == WORKED_CANONICAL
    reordered = dict(reversed(list(WORKED_PAYLOAD.items())))
    assert canonical_bytes(reordered) == WORKED_CANONICAL  # sort_keys: order never matters


def test_canonical_bytes_hebrew_is_raw_utf8_not_escapes() -> None:
    assert canonical_bytes({"hint": "חיפה"}) == '{"hint":"חיפה"}'.encode()
    assert b"\\u" not in canonical_bytes({"hint": "חיפה"})


def test_sha256_hex_of_empty_input_is_the_known_constant() -> None:
    assert sha256_hex(b"") == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


def test_both_dialects_reproduce_the_interop_golden_digests() -> None:
    assert ReferenceDialect().commit(WORKED_PAYLOAD, WORKED_NONCE) == DIGEST_A
    assert BookDialect().commit(WORKED_PAYLOAD, WORKED_NONCE) == DIGEST_B
    assert DIGEST_A != DIGEST_B  # the two digests share nothing (INTEROP §3.1)


def test_reference_dialect_reproduces_sample_run_step0_commit() -> None:
    dialect = ReferenceDialect()
    assert dialect.commit(SAMPLE_SPEC_PAYLOAD, SAMPLE_SPEC_NONCE) == SAMPLE_SPEC_COMMIT
    assert dialect.verify(SAMPLE_SPEC_PAYLOAD, SAMPLE_SPEC_NONCE, SAMPLE_SPEC_COMMIT)


def test_reference_dialect_is_the_agreement_signature_construction() -> None:
    # INTEROP §3.3: the agreement signature is ALWAYS the pipe-append form, even when the
    # per-step dialect negotiated for the series is `book`.
    assert ReferenceDialect().commit(AGREEMENT_TERMS, AGREEMENT_NONCE) == AGREEMENT_SIGNATURE
