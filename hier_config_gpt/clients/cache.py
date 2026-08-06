"""Response caching for LLM API calls to reduce costs and improve performance."""

from __future__ import annotations

import contextlib
import hashlib
import json
import logging
import time
from pathlib import Path
from typing import Any, cast

logger = logging.getLogger(__name__)


def _coerce_timestamp(raw_timestamp: object) -> float:
    """Convert a cached timestamp value into a float, defaulting to zero."""
    if isinstance(raw_timestamp, int | float):
        return float(raw_timestamp)
    return 0.0


class ResponseCache:
    """Simple file-based cache for LLM responses.

    Caches responses by prompt hash with configurable TTL (time-to-live).
    """

    def __init__(
        self,
        cache_dir: Path | None = None,
        ttl_seconds: float = 3600.0,
        *,
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

    @staticmethod
    def _get_cache_key(prompt: str, model: str) -> str:
        """Generate a cache key from prompt and model."""
        content = f"{model}:{prompt}"
        return hashlib.sha256(content.encode()).hexdigest()

    def _get_cache_path(self, cache_key: str) -> Path:
        """Get the file path for a cache key."""
        return self.cache_dir / f"{cache_key}.json"

    @staticmethod
    def _read_cache_file(cache_path: Path) -> dict[str, object] | None:
        """Read a cache file, returning None when unreadable or malformed."""
        try:
            data: object = json.loads(cache_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to read cache file %s: %s", cache_path, exc)
            return None

        if isinstance(data, dict):
            return cast("dict[str, object]", data)
        return None

    def get(self, prompt: str, model: str) -> dict[str, Any] | None:
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

        cached_data = self._read_cache_file(cache_path)
        if cached_data is None:
            return None

        age = time.time() - _coerce_timestamp(cached_data.get("timestamp", 0))
        if age > self.ttl_seconds:
            logger.debug("Cache expired for key %s (age: %.1fs)", cache_key[:8], age)
            with contextlib.suppress(OSError):
                cache_path.unlink()  # Delete expired cache
            return None

        logger.info("Cache hit for key %s (age: %.1fs)", cache_key[:8], age)
        response = cached_data.get("response")
        if isinstance(response, dict):
            return cast("dict[str, Any]", response)
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
            cache_path.write_text(json.dumps(cached_data, indent=2), encoding="utf-8")
        except OSError as exc:
            logger.warning("Failed to write cache file %s: %s", cache_path, exc)
        else:
            logger.debug("Cached response for key %s", cache_key[:8])

    @staticmethod
    def _delete_cache_file(cache_file: Path) -> bool:
        """Delete one cache file, returning True on success."""
        try:
            cache_file.unlink()
        except OSError as exc:
            logger.warning("Failed to delete cache file %s: %s", cache_file, exc)
            return False
        return True

    def clear(self) -> int:
        """Clear all cache entries.

        Returns:
            Number of cache files deleted.

        """
        if not self.enabled or not self.cache_dir.exists():
            return 0

        count = sum(
            self._delete_cache_file(cache_file)
            for cache_file in self.cache_dir.glob("*.json")
        )

        logger.info("Cleared %d cache entries", count)
        return count

    def _cleanup_file_if_expired(self, cache_file: Path, current_time: float) -> bool:
        """Delete one cache file when expired, returning True when deleted."""
        cached_data = self._read_cache_file(cache_file)
        if cached_data is None:
            return False

        age = current_time - _coerce_timestamp(cached_data.get("timestamp", 0))
        if age > self.ttl_seconds:
            return self._delete_cache_file(cache_file)
        return False

    def cleanup_expired(self) -> int:
        """Remove expired cache entries.

        Returns:
            Number of expired cache files deleted.

        """
        if not self.enabled or not self.cache_dir.exists():
            return 0

        current_time = time.time()
        count = sum(
            self._cleanup_file_if_expired(cache_file, current_time)
            for cache_file in self.cache_dir.glob("*.json")
        )

        if count > 0:
            logger.info("Cleaned up %d expired cache entries", count)

        return count
