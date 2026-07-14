"""Replay subcommand helper — headless verdict print + optional Tk viewer.

Kept out of ``cli.py`` so the CLI's only top-level game-logic import stays
:mod:`pursuit.sdk` (Table-5 gate); ``cli`` imports this lazily in the ``replay`` branch.
The verdict is ALWAYS printed first, so a headless machine still gets the audit result
even though the viewer cannot open.
"""

from __future__ import annotations

import json

from pursuit.interface.replay_verify import verify_log


def replay_command(logfile: str, no_gui: bool) -> int:
    """Verify a sealed series log; print the JSON verdict; optionally open the Tk viewer."""
    verdict = verify_log(logfile)
    print(json.dumps(verdict, ensure_ascii=False, indent=2))
    if not no_gui:
        _try_view(logfile)
    return 0 if verdict.get("passed") else 1


def _try_view(logfile: str) -> None:
    """Open :class:`ReplayViewer` if a display exists; headless failures are swallowed."""
    try:
        from pursuit.interface.replay_view import ReplayViewer

        ReplayViewer(logfile).run()
    except Exception:  # noqa: BLE001 — no display / no Tk: the verdict is already printed
        pass
