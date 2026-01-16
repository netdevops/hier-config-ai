"""Caching wrapper for GPT clients."""

from __future__ import annotations

import logging
from typing import Optional

from .cache import ResponseCache
from .models import GPTClient, GPTPlanResponse

logger = logging.getLogger(__name__)


class CachedGPTClient(GPTClient):
    """Wrapper that adds caching to any GPT client.

    This client wraps another GPTClient and caches its responses
    to reduce API costs and improve performance.
    """

    def __init__(
        self,
        client: GPTClient,
        cache: Optional[ResponseCache] = None,
    ) -> None:
        """Initialize the cached client wrapper.

        Args:
            client: The underlying GPT client to wrap.
            cache: The response cache instance (creates default if None).
        """
        super().__init__()
        self.client = client
        self.cache = cache or ResponseCache()
        self._model_id = getattr(client, "model", "unknown")

    def chat(self, prompt: str) -> str:
        """Send a chat prompt, using cache if available.

        Args:
            prompt: The prompt to send.

        Returns:
            The response text.
        """
        # Check cache
        cached = self.cache.get(prompt, self._model_id)
        if cached is not None:
            logger.debug("Using cached chat response")
            return cached.get("text", "")

        # Call underlying client
        response = self.client.chat(prompt)

        # Cache response
        self.cache.set(prompt, self._model_id, {"text": response})

        return response

    def generate_plan(self, prompt: str) -> GPTPlanResponse:
        """Generate a plan, using cache if available.

        Args:
            prompt: The prompt to send.

        Returns:
            The generated plan response.
        """
        # Check cache
        cached = self.cache.get(prompt, self._model_id)
        if cached is not None:
            logger.info("Using cached plan response")
            # Reconstruct GPTPlanResponse from cached data
            metadata = cached.get("metadata", {})
            metadata["from_cache"] = True
            return GPTPlanResponse(
                plan=cached.get("plan", []),
                metadata=metadata,
            )

        # Call underlying client
        response = self.client.generate_plan(prompt)

        # Cache response (convert to dict for JSON serialization)
        cache_data = {
            "plan": response.plan,
            "metadata": response.metadata,
        }
        self.cache.set(prompt, self._model_id, cache_data)

        return response
