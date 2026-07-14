"""Unit tests for pursuit.domain.protocol / protocol_audit — INTEROP §2 byte fidelity.

Golden dicts below are copied verbatim from planning/INTEROP.md §2.2/§2.3/§2.4;
the commit vector is the professor's sample-run record (§3.1, dialect A, verified
2026-07-13). No sockets, no processes, no LLMs — pure envelope logic.
"""

from __future__ import annotations

import pytest

from pursuit.constants import Direction, MoveType
from pursuit.domain.crypto import ReferenceDialect
from pursuit.domain.protocol import (
    CAPTURE_CONCESSION_HINT,
    FALLBACK_HINT,
    SILENCE_HINT,
    ControlMessage,
    TurnMessage,
)
from pursuit.domain.protocol_audit import (
    HOLD_WIRE,
    SEALED_STEP_KEYS,
    AuditPayload,
    AuditRecord,
    format_move_string,
    parse_move_string,
    sealed_payload,
)
from pursuit.exceptions import TransportError

# --- Golden wire bodies, verbatim from INTEROP §2.2 / §2.3 / §2.4 -----------------

GOLDEN_TURN = {
    "step": 4,
    "sender": "police",
    "hint": "I'm sweeping the blocks near Central Park.",
    "smell_grid": {"2,3": 0.9, "2,4": 0.6, "1,3": 0.6, "3,3": 0.6, "2,2": 0.6, "1,2": 0.3},
    "commit": "eb9e7590c3abae35ea775f7787aadbfeaa430ddc5e47cf890eb7cb62ee204add",
    "timestamp": "2026-07-11T10:52:41.101957+00:00",
    "barrier_placed": [2, 5],
    "capture_claim": [2, 3],
    "claim_response": None,
    "win_claim": None,
}

GOLDEN_STEP1_PAYLOAD = {
    "step": 1, "state": "grid=7x7;self=[4, 3];barriers=[]", "position": [4, 3],
    "move": "MOVE:S", "intent": "truth", "verdict": "truth",
    "hint": "I keep moving through the streets.",
    "prompt_discussion": {"llm_prompt": "...", "llm_reasoning": "...",
                          "bluff_classification": "truth"},
    "model": "stub", "tokens_step": 0, "tokens_total": 0,
    "response_seconds": 0.0, "random_move": False,
}
GOLDEN_STEP1_NONCE = "22fdde9fd1571e88dfe922d6190dffcc"
GOLDEN_STEP1_COMMIT = "eb9e7590c3abae35ea775f7787aadbfeaa430ddc5e47cf890eb7cb62ee204add"

GOLDEN_AUDIT = {
    "sender": "thief",
    "result_claim": "capture",
    "records": [
        {"payload": {"step": 0, "type": "system_spec", "model": "qwen2.5:7b",
                     "code_version": "1.12", "group_name": "Nis-Yar-1", "sub_game_number": 1},
         "nonce": "5f72978b482c02eeb3d8a20b01e619b9",
         "commit": "78a31c516536350bfdb8a3ee4ba3e131ae0676d7b4b95d02ff94b1aa84b85e65"},
        {"payload": GOLDEN_STEP1_PAYLOAD,
         "nonce": GOLDEN_STEP1_NONCE,
         "commit": GOLDEN_STEP1_COMMIT},
    ],
}

GOLDEN_CONTROL = {
    "kind": "enable", "sender": "police", "sub_game_number": 1,
    "status": "PLAYING", "step_budget": 30.0, "payload": None,
}


# --- TurnMessage -------------------------------------------------------------------

def test_turn_golden_round_trip() -> None:
    msg = TurnMessage.from_wire(GOLDEN_TURN)
    assert msg.step == 4
    assert msg.sender == "police"
    assert msg.smell_grid["2,3"] == 0.9
    assert msg.barrier_placed == [2, 5]
    assert msg.capture_claim == [2, 3]
    assert msg.claim_response is None and msg.win_claim is None
    assert msg.to_wire() == GOLDEN_TURN  # byte-faithful: exact field names and values


def test_turn_optional_fields_default_null() -> None:
    minimal = {k: GOLDEN_TURN[k]
               for k in ("step", "sender", "hint", "smell_grid", "commit", "timestamp")}
    msg = TurnMessage.from_wire(minimal)
    assert msg.to_wire() == {**minimal, "barrier_placed": None, "capture_claim": None,
                             "claim_response": None, "win_claim": None}


@pytest.mark.parametrize("missing", ["step", "sender", "hint", "smell_grid", "commit",
                                     "timestamp"])
def test_turn_missing_required_rejected(missing: str) -> None:
    data = {k: v for k, v in GOLDEN_TURN.items() if k != missing}
    with pytest.raises(TransportError, match=missing):
        TurnMessage.from_wire(data)


def test_turn_unknown_key_rejected() -> None:
    # Strict per §2.2: the reference's TurnMessage(**data) would TypeError on extras.
    with pytest.raises(TransportError, match="unknown"):
        TurnMessage.from_wire({**GOLDEN_TURN, "surprise": 1})


@pytest.mark.parametrize(("field", "bad"), [
    ("step", "4"), ("step", True), ("sender", "cop"), ("sender", 7),
    ("hint", None), ("smell_grid", [["2,3", 0.9]]), ("commit", 123), ("timestamp", None),
])
def test_turn_bad_types_rejected(field: str, bad: object) -> None:
    with pytest.raises(TransportError):
        TurnMessage.from_wire({**GOLDEN_TURN, field: bad})


def test_turn_body_must_be_dict() -> None:
    with pytest.raises(TransportError, match="dict"):
        TurnMessage.from_wire([GOLDEN_TURN])  # type: ignore[arg-type]


def test_fixed_literals_verbatim() -> None:
    assert CAPTURE_CONCESSION_HINT == "You got me."
    assert SILENCE_HINT == "(silence)"
    assert FALLBACK_HINT == "I keep moving through the streets."


# --- ControlMessage ----------------------------------------------------------------

def test_control_golden_round_trip() -> None:
    msg = ControlMessage.from_wire(GOLDEN_CONTROL)
    assert (msg.kind, msg.sender, msg.status) == ("enable", "police", "PLAYING")
    assert msg.to_wire() == GOLDEN_CONTROL


def test_control_unknown_keys_silently_dropped() -> None:
    # The ONE forward-compatible envelope (§2.4): extensions must not break parsing.
    msg = ControlMessage.from_wire({**GOLDEN_CONTROL, "future_field": {"x": 1}})
    assert msg == ControlMessage.from_wire(GOLDEN_CONTROL)


@pytest.mark.parametrize("data", [
    {"kind": "enable"},                       # missing sender
    {"sender": "police"},                     # missing kind
    {"kind": "explode", "sender": "police"},  # unknown kind
    {"kind": "enable", "sender": "sheriff"},  # unknown role
    "not-a-dict",
])
def test_control_rejections(data: object) -> None:
    with pytest.raises(TransportError):
        ControlMessage.from_wire(data)  # type: ignore[arg-type]


# --- AuditPayload ------------------------------------------------------------------

def test_audit_golden_round_trip() -> None:
    payload = AuditPayload.from_wire(GOLDEN_AUDIT)
    assert payload.sender == "thief"
    assert payload.result_claim == "capture"
    assert len(payload.records) == 2
    assert payload.records[1].nonce == GOLDEN_STEP1_NONCE
    assert payload.to_wire() == GOLDEN_AUDIT


def test_audit_record_payload_interior_is_extension_tolerant() -> None:
    # §2.3: commits are recomputed from the record's own payload, so extra sealed
    # keys (D9 github_commit) must parse — while record/envelope levels stay strict.
    record = {"payload": {**GOLDEN_STEP1_PAYLOAD, "github_commit": "abc123"},
              "nonce": GOLDEN_STEP1_NONCE, "commit": "00" * 32}
    parsed = AuditRecord.from_wire(record)
    assert parsed.payload["github_commit"] == "abc123"


@pytest.mark.parametrize("mutate", [
    lambda d: {**d, "extra_top": 1},                          # unknown top-level key
    lambda d: {k: v for k, v in d.items() if k != "records"},  # missing records
    lambda d: {**d, "result_claim": "tampered"},              # claim outside the set
    lambda d: {**d, "sender": "auditor"},                     # unknown role
    lambda d: {**d, "records": [{"payload": {}, "nonce": "aa"}]},   # record sans commit
    lambda d: {**d, "records": [{"payload": {}, "nonce": "aa", "commit": "bb",
                                 "rogue": 1}]},               # record-level extra key
])
def test_audit_rejections(mutate) -> None:
    with pytest.raises(TransportError):
        AuditPayload.from_wire(mutate(GOLDEN_AUDIT))


def test_audit_accepts_all_negotiated_result_claims() -> None:
    for claim in ("capture", "survival", "timeout", "technical_loss"):
        assert AuditPayload.from_wire({**GOLDEN_AUDIT, "result_claim": claim}).result_claim


# --- sealed_payload ----------------------------------------------------------------

def test_sealed_payload_reproduces_golden_record_and_commit() -> None:
    built = sealed_payload(
        state_string="grid=7x7;self=[4, 3];barriers=[]", move_string="MOVE:S",
        intent="truth", hint="I keep moving through the streets.", step=1, role="thief",
        extra={"prompt_discussion": {"llm_prompt": "...", "llm_reasoning": "...",
                                     "bluff_classification": "truth"}},
    )
    assert built == GOLDEN_STEP1_PAYLOAD  # exact key set AND values (§2.3 sample)
    # INTEROP §3.1 worked dialect-A vector: our builder's identity keys hash byte-exact.
    # (The full-record commit is NOT reproducible here: §2.3 elides the real llm
    # prompt/reasoning text behind "...", so only the 4-key worked subset is golden.)
    subset = {key: built[key] for key in ("step", "move", "intent", "state")}
    assert ReferenceDialect().commit(subset, GOLDEN_STEP1_NONCE) == (
        "b578bc307517f62029449e9fa845e6e981b8c802779713072324af02a722624b"
    )


def test_sealed_payload_exact_key_set_and_verdict_duplication() -> None:
    built = sealed_payload("grid=5x5;self=[0, 4];barriers=[[1, 1]]", "BARRIER:E",
                           "lie", "hint", 7, "police", None)
    assert tuple(built) == SEALED_STEP_KEYS  # exact keys, insertion order preserved
    assert built["verdict"] == built["intent"] == "lie"  # both present or hashes break
    assert built["position"] == [0, 4]  # derived from the state string, never passed


def test_sealed_payload_extra_adds_and_overrides_telemetry_only() -> None:
    built = sealed_payload("grid=7x7;self=[4, 3];barriers=[]", HOLD_WIRE, "truth",
                           "h", 2, "thief",
                           extra={"model": "qwen2.5:7b", "tokens_step": 41,
                                  "github_commit": "deadbeef"})
    assert (built["model"], built["tokens_step"]) == ("qwen2.5:7b", 41)
    assert built["github_commit"] == "deadbeef"  # audit-safe extension key (D9)
    with pytest.raises(TransportError, match="identity"):
        sealed_payload("grid=7x7;self=[4, 3];barriers=[]", HOLD_WIRE, "truth",
                       "h", 2, "thief", extra={"move": "MOVE:N"})


@pytest.mark.parametrize(("kwargs", "hint"), [
    ({"intent": "bluff"}, "intent"),
    ({"role": "referee"}, "sender"),
    ({"move_string": "FLY:N"}, "move"),
    ({"state_string": "no-self-here"}, "state"),
    ({"step": "1"}, "step"),
])
def test_sealed_payload_rejections(kwargs: dict, hint: str) -> None:
    base = {"state_string": "grid=7x7;self=[4, 3];barriers=[]", "move_string": "MOVE:S",
            "intent": "truth", "hint": "h", "step": 1, "role": "thief"}
    with pytest.raises(TransportError):
        sealed_payload(**{**base, **kwargs})


# --- move-string codec -------------------------------------------------------------

@pytest.mark.parametrize(("move_type", "direction", "wire"), [
    (MoveType.MOVE, Direction.N, "MOVE:N"),
    (MoveType.MOVE, Direction.S, "MOVE:S"),
    (MoveType.MOVE, Direction.E, "MOVE:E"),
    (MoveType.MOVE, Direction.W, "MOVE:W"),
    (MoveType.BARRIER, Direction.E, "BARRIER:E"),
    (MoveType.BARRIER, Direction.STAY, "BARRIER:STAY"),  # own-cell, book 5-option rule
    (MoveType.HOLD, None, "HOLD:-"),
])
def test_move_string_round_trip_table(move_type: MoveType, direction: Direction | None,
                                      wire: str) -> None:
    assert format_move_string(move_type, direction) == wire
    assert parse_move_string(wire) == (move_type, direction)


def test_bare_hold_parses_but_canonical_form_is_hold_dash() -> None:
    move_type, direction = parse_move_string("HOLD")
    assert (move_type, direction) == (MoveType.HOLD, None)
    assert format_move_string(move_type, direction) == HOLD_WIRE == "HOLD:-"


@pytest.mark.parametrize("bad", ["MOVE:STAY", "MOVE:X", "MOVE", "FLY:N", "HOLD:N",
                                 "move:N", "", ":N", 42, None])
def test_move_string_parse_rejections(bad: object) -> None:
    with pytest.raises(TransportError):
        parse_move_string(bad)


def test_move_string_format_rejections() -> None:
    with pytest.raises(TransportError):
        format_move_string(MoveType.MOVE, None)  # a MOVE must carry a direction
    with pytest.raises(TransportError):
        format_move_string(MoveType.MOVE, Direction.STAY)  # staying put is HOLD
