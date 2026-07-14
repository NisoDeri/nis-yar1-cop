"""CORE-vector conformance: our crypto/id/scent seams reproduce the league interop
kit byte-for-byte.

The kit (rmisegal/copthief-league-protocol) is cloned, gitignored, under
``reference/copthief-league-protocol/vectors``. When it is absent — CI without the
kit — the whole module skips so the pipeline stays green. When present, every CORE
vector is re-derived at runtime and asserted equal to the published golden value:
the ``ensure_ascii=False`` Hebrew form, the float ``0.1`` round-trip, the sorted
game-uid, and the reference scent field. A single divergent byte here is a real
cross-team ``tamper_forfeit`` in a live series (INTEROP §3).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

_KIT = Path(__file__).resolve().parents[2] / "reference" / "copthief-league-protocol"
VECTORS_DIR = _KIT / "vectors"

if not VECTORS_DIR.exists():
    pytest.skip(
        f"league interop kit not cloned at {VECTORS_DIR}; conformance skipped",
        allow_module_level=True,
    )

from pursuit.domain.crypto.canonical import canonical_bytes, sha256_hex  # noqa: E402
from pursuit.domain.crypto.dialects import BookDialect, ReferenceDialect  # noqa: E402
from pursuit.domain.game_ids import derive_game_ids  # noqa: E402
from pursuit.domain.scent import make_scent_model  # noqa: E402


def load(name: str) -> dict:
    """Load one vector file, decoded as UTF-8 (kit hints carry Hebrew/emoji)."""
    return json.loads((VECTORS_DIR / f"{name}.json").read_text(encoding="utf-8"))


# Shared pheromone terms (decay/min-center) come from the signed-terms vector, not
# literals — the emit field depends only on board_size/grid/intensity read per case.
_TERMS = load("terms_signature")["vectors"][0]["terms"]


@pytest.mark.parametrize("case", load("commit_reveal")["vectors"])
def test_commit_reveal_reference_form(case: dict) -> None:
    """Each sealed record re-hashes to its published reference commit (CORE form)."""
    got = ReferenceDialect().commit(case["payload"], case["nonce"])
    assert got == case["commit"], case["note"]


def test_commit_reveal_divergent_forms() -> None:
    """The two full-record constructions stay distinct: reference is CORE, book is ch.5."""
    div = load("commit_reveal")["divergent_forms"]
    payload, nonce = div["payload"], div["nonce"]
    assert ReferenceDialect().commit(payload, nonce) == div["reference_form"]
    assert BookDialect().commit(payload, nonce) == div["book_ch5_listing_form"]


@pytest.mark.parametrize("case", load("terms_signature")["vectors"])
def test_terms_signature(case: dict) -> None:
    """Agreement signature over the terms — pins the float 0.1 shortest round-trip."""
    got = ReferenceDialect().commit(case["terms"], case["nonce"])
    assert got == case["signature"]


@pytest.mark.parametrize("case", load("game_uid")["vectors"])
def test_game_uid_deterministic_and_order_free(case: dict) -> None:
    """derive_game_ids reproduces the uid and is invariant to group order (sorted)."""
    groups = [case["group_a"], case["group_b"]]
    _, uid = derive_game_ids(case["terms"], groups)
    assert uid == case["game_uid"]
    _, swapped = derive_game_ids(case["terms"], list(reversed(groups)))
    assert swapped == uid


@pytest.mark.parametrize("case", load("pheromone")["emit"])
def test_pheromone_emit_field(case: dict) -> None:
    """One reference emission reproduces the kit's wire-rounded scent field."""
    model = make_scent_model(
        {
            "dialect": "reference",
            "board_size": case["board_size"],
            "smell_grid_size": case["grid_size"],
            "emit_intensity": case["intensity"],
            "decay_per_step": _TERMS["decay_per_step"],
            "min_center_intensity": _TERMS["min_center_intensity"],
        }
    )
    model.deposit(tuple(case["center"]))
    field = {key: round(value, 3) for key, value in model.snapshot().items()}
    assert field == case["field"], case["note"]


@pytest.mark.parametrize("case", load("canonical_json")["vectors"])
def test_canonical_json_bytes_and_hash(case: dict) -> None:
    """Canonical bytes + sha256 match; the Hebrew/emoji cases pin ensure_ascii=False."""
    raw = canonical_bytes(case["object"])
    assert raw.decode("utf-8") == case["canonical"], case["note"]
    assert sha256_hex(raw) == case["sha256"], case["note"]
