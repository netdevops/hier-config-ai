"""File-based response cache for model requests.

Cached payloads contain whole device configurations, so the cache directory is
created private to the current user and every entry is written with restrictive
permissions.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import logging
import time
from pathlib import Path
from typing import cast

logger = logging.getLogger(__name__)

_DIR_MODE = 0o700
_FILE_MODE = 0o600


def _write_private(temporary: Path, document: str, path: Path) -> None:
    """Write `document` to a private temporary file, then move it into place.

    Renaming rather than writing in place means a concurrent reader never sees
    a half-written entry.
    """
    temporary.write_text(document, encoding="utf-8")
    temporary.chmod(_FILE_MODE)
    temporary.replace(path)


def _coerce_timestamp(raw_timestamp: object) -> float:
    """Convert a cached timestamp value into a float, defaulting to zero."""
    if isinstance(raw_timestamp, int | float):
        return float(raw_timestamp)
    return 0.0


class ResponseCache:
    """Time-limited, on-disk cache keyed by an opaque caller-supplied string.

    The cache stores raw bytes and never inspects them. Callers own the key, so
    everything that changes a response — provider, model, settings, and the
    full request body — must be folded into the key by the caller. See
    `hier_config_ai.model_wrappers.CachedModel.cache_key`.
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
            cache_dir: Directory for cache files (default: ~/.hier_config_ai/cache).
            ttl_seconds: Time-to-live for cache entries in seconds (default: 3600).
            enabled: Whether caching is enabled (default: True).

        """
        if cache_dir is None:
            cache_dir = Path.home() / ".hier_config_ai" / "cache"

        self.cache_dir = Path(cache_dir)
        self.ttl_seconds = ttl_seconds
        self.enabled = enabled

        if self.enabled:
            self.cache_dir.mkdir(parents=True, exist_ok=True, mode=_DIR_MODE)
            with contextlib.suppress(OSError):
                self.cache_dir.chmod(_DIR_MODE)
            logger.debug(
                "Response cache initialized at %s (TTL: %ss)",
                self.cache_dir,
                ttl_seconds,
            )

    @staticmethod
    def build_key(*parts: str) -> str:
        """Hash the given parts into a cache key.

        Parts are joined with a separator that cannot appear in a hex digest or
        a JSON document boundary, so two different part lists cannot collide by
        concatenating to the same string.
        """
        return hashlib.sha256("\x00".join(parts).encode()).hexdigest()

    def _path(self, key: str) -> Path:
        """Return the file path holding the entry for `key`."""
        return self.cache_dir / f"{key}.json"

    def _load(self, path: Path) -> dict[str, object] | None:
        """Read and decode one cache file, discarding it if it is unusable."""
        try:
            raw: object = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None
        except (OSError, json.JSONDecodeError):
            logger.warning("Discarding unreadable cache entry %s", path)
            self._discard(path)
            return None

        if not isinstance(raw, dict):
            self._discard(path)
            return None

        return cast("dict[str, object]", raw)

    @staticmethod
    def _discard(path: Path) -> None:
        """Delete a cache file, ignoring the case where it is already gone."""
        with contextlib.suppress(OSError):
            path.unlink()

    def get(self, key: str) -> bytes | None:
        """Return the cached payload for `key`, or None when absent or stale."""
        if not self.enabled:
            return None

        path = self._path(key)
        raw = self._load(path)
        if raw is None:
            return None

        age = time.time() - _coerce_timestamp(raw.get("timestamp"))
        if age > self.ttl_seconds:
            logger.debug("Cache entry %s expired after %.0fs", key, age)
            self._discard(path)
            return None

        payload = raw.get("payload")
        return payload.encode() if isinstance(payload, str) else None

    def set(self, key: str, payload: bytes) -> None:
        """Store `payload` under `key`.

        Writes to a temporary file and renames it, so a concurrent reader never
        observes a half-written entry.
        """
        if not self.enabled:
            return

        path = self._path(key)
        temporary = path.with_suffix(f".{id(payload):x}.tmp")
        document = json.dumps(
            {"timestamp": time.time(), "payload": payload.decode()},
        )

        try:
            _write_private(temporary, document, path)
        except OSError as exc:
            logger.warning("Could not write cache entry %s: %s", path, exc)
            self._discard(temporary)

    def clear(self) -> int:
        """Delete every cache entry and return how many were removed."""
        paths = list(self.cache_dir.glob("*.json"))
        for path in paths:
            self._discard(path)
        return len(paths)

    def cleanup_expired(self) -> int:
        """Delete expired entries and return how many were removed."""
        removed = 0
        now = time.time()
        for path in self.cache_dir.glob("*.json"):
            raw = self._load(path)
            stale = raw is None or (
                now - _coerce_timestamp(raw.get("timestamp")) > self.ttl_seconds
            )
            if stale:
                self._discard(path)
                removed += 1
        return removed
