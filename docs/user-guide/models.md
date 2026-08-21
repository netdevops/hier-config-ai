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

model = OpenAIChatModel(
    "llama3.3",
    provider=OpenAIProvider(base_url="http://localhost:11434/v1", api_key="ollama"),
)
workflow.set_agent(build_agent(model, driver=running.driver))
```

Structured output depends on the model supporting tool calling. Small local
models often do not, and will fail validation repeatedly rather than silently
returning something wrong.

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
