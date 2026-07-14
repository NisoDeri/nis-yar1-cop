"""Watchdog — daemon-thread freeze monitor with a heartbeat registry (rule 7, arch §5).

The reference's only timer is the per-turn deadline, which resets on any message — a
slow-but-alive livelock never fires it (reference gap #17). This watchdog is independent
of the turn loop: every subsystem (`turn-loop`, `transport`, `server`, ...) calls
``kick(name)`` on each sign of life; a heartbeat older than ``threshold_sec`` fires
``on_freeze(name)`` exactly ONCE per freeze episode (a later kick re-arms the alarm).
The runtime's callback maps the fire to controlled log extraction + ``technical_loss``
0/0 — no game logic lives here. ``threshold_sec`` comes from the SHARED config via the
caller (agreed 60s, Appendix F Table 19); nothing is hardcoded. The clock is injected so
tests can drive ``check_now()`` deterministically without sleeping.
"""

from __future__ import annotations

import contextlib
import threading
import time
from collections.abc import Callable

from pursuit.exceptions import ConfigError

#: Poll cadence as a fraction of the threshold — an implementation detail, not a game term.
_POLL_FRACTION = 10.0


class Watchdog:
    """Heartbeat registry + daemon poll thread; fires ``on_freeze(name)`` once per freeze."""

    def __init__(self, threshold_sec: float, on_freeze: Callable[[str], None], *,
                 poll_interval: float | None = None,
                 clock: Callable[[], float] = time.monotonic) -> None:
        if not threshold_sec > 0:
            raise ConfigError(f"watchdog threshold must be positive, got {threshold_sec!r}")
        self.threshold_sec = float(threshold_sec)
        self._on_freeze = on_freeze
        self._poll = float(poll_interval) if poll_interval else self.threshold_sec / _POLL_FRACTION
        self._clock = clock
        self._beats: dict[str, float] = {}
        self._fired: set[str] = set()
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def kick(self, name: str) -> None:
        """Record a heartbeat for ``name``; a live beat re-arms a fired alarm."""
        with self._lock:
            self._beats[name] = self._clock()
            self._fired.discard(name)

    def ages(self) -> dict[str, float]:
        """Heartbeat ages in seconds — the crash-diagnostics snapshot (arch §5 step 3)."""
        with self._lock:
            now = self._clock()
            return {name: now - beat for name, beat in self._beats.items()}

    def check_now(self) -> list[str]:
        """One scan: fire the callback for every newly frozen heartbeat; return the names.

        The poll thread calls this every tick; tests may call it directly with a fake
        clock. A crashing callback never kills the watchdog — it must outlive our bugs.
        """
        with self._lock:
            now = self._clock()
            frozen = [name for name, beat in self._beats.items()
                      if name not in self._fired and now - beat > self.threshold_sec]
            self._fired.update(frozen)
        for name in frozen:
            with contextlib.suppress(Exception):  # rule 7: the monitor survives its handler
                self._on_freeze(name)
        return frozen

    def start(self) -> None:
        """Spawn the daemon poll thread (idempotent while already running)."""
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="pursuit-watchdog", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Signal the poll thread to exit and wait briefly for it."""
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=max(1.0, self._poll * 4))
            self._thread = None

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def _run(self) -> None:
        while not self._stop.wait(self._poll):
            self.check_now()
