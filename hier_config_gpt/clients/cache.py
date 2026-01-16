"""Response caching for LLM API calls to reduce costs and improve performance."""

from __future__ import annotations

import hashlib
import json
import logging
import time
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


class ResponseCache:
    """Simple file-based cache for LLM responses.

    Caches responses by prompt hash with configurable TTL (time-to-live).
    """

    def __init__(
        self,
        cache_dir: Optional[Path] = None,
        ttl_seconds: float = 3600.0,
        enabled: bool = True,
    ) -> None:
        """Initialize the response cache.

        Args:
            cache_dir: Directory for cache files (default: ~/.hier_config_gpt/cache).
            ttl_seconds: Time-to-live for cache entries in seconds (default: 3600).
            enabled: Whether caching is enabled (default: True).
        """
        if cache_dir is None:
            cache_dir = Path.home() / ".hier_config_gpt" / "cache"

        self.cache_dir = Path(cache_dir)
        self.ttl_seconds = ttl_seconds
        self.enabled = enabled

        if self.enabled:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            logger.debug(
                "Response cache initialized at %s (TTL: %ds)",
                self.cache_dir,
                ttl_seconds,
            )

    def _get_cache_key(self, prompt: str, model: str) -> str:
        """Generate a cache key from prompt and model."""
        content = f"{model}:{prompt}"
        return hashlib.sha256(content.encode()).hexdigest()

    def _get_cache_path(self, cache_key: str) -> Path:
        """Get the file path for a cache key."""
        return self.cache_dir / f"{cache_key}.json"

    def get(self, prompt: str, model: str) -> Optional[dict[str, Any]]:
        """Retrieve a cached response if available and not expired.

        Args:
            prompt: The prompt text.
            model: The model identifier.

        Returns:
            Cached response data or None if not found or expired.
        """
        if not self.enabled:
            return None

        cache_key = self._get_cache_key(prompt, model)
        cache_path = self._get_cache_path(cache_key)

        if not cache_path.exists():
            logger.debug("Cache miss for key %s", cache_key[:8])
            return None

        try:
            with cache_path.open("r") as f:
                cached_data = json.load(f)

            # Check if expired
            cached_time = cached_data.get("timestamp", 0)
            age = time.time() - cached_time

            if age > self.ttl_seconds:
                logger.debug(
                    "Cache expired for key %s (age: %.1fs)", cache_key[:8], age
                )
                cache_path.unlink()  # Delete expired cache
                return None

            logger.info("Cache hit for key %s (age: %.1fs)", cache_key[:8], age)
            return cached_data.get("response")

        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to read cache file %s: %s", cache_path, e)
            return None

    def set(self, prompt: str, model: str, response: dict[str, Any]) -> None:
        """Store a response in the cache.

        Args:
            prompt: The prompt text.
            model: The model identifier.
            response: The response data to cache.
        """
        if not self.enabled:
            return

        cache_key = self._get_cache_key(prompt, model)
        cache_path = self._get_cache_path(cache_key)

        cached_data = {
            "timestamp": time.time(),
            "prompt_hash": cache_key,
            "model": model,
            "response": response,
        }

        try:
            with cache_path.open("w") as f:
                json.dump(cached_data, f, indent=2)
            logger.debug("Cached response for key %s", cache_key[:8])
        except OSError as e:
            logger.warning("Failed to write cache file %s: %s", cache_path, e)

    def clear(self) -> int:
        """Clear all cache entries.

        Returns:
            Number of cache files deleted.
        """
        if not self.enabled or not self.cache_dir.exists():
            return 0

        count = 0
        for cache_file in self.cache_dir.glob("*.json"):
            try:
                cache_file.unlink()
                count += 1
            except OSError as e:
                logger.warning("Failed to delete cache file %s: %s", cache_file, e)

        logger.info("Cleared %d cache entries", count)
        return count

    def cleanup_expired(self) -> int:
        """Remove expired cache entries.

        Returns:
            Number of expired cache files deleted.
        """
        if not self.enabled or not self.cache_dir.exists():
            return 0

        count = 0
        current_time = time.time()

        for cache_file in self.cache_dir.glob("*.json"):
            try:
                with cache_file.open("r") as f:
                    cached_data = json.load(f)

                cached_time = cached_data.get("timestamp", 0)
                age = current_time - cached_time

                if age > self.ttl_seconds:
                    cache_file.unlink()
                    count += 1

            except (json.JSONDecodeError, OSError) as e:
                logger.warning("Failed to process cache file %s: %s", cache_file, e)

        if count > 0:
            logger.info("Cleaned up %d expired cache entries", count)

        return count
