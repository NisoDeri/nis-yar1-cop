"""Unit tests for pursuit.domain.crypto.signing — Ed25519 declaration signing (D14)."""

from __future__ import annotations

import base64

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

from pursuit.domain.crypto.signing import (
    SIGNATURE_PREFIX,
    generate_keypair,
    sign,
    verify_signature,
)
from pursuit.exceptions import CryptoError

PAYLOAD = {
    "declaration_type": "pre_game_declaration",
    "group_id": "nis-yar1",
    "counted_games_so_far": 2,  # rule 37 ledger lives INSIDE the signed JSON (A9b)
    "setting": "חיפה",
}


def _ec_pems() -> tuple[bytes, bytes]:
    """A valid-PEM but non-Ed25519 keypair, for wrong-algorithm error paths."""
    key = ec.generate_private_key(ec.SECP256R1())
    private = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    public = key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return private, public


def test_generate_keypair_emits_distinct_pem_pairs() -> None:
    private_pem, public_pem = generate_keypair()
    assert private_pem.startswith(b"-----BEGIN PRIVATE KEY-----")
    assert public_pem.startswith(b"-----BEGIN PUBLIC KEY-----")
    assert generate_keypair() != (private_pem, public_pem)  # fresh entropy each call


def test_sign_verify_roundtrip_and_wire_format() -> None:
    private_pem, public_pem = generate_keypair()
    signature = sign(private_pem, PAYLOAD)
    assert signature.startswith(SIGNATURE_PREFIX)
    raw = base64.b64decode(signature.removeprefix(SIGNATURE_PREFIX), validate=True)
    assert len(raw) == 64  # Ed25519 signature size
    assert verify_signature(public_pem, PAYLOAD, signature)


def test_key_order_is_irrelevant_under_canonical_bytes() -> None:
    private_pem, public_pem = generate_keypair()
    signature = sign(private_pem, PAYLOAD)
    reordered = dict(reversed(list(PAYLOAD.items())))
    assert verify_signature(public_pem, reordered, signature)


def test_tampered_payload_fails_verification() -> None:
    private_pem, public_pem = generate_keypair()
    signature = sign(private_pem, PAYLOAD)
    assert not verify_signature(public_pem, {**PAYLOAD, "counted_games_so_far": 0}, signature)
    assert not verify_signature(public_pem, {**PAYLOAD, "extra": 1}, signature)


def test_wrong_public_key_fails_verification() -> None:
    private_pem, _ = generate_keypair()
    _, other_public = generate_keypair()
    signature = sign(private_pem, PAYLOAD)
    assert not verify_signature(other_public, PAYLOAD, signature)


@pytest.mark.parametrize(
    "bad_signature",
    ["", "ed25519:", "ed25519:!!!not-base64!!!", "rsa:AAAA", "ed25519:QUJD", None],
)
def test_malformed_signature_strings_return_false(bad_signature: str | None) -> None:
    _, public_pem = generate_keypair()
    assert not verify_signature(public_pem, PAYLOAD, bad_signature)


def test_garbage_or_wrong_algorithm_public_key_returns_false() -> None:
    private_pem, _ = generate_keypair()
    signature = sign(private_pem, PAYLOAD)
    assert not verify_signature(b"not a pem at all", PAYLOAD, signature)
    assert not verify_signature(private_pem, PAYLOAD, signature)  # private-as-public PEM
    _, ec_public = _ec_pems()
    assert not verify_signature(ec_public, PAYLOAD, signature)  # valid PEM, not Ed25519


def test_sign_with_unusable_key_material_raises_crypto_error() -> None:
    _, public_pem = generate_keypair()
    with pytest.raises(CryptoError):
        sign(b"not a pem at all", PAYLOAD)
    with pytest.raises(CryptoError):
        sign(public_pem, PAYLOAD)  # public half where a private key is required
    ec_private, _ = _ec_pems()
    with pytest.raises(CryptoError):
        sign(ec_private, PAYLOAD)  # valid PEM private key, wrong algorithm
