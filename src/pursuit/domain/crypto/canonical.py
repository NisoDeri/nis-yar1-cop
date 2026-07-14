"""Canonical JSON bytes — the ONE serialization every league hash runs over.

INTEROP §3 ("byte-exact or interop dies") pins the compact canonical form:

    json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))

encoded as UTF-8 before hashing.

- ``sort_keys=True`` — key order never matters; both peers hash identical bytes.
- ``separators=(",", ":")`` — compact, no spaces. The SPACED ``consensus_signature``
  hasher (declaration blocks, mutual-agreement fields, INTEROP §3.4) is a different
  function in the report layer — never conflate the two (INTEROP §7 landmine 7).
- ``ensure_ascii=False`` — non-ASCII (Hebrew hints) hashes as raw UTF-8 bytes, not
  ``\\uXXXX`` escapes; a peer hashing with Python's default produces different digests
  for any non-ASCII hint.

Pure functions, zero I/O — domain-layer discipline (architecture.md §1).
"""

from __future__ import annotations

import hashlib
import json


def canonical_bytes(obj: object) -> bytes:
    """Serialize ``obj`` to compact canonical JSON, UTF-8 encoded (INTEROP §3)."""
    text = json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return text.encode("utf-8")


def sha256_hex(data: bytes) -> str:
    """Lowercase hex SHA-256 of ``data`` — the league's only digest primitive."""
    return hashlib.sha256(data).hexdigest()
