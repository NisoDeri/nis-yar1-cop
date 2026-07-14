"""Ed25519 signing for the declaration and step-0 record (DECISIONS D14, rulings A7/A9b).

No staff-distributed key exists: each team generates its own Ed25519 keypair; PUBLIC keys
are exchanged with the partner and locked into the signed pre-game declaration, so the
hardware/spec record and the counted-games-so-far ledger (rule 37) cannot be altered
mid-series. PRIVATE keys live OUTSIDE the repo at runtime (rules 39-40; ``.gitignored``
path in the private config) — every function here is pure over passed-in PEM key
material: no file I/O, no key store, no module state.

Wire format (INTEROP §5.5 item 5): ``"ed25519:<base64>"`` over ``canonical_bytes(payload)``,
so key order and unicode in the signed dict never matter.
"""

from __future__ import annotations

import base64
from collections.abc import Mapping

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

from pursuit.domain.crypto.canonical import canonical_bytes
from pursuit.exceptions import CryptoError

SIGNATURE_PREFIX = "ed25519:"


def generate_keypair() -> tuple[bytes, bytes]:
    """Fresh Ed25519 keypair as ``(private_pem_bytes, public_pem_bytes)``.

    The caller persists the private half OUTSIDE the repo; only the public half ever
    travels (inside the pre-game declaration, D14).
    """
    private = ed25519.Ed25519PrivateKey.generate()
    private_pem = private.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    public_pem = private.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return private_pem, public_pem


def sign(private_pem: bytes, payload: Mapping[str, object]) -> str:
    """Sign ``canonical_bytes(payload)``; return the ``ed25519:<base64>`` wire string.

    Raises CryptoError on unusable key material — that is OUR configuration bug, so we
    fail fast at startup rather than emit an unverifiable declaration.
    """
    try:
        key = serialization.load_pem_private_key(private_pem, password=None)
    except (ValueError, TypeError) as exc:
        raise CryptoError(f"unusable Ed25519 private key material: {exc}") from exc
    if not isinstance(key, ed25519.Ed25519PrivateKey):
        raise CryptoError("private key is not Ed25519 (D14 mandates Ed25519)")
    raw = key.sign(canonical_bytes(payload))
    return SIGNATURE_PREFIX + base64.b64encode(raw).decode("ascii")


def verify_signature(public_pem: bytes, payload: Mapping[str, object], signature_str: str) -> bool:
    """True iff ``signature_str`` is a valid signature over ``payload`` by that key.

    Total over adversarial input: a malformed key, prefix, base64 blob or signature is
    a failed verification (False), never a crash — opponent-supplied material must not
    be able to abort our audit.
    """
    if not isinstance(signature_str, str) or not signature_str.startswith(SIGNATURE_PREFIX):
        return False
    try:
        key = serialization.load_pem_public_key(public_pem)
    except (ValueError, TypeError):
        return False
    if not isinstance(key, ed25519.Ed25519PublicKey):
        return False
    try:
        raw = base64.b64decode(signature_str[len(SIGNATURE_PREFIX) :], validate=True)
        key.verify(raw, canonical_bytes(payload))
    except (InvalidSignature, ValueError):
        return False
    return True
