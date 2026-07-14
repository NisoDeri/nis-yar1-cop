from __future__ import annotations

import queue
import threading
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pursuit.interface.window import PeerWindow

_POLL_MS = 100


class LiveGameDriver:
    """Bridges a daemon game thread to the Tkinter main thread via a threading.Queue.

    Usage pattern:
        q = queue.Queue()
        driver = LiveGameDriver(role, q)
        # game thread calls driver.push(...) freely
        driver.attach(window)   # called from the main thread; starts polling
    """

    def __init__(self, role: str, events_queue: queue.Queue) -> None:
        self._role = role
        self._queue: queue.Queue = events_queue
        self._window: PeerWindow | None = None

    def attach(self, window: PeerWindow) -> None:
        """Bind the window and start the Tkinter after() polling loop.

        Must be called from the Tkinter main thread AFTER the window is visible.
        """
        self._window = window
        self._poll()

    def push(self, event_type: str, **data: Any) -> None:
        """Thread-safe: enqueue an event dict for the main-thread poll loop."""
        self._queue.put_nowait({"type": event_type, **data})

    # ---- internals (main-thread only) ----

    def _poll(self) -> None:
        try:
            while True:
                event = self._queue.get_nowait()
                self._dispatch(event)
        except queue.Empty:
            pass
        if self._window is not None:
            self._window.after(_POLL_MS, self._poll)

    def _dispatch(self, event: dict[str, Any]) -> None:
        if self._window is None:
            return
        etype = event.get("type")
        if etype == "render":
            self._window.render(event)
        elif etype == "turn":
            self._window.set_turn(event.get("mine", False), event.get("text"))
        elif etype == "label":
            self._window.set_label(event["key"], event["value"])
        elif etype == "verified_ok":
            self._window.show_verified_ok()


def start_game_thread(target: Any, *args: Any, **kwargs: Any) -> threading.Thread:
    """Launch *target* as a daemon thread and return it (already started)."""
    t = threading.Thread(target=target, args=args, kwargs=kwargs, daemon=True)
    t.start()
    return t
