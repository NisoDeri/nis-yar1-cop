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


def _optional_private(config: ConfigManager, path: str, default: Any) -> Any:
    """Private-config read where absence is legal (runtime ledger state, not a term)."""
    try:
        return config.private(path)
    except ConfigError:
        return default


def build_identity(config: ConfigManager, public_pem: bytes) -> dict[str, Any]:
    """The unsigned identity block (INTEROP §2.1) + D14/rule-37 additive keys."""
    identity: dict[str, Any] = {
        "group_id": config.private("game.group_id"),
        "group_name": config.private("game.group_name"),
        "members": config.private("game.members"),
        "repos": config.private("game.repos"),
        "mcp_servers": config.private("game.mcp_servers"),
        "llm_model": config.private("trash_talk.model"),
        "ed25519_public_key": public_pem.decode("ascii"),
        "counted_games_so_far": int(_optional_private(config, "game.counted_games_so_far", 0)),
    }
    spec = _optional_private(config, "game.spec", None)  # step0 owns full HW collection
    if spec is not None:
        identity["spec"] = spec
    return identity


def build_agreement_message(config: ConfigManager, public_pem: bytes) -> dict[str, Any]:
    """One signed ``negotiate`` body: fresh nonce, §3.3 signature, unsigned identity."""
    terms = build_terms(config)
    nonce = generate_nonce()
    return {
        "terms": terms,
        "nonce": nonce,
        "signature": agreement_signature(terms, nonce),
        "identity": build_identity(config, public_pem),
    }
