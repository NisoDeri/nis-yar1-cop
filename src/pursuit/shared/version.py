"""Single source of truth for release/identity constants (import, never hardcode).

Kept pure and dependency-free so any layer — artifacts, declaration, README tooling,
CI gates — reads the same strings. Bump ``__version__`` on a tagged submission; keep
``BOOK_VERSION`` in lock-step with the rule-book edition the wire conforms to.
"""

from __future__ import annotations

__version__ = "1.0.0"
BOOK_VERSION = "3.0.0"
COURSE = "Orchestration of AI Agents (Dr. Yoram Segal, University of Haifa)"
GROUP_ID = "nis-yar1"
GROUP_NAME = "Nis-Yar-1"
MEMBERS = ("Nissim Deri", "Yarden Tziar")
LICENSE_NOTICE = (
    "MIT License (c) 2026 Nissim Deri, Yarden Tziar (group nis-yar1). "
    "Wire protocol interoperates with the course reference simulator "
    "(github.com/rmisegal/Game-P2P-Cop-Chase) — studied, not copied."
)

__all__ = [
    "BOOK_VERSION",
    "COURSE",
    "GROUP_ID",
    "GROUP_NAME",
    "LICENSE_NOTICE",
    "MEMBERS",
    "__version__",
]
