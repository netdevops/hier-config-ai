"""Tests for the on-disk response cache."""

from __future__ import annotations

import json
import stat
import time
from typing import TYPE_CHECKING

from hier_config_ai.cache import ResponseCache

if TYPE_CHECKING:
    from pathlib import Path

PAYLOAD = b'{"plan": ["interface GigabitEthernet0/1"]}'


def build(tmp_path: Path, **kwargs: object) -> ResponseCache:
    """Build a cache rooted in a temporary directory."""
    return ResponseCache(cache_dir=tmp_path / "cache", **kwargs)  # type: ignore[arg-type]


def test_stored_payload_is_returned(tmp_path: Path) -> None:
    """A stored entry comes back unchanged."""
    cache = build(tmp_path)
    cache.set("key", PAYLOAD)
    assert cache.get("key") == PAYLOAD


def test_missing_key_returns_none(tmp_path: Path) -> None:
    """An absent entry is a miss, not an error."""
    assert build(tmp_path).get("absent") is None


def test_expired_entry_is_discarded(tmp_path: Path) -> None:
    """An entry past its TTL is treated as a miss and removed."""
    cache = build(tmp_path, ttl_seconds=0.01)
    cache.set("key", PAYLOAD)
    time.sleep(0.02)
    assert cache.get("key") is None
    assert not list((tmp_path / "cache").glob("*.json"))


def test_disabled_cache_stores_nothing(tmp_path: Path) -> None:
    """A disabled cache neither writes nor reads."""
    cache = build(tmp_path, enabled=False)
    cache.set("key", PAYLOAD)
    assert cache.get("key") is None


def test_distinct_parts_produce_distinct_keys() -> None:
    """Keys derived from different parts do not collide.

    Parts are joined with a separator that cannot appear inside them, so
    ("ab", "c") and ("a", "bc") stay distinct.
    """
    assert ResponseCache.build_key("ab", "c") != ResponseCache.build_key("a", "bc")


def test_same_parts_produce_the_same_key() -> None:
    """The key is a pure function of its parts."""
    assert ResponseCache.build_key("a", "b") == ResponseCache.build_key("a", "b")


def test_cache_directory_is_private(tmp_path: Path) -> None:
    """Cached prompts hold device configs, so the directory is owner-only."""
    cache = build(tmp_path)
    mode = stat.S_IMODE((tmp_path / "cache").stat().st_mode)
    assert mode == 0o700
    cache.set("key", PAYLOAD)
    entry = next((tmp_path / "cache").glob("*.json"))
    assert stat.S_IMODE(entry.stat().st_mode) == 0o600


def test_unreadable_entry_is_discarded(tmp_path: Path) -> None:
    """A corrupt entry is removed rather than raising."""
    cache = build(tmp_path)
    cache.set("key", PAYLOAD)
    entry = next((tmp_path / "cache").glob("*.json"))
    entry.write_text("not json", encoding="utf-8")
    assert cache.get("key") is None
    assert not entry.exists()


def test_non_object_entry_is_discarded(tmp_path: Path) -> None:
    """A JSON document that is not an object is discarded."""
    cache = build(tmp_path)
    cache.set("key", PAYLOAD)
    entry = next((tmp_path / "cache").glob("*.json"))
    entry.write_text(json.dumps([1, 2]), encoding="utf-8")
    assert cache.get("key") is None


def test_clear_removes_every_entry(tmp_path: Path) -> None:
    """Clearing reports how many entries it removed."""
    cache = build(tmp_path)
    cache.set("one", PAYLOAD)
    cache.set("two", PAYLOAD)
    assert cache.clear() == 2
    assert cache.get("one") is None


def test_cleanup_removes_only_expired_entries(tmp_path: Path) -> None:
    """Expired entries go, live ones stay."""
    cache = build(tmp_path, ttl_seconds=60.0)
    cache.set("fresh", PAYLOAD)
    stale = tmp_path / "cache" / f"{ResponseCache.build_key('stale')}.json"
    stale.write_text(
        json.dumps({"timestamp": time.time() - 3600, "payload": "x"}),
        encoding="utf-8",
    )
    assert cache.cleanup_expired() == 1
    assert cache.get("fresh") == PAYLOAD


def test_write_is_atomic(tmp_path: Path) -> None:
    """No temporary file survives a successful write."""
    cache = build(tmp_path)
    cache.set("key", PAYLOAD)
    assert not list((tmp_path / "cache").glob("*.tmp"))
