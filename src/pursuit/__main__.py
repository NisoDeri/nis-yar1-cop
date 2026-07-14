"""``python -m pursuit`` — the one console entry point (architecture §8 run map)."""

from pursuit.interface.cli import main

if __name__ == "__main__":  # pragma: no cover — process entry
    raise SystemExit(main())
