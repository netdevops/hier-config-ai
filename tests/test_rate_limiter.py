"""Tests for the token bucket rate limiter."""

from __future__ import annotations

import time

import pytest

from hier_config_ai.rate_limiter import RateLimiter


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


def test_zero_max_requests_is_refused() -> None:
    """A bucket that can never fill is a configuration error."""
    with pytest.raises(ValueError, match="max_requests"):
        RateLimiter(max_requests=0)


def test_zero_time_window_is_refused() -> None:
    """A zero-length window would divide by zero when refilling."""
    with pytest.raises(ValueError, match="time_window_seconds"):
        RateLimiter(max_requests=1, time_window_seconds=0.0)


async def test_async_acquire_grants_when_tokens_are_free() -> None:
    """The async path takes a token without blocking the event loop."""
    limiter = RateLimiter(max_requests=2, time_window_seconds=60.0)
    assert await limiter.aacquire() is True


async def test_async_acquire_times_out_when_starved() -> None:
    """A caller that cannot be served within its timeout is told so."""
    limiter = RateLimiter(max_requests=1, time_window_seconds=600.0)
    assert await limiter.aacquire() is True
    assert await limiter.aacquire(timeout=0.01) is False


async def test_async_acquire_waits_then_succeeds() -> None:
    """A starved caller is served once the bucket refills."""
    limiter = RateLimiter(max_requests=1, time_window_seconds=0.05)
    assert await limiter.aacquire() is True
    assert await limiter.aacquire(timeout=1.0) is True
