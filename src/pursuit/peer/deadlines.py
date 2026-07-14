"""DeadlineTracker — every wait in the peer runs under a NAMED, budgeted deadline (rule 6).

Both loops (the turn loop and the control listener) arm a deadline before blocking and
``check()`` it on every tick: expiry surfaces as a :class:`~pursuit.exceptions.DeadlineError`
naming the wait, never a silent hang (the runtime maps a turn-deadline expiry to the D4
``technical_loss`` 0/0 path). Budgets always arrive from the negotiated shared config via the
caller — this module holds no timeout literals. The clock is injected for deterministic tests.
"""

from __future__ import annotations

import time
from collections.abc import Callable

from pursuit.exceptions import ConfigError, DeadlineError


class DeadlineTracker:
    """Named absolute deadlines over an injected monotonic clock."""

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._deadlines: dict[str, float] = {}

    def arm(self, name: str, budget_sec: float) -> None:
        """Start (or restart) the named deadline ``budget_sec`` from now.

        Re-arming an existing name resets it — the reference's per-turn deadline
        resets on every received message (INTEROP §1) and this is that reset.
        """
        if not budget_sec > 0:
            raise ConfigError(f"deadline '{name}' needs a positive budget, got {budget_sec!r}")
        self._deadlines[name] = self._clock() + float(budget_sec)

    def disarm(self, name: str) -> None:
        """Forget the named deadline; disarming an unknown name is a no-op."""
        self._deadlines.pop(name, None)

    def armed(self, name: str) -> bool:
        return name in self._deadlines

    def active(self) -> list[str]:
        """All armed deadline names (diagnostics / watchdog crash extraction)."""
        return sorted(self._deadlines)

    def remaining(self, name: str) -> float:
        """Seconds left on the named deadline (negative = overshoot, rule-6 evidence)."""
        if name not in self._deadlines:
            raise DeadlineError(f"no deadline named '{name}' is armed")
        return self._deadlines[name] - self._clock()

    def expired(self, name: str) -> bool:
        """True once the named budget is spent (non-throwing poll form)."""
        return self.remaining(name) <= 0.0

    def check(self, name: str) -> float:
        """Remaining seconds, or DeadlineError naming the wait and the overshoot."""
        left = self.remaining(name)
        if left <= 0.0:
            raise DeadlineError(f"deadline '{name}' exceeded its budget by {-left:g}s")
        return left
