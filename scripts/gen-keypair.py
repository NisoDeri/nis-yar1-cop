#!/usr/bin/env python3
"""Generate Ed25519 team keypair (D14). Output: secrets/keys.json (gitignored)."""
import base64
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from pursuit.domain.crypto.signing import generate_keypair  # noqa: E402

priv, pub = generate_keypair()
out = {"group_id": "nis-yar1", "algorithm": "ed25519",
       "public_key_b64": base64.b64encode(pub).decode(),
       "private_key_b64": base64.b64encode(priv).decode()}
Path("secrets").mkdir(exist_ok=True)
(Path("secrets") / "keys.json").write_text(json.dumps(out, indent=2))
print("Written to secrets/keys.json")
print("Public key:", out["public_key_b64"])
