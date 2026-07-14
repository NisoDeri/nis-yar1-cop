"""Deterministic game identifiers — both peers derive identical ids with zero round-trips.

Byte-exact re-implementation of the reference derivation (INTEROP §3.2, verified against
the professor's sample-run artifacts):

    pair     = sorted([gid_a, gid_b])                     # lexicographic normalization
    game_id  = f"{pair[0]}-vs-{pair[1]}"
    seed     = canonical_json(terms) + "|" + pair[0] + "|" + pair[1]
    game_uid = str(uuid.UUID(bytes=sha256(seed)[:16]))    # first 16 digest bytes

- ``canonical_json`` is the compact hasher: ``sort_keys=True, ensure_ascii=False,
  separators=(",", ":")`` — non-ASCII hashes as raw UTF-8 bytes (INTEROP §3).
- The uid commits to the full signed terms dict: any single differing term value yields a
  different uid. Terms must come from JSON loads (float repr ``0.1`` not ``0.10``).
- The result is NOT RFC-4122-valid (version/variant bits are whatever sha256 produced).
  Never "normalize" it; copy byte-for-byte (INTEROP §7 landmine 3).
"""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Sequence

from pursuit.exceptions import ConfigError


def _canonical_json(data: dict) -> str:
    """Compact canonical JSON — the commit/config/uid hasher (INTEROP §3)."""
    return json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def derive_game_ids(terms: dict, group_ids: Sequence[str]) -> tuple[str, str]:
    """Derive ``(game_id, game_uid)`` from the signed terms and the two group ids.

    Deterministic and order-normalized: both peers call this with the same terms and the
    two gids in either order and obtain byte-identical results.
    """
    if len(group_ids) != 2 or not all(isinstance(g, str) and g for g in group_ids):
        raise ConfigError(f"derive_game_ids needs exactly two non-empty group ids: {group_ids!r}")
    if not terms:
        raise ConfigError("derive_game_ids needs the signed terms dict; got empty terms")
    pair = sorted(group_ids)
    game_id = f"{pair[0]}-vs-{pair[1]}"
    seed = f"{_canonical_json(terms)}|{pair[0]}|{pair[1]}"
    digest = hashlib.sha256(seed.encode("utf-8")).digest()
    game_uid = str(uuid.UUID(bytes=digest[:16]))
    return game_id, game_uid
