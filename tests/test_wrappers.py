"""Tests for the caching and rate-limiting model wrappers."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from hier_config_ai.agent import build_agent
from hier_config_ai.cache import ResponseCache
from hier_config_ai.model_wrappers import CachedModel, RateLimitedModel
from hier_config_ai.rate_limiter import RateLimiter
from tests.conftest import CORRECT_PLAN, INCOMPLETE_PLAN, scripted_model

if TYPE_CHECKING:
    from pathlib import Path

    from hier_config_ai.deps import RemediationDeps


async def run_once(model: object, deps: RemediationDeps) -> list[str]:
    """Run a one-shot agent against `model` and return the plan."""
    agent = build_agent(model)  # type: ignore[arg-type]
    result = await agent.run("remediate", deps=deps)
    return result.output.plan


async def test_cache_serves_the_second_identical_request(
    tmp_path: Path,
    deps: RemediationDeps,
) -> None:
    """An identical second request is answered from disk, not the model."""
    calls: list[int] = []

    inner = scripted_model(CORRECT_PLAN)
    original = inner.request

    async def counted(*args: object, **kwargs: object) -> object:
        calls.append(1)
        return await original(*args, **kwargs)  # type: ignore[arg-type]

    inner.request = counted  # type: ignore[method-assign, assignment]
    cache = ResponseCache(cache_dir=tmp_path / "cache", ttl_seconds=60.0)
    model = CachedModel(inner, cache)

    first = await run_once(model, deps)
    calls_after_first = len(calls)
    second = await run_once(model, deps)

    assert first == second == CORRECT_PLAN
    assert len(calls) == calls_after_first, "second run should not reach the model"


async def test_chat_and_plan_prompts_do_not_share_a_key(
    tmp_path: Path,
    deps: RemediationDeps,
) -> None:
    """Different requests get different cache keys.

    The previous cache keyed on prompt and model only, so a `chat()` answer
    could be served to `generate_plan()` and produce an empty plan that looked
    like success.
    """
    cache = ResponseCache(cache_dir=tmp_path / "cache", ttl_seconds=60.0)
    model = CachedModel(scripted_model(CORRECT_PLAN), cache)
    agent = build_agent(model)

    first = await agent.run("prompt one", deps=deps)
    second = await agent.run("prompt two", deps=deps)

    assert first.output.plan == CORRECT_PLAN
    assert second.output.plan == CORRECT_PLAN
    assert len(list((tmp_path / "cache").glob("*.json"))) == 2


async def test_rate_limited_model_answers_and_spends_budget(
    deps: RemediationDeps,
) -> None:
    """The wrapper passes the request through and consumes a token."""
    limiter = RateLimiter(max_requests=5, time_window_seconds=60.0)
    model = RateLimitedModel(scripted_model(CORRECT_PLAN), limiter)
    assert await run_once(model, deps) == CORRECT_PLAN
    assert limiter.available_tokens < 5


async def test_cache_hits_across_a_multi_turn_conversation(
    tmp_path: Path,
    deps: RemediationDeps,
) -> None:
    """Repeating a run with tool calls and retries reuses the cached answers.

    Every run here is multi-turn, because tools and `ModelRetry` both add
    turns. Keys built by stripping volatile-looking field names still carried
    `usage` and `provider_response_id`, so no request after the first ever hit
    the cache — and a single-turn test could not see it.
    """
    cache = ResponseCache(cache_dir=tmp_path / "cache", ttl_seconds=60.0)
    inner = scripted_model(INCOMPLETE_PLAN, CORRECT_PLAN)
    model = CachedModel(inner, cache)

    first = await run_once(model, deps)
    entries_after_first = len(list((tmp_path / "cache").glob("*.json")))
    second = await run_once(model, deps)

    assert first == second == CORRECT_PLAN
    assert entries_after_first > 1, "the run should be multi-turn"
    assert len(list((tmp_path / "cache").glob("*.json"))) == entries_after_first, (
        "the second run should add no new cache entries"
    )


async def test_cache_hits_do_not_spend_rate_limit_budget(
    tmp_path: Path,
    deps: RemediationDeps,
) -> None:
    """A repeated run is served from cache without charging the limiter.

    The wrappers used to nest the other way round, so the limiter charged
    before the cache was consulted and a fleet run was throttled on requests
    that never left the process.
    """
    cache = ResponseCache(cache_dir=tmp_path / "cache", ttl_seconds=60.0)
    limiter = RateLimiter(max_requests=60, time_window_seconds=60.0)
    agent = build_agent(
        scripted_model(CORRECT_PLAN),
        cache=cache,
        rate_limiter=limiter,
    )

    await agent.run("remediate", deps=deps)
    spent_after_first = 60.0 - limiter.available_tokens
    await agent.run("remediate", deps=deps)
    spent_after_second = 60.0 - limiter.available_tokens

    assert spent_after_first > 0
    assert spent_after_second == pytest.approx(spent_after_first, abs=0.5)
