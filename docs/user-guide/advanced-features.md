# Advanced Features

## Caching

```python
from hier_config_ai import ResponseCache

workflow.set_model("anthropic:claude-sonnet-4-5", cache=ResponseCache(ttl_seconds=3600))
```

The cache wraps the model rather than the client, so it covers tool calls and
retries as well as the first request.

Keys cover the provider, the model, the settings, the message history, and the
request shape. Per-run fields such as timestamps and conversation ids are
excluded, since including them would make every request unique and the cache
would never hit.

!!! warning "Cached payloads contain device configurations"
    The cache directory is created `0o700` and entries `0o600`. It defaults to
    `~/.hier_config_ai/cache`. Point it somewhere else with
    `ResponseCache(cache_dir=...)`, and treat it as sensitive.

```python
cache.cleanup_expired()   # drop stale entries
cache.clear()             # drop everything
```

## Rate limiting

```python
from hier_config_ai import RateLimiter

workflow.set_model(
    "anthropic:claude-sonnet-4-5",
    rate_limiter=RateLimiter(max_requests=60, time_window_seconds=60),
)
```

A token bucket, limiting requests rather than tokens. Use it alongside a
provider's own limits, not in place of them. The async path yields to the event
loop while waiting, so one throttled request does not stall the others.

Supply both and the cache sits outside the limiter, so a cache hit costs no
budget. Streaming requests are limited too.

## Failover

Ordered failover is PydanticAI's, not ours:

```python
from pydantic_ai.models.fallback import FallbackModel
from hier_config_ai import build_agent

workflow.set_agent(
    build_agent(FallbackModel("anthropic:claude-sonnet-4-5", "openai:gpt-4.1"))
)
```

## Consensus

To ask several models the same question and accept only an answer they agree on:

```python
from hier_config_ai import build_agent, consensus_plan
from hier_config_ai.deps import RemediationDeps

agents = [
    build_agent("anthropic:claude-sonnet-4-5"),
    build_agent("openai:gpt-4.1"),
    build_agent("google-gla:gemini-2.0-flash"),
]

plan = await consensus_plan(agents, prompt, deps)
```

Votes are counted on parsed configuration, so two models that write the same
configuration in a different order still agree. The majority is measured against
the agents asked, not the agents that answered.

!!! note "Quorum did not work before 0.2.0"
    Votes were compared as exact joined strings, so any difference in ordering
    or whitespace prevented agreement and quorum almost always failed. And
    because the threshold divided by the providers that answered, one surviving
    provider out of three could carry the vote by itself.

Consensus costs one full run per model. Reach for failover first; use consensus
only where a wrong plan is expensive enough to justify the bill.

## Concurrency

Rules run concurrently within a workflow:

```python
workflow = AIWorkflowRemediation(running, intended, max_concurrency=8)
```

## Evaluation

Prompt edits, model changes, and retrieval can make output worse as easily as
better. The harness in `evals/` measures whether plans actually converge.

```bash
poetry install --with dev,evals --all-extras
poetry run python evals/run_evals.py --model anthropic:claude-sonnet-4-5
```

The `Converges` scorer applies each plan and re-diffs it. There is usually more
than one correct plan, so no reference answer is used. `PlanLength` is recorded
so a change that keeps plans converging but makes them much longer is visible.

This calls a real provider and costs money, so it is not part of CI.

## Retrieval

Not implemented in 0.2.0. The seams exist: `RemediationDeps.retriever`, the
`Retriever` protocol, tool registration through a list, and a single
retry-message helper. Implement the protocol and assign it to
`workflow.retriever` before `set_model()` to prepare for 0.3.0.
