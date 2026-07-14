"""Signed-agreement terms: build, sign, verify (INTEROP §2.1/§3.3/§4; DECISIONS D3).

The wire ``terms`` dict is the COMPLETE signed contract — a stock reference peer does an
exact-dict-equality check, so extra keys break the handshake (§7 landmine 9). D3 dialect
ids are injected on the wire ONLY under ``negotiation.wire_dialect_terms``; the opt-in E6
``rule_deltas`` block (mutually-agreed floor RAISES) is added the same way. Pure functions
over loaded config trees — zero I/O (architecture.md domain layer)."""

from __future__ import annotations

from typing import Any

from pursuit.domain.crypto.canonical import canonical_bytes
from pursuit.domain.crypto.dialects import ReferenceDialect
from pursuit.exceptions import ConfigError, NegotiationError
from pursuit.shared.config import ConfigManager

#: Wire term -> game.json dotted path. EXACTLY INTEROP §2.1's 14 keys (order is cosmetic).
WIRE_TERM_SOURCES: dict[str, str] = {
    "board_size": "board_and_agents.grid_size",
    "smell_grid_size": "pheromones.pheromone_grid_size",
    "decay_per_step": "pheromones.pheromone_decay",
    "emit_intensity": "pheromones.pheromone_center_intensity",
    "min_center_intensity": "pheromones.pheromone_min_center_intensity",
    "max_steps": "movement_and_barriers.max_moves",
    "barriers_max": "movement_and_barriers.max_barriers",
    "setting": "world.map_area",
    "hint_max_words": "world.hint_max_words",
    "axis_origin_corner": "board_and_agents.axis_origin_corner",
    "axis_start_index": "board_and_agents.axis_start_index",
    "thief_start": "board_and_agents.thief_start",
    "cop_start": "board_and_agents.cop_start",
    "num_games": "network_and_league.num_games",
}

#: D3 dialect ids -> config paths; injected only under ``negotiation.wire_dialect_terms``.
DIALECT_TERM_SOURCES: dict[str, str] = {
    "crypto_dialect": "crypto.dialect",
    "scent_dialect": "pheromones.dialect",
}

#: Shared game.json flag gating the extended (dialects-on-the-wire) terms shape.
WIRE_DIALECT_FLAG = "negotiation.wire_dialect_terms"

#: E6 rule-delta key -> game.json path holding its BOOK MINIMUM (a delta may only RAISE).
RULE_DELTA_SOURCES: dict[str, str] = {
    "max_moves": "movement_and_barriers.max_moves",
    "max_barriers": "movement_and_barriers.max_barriers",
    "hint_max_words": "world.hint_max_words",
    "token_budget": "network_and_league.token_budget_per_series",
}

#: Shared game.json key carrying the proposed overrides (absent = capability OFF).
RULE_DELTAS_FLAG = "negotiation.propose_rule_deltas"


def _wire_dialect_terms_enabled(config: ConfigManager) -> bool:
    """Read the shared extended-shape flag; absent means False (stock 14-key shape)."""
    try:
        flag = config.game(WIRE_DIALECT_FLAG)
    except ConfigError:
        return False
    if not isinstance(flag, bool):
        raise ConfigError(f"'{WIRE_DIALECT_FLAG}' must be a JSON boolean, got {flag!r}")
    return flag


def _proposed_rule_deltas(config: ConfigManager) -> dict[str, Any]:
    """Validate opt-in E6 deltas (absent -> ``{}``). SAFETY INVARIANT: each must RAISE its
    parameter above the book minimum, else (unknown/non-numeric/at-or-below) ConfigError."""
    try:
        proposed = config.game(RULE_DELTAS_FLAG)
    except ConfigError:
        return {}
    if not isinstance(proposed, dict):
        raise ConfigError(f"'{RULE_DELTAS_FLAG}' must be a JSON object, got {proposed!r}")
    for key, value in proposed.items():
        if key not in RULE_DELTA_SOURCES:
            raise ConfigError(f"unknown rule delta '{key}' (not a negotiable parameter)")
        floor = config.game(RULE_DELTA_SOURCES[key])
        if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= floor:
            raise ConfigError(f"rule delta '{key}'={value!r} must RAISE above minimum {floor!r}")
    return dict(proposed)


def build_terms(config: ConfigManager) -> dict[str, Any]:
    """Signed wire ``terms`` from SHARED game.json: 14 INTEROP §2.1 keys, +2 dialect keys
    iff ``wire_dialect_terms`` on, +``rule_deltas`` iff E6 proposed. Missing -> ConfigError."""
    terms: dict[str, Any] = {key: config.game(path) for key, path in WIRE_TERM_SOURCES.items()}
    if _wire_dialect_terms_enabled(config):
        for key, path in DIALECT_TERM_SOURCES.items():
            terms[key] = config.game(path)
    deltas = _proposed_rule_deltas(config)
    if deltas:
        terms["rule_deltas"] = deltas
    return terms


def accept_rule_deltas(theirs: dict[str, Any], ours: dict[str, Any]) -> dict[str, Any]:
    """Merge two E6 blocks iff both peers signed value-equal deltas; any unmatched key or
    diverging value refuses (NegotiationError). Returns the merged block."""
    if not isinstance(theirs, dict) or not isinstance(ours, dict):
        raise NegotiationError("rule_deltas block is not a dict")
    for key in sorted(set(ours) | set(theirs)):
        if key not in theirs:
            raise NegotiationError(f"rule delta '{key}': not signed by opponent")
        if key not in ours:
            raise NegotiationError(f"rule delta '{key}': unsigned extra from opponent")
        if not _same_wire_value(ours[key], theirs[key]):
            raise NegotiationError(f"rule delta '{key}': ours={ours[key]!r} theirs={theirs[key]!r}")
    return dict(ours)


def agreement_signature(terms: dict[str, Any], nonce: str) -> str:
    """Agreement signature ``sha256(canonical_json(terms) + "|" + nonce)`` (INTEROP §3.3):
    the dialect-A pipe-append form a reference peer verifies. Golden §2.1 -> ``167fef4e...``."""
    return ReferenceDialect().commit(terms, nonce)


def verify_agreement_signature(terms: dict[str, Any], nonce: str, signature: str) -> bool:
    """Constant-time check of an opponent's agreement signature (INTEROP §4 step 3b)."""
    return ReferenceDialect().verify(terms, nonce, signature)


def verify_terms(mine: dict[str, Any], theirs: dict[str, Any]) -> None:
    """Exact-dict-equality gate (INTEROP §4 step 3a) — NegotiationError on divergence.

    Per-key equality is on canonical WIRE bytes, so types matter (float vs str vs int vs
    bool all mismatch — §7 landmine 9); names the FIRST diverging key in sorted order.
    """
    if not isinstance(theirs, dict):
        raise NegotiationError(f"opponent terms is not a dict: {type(theirs).__name__}")
    for key in sorted(set(mine) | set(theirs)):
        if key not in theirs:
            raise NegotiationError(f"terms mismatch at '{key}': missing from opponent terms")
        if key not in mine:
            raise NegotiationError(f"terms mismatch at '{key}': unagreed extra term from opponent")
        if not _same_wire_value(mine[key], theirs[key]):
            raise NegotiationError(
                f"terms mismatch at '{key}': ours={mine[key]!r} theirs={theirs[key]!r}"
            )


def _same_wire_value(a: Any, b: Any) -> bool:
    """Byte-exact equality under the compact canonical JSON (the wire's own semantics)."""
    try:
        return canonical_bytes(a) == canonical_bytes(b)
    except TypeError:  # non-JSON value cannot have come off the wire — never equal
        return False
