"""Tests for the caching and rate-limiting client wrappers."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from hier_config_gpt.clients.cache import ResponseCache
from hier_config_gpt.clients.cached_client import CachedGPTClient
from hier_config_gpt.clients.models import GPTPlanResponse
from hier_config_gpt.clients.rate_limited_client import RateLimitedGPTClient
from hier_config_gpt.clients.rate_limiter import RateLimiter
from tests.conftest import StubGPTClient

if TYPE_CHECKING:
    import pytest


def test_cached_client_chat_miss_then_hit(tmp_path: Path) -> None:
    stub = StubGPTClient(chat_response="live response")
    client = CachedGPTClient(stub, cache=ResponseCache(cache_dir=tmp_path))

    assert client.chat("prompt") == "live response"
    assert client.chat("prompt") == "live response"
    # The second call was served from the cache.
    assert len(stub.prompts) == 1


def test_cached_client_generate_plan_miss_then_hit(tmp_path: Path) -> None:
    plan = GPTPlanResponse(plan=["command1"], metadata={"provider": "stub"})
    stub = StubGPTClient(plan_responses=(plan,))
    client = CachedGPTClient(stub, cache=ResponseCache(cache_dir=tmp_path))

    first = client.generate_plan("prompt")
    second = client.generate_plan("prompt")

    assert first.plan == ["command1"]
    assert second.plan == ["command1"]
    assert second.metadata["from_cache"] is True
    # The second call was served from the cache.
    assert len(stub.prompts) == 1


def test_cached_client_default_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    client = CachedGPTClient(StubGPTClient(chat_response="live"))

    assert client.chat("prompt") == "live"
    assert client.cache.cache_dir == tmp_path / ".hier_config_gpt" / "cache"


def test_rate_limited_client_passthrough() -> None:
    plan = GPTPlanResponse(plan=["command1"])
    stub = StubGPTClient(plan_responses=(plan,), chat_response="chat response")
    client = RateLimitedGPTClient(stub, max_requests=10, time_window_seconds=60.0)

    assert client.chat("prompt") == "chat response"
    assert client.generate_plan("prompt").plan == ["command1"]
    assert client.rate_limiter.available_tokens < 10


def test_rate_limited_client_custom_limiter() -> None:
    limiter = RateLimiter(max_requests=5, time_window_seconds=60.0)
    client = RateLimitedGPTClient(StubGPTClient(), rate_limiter=limiter)

    assert client.rate_limiter is limiter
