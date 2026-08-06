"""Rate limiting for LLM API calls using token bucket algorithm."""

from __future__ import annotations

import logging
import threading
import time

logger = logging.getLogger(__name__)


class RateLimiter:
    """Token bucket rate limiter for API calls.

    Implements the token bucket algorithm to limit the rate of API requests.
    Supports configurable requests per time period.
    """

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
        self.max_requests = max_requests
        self.time_window = time_window_seconds
        self.tokens = float(max_requests)
        self.last_update = time.time()
        self.lock = threading.Lock()

        logger.debug(
            "Rate limiter initialized: %d requests per %.1f seconds",
            max_requests,
            time_window_seconds,
        )

    def _refill_tokens(self) -> None:
        """Refill tokens based on elapsed time."""
        now = time.time()
        elapsed = now - self.last_update

        # Calculate how many tokens to add based on elapsed time
        tokens_to_add = (elapsed / self.time_window) * self.max_requests
        self.tokens = min(self.max_requests, self.tokens + tokens_to_add)
        self.last_update = now

    def acquire(self, tokens: int = 1, timeout: float | None = None) -> bool:
        """Acquire tokens from the bucket, blocking if necessary.

        Args:
            tokens: Number of tokens to acquire (default: 1).
            timeout: Maximum time to wait for tokens in seconds (None = wait forever).

        Returns:
            True if tokens were acquired, False if timeout occurred.

        """
        deadline = None if timeout is None else time.time() + timeout

        with self.lock:
            while True:
                self._refill_tokens()

                if self.tokens >= tokens:
                    self.tokens -= tokens
                    logger.debug(
                        "Acquired %d token(s), %.1f remaining",
                        tokens,
                        self.tokens,
                    )
                    return True

                # Check timeout
                if deadline is not None and time.time() >= deadline:
                    logger.warning("Rate limiter timeout after %.1fs", timeout)
                    return False

                # Calculate wait time until next token is available
                tokens_needed = tokens - self.tokens
                wait_time = (tokens_needed / self.max_requests) * self.time_window

                # Cap wait time at 1 second to allow periodic checks
                wait_time = min(wait_time, 1.0)

                logger.debug("Rate limited, waiting %.2fs for tokens", wait_time)
                time.sleep(wait_time)

    def try_acquire(self, tokens: int = 1) -> bool:
        """Try to acquire tokens without blocking.

        Args:
            tokens: Number of tokens to acquire (default: 1).

        Returns:
            True if tokens were acquired, False otherwise.

        """
        return self.acquire(tokens, timeout=0)

    @property
    def available_tokens(self) -> float:
        """The current number of available tokens."""
        with self.lock:
            self._refill_tokens()
            return self.tokens

    def reset(self) -> None:
        """Reset the rate limiter to full capacity."""
        with self.lock:
            self.tokens = float(self.max_requests)
            self.last_update = time.time()
            logger.debug("Rate limiter reset to %d tokens", self.max_requests)
