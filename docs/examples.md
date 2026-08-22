# Examples

## Access list resequencing

The case hier-config cannot resolve on its own, and the one its
[custom workflows guide](https://hier-config.readthedocs.io/en/latest/user/custom-workflows/)
solves with hand-written Python. `examples/ollama_acl.py` runs it against a
local Ollama model.

```python
import asyncio

from hier_config import HConfig, Platform
from hier_config.models import MatchRule

from hier_config_ai import (
    AIRemediationExample,
    AIRemediationRule,
    AIWorkflowRemediation,
)

running = HConfig.from_text(Platform.CISCO_IOS, """
ip access-list extended TEST
 12 permit ip 10.0.0.0 0.0.0.7 any
""")

intended = HConfig.from_text(Platform.CISCO_IOS, """
ip access-list extended TEST
 10 permit ip 10.0.1.0 0.0.0.255 any
 20 permit ip 10.0.0.0 0.0.0.7 any
""")

workflow = AIWorkflowRemediation(running, intended)
workflow.set_model("anthropic:claude-sonnet-4-5")
workflow.add_rule(
    AIRemediationRule(
        description=(
            "Rewrite the access list so its entries end up with the intended "
            "sequence numbers.\n"
            "An entry cannot be renumbered in place. Delete it by number with "
            "'no <seq>', then add it back at its new number.\n"
            "The list must never deny live traffic while it is being "
            "rewritten. Add '1 permit ip any any' as the first command, and "
            "remove it with 'no 1' as the last."
        ),
        lineage=(MatchRule(startswith="ip access-list"),),
        example=AIRemediationExample(
            running_config="ip access-list extended EXAMPLE\n 15 permit ip any any",
            remediation_config=(
                "ip access-list extended EXAMPLE\n"
                "  1 permit ip any any\n"
                "  no 15\n"
                "  10 permit ip 192.0.2.0 0.0.0.255 any\n"
                "  20 permit ip any any\n"
                "  no 1"
            ),
        ),
    )
)

print("\n".join(asyncio.run(workflow.aai_remediation_config()).to_lines()))
```

```
ip access-list extended TEST
  1 permit ip any any
  no 12
  10 permit ip 10.0.1.0 0.0.0.255 any
  20 permit ip 10.0.0.0 0.0.0.7 any
  no 1
```

The temporary allow-all keeps the list from denying traffic while its entries
are renumbered. It and its `no 1` are recognised as a pair whose net effect is
nothing; forgetting the cleanup would be rejected.

!!! note "State ordering constraints explicitly"
    Without the traffic-safety sentence in `description`, the model returns the
    same plan hier-config generates and validation accepts it — the end state is
    identical. Convergence proves the end state, not that the path was safe.

## Running it on a laptop

The same rule against a local model. `output_mode="native"` and a temperature of
zero are what make a small model usable; see
[Models and Agents](user-guide/models.md).

```python
from pydantic_ai.models.ollama import OllamaModel
from pydantic_ai.providers.ollama import OllamaProvider

model = OllamaModel(
    "qwen2.5-coder:7b",
    provider=OllamaProvider(base_url="http://localhost:11434/v1"),
)
workflow.set_model(
    model,
    settings={"temperature": 0.0, "timeout": 180.0},
    output_mode="native",
)
```

Verified end to end against `qwen2.5-coder:7b`, which produces the traffic-safe
plan above. A 3B model manages simpler sections but not this one.

## Reviewing before applying

```python
from hier_config_ai import build_agent
from hier_config_ai.deps import RemediationDeps

agent = build_agent("anthropic:claude-sonnet-4-5", driver=running.driver)
result = await agent.run(prompt, deps=RemediationDeps(running, intended))
plan = result.output

print(plan.reasoning)
print(f"confidence: {plan.confidence}")

if plan.commands_requiring_review:
    print("Review before applying:")
    for command in plan.commands_requiring_review:
        print(" ", command)

if plan.confidence == "low":
    raise SystemExit("Low confidence. Have an engineer check this.")
```

## Several rules on one device

Rules run concurrently, so this costs one round trip, not three.

```python
workflow.add_rule(acl_rule)
workflow.add_rule(vlan_rule)
workflow.add_rule(interface_rule)

remediation = await workflow.aai_remediation_config()

for usage in workflow.usage:
    print(usage.input_tokens, usage.output_tokens)
```

## Many devices at once

```python
import asyncio

async def remediate(device):
    workflow = AIWorkflowRemediation(device.running, device.intended)
    workflow.set_model("anthropic:claude-sonnet-4-5", cache=shared_cache)
    workflow.add_rule(acl_rule)
    return device.name, await workflow.aai_remediation_config()

async def main(devices):
    limit = asyncio.Semaphore(10)

    async def one(device):
        async with limit:
            return await remediate(device)

    return await asyncio.gather(*(one(d) for d in devices), return_exceptions=True)
```

Share one `ResponseCache` and one `RateLimiter` across devices. Identical
sections across a fleet then cost a single call.

## Failover

```python
from pydantic_ai.models.fallback import FallbackModel
from hier_config_ai import build_agent

workflow.set_agent(
    build_agent(
        FallbackModel("anthropic:claude-sonnet-4-5", "openai:gpt-4.1"),
        driver=running.driver,
    )
)
```

## Self-hosted model

```python
from pydantic_ai.models.ollama import OllamaModel
from pydantic_ai.providers.ollama import OllamaProvider

model = OllamaModel(
    "qwen2.5-coder:7b",
    provider=OllamaProvider(base_url="http://localhost:11434/v1"),
)
workflow.set_model(model, output_mode="native", settings={"temperature": 0.0})
```

Structured output needs tool calling. Small local models often lack it, and will
fail validation repeatedly rather than quietly returning something wrong.

## Handling failure

```python
from hier_config_ai import AIClientInitializationError, RemediationError

try:
    remediation = await workflow.aai_remediation_config()
except AIClientInitializationError:
    print("No model configured.")
except RemediationError as exc:
    print(f"Could not produce a usable plan: {exc}")
```

A plan that fails validation is not an error. It goes back to the model, which
corrects it. `RemediationError` means the model could not produce a working plan
within its retries.
