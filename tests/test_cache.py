"""Tests for the file-based response cache."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import TYPE_CHECKING

from hier_config_gpt.clients.cache import ResponseCache

if TYPE_CHECKING:
    import pytest


def test_cache_set_and_get(tmp_path: Path) -> None:
    cache = ResponseCache(cache_dir=tmp_path)
    cache.set("prompt", "model", {"text": "response"})

    assert cache.get("prompt", "model") == {"text": "response"}


def test_cache_get_miss(tmp_path: Path) -> None:
    cache = ResponseCache(cache_dir=tmp_path)

    assert cache.get("unknown prompt", "model") is None


def test_cache_get_expired_deletes_file(tmp_path: Path) -> None:
    cache = ResponseCache(cache_dir=tmp_path, ttl_seconds=0.0)
    cache.set("prompt", "model", {"text": "response"})
    assert len(list(tmp_path.glob("*.json"))) == 1

    time.sleep(0.01)
    assert cache.get("prompt", "model") is None
    assert len(list(tmp_path.glob("*.json"))) == 0


def test_cache_disabled(tmp_path: Path) -> None:
    cache_dir = tmp_path / "cache"
    cache = ResponseCache(cache_dir=cache_dir, enabled=False)

    cache.set("prompt", "model", {"text": "response"})
    assert not cache_dir.exists()
    assert cache.get("prompt", "model") is None
    assert cache.clear() == 0
    assert cache.cleanup_expired() == 0


def test_cache_default_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    cache = ResponseCache()

    assert cache.cache_dir == tmp_path / ".hier_config_gpt" / "cache"
    assert cache.cache_dir.is_dir()


def test_cache_corrupt_file_returns_none(tmp_path: Path) -> None:
    cache = ResponseCache(cache_dir=tmp_path)
    cache.set("prompt", "model", {"text": "response"})
    cache_file = next(tmp_path.glob("*.json"))
    cache_file.write_text("not json", encoding="utf-8")

    assert cache.get("prompt", "model") is None


def test_cache_non_dict_payload_returns_none(tmp_path: Path) -> None:
    cache = ResponseCache(cache_dir=tmp_path)
    cache.set("prompt", "model", {"text": "response"})
    cache_file = next(tmp_path.glob("*.json"))
    cache_file.write_text("[1, 2, 3]", encoding="utf-8")

    assert cache.get("prompt", "model") is None


def test_cache_non_dict_response_returns_none(tmp_path: Path) -> None:
    cache = ResponseCache(cache_dir=tmp_path)
    cache.set("prompt", "model", {"text": "response"})
    cache_file = next(tmp_path.glob("*.json"))
    cache_file.write_text(
        json.dumps({"timestamp": time.time(), "response": "not a dict"}),
        encoding="utf-8",
    )

    assert cache.get("prompt", "model") is None


def test_cache_clear(tmp_path: Path) -> None:
    cache = ResponseCache(cache_dir=tmp_path)
    cache.set("prompt1", "model", {"text": "response1"})
    cache.set("prompt2", "model", {"text": "response2"})

    assert cache.clear() == 2
    assert cache.get("prompt1", "model") is None


def test_cache_cleanup_expired(tmp_path: Path) -> None:
    cache = ResponseCache(cache_dir=tmp_path, ttl_seconds=3600.0)
    cache.set("fresh", "model", {"text": "fresh"})
    expired_file = tmp_path / "expired.json"
    expired_file.write_text(
        json.dumps({"timestamp": time.time() - 7200, "response": {"text": "old"}}),
        encoding="utf-8",
    )

    assert cache.cleanup_expired() == 1
    assert not expired_file.exists()
    assert cache.get("fresh", "model") == {"text": "fresh"}


def test_cache_cleanup_expired_skips_corrupt_files(tmp_path: Path) -> None:
    cache = ResponseCache(cache_dir=tmp_path)
    corrupt_file = tmp_path / "corrupt.json"
    corrupt_file.write_text("not json", encoding="utf-8")

    assert cache.cleanup_expired() == 0
    assert corrupt_file.exists()


def test_cache_missing_timestamp_treated_as_expired(tmp_path: Path) -> None:
    cache = ResponseCache(cache_dir=tmp_path, ttl_seconds=3600.0)
    cache.set("prompt", "model", {"text": "response"})
    cache_file = next(tmp_path.glob("*.json"))
    cache_file.write_text(
        json.dumps({"timestamp": "invalid", "response": {"text": "response"}}),
        encoding="utf-8",
    )

    assert cache.get("prompt", "model") is None
