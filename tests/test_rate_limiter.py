"""Tests for the token bucket rate limiter."""

from __future__ import annotations

import time

from hier_config_gpt.clients.rate_limiter import RateLimiter


def test_rate_limiter_initial_capacity() -> None:
    limiter = RateLimiter(max_requests=10, time_window_seconds=60.0)

    assert limiter.available_tokens == 10


def test_rate_limiter_acquire_decrements_tokens() -> None:
    limiter = RateLimiter(max_requests=10, time_window_seconds=60.0)

    assert limiter.acquire(tokens=3) is True
    assert limiter.available_tokens < 8


def test_rate_limiter_try_acquire_exhausted() -> None:
    limiter = RateLimiter(max_requests=2, time_window_seconds=60.0)

    assert limiter.try_acquire(tokens=2) is True
    assert limiter.try_acquire(tokens=1) is False


def test_rate_limiter_acquire_timeout() -> None:
    limiter = RateLimiter(max_requests=1, time_window_seconds=60.0)

    assert limiter.acquire(tokens=1) is True
    assert limiter.acquire(tokens=1, timeout=0) is False


def test_rate_limiter_acquire_blocks_until_refill() -> None:
    limiter = RateLimiter(max_requests=5, time_window_seconds=0.1)

    assert limiter.acquire(tokens=5) is True
    # The bucket is empty, but refills within the tiny time window.
    assert limiter.acquire(tokens=1, timeout=5.0) is True


def test_rate_limiter_refill_over_time() -> None:
    limiter = RateLimiter(max_requests=5, time_window_seconds=0.05)

    assert limiter.acquire(tokens=5) is True
    # After a full time window the bucket refills to capacity.
    time.sleep(0.06)
    assert limiter.available_tokens == 5


def test_rate_limiter_reset() -> None:
    limiter = RateLimiter(max_requests=5, time_window_seconds=60.0)

    assert limiter.acquire(tokens=5) is True
    limiter.reset()
    assert limiter.available_tokens == 5
