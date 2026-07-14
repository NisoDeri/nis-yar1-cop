"""Gatekeeper — the single 3-gate doorway in front of any guarded call.

Every guarded external call (Gmail send, LLM/Ollama query) passes through
:meth:`Gatekeeper.execute`, which enforces three independent gates in order:

1. **Daily quota** — at most ``daily_quota`` calls per rolling 24h window.
2. **Token-bucket rate limiter** — ``bucket_capacity`` tokens, refilled at
   ``refill_per_sec``; one token per call, refuse when empty.
3. **Circuit breaker** — after ``breaker_threshold`` consecutive failures it
   OPENs for ``breaker_cooldown`` seconds (fast-refuse), then half-open probes
   a single call, closing on success or re-opening on failure.

Clock is injected (``clock=time.monotonic`` default) so tests are fully
deterministic with a fake clock. No parameters are hardcoded into the logic —
``from_config`` reads them from the agreed ``rate_limiter_gatekeeper`` block.
"""

from __future__ import annotations

import time
from collections import deque
from collections.abc import Callable
from typing import Any

_DAY_SECONDS = 86_400.0


class GatekeeperError(Exception):
    """A guarded call was refused by one of the three gates (fast-fail)."""


class Gatekeeper:
    """Three-gate guard (quota + token bucket + circuit breaker) for one service."""

    def __init__(
        self,
        service: str,
        daily_quota: int,
        bucket_capacity: float,
        refill_per_sec: float,
        breaker_threshold: int,
        breaker_cooldown: float,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.service = service
        self._daily_quota = int(daily_quota)
        self._capacity = float(bucket_capacity)
        self._refill = float(refill_per_sec)
        self._threshold = int(breaker_threshold)
        self._cooldown = float(breaker_cooldown)
        self._clock = clock
        self._calls: deque[float] = deque()
        self._tokens = float(bucket_capacity)
        self._last_refill = clock()
        self._failures = 0
        self._opened_at: float | None = None
        self._half_open = False

    @classmethod
    def from_config(cls, config: Any, service: str) -> Gatekeeper:
        """Build from the agreed ``rate_limiter_gatekeeper`` block (sane defaults)."""
        block = _rate_block(config)
        rpm = float(block.get("requests_per_minute", 30))
        capacity = float(block.get("bucket_capacity", block.get("concurrent_requests", 2)))
        threshold = int(block.get("breaker_threshold", block.get("max_retries", 3)))
        cooldown = float(block.get("breaker_cooldown", block.get("retry_backoff_sec", 5)))
        return cls(
            service=service,
            daily_quota=int(block.get("daily_quota", int(rpm * 60 * 24))),
            bucket_capacity=capacity,
            refill_per_sec=float(block.get("refill_per_sec", rpm / 60.0)),
            breaker_threshold=threshold,
            breaker_cooldown=cooldown,
        )

    def execute(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """Run ``fn`` through all three gates; refusal raises GatekeeperError."""
        self._check_breaker()
        self._check_quota()
        self._consume_token()
        try:
            result = fn(*args, **kwargs)
        except Exception:
            self._on_failure()
            raise
        self._on_success()
        return result

    # -- gate 3: circuit breaker ------------------------------------------
    def _check_breaker(self) -> None:
        if self._opened_at is None:
            return
        if self._clock() - self._opened_at < self._cooldown:
            raise GatekeeperError(f"{self.service}: circuit breaker OPEN (fast-refuse)")
        self._half_open = True  # cooldown elapsed: allow a single probe call

    def _on_failure(self) -> None:
        self._failures += 1
        if self._half_open or self._failures >= self._threshold:
            self._opened_at = self._clock()
            self._half_open = False

    def _on_success(self) -> None:
        self._failures = 0
        self._opened_at = None
        self._half_open = False

    # -- gate 1: rolling daily quota --------------------------------------
    def _check_quota(self) -> None:
        now = self._clock()
        while self._calls and now - self._calls[0] >= _DAY_SECONDS:
            self._calls.popleft()
        if len(self._calls) >= self._daily_quota:
            raise GatekeeperError(
                f"{self.service}: daily quota of {self._daily_quota} exhausted"
            )
        self._calls.append(now)

    # -- gate 2: token bucket ---------------------------------------------
    def _consume_token(self) -> None:
        now = self._clock()
        elapsed = now - self._last_refill
        self._last_refill = now
        self._tokens = min(self._capacity, self._tokens + elapsed * self._refill)
        if self._tokens < 1.0:
            self._calls.pop()  # un-count: call refused, not attempted
            raise GatekeeperError(f"{self.service}: rate limit — token bucket empty")
        self._tokens -= 1.0


def _rate_block(config: Any) -> dict[str, Any]:
    """Extract the ``rate_limiter_gatekeeper`` dict from a ConfigManager or dict."""
    if hasattr(config, "game"):
        try:
            block = config.game("rate_limiter_gatekeeper")
        except Exception:
            block = {}
        return block if isinstance(block, dict) else {}
    if isinstance(config, dict):
        block = config.get("rate_limiter_gatekeeper", config)
        return block if isinstance(block, dict) else {}
    return {}
