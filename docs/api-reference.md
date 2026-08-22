# API Reference

## AIWorkflowRemediation

Extends hier-config's `WorkflowRemediation`.

```python
AIWorkflowRemediation(
    running_config: HConfig,
    generated_config: HConfig,
    plugins: Iterable[Callable[[HConfig], None]] = (),
    *,
    prompt_template: PromptTemplate | None = None,
    max_concurrency: int = 4,
)
```

| Method | Description |
| --- | --- |
| `set_model(model, *, settings=None, cache=None, rate_limiter=None, retries=3, output_mode="tool", enable_tools=True)` | Build an agent for a model name or `Model`. |
| `set_agent(agent)` | Use a pre-built agent. |
| `add_rule(rule)` | Add a remediation rule. |
| `clear_rules()` | Remove every rule. |
| `await aai_remediation_config()` | Generate the remediation config. Rules run concurrently. |
| `ai_remediation_config()` | Synchronous form. Raises `RuntimeError` inside a running event loop. |

| Property | Description |
| --- | --- |
| `rules` | The rules currently loaded. |
| `retriever` | Retriever handed to tools and validators. Plain attribute; set it before `set_model()`. |
| `usage` | Per-rule token usage from the most recent run. |

Raises `AIClientInitializationError` when no model is configured, and
`RemediationError` when no rules are loaded or the model produces nothing usable.

## Models

### AIRemediationRule

| Field | Type | Description |
| --- | --- | --- |
| `description` | `str` | What the model should achieve. Write it as an instruction. |
| `lineage` | `tuple[MatchRule, ...]` | Selects the config section, as in hier-config. |
| `example` | `AIRemediationExample` | A worked running/remediation pair. |

### AIRemediationExample

| Field | Type |
| --- | --- |
| `running_config` | `str` |
| `remediation_config` | `str` |

### AIRemediationContext

Built per rule and passed to the prompt template.

| Field | Type |
| --- | --- |
| `description` | `str` |
| `running_config` | `str` |
| `generated_config` | `str` |
| `example` | `AIRemediationExample` |

### AIPlanResponse

What the model returns, after validation.

| Field | Type | Description |
| --- | --- | --- |
| `plan` | `list[str]` | The commands. Blank entries are dropped; indentation is preserved. |
| `reasoning` | `str` | Why the model chose them. |
| `confidence` | `"high" \| "medium" \| "low"` | The model's own assessment. |
| `commands_requiring_review` | `list[str]` | Commands that can cut reachability. |
| `metadata` | `dict[str, Any]` | Free-form. Consensus results land here. |

## build_agent

```python
build_agent(
    model: Model | str,
    *,
    driver: HConfigDriverBase | None = None,
    settings: ModelSettings | None = None,
    cache: ResponseCache | None = None,
    rate_limiter: RateLimiter | None = None,
    retriever: Retriever | None = None,
    retries: int = 3,
    max_concurrency: int | None = None,
    output_mode: Literal["tool", "native", "prompted"] = "tool",
    enable_tools: bool = True,
) -> Agent[RemediationDeps, AIPlanResponse]
```

Set `output_mode="native"` for a small self-hosted model; the default
`"tool"` mode relies on tool calling, which they are often unreliable at.

Passing `driver` adds that platform's indentation, section exits, replacement
negations, and idempotent commands to the system prompt.

## RemediationDeps

Per-run state shared by the prompt, tools, and validators.

| Field | Type |
| --- | --- |
| `running_config` | `HConfig` |
| `generated_config` | `HConfig` |
| `retriever` | `Retriever \| None` |

`deps.driver` returns the running config's driver. `canonical_future`,
`canonical_lines`, and `canonical_line_set` are cached derivations of the
convergence target, computed once per run.

## Retriever

A protocol. No implementation ships in 0.2.0.

```python
async def search(query: str, *, platform: Platform, k: int = 5) -> list[str]
async def similar_remediations(
    running_config: HConfig,
    generated_config: HConfig,
    *,
    platform: Platform,
    k: int = 3,
) -> list[AIRemediationExample]
```

## Validation

| Function | Description |
| --- | --- |
| `remaining_difference(deps, plan)` | Returns `(missing, unwanted)`. Both empty means the plan converges. |
| `plan_converges(deps, plan)` | Whether a plan produces the intended configuration. |
| `review_patterns(negation_prefix)` | Risky-command patterns for a platform's negation syntax. |
| `format_difference(missing, unwanted)` | Renders a failed check for the model. |
| `validate_plan(ctx, output)` | The output validator. Raises `ModelRetry`. |

## Tools

| Function | Description |
| --- | --- |
| `test_remediation(ctx, commands)` | Reports what candidate commands would do. |
| `get_config_section(ctx, lineage)` | Fetches a further config section. |
| `build_tools(retriever=None)` | Returns the tools an agent should be given. |

## consensus_plan

```python
await consensus_plan(agents, prompt, deps) -> AIPlanResponse
```

Runs every agent concurrently and returns the plan a majority agree on. Votes
are counted on parsed configuration, using `deps.driver`. Raises
`ConsensusError` if every agent fails or no plan reaches a majority, and
`ValueError` if no agents were supplied.

`plan_fingerprint(driver, plan)` exposes the value votes are counted on.

## Caching and rate limiting

```python
ResponseCache(cache_dir=None, ttl_seconds=3600.0, *, enabled=True)
RateLimiter(max_requests=60, time_window_seconds=60.0)
```

| Method | Description |
| --- | --- |
| `ResponseCache.build_key(*parts)` | Hash parts into a key. |
| `ResponseCache.get(key)` / `.set(key, payload)` | Read and write entries. |
| `ResponseCache.clear()` / `.cleanup_expired()` | Remove entries. |
| `RateLimiter.acquire(tokens=1, timeout=None)` | Take tokens, blocking. |
| `RateLimiter.aacquire(tokens=1, timeout=None)` | Take tokens without blocking the event loop. |
| `RateLimiter.try_acquire(tokens=1)` | Take tokens only if free now. |

`CachedModel` and `RateLimitedModel` wrap any PydanticAI model.

## PromptTemplate

```python
PromptTemplate(template: str | None = None)
PromptTemplate.from_file(path)
PromptTemplate.build(context: AIRemediationContext) -> str
```

Requires `{running_config}`, `{generated_config}`, `{description}`,
`{example_running_config}`, and `{example_remediation_config}`.

## Exceptions

```
HierConfigAIError
├── AIClientInitializationError
└── RemediationError
    └── ConsensusError
```

## Other

| Name | Description |
| --- | --- |
| `scoped_config(config, lineage)` | Returns only the part of a config a lineage selects. |
| `build_context(rule, running, generated)` | Builds the prompt context for one rule. |
| `__version__` | The installed version. |
