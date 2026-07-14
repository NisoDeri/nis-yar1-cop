#!/usr/bin/env python3
"""Advisory scan for hardcoded game parameters in src/pursuit (zero-hardcoding gate).

Every Appendix-F number (board 7, barriers 14, clock 35, emit 0.9, decay 0.1) must
enter the program through config (``game.json`` / ``game.toml``) and be injected, never
baked into logic — see DECISIONS D4 and STRATEGY §7. This is a *lint*, not a gate: it
prints suspects for a human to eyeball and ALWAYS exits 0, so CI never blocks on a false
positive (a loop bound of ``range(7)`` is fine; ``grid_size = 7`` is not). Config files,
tests and constants/version modules are exempt by design.

Usage (from the repo root)::

    python tools/check_no_hardcoded.py            # scan src/pursuit
    python tools/check_no_hardcoded.py src/other  # scan an explicit root
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# Appendix-F game values that must live in config, not code.
SUSPECT_NUMBERS = ("7", "14", "35", "0.9", "0.1")

# Files whose whole purpose is to name/serialize/test these values.
EXEMPT_NAMES = frozenset({"constants.py", "version.py"})
EXEMPT_PARTS = frozenset({"config", "tests", "test"})

# Assignment/keyword shapes where a bare literal is genuinely suspicious.
_NUM = "|".join(re.escape(n) for n in SUSPECT_NUMBERS)
SUSPECT_RE = re.compile(
    rf"(?<![\w.])(?:=|:|return|,)\s*(?:{_NUM})(?![\w.])",
)
# Lines that are obviously safe even if they contain a suspect number.
SAFE_HINT_RE = re.compile(r"#.*config|cfg\.|config\[|getattr|\.get\(|noqa")


def is_exempt(path: Path) -> bool:
    """True when the file is config/tests/vocabulary — legitimately literal."""
    if path.name in EXEMPT_NAMES:
        return True
    return bool(EXEMPT_PARTS & {p.lower() for p in path.parts})


def scan_line(line: str) -> bool:
    """True when a line hardcodes a suspect game number with no config escape hatch."""
    stripped = line.strip()
    if stripped.startswith("#") or SAFE_HINT_RE.search(line):
        return False
    return bool(SUSPECT_RE.search(line))


def scan_file(path: Path) -> list[tuple[int, str]]:
    """Return ``(lineno, text)`` for every suspect line in one file."""
    hits: list[tuple[int, str]] = []
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return hits
    for lineno, line in enumerate(text.splitlines(), start=1):
        if scan_line(line):
            hits.append((lineno, line.strip()))
    return hits


def scan_tree(root: Path) -> dict[Path, list[tuple[int, str]]]:
    """Map every non-exempt ``*.py`` under ``root`` to its suspect lines."""
    report: dict[Path, list[tuple[int, str]]] = {}
    for path in sorted(root.rglob("*.py")):
        if "__pycache__" in path.parts or is_exempt(path):
            continue
        hits = scan_file(path)
        if hits:
            report[path] = hits
    return report


def main(argv: list[str] | None = None) -> int:
    """Print an advisory report; ALWAYS exit 0 (lint, never a blocking gate)."""
    args = list(sys.argv[1:] if argv is None else argv)
    root = Path(args[0]) if args else Path("src") / "pursuit"
    if not root.exists():
        print(f"advisory: scan root {root} does not exist; nothing to check")
        return 0
    report = scan_tree(root)
    total = sum(len(v) for v in report.values())
    if not report:
        print(f"advisory: no hardcoded game parameters found under {root}")
        return 0
    print(f"advisory: {total} suspect line(s) in {len(report)} file(s) under {root}")
    print("(review each: a loop bound is fine; a baked-in game term is not)\n")
    for path, hits in report.items():
        print(path)
        for lineno, text in hits:
            print(f"  {lineno:>4}: {text}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
