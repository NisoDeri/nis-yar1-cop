"""Bounded brain execution — a hung/slow brain becomes a bounded event, never a freeze.

The move is pure Python and normally sub-millisecond, but a pathological state must never
FREEZE the turn: the watchdog can only *log* a frozen main thread, it cannot interrupt it.
``decide_bounded`` runs the brain under a hard wall-clock deadline on a worker thread; on
overrun it plays a safe HOLD (flagged) so the sub-game keeps moving. A truly hung worker is
abandoned (``shutdown(wait=False)`` — we never block on it); if we somehow still stall, the
opponent's own turn deadline ends the game as a technical loss anyway (A6).
"""

from __future__ import annotations

import concurrent.futures as cf
from typing import Any

from pursuit.constants import MoveType
from pursuit.domain.protocol import SILENCE_HINT
from pursuit.strategy.base import Decision


def _timeout_hold() -> Decision:
    """The safe fallback when a brain overruns its deadline: stay put, truthfully flagged."""
    return Decision(MoveType.HOLD, None, SILENCE_HINT, "truth",
                    reasoning="brain deadline exceeded -> safe HOLD", random_move=True)


def decide_bounded(brain: Any, args: tuple[Any, ...], deadline_seconds: float | None) -> Decision:
    """Run ``brain.decide(*args)`` under a hard deadline; a safe HOLD on overrun.

    ``deadline_seconds`` None/<=0 runs inline (tests, deterministic fast play).
    """
    if not deadline_seconds or deadline_seconds <= 0:
        return brain.decide(*args)
    executor = cf.ThreadPoolExecutor(max_workers=1)
    future = executor.submit(brain.decide, *args)
    try:
        result = future.result(timeout=float(deadline_seconds))
    except cf.TimeoutError:
        executor.shutdown(wait=False)  # abandon the hung worker; NEVER block the turn
        return _timeout_hold()
    executor.shutdown(wait=False)
    return result
