"""Course hard gate: every source .py file must be <= 150 lines. Exit 1 on violation."""

import sys
from pathlib import Path

LIMIT = 150


def main() -> int:
    root = Path(__file__).resolve().parent.parent / "src"
    violations = []
    for path in sorted(root.rglob("*.py")):
        count = len(path.read_text(encoding="utf-8").splitlines())
        if count > LIMIT:
            violations.append(f"{path.relative_to(root.parent)}: {count} lines (limit {LIMIT})")
    for line in violations:
        print(line)
    if not violations:
        print(f"OK: all src files <= {LIMIT} lines")
    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main())
