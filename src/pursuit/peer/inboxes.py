"""PeerInboxes — thread-safe channels between the MCP server thread and the runtime.

The server tools only enqueue (INTEROP §1: zero server-side validation); the
consuming runtime blocks with a negotiated deadline (rule 6) and gets a named
:class:`~pursuit.exceptions.DeadlineError` instead of a bare ``queue.Empty``.
Duplicate deliveries are possible on the wire (retry semantics, INTEROP §1) —
dedup is the consumer's job, never the queue's.
"""

from __future__ import annotations

import queue
from typing import Any

from pursuit.exceptions import DeadlineError


class Inbox:
    """One thread-safe FIFO channel with deadline-aware blocking reads."""

    def __init__(self, name: str) -> None:
        self.name = name
        self._queue: queue.Queue[Any] = queue.Queue()

    def put(self, item: Any) -> None:
        """Enqueue; never blocks (unbounded, like the reference's inboxes)."""
        self._queue.put(item)

    def get(self, timeout: float) -> Any:
        """Blocking read; DeadlineError if nothing arrives within ``timeout``."""
        try:
            return self._queue.get(timeout=timeout)
        except queue.Empty as exc:
            raise DeadlineError(
                f"no message on '{self.name}' inbox within {timeout:g}s"
            ) from exc

    def get_nowait(self) -> Any | None:
        """Non-blocking poll (the 0.5 s turn-loop tick); None when empty."""
        try:
            return self._queue.get_nowait()
        except queue.Empty:
            return None

    def drain(self) -> list[Any]:
        """Empty the channel, returning everything (restart hygiene)."""
        items: list[Any] = []
        while True:
            try:
                items.append(self._queue.get_nowait())
            except queue.Empty:
                return items

    def __len__(self) -> int:
        return self._queue.qsize()


class PeerInboxes:
    """The four league channels (INTEROP §2) — one :class:`Inbox` per tool."""

    CHANNELS: tuple[str, ...] = ("negotiation", "turns", "audits", "controls")

    def __init__(self) -> None:
        self.negotiation = Inbox("negotiation")
        self.turns = Inbox("turns")
        self.audits = Inbox("audits")
        self.controls = Inbox("controls")

    def channel(self, name: str) -> Inbox:
        """Look up a channel by wire name; ValueError on anything unknown."""
        if name not in self.CHANNELS:
            raise ValueError(f"unknown inbox channel '{name}'")
        return getattr(self, name)

    def drain_all(self) -> dict[str, list[Any]]:
        """Drain every channel (series restart drains inboxes — INTEROP §2.4)."""
        return {name: self.channel(name).drain() for name in self.CHANNELS}
