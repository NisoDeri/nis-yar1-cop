"""Watchdog unit tests — fake-clock scans plus one tiny-threshold real-thread test.

Deterministic by design: every behavioral assertion drives ``check_now()`` with an
injected clock (no sleeping); the single daemon-thread test uses a 0.05s threshold
and an Event wait bounded at 0.3s. No sockets, no processes beyond the daemon thread.
"""

from __future__ import annotations

import threading

import pytest

from pursuit.exceptions import ConfigError
from pursuit.peer.watchdog import Watchdog


class FakeClock:
    def __init__(self, start: float = 50.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class Recorder:
    def __init__(self) -> None:
        self.fired: list[str] = []

    def __call__(self, name: str) -> None:
        self.fired.append(name)


def make_dog(threshold: float = 60.0) -> tuple[Watchdog, Recorder, FakeClock]:
    clock, recorder = FakeClock(), Recorder()
    return Watchdog(threshold, recorder, clock=clock), recorder, clock


def test_fresh_heartbeat_never_fires() -> None:
    dog, recorder, clock = make_dog(60.0)
    dog.kick("turn-loop")
    clock.advance(60.0)  # exactly at threshold is still alive (strict >)
    assert dog.check_now() == []
    assert recorder.fired == []


def test_stale_heartbeat_fires_the_callback_once() -> None:
    dog, recorder, clock = make_dog(60.0)
    dog.kick("turn-loop")
    clock.advance(60.1)
    assert dog.check_now() == ["turn-loop"]
    assert dog.check_now() == []  # once per freeze episode, never spammed
    assert recorder.fired == ["turn-loop"]


def test_kick_rearms_a_fired_alarm() -> None:
    dog, recorder, clock = make_dog(60.0)
    dog.kick("transport")
    clock.advance(61.0)
    dog.check_now()
    dog.kick("transport")  # sign of life -> alarm re-armed
    clock.advance(61.0)
    dog.check_now()
    assert recorder.fired == ["transport", "transport"]


def test_heartbeats_are_independent() -> None:
    dog, recorder, clock = make_dog(10.0)
    dog.kick("turn-loop")
    clock.advance(6.0)
    dog.kick("server")
    clock.advance(6.0)  # turn-loop is 12s stale, server only 6s
    assert dog.check_now() == ["turn-loop"]
    assert recorder.fired == ["turn-loop"]


def test_ages_snapshot_for_crash_diagnostics() -> None:
    dog, _recorder, clock = make_dog(60.0)
    dog.kick("turn-loop")
    clock.advance(2.5)
    dog.kick("server")
    clock.advance(1.5)
    ages = dog.ages()
    assert ages["turn-loop"] == pytest.approx(4.0)
    assert ages["server"] == pytest.approx(1.5)


def test_crashing_callback_never_kills_the_watchdog() -> None:
    clock = FakeClock()
    seen: list[str] = []

    def bad_callback(name: str) -> None:
        seen.append(name)
        raise RuntimeError("handler bug")

    dog = Watchdog(10.0, bad_callback, clock=clock)
    dog.kick("turn-loop")
    dog.kick("server")
    clock.advance(11.0)
    assert sorted(dog.check_now()) == ["server", "turn-loop"]  # both fired despite the raise
    assert sorted(seen) == ["server", "turn-loop"]
    dog.kick("turn-loop")  # the registry still works afterwards
    assert dog.check_now() == []


@pytest.mark.parametrize("threshold", [0.0, -5.0])
def test_non_positive_threshold_is_a_config_error(threshold: float) -> None:
    with pytest.raises(ConfigError, match="threshold"):
        Watchdog(threshold, lambda name: None)


def test_threshold_comes_from_the_caller_not_a_literal() -> None:
    dog, recorder, clock = make_dog(0.25)  # any agreed value works — nothing hardcoded
    dog.kick("turn-loop")
    clock.advance(0.3)
    assert dog.check_now() == ["turn-loop"]
    assert recorder.fired == ["turn-loop"]


def test_daemon_thread_fires_within_a_tiny_real_threshold() -> None:
    """One real-clock run: 0.05s freeze threshold, bounded 0.3s wait, then clean stop."""
    fired = threading.Event()
    names: list[str] = []

    def on_freeze(name: str) -> None:
        names.append(name)
        fired.set()

    dog = Watchdog(0.05, on_freeze, poll_interval=0.01)
    dog.kick("turn-loop")
    dog.start()
    dog.start()  # idempotent while running
    try:
        assert dog.running
        assert fired.wait(timeout=0.3), "watchdog did not fire within 0.3s"
        assert names == ["turn-loop"]
    finally:
        dog.stop()
    assert not dog.running
    dog.stop()  # idempotent after stop
