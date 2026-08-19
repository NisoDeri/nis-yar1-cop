"""Outbound agreement-message assembly (INTEROP §2.1) — split from handshake.py.

Builds the one signed ``negotiate`` body a peer pushes: terms (domain/negotiation),
fresh nonce, §3.3 pipe-append signature, and the UNSIGNED identity block. The identity
carries our D14/rule-37 additive keys — the Ed25519 PUBLIC key and the
counted-games-so-far ledger count (ruling A9b) — which are later locked into the signed
pre-game declaration; a stock reference peer simply carries them along (identity is
deliberately outside the crypto, INTEROP §2.1).
"""

from __future__ import annotations

from typing import Any

from pursuit.domain.crypto.dialects import generate_nonce
from pursuit.domain.negotiation import agreement_signature, build_terms
from pursuit.exceptions import ConfigError
from pursuit.shared.config import ConfigManager

SCENT_MODEL_SHA256: dict[str, str] = {
    "reference": "81ebee59640e80eae8ca9ee5f86abd26e7edf5cdbb27d15925cb6ee45ca6ddf4",
    "multiplicative_book_v1": "934c220d5bf62acaa3297c6c9d723ea954c220260b02292ca17f6d5daef9f4d9",
}
WIRE_SHAPE_SHA256 = "229ae6487a418c3fcb6da9be404de2f2533c288ebc228811bff6dedc4164d6f7"
INFO_MODE_SHA256 = "020947daeeb3f73494af9b04201326791742c7184085456e3517d21981ee1202"


def _optional_private(config: ConfigManager, path: str, default: Any) -> Any:
    """Private-config read where absence is legal (runtime ledger state, not a term)."""
    try:
        return config.private(path)
    except ConfigError:
        return default


def build_identity(config: ConfigManager, public_pem: bytes) -> dict[str, Any]:
    """The unsigned identity block (INTEROP §2.1) + D14/rule-37 additive keys."""
    counted = int(_optional_private(config, "game.counted_games_so_far", 0))
    identity: dict[str, Any] = {
        "group_id": config.private("game.group_id"),
        "group_name": config.private("game.group_name"),
        "members": config.private("game.members"),
        "repos": config.private("game.repos"),
        "mcp_servers": config.private("game.mcp_servers"),
        "llm_model": config.private("trash_talk.model"),
        "ed25519_public_key": public_pem.decode("ascii"),
        # Three spellings of the same counter — different league peers read different keys;
        # sending all three means an opponent never has to default our prior count to 0.
        "counted_games_so_far": counted,
        "counted_games_played": counted,
        "counted_matches_played": counted,
    }
    commit = _optional_private(config, "game.github_commit", None)
    if commit is not None:  # so the opponent's report records OUR commit, not "unknown"
        identity["github_commit"] = str(commit)
    spec = _optional_private(config, "game.spec", None)  # step0 owns full HW collection
    if spec is not None:
        identity["spec"] = spec
    return identity


def build_lock_declarations(config: ConfigManager) -> dict[str, Any]:
    """Top-level optional negotiate extras from the league-kit locked-model registry."""
    declarations: dict[str, Any] = {
        "schema_version": str(config.game("schema_version")),
        "config_sha256": config.config_sha256(),
        "wire_shape_sha256": WIRE_SHAPE_SHA256,
        "info_mode_sha256": INFO_MODE_SHA256,
        "commit_order": "thief_first",
    }
    scent_hash = SCENT_MODEL_SHA256.get(str(config.game("pheromones.dialect")))
    if scent_hash is not None:
        declarations["scent_model_sha256"] = scent_hash
    return declarations


def build_agreement_message(
    config: ConfigManager,
    public_pem: bytes,
    *,
    sub_game_number: int | None = None,
    role: str | None = None,
) -> dict[str, Any]:
    """One signed ``negotiate`` body: fresh nonce, §3.3 signature, unsigned identity.

    ``sub_game_number``/``role`` are the §7.2 pairing declaration — they ride TOP-LEVEL,
    beside (never inside) ``terms`` so they cannot disturb the signature. Either is only
    written when supplied; ``None`` means "declare nothing", exactly what a stock reference
    peer does (an omission never triggers a refusal — INTEROP §7.2).
    """
    terms = build_terms(config)
    nonce = generate_nonce()
    message: dict[str, Any] = {
        "terms": terms,
        "nonce": nonce,
        "signature": agreement_signature(terms, nonce),
        "identity": build_identity(config, public_pem),
    }
    message.update(build_lock_declarations(config))
    if sub_game_number is not None:
        message["sub_game_number"] = int(sub_game_number)
    if role is not None:
        message["role"] = str(role)
    return message
