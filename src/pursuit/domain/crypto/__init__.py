"""Crypto seam — canonical hashing, commit dialects, Ed25519 signing (D3/D14).

``make_hash_dialect`` is the single construction point for the commit dialect: the
dialect id comes from the SIGNED shared ``crypto`` config block (rule-23 locked), never
from defaults scattered around the engine. Default ``reference`` — the league
conformance-kit CORE form and our shipped ``crypto.dialect`` (a partial/absent crypto
block must NOT silently fall back to a construction the pod does not use = a 0/0 trap);
``book`` (ruling A1, nonce-inside-JSON) stays available by explicit rule-23 negotiation.
"""

from __future__ import annotations

from collections.abc import Mapping

from pursuit.domain.crypto.canonical import canonical_bytes, sha256_hex
from pursuit.domain.crypto.dialects import (
    BookDialect,
    HashDialect,
    ReferenceDialect,
    generate_nonce,
)
from pursuit.domain.crypto.signing import generate_keypair, sign, verify_signature
from pursuit.exceptions import ConfigError

_DIALECTS: dict[str, type[HashDialect]] = {
    BookDialect.name: BookDialect,
    ReferenceDialect.name: ReferenceDialect,
}

#: League CORE form (conformance kit) + our shipped crypto.dialect — the safe default.
DEFAULT_DIALECT = ReferenceDialect.name


def make_hash_dialect(crypto_cfg: Mapping[str, object] | None = None) -> HashDialect:
    """Build the negotiated commit dialect from the signed ``crypto`` config block.

    A missing block or missing ``dialect`` key means ``reference`` (the CORE form).
    Anything outside the negotiable set is a ConfigError — fail fast at startup, never
    mid-series (exceptions.py discipline).
    """
    name = (crypto_cfg or {}).get("dialect", DEFAULT_DIALECT)
    if not isinstance(name, str) or name not in _DIALECTS:
        raise ConfigError(
            f"unknown crypto dialect {name!r}; negotiable values: {sorted(_DIALECTS)}"
        )
    return _DIALECTS[name]()


__all__ = [
    "DEFAULT_DIALECT",
    "BookDialect",
    "HashDialect",
    "ReferenceDialect",
    "canonical_bytes",
    "generate_keypair",
    "generate_nonce",
    "make_hash_dialect",
    "sha256_hex",
    "sign",
    "verify_signature",
]
