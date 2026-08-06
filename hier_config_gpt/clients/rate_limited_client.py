"""Rate-limited wrapper for GPT clients."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from .models import GPTClient
from .rate_limiter import RateLimiter

if TYPE_CHECKING:
    from .models import GPTPlanResponse

logger = logging.getLogger(__name__)


class RateLimitedGPTClient(GPTClient):
    """Wrapper that adds rate limiting to any GPT client.

    This client wraps another GPTClient and enforces rate limits
    to comply with API provider rate limits and avoid throttling.
    """

    def __init__(
        self,
        client: GPTClient,
        rate_limiter: RateLimiter | None = None,
        max_requests: int = 60,
        time_window_seconds: float = 60.0,
    ) -> None:
        """Initialize the rate-limited client wrapper.

        Args:
            client: The underlying GPT client to wrap.
            rate_limiter: Custom rate limiter instance (creates default if None).
            max_requests: Maximum requests per time window (default: 60).
            time_window_seconds: Time window in seconds (default: 60.0).

        """
        super().__init__()
        self.client = client

        if rate_limiter is None:
            rate_limiter = RateLimiter(
                max_requests=max_requests,
                time_window_seconds=time_window_seconds,
            )

        self.rate_limiter = rate_limiter

    def chat(self, prompt: str) -> str:
        """Send a chat prompt with rate limiting.

        Args:
            prompt: The prompt to send.

        Returns:
            The response text.

        """
        logger.debug("Acquiring rate limit token for chat request")
        self.rate_limiter.acquire(tokens=1)
        return self.client.chat(prompt)

    def generate_plan(self, prompt: str) -> GPTPlanResponse:
        """Generate a plan with rate limiting.

        Args:
            prompt: The prompt to send.

        Returns:
            The generated plan response.

        """
        logger.debug("Acquiring rate limit token for generate_plan request")
        self.rate_limiter.acquire(tokens=1)
        return self.client.generate_plan(prompt)
