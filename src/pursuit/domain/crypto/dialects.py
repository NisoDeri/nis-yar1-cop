"""Commit-reveal hash dialects — the D3 crypto seam (nonce inside vs pipe-appended).

Book rule 18 seals each step: the true position/move/intent never travel in the clear;
only ``commit = sha256(...)`` does, with the nonce withheld until the end-game audit.
Two constructions exist in the wild (INTEROP §3.1):

- ``book`` (dialect B) — nonce a key INSIDE the canonical JSON, per the book's chapter-5
  schema. AUTHORITATIVE for league cross-audits (NotebookLM ruling A1, 2026-07-13) and
  therefore our default.
- ``reference`` (dialect A) — nonce pipe-appended AFTER the canonical JSON, as the stock
  reference peer (rmisegal/Game-P2P-Cop-Chase) computes it. Kept for compatibility with
  stock-reference partners, selected only by explicit negotiation + rule-23 lock. This
  construction is also ALWAYS the agreement-signature form (INTEROP §3.3), regardless of
  the per-step dialect negotiated.

An unnegotiated dialect mismatch "fails" every step at cross-audit → false
tamper_forfeit; the dialect id is locked inside the signed shared terms (DECISIONS D3).

Nonces come from ``secrets`` (cryptographic, deliberately NOT an injected
``random.Random`` — a predictable nonce would let the opponent brute-force the sealed
payload before the reveal).
"""

from __future__ import annotations

import secrets
from collections.abc import Mapping
from typing import ClassVar

from pursuit.domain.crypto.canonical import canonical_bytes, sha256_hex
from pursuit.exceptions import CryptoError

#: 16 random bytes → 32 lowercase hex chars on the wire (INTEROP §2.1, frozen protocol).
NONCE_BYTES = 16


def generate_nonce() -> str:
    """Fresh commit nonce — secret until the final audit (book rule 18)."""
    return secrets.token_hex(NONCE_BYTES)


class HashDialect:
    """Base commit dialect: subclasses define ``commit``; ``verify`` is shared."""

    name: ClassVar[str]

    def commit(self, payload: Mapping[str, object], nonce: str) -> str:
        """Hex digest sealing ``payload`` under ``nonce``."""
        raise NotImplementedError

    def verify(self, payload: Mapping[str, object], nonce: str, digest: str) -> bool:
        """Constant-time check that ``digest`` seals ``payload`` under ``nonce``.

        Total over adversarial input: a malformed revealed payload (e.g. a smuggled
        ``nonce`` key under the book dialect) is a failed verification, never a crash.
        """
        try:
            expected = self.commit(payload, nonce)
        except CryptoError:
            return False
        return secrets.compare_digest(expected.encode("ascii"), digest.encode("utf-8"))


class BookDialect(HashDialect):
    """Dialect B — nonce a key INSIDE the canonical JSON (ruling A1; our default).

    ``commit = sha256(canonical_json({**payload, "nonce": nonce}))``
    """

    name = "book"

    def commit(self, payload: Mapping[str, object], nonce: str) -> str:
        if "nonce" in payload:
            raise CryptoError("sealed payload must not carry the reserved 'nonce' key")
        return sha256_hex(canonical_bytes({**payload, "nonce": nonce}))


class ReferenceDialect(HashDialect):
    """Dialect A — nonce pipe-appended OUTSIDE the canonical JSON (stock reference).

    INTEROP §3.1 defines ``sha256(canonical_json(payload) + "|" + nonce)`` with the join
    done on ``str`` and the result UTF-8 encoded; because ``"|"`` is ASCII and UTF-8
    encoding distributes over concatenation, joining the encoded bytes below is
    byte-identical (verified against the sample-run commits, 19/19 records).
    """

    name = "reference"

    def commit(self, payload: Mapping[str, object], nonce: str) -> str:
        return sha256_hex(canonical_bytes(payload) + b"|" + nonce.encode("utf-8"))
