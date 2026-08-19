"""Settlement consensus signature — the release's SECOND canonical form (kit §6, CORE).

Unlike every other league hash (compact §2 form), the settlement consensus signature uses
``json.dumps`` DEFAULT (spaced) separators + ``sort_keys`` + ``ensure_ascii=False``, and is
SIGN-THEN-INSERT: computed over the report SANS its own signature key, then that key — the
Hebrew ``"חתימת_קונסנזוס_משותפת"`` — is added. Two teams that sign the compact form (or over
the whole per-side body) fail settlement at the exact moment they must agree, and BOTH score 0
(rule 35). The signed SCOPE is the trimmed cross-team object both honest teams derive identically
— game_id + aggregate + agreement-only sub-game rows — never the full result body (its per-side
tokens/timestamps can never match). Byte-exact vs vectors/report_consensus.json (kit sha 960499fd).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any

CONSENSUS_KEY = "חתימת_קונסנזוס_משותפת"
#: The only per-sub-game fields two honest teams must agree on (SPEC §6 scope).
_ROW_KEYS = ("sub_game_number", "roles", "result", "winner_group", "tie", "score")
_MUTUAL_ROW_KEYS = ("sub_game_number", "roles", "result", "winner_group", "score")
_AGG_KEYS = ("total_score", "sub_games_won", "ties", "winner_group", "series_tie")


def consensus_bytes(report: Mapping[str, Any]) -> bytes:
    """The §6 spaced canonical form: json.dumps defaults + sort_keys + ensure_ascii=False."""
    return json.dumps(report, sort_keys=True, ensure_ascii=False).encode("utf-8")


def consensus_signature(report: Mapping[str, Any]) -> str:
    """SHA-256 over the spaced form of the report WITHOUT its own signature key."""
    preimage = {key: value for key, value in report.items() if key != CONSENSUS_KEY}
    return hashlib.sha256(consensus_bytes(preimage)).hexdigest()


def sign_consensus(report: Mapping[str, Any]) -> dict[str, Any]:
    """Sign-then-insert: the report body plus ``{CONSENSUS_KEY: signature}``."""
    body = {key: value for key, value in report.items() if key != CONSENSUS_KEY}
    return {**body, CONSENSUS_KEY: consensus_signature(body)}


def verify_consensus(signed: Mapping[str, Any]) -> bool:
    """True iff the embedded signature matches the recomputed spaced hash (pop-and-rehash)."""
    signature = signed.get(CONSENSUS_KEY)
    return isinstance(signature, str) and signature == consensus_signature(signed)


def consensus_scope(result: Mapping[str, Any]) -> dict[str, Any]:
    """The cross-team settlement object: agreement-only aggregate + trimmed sub-game rows."""
    aggregate = result.get("final_result", {})
    return {
        "game_id": result.get("game_id"),
        "aggregate": {key: aggregate.get(key) for key in _AGG_KEYS},
        "sub_games": [{key: row.get(key) for key in _ROW_KEYS}
                      for row in result.get("sub_games", [])],
    }


def mutual_agreement_scope(result: Mapping[str, Any]) -> dict[str, Any]:
    """Outcome-only agreement hash scope; intentionally omits the row ``tie`` field."""
    aggregate = result.get("final_result", {})
    return {
        "game_id": result.get("game_id"),
        "aggregate": {key: aggregate.get(key) for key in _AGG_KEYS},
        "sub_games": [{key: row.get(key) for key in _MUTUAL_ROW_KEYS}
                      for row in result.get("sub_games", [])],
    }


def mutual_agreement_signature(result: Mapping[str, Any]) -> str:
    """SHA-256 over the spaced symmetric outcome scope both teams independently derive."""
    return hashlib.sha256(consensus_bytes(mutual_agreement_scope(result))).hexdigest()


def settlement(result: Mapping[str, Any]) -> dict[str, Any]:
    """The signed consensus block to embed in the result artifact (scope + its signature)."""
    return sign_consensus(consensus_scope(result))
