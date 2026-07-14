"""DeadlineTracker unit tests — injected fake clock, zero sleeping, no sockets."""

from __future__ import annotations

import pytest

from pursuit.exceptions import ConfigError, DeadlineError
from pursuit.peer.deadlines import DeadlineTracker


class FakeClock:
    """Deterministic monotonic clock the tests advance by hand."""

    def __init__(self, start: float = 100.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def tracker(clock: FakeClock) -> DeadlineTracker:
    return DeadlineTracker(clock=clock)


def test_arm_and_remaining_counts_down(tracker: DeadlineTracker, clock: FakeClock) -> None:
    tracker.arm("turn", 30.0)
    assert tracker.remaining("turn") == pytest.approx(30.0)
    clock.advance(12.5)
    assert tracker.remaining("turn") == pytest.approx(17.5)
    assert not tracker.expired("turn")


def test_expired_flips_once_budget_is_spent(tracker: DeadlineTracker, clock: FakeClock) -> None:
    tracker.arm("turn", 30.0)
    clock.advance(30.0)  # exactly spent counts as expired (remaining <= 0)
    assert tracker.expired("turn")
    clock.advance(5.0)
    assert tracker.remaining("turn") == pytest.approx(-5.0)  # overshoot is visible evidence


def test_check_returns_remaining_then_raises_named_error(
    tracker: DeadlineTracker, clock: FakeClock
) -> None:
    tracker.arm("negotiate", 60.0)
    assert tracker.check("negotiate") == pytest.approx(60.0)
    clock.advance(61.0)
    with pytest.raises(DeadlineError, match="negotiate"):
        tracker.check("negotiate")


def test_rearm_resets_the_budget(tracker: DeadlineTracker, clock: FakeClock) -> None:
    """The per-turn deadline resets on every received message (INTEROP §1)."""
    tracker.arm("turn", 10.0)
    clock.advance(9.0)
    tracker.arm("turn", 10.0)
    clock.advance(9.0)
    assert not tracker.expired("turn")
    assert tracker.remaining("turn") == pytest.approx(1.0)


def test_named_deadlines_are_independent(tracker: DeadlineTracker, clock: FakeClock) -> None:
    tracker.arm("turn", 5.0)
    tracker.arm("audit", 50.0)
    clock.advance(10.0)
    assert tracker.expired("turn")
    assert not tracker.expired("audit")
    assert tracker.active() == ["audit", "turn"]


def test_disarm_forgets_and_is_idempotent(tracker: DeadlineTracker) -> None:
    tracker.arm("turn", 5.0)
    assert tracker.armed("turn")
    tracker.disarm("turn")
    tracker.disarm("turn")  # unknown/disarmed name is a no-op
    assert not tracker.armed("turn")
    assert tracker.active() == []


def test_unknown_name_raises_deadline_error(tracker: DeadlineTracker) -> None:
    with pytest.raises(DeadlineError, match="no deadline named 'ghost'"):
        tracker.remaining("ghost")
    with pytest.raises(DeadlineError, match="ghost"):
        tracker.check("ghost")
    with pytest.raises(DeadlineError, match="ghost"):
        tracker.expired("ghost")


@pytest.mark.parametrize("budget", [0.0, -1.0])
def test_non_positive_budget_is_a_config_error(tracker: DeadlineTracker, budget: float) -> None:
    with pytest.raises(ConfigError, match="positive budget"):
        tracker.arm("turn", budget)


def test_default_clock_is_monotonic_wallclock() -> None:
    tracker = DeadlineTracker()  # real time.monotonic, but no sleeping needed
    tracker.arm("turn", 3600.0)
    assert 0.0 < tracker.check("turn") <= 3600.0
