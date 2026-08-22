"""Token-bucket rate limiting for model requests."""

from __future__ import annotations

import asyncio
import logging
import threading
import time

logger = logging.getLogger(__name__)

# Longest single sleep between bucket checks. Waiters wake up at least this
# often so a timeout is honoured promptly even when the bucket is far from full.
_MAX_SLEEP_SECONDS = 1.0


class RateLimiter:
    """Token bucket limiting how many requests may start per time window."""

    def __init__(
        self,
        max_requests: int = 60,
        time_window_seconds: float = 60.0,
    ) -> None:
        """Initialize the rate limiter.

        Args:
            max_requests: Maximum number of requests allowed in the time window.
            time_window_seconds: Time window in seconds for rate limiting.

        """
        if max_requests <= 0:
            msg = "max_requests must be greater than zero."
            raise ValueError(msg)
        if time_window_seconds <= 0:
            msg = "time_window_seconds must be greater than zero."
            raise ValueError(msg)

        self.max_requests = max_requests
        self.time_window = time_window_seconds
        self.tokens = float(max_requests)
        self.last_update = time.monotonic()
        self.lock = threading.Lock()

        logger.debug(
            "Rate limiter initialized: %d requests per %.1f seconds",
            max_requests,
            time_window_seconds,
        )

    def _refill_locked(self) -> None:
        """Refill the bucket. The caller must already hold the lock."""
        now = time.monotonic()
        elapsed = now - self.last_update
        tokens_to_add = (elapsed / self.time_window) * self.max_requests
        self.tokens = min(float(self.max_requests), self.tokens + tokens_to_add)
        self.last_update = now

    def _check_capacity(self, tokens: int) -> None:
        """Refuse a request the bucket can never satisfy.

        The bucket refills to at most `max_requests`, so waiting for more than
        that would block forever rather than eventually succeed.
        """
        if tokens > self.max_requests:
            msg = (
                f"Cannot acquire {tokens} tokens from a bucket that holds at "
                f"most {self.max_requests}."
            )
            raise ValueError(msg)

    def _take(self, tokens: int) -> float:
        """Take tokens if available.

        Returns:
            0.0 when the tokens were taken, otherwise how long to wait before
            trying again. The lock is never held while the caller waits, so one
            blocked waiter cannot stall the others.

        """
        with self.lock:
            self._refill_locked()

            if self.tokens >= tokens:
                self.tokens -= tokens
                return 0.0

            shortfall = tokens - self.tokens
            wait = (shortfall / self.max_requests) * self.time_window
            return min(wait, _MAX_SLEEP_SECONDS)

    def _next_sleep(self, tokens: int, deadline: float | None) -> float | None:
        """Decide what a waiter should do next.

        Returns:
            0.0 once the tokens are taken, None once the deadline has passed,
            otherwise how long to wait before trying again. Sync and async
            callers share this so their timeout accounting cannot drift apart.

        """
        wait = self._take(tokens)
        if wait <= 0.0:
            return 0.0
        if deadline is None:
            return wait

        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return None
        return min(wait, remaining)

    def acquire(self, tokens: int = 1, timeout: float | None = None) -> bool:
        """Take tokens from the bucket, waiting until they are available.

        Args:
            tokens: Number of tokens to acquire (default: 1).
            timeout: Maximum time to wait in seconds (None waits forever).

        Returns:
            True if the tokens were acquired, False if the timeout expired.

        """
        self._check_capacity(tokens)
        deadline = None if timeout is None else time.monotonic() + timeout

        while (wait := self._next_sleep(tokens, deadline)) is not None:
            if wait <= 0.0:
                return True
            time.sleep(wait)

        logger.warning("Rate limiter timed out after %.1fs", timeout)
        return False

    async def aacquire(self, tokens: int = 1, timeout: float | None = None) -> bool:
        """Take tokens without blocking the event loop.

        Args:
            tokens: Number of tokens to acquire (default: 1).
            timeout: Maximum time to wait in seconds (None waits forever).

        Returns:
            True if the tokens were acquired, False if the timeout expired.

        """
        self._check_capacity(tokens)
        deadline = None if timeout is None else time.monotonic() + timeout

        while (wait := self._next_sleep(tokens, deadline)) is not None:
            if wait <= 0.0:
                return True
            await asyncio.sleep(wait)

        logger.warning("Rate limiter timed out after %.1fs", timeout)
        return False

    def try_acquire(self, tokens: int = 1) -> bool:
        """Take tokens only if they are available right now."""
        self._check_capacity(tokens)
        wait = self._next_sleep(tokens, None)
        return wait is not None and wait <= 0.0

    @property
    def available_tokens(self) -> float:
        """How many tokens the bucket currently holds."""
        with self.lock:
            self._refill_locked()
            return self.tokens

    def reset(self) -> None:
        """Refill the bucket to capacity."""
        with self.lock:
            self.tokens = float(self.max_requests)
            self.last_update = time.monotonic()
