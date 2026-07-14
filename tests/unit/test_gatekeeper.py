"""Deterministic unit tests for the 3-gate :class:`Gatekeeper`.

A fake, hand-advanced clock makes every timing gate (quota window, token
refill, breaker cooldown) reproducible with zero wall-clock waiting.
"""

from __future__ import annotations

import pytest

from pursuit.infra.gatekeeper import Gatekeeper, GatekeeperError


class FakeClock:
    """Injectable monotonic clock; time only moves when a test advances it."""

    def __init__(self, start: float = 0.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def _ok() -> str:
    return "ok"


def _boom() -> str:
    raise ValueError("provider down")


def test_daily_quota_refuses_when_exhausted() -> None:
    clock = FakeClock()
    gk = Gatekeeper(
        "gmail", daily_quota=3, bucket_capacity=1000, refill_per_sec=1000,
        breaker_threshold=99, breaker_cooldown=1, clock=clock,
    )
    assert [gk.execute(_ok) for _ in range(3)] == ["ok", "ok", "ok"]
    with pytest.raises(GatekeeperError, match="daily quota"):
        gk.execute(_ok)


def test_daily_quota_window_rolls_off_after_24h() -> None:
    clock = FakeClock()
    gk = Gatekeeper(
        "gmail", daily_quota=1, bucket_capacity=1000, refill_per_sec=1000,
        breaker_threshold=99, breaker_cooldown=1, clock=clock,
    )
    gk.execute(_ok)
    with pytest.raises(GatekeeperError, match="daily quota"):
        gk.execute(_ok)
    clock.advance(86_400.0)  # the first call ages out of the rolling window
    assert gk.execute(_ok) == "ok"


def test_token_bucket_refuses_then_refills_after_time_advance() -> None:
    clock = FakeClock()
    gk = Gatekeeper(
        "ollama", daily_quota=1000, bucket_capacity=2, refill_per_sec=1.0,
        breaker_threshold=99, breaker_cooldown=1, clock=clock,
    )
    assert gk.execute(_ok) == "ok"
    assert gk.execute(_ok) == "ok"
    with pytest.raises(GatekeeperError, match="token bucket empty"):
        gk.execute(_ok)
    clock.advance(1.0)  # refill_per_sec=1 -> exactly one token back
    assert gk.execute(_ok) == "ok"
    with pytest.raises(GatekeeperError, match="token bucket empty"):
        gk.execute(_ok)


def test_refused_call_does_not_consume_quota() -> None:
    clock = FakeClock()
    gk = Gatekeeper(
        "ollama", daily_quota=5, bucket_capacity=1, refill_per_sec=0.0,
        breaker_threshold=99, breaker_cooldown=1, clock=clock,
    )
    assert gk.execute(_ok) == "ok"
    for _ in range(3):  # bucket empty, refill 0 -> always refused
        with pytest.raises(GatekeeperError, match="token bucket empty"):
            gk.execute(_ok)
    assert len(gk._calls) == 1  # only the one successful call counted


def test_breaker_opens_after_k_failures_and_half_opens_after_cooldown() -> None:
    clock = FakeClock()
    gk = Gatekeeper(
        "ollama", daily_quota=1000, bucket_capacity=1000, refill_per_sec=1000,
        breaker_threshold=3, breaker_cooldown=10, clock=clock,
    )
    for _ in range(3):  # K consecutive failures -> breaker OPENs
        with pytest.raises(ValueError):
            gk.execute(_boom)
    with pytest.raises(GatekeeperError, match="circuit breaker OPEN"):
        gk.execute(_ok)  # fast-refused while OPEN
    clock.advance(10.0)  # cooldown elapsed -> half-open probe closes on success
    assert gk.execute(_ok) == "ok"
    for _ in range(3):  # breaker fully closed again, fresh failure budget
        with pytest.raises(ValueError):
            gk.execute(_boom)
    with pytest.raises(GatekeeperError, match="circuit breaker OPEN"):
        gk.execute(_ok)


def test_half_open_probe_failure_reopens_breaker() -> None:
    clock = FakeClock()
    gk = Gatekeeper(
        "ollama", daily_quota=1000, bucket_capacity=1000, refill_per_sec=1000,
        breaker_threshold=1, breaker_cooldown=5, clock=clock,
    )
    with pytest.raises(ValueError):
        gk.execute(_boom)  # threshold=1 -> OPEN immediately
    with pytest.raises(GatekeeperError, match="circuit breaker OPEN"):
        gk.execute(_ok)
    clock.advance(5.0)
    with pytest.raises(ValueError):
        gk.execute(_boom)  # half-open probe fails -> re-OPEN
    with pytest.raises(GatekeeperError, match="circuit breaker OPEN"):
        gk.execute(_ok)


def test_from_config_reads_rate_limiter_block() -> None:
    cfg = {"rate_limiter_gatekeeper": {
        "requests_per_minute": 60, "concurrent_requests": 2,
        "max_retries": 4, "retry_backoff_sec": 7,
    }}
    gk = Gatekeeper.from_config(cfg, "gmail")
    assert gk.service == "gmail"
    assert gk._refill == pytest.approx(1.0)  # 60 rpm / 60
    assert gk._capacity == 2.0
    assert gk._threshold == 4
    assert gk._cooldown == 7.0
