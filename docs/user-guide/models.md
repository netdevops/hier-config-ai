# Models and Agents

## Naming a model

Any PydanticAI model name works:

```python
workflow.set_model("anthropic:claude-sonnet-4-5")
workflow.set_model("openai:gpt-4.1")
workflow.set_model("google-gla:gemini-2.0-flash")
workflow.set_model("bedrock:anthropic.claude-sonnet-4-5-20250929-v1:0")
workflow.set_model("groq:llama-3.3-70b-versatile")
workflow.set_model("mistral:mistral-large-latest")
```

`set_model()` hands the running configuration's driver to the agent, so the
system prompt describes the real platform: its indent width, its section exit
commands, its replacement negations, and the commands that overwrite rather
than stack.

## Options

```python
from hier_config_ai import RateLimiter, ResponseCache

workflow.set_model(
    "anthropic:claude-sonnet-4-5",
    settings={"temperature": 0.0, "max_tokens": 2048},
    cache=ResponseCache(ttl_seconds=3600),
    rate_limiter=RateLimiter(max_requests=60, time_window_seconds=60),
    retries=3,
)
```

`retries` is how many times the model may correct a rejected plan, not how many
times a failed HTTP request is retried. PydanticAI and the provider SDKs handle
transport retries themselves.

## Building the agent yourself

For anything `set_model()` does not expose, build the agent and pass it in:

```python
from pydantic_ai.models.anthropic import AnthropicModel
from hier_config_ai import build_agent

model = AnthropicModel("claude-sonnet-4-5")
workflow.set_agent(build_agent(model, driver=running.driver))
```

## Self-hosted models

Ollama, vLLM, and anything else with an OpenAI-compatible endpoint:

```python
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from hier_config_ai import build_agent

model = OpenAIChatModel(
    "llama3.2:3b",
    # api_key is a required placeholder; Ollama ignores it.
    provider=OpenAIProvider(base_url="http://localhost:11434/v1", api_key="ollama"),
)

workflow.set_agent(
    build_agent(
        model,
        driver=running.driver,
        output_mode="native",
        settings={"temperature": 0.0, "timeout": 120.0},
    )
)
```

!!! important "Two settings decide whether a local model works at all"
    **`output_mode="native"`.** The default, `"tool"`, asks for structured
    output through a tool call. Hosted models are reliable at that; small
    self-hosted ones frequently are not. Measured against Ollama, `llama3.2:3b`
    emitted the tool call as plain text and passed `plan` as a JSON-encoded
    *string* rather than an array, while `qwen2.5-coder:7b` nested the whole
    `{"name": ..., "arguments": ...}` envelope inside the arguments. Both then
    exhausted their retries. `"native"` asks for a JSON schema on the response
    itself, which both handle correctly.

    **`temperature: 0.0`.** Ollama defaults to `0.8`. At that setting the same
    model and prompt succeeded on one run and failed the next. Pin it to zero
    and the results become reproducible.

    With both applied, `llama3.2:3b` and `qwen2.5-coder:7b` each produced a
    converging plan on the first request.

    Set a `timeout` as well. Without one, a model that will never answer blocks
    the run indefinitely instead of failing.

`"prompted"` is a third option, which asks for JSON in the response text and
parses it. Try it if a model supports neither of the others.

!!! warning "Reasoning models"
    A reasoning model such as `deepseek-r1` emits its thinking before its
    answer, which fights structured output and can leave a run apparently
    hung for a very long time. Prefer a straightforward instruct or coder
    model locally.

Whichever mode you choose, the plan is still validated: a local model cannot
return configuration that fails the convergence check.

If a model cannot cope with having tools available at all, `enable_tools=False`
removes them. That loses the check-your-work loop, so try it only after the
settings above.

## Reading the result

```python
result = await agent.run(prompt, deps=deps)

result.output.plan                       # the commands
result.output.reasoning                  # why the model chose them
result.output.confidence                 # "high" | "medium" | "low"
result.output.commands_requiring_review  # commands that can cut reachability
```

## Token usage

```python
await workflow.aai_remediation_config()
for usage in workflow.usage:
    print(usage.input_tokens, usage.output_tokens)
```

One entry per rule, from the most recent run.
