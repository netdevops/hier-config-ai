# hier-config-ai

[![PyPI](https://img.shields.io/pypi/v/hier-config-ai.svg)](https://pypi.org/project/hier-config-ai/)
[![Python](https://img.shields.io/pypi/pyversions/hier-config-ai.svg)](https://pypi.org/project/hier-config-ai/)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)

Network configuration remediation driven by a language model, built on
[hier-config](https://github.com/netdevops/hier-config) and
[PydanticAI](https://ai.pydantic.dev/).

## What it is for

hier-config resolves most configuration differences deterministically. A few it
cannot, and its
[custom workflows guide](https://hier-config.readthedocs.io/en/latest/user/custom-workflows/)
shows how those are handled today: inspect the default remediation, decide it is
wrong, and build the correct one yourself in Python.

This library lets you describe the requirement instead.

## The canonical case

An access list needs a new entry ahead of an existing one, so the existing entry
must move from sequence 12 to 20. hier-config produces the right end state:

```
ip access-list extended TEST
  no 12 permit ip 10.0.0.0 0.0.0.7 any
  10 permit ip 10.0.1.0 0.0.0.255 any
  20 permit ip 10.0.0.0 0.0.0.7 any
```

Between the removal and the re-add, though, the list matches nothing and an
implicit deny drops live traffic. Avoiding that is what the manual workflow
exists for — a temporary allow-all, a renumbering loop, a cleanup, written in
Python and maintained per access list.

Described as a rule instead:

```python
acl_rule = AIRemediationRule(
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
```

Which produces:

```
ip access-list extended TEST
  1 permit ip any any
  no 12
  10 permit ip 10.0.1.0 0.0.0.255 any
  20 permit ip 10.0.0.0 0.0.0.7 any
  no 1
```

The rule matches `ip access-list` generally rather than one list by name.
`examples/ollama_acl.py` runs this against a local Ollama model, verified with
`qwen2.5-coder:7b` on a laptop — it does not need a frontier model.

## The plan is verified, not trusted

The model's plan is applied to the running configuration and re-checked against
the intended one. If it does not converge, the difference goes back to the model
and it corrects itself.

```
rule -> prompt -> model -> plan
                            |
                     apply and re-diff
                            |
                 converged? -- no --> tell the model what is still wrong
                            |
                           yes
                            |
                          HConfig
```

That loop is the point of the library. A plan that reads well and still leaves
the device misconfigured is worse than no plan at all.

The scaffolding above is understood: `1 permit ip any any` followed by `no 1` is
a pair whose net effect is nothing. **Forgetting the cleanup is rejected** — a
`permit ip any any` left in a live access list is a hole.

## What it does not do for you

**Convergence proves the end state, not the path.** Leave the traffic-safety
sentence out of the description and the model returns the same unsafe plan
hier-config generates, which validation accepts because the end state matches.
Ordering constraints have to be stated. That is prose rather than Python, but it
is not inferred.

**Only send what needs judgment.** Deterministic remediation is correct for most
configuration, and it is free, instant, and never wrong.

## Install

```bash
pip install "hier-config-ai[anthropic]"    # or [openai], [google], [bedrock]
```

Ollama, Azure OpenAI, and OpenRouter speak the OpenAI-compatible API, so they
use the `openai` extra.

## Use

The rule above, with the surrounding scaffolding:

```python
import asyncio

from hier_config import HConfig, Platform
from hier_config.models import MatchRule

from hier_config_ai import (
    AIRemediationExample,
    AIRemediationRule,
    AIWorkflowRemediation,
)

running = HConfig.from_text(Platform.CISCO_IOS, open("running.conf").read())
intended = HConfig.from_text(Platform.CISCO_IOS, open("intended.conf").read())

workflow = AIWorkflowRemediation(running, intended)
workflow.set_model("anthropic:claude-sonnet-4-5")
workflow.add_rule(acl_rule)   # the AIRemediationRule shown above

remediation = asyncio.run(workflow.aai_remediation_config())
print("\n".join(remediation.to_lines()))
```

Add one rule per section that needs judgment. Rules run concurrently, so a
device with several of them costs one round trip rather than several.
`aai_remediation_config()` is the async form.

## Reviewing a plan before you apply it

```python
result = await agent.run(prompt, deps=deps)
plan = result.output

plan.plan                        # the commands
plan.reasoning                   # why the model chose them
plan.confidence                  # "high" | "medium" | "low"
plan.commands_requiring_review    # commands that can cut reachability
```

Commands that would reload or wipe the device are rejected outright and never
reach you. Commands that are risky but legitimate are listed in
`commands_requiring_review` rather than blocked.

## Choosing a model

Any PydanticAI model name works:

```python
workflow.set_model("anthropic:claude-sonnet-4-5")
workflow.set_model("openai:gpt-4.1")
workflow.set_model("google-gla:gemini-2.0-flash")
workflow.set_model("bedrock:anthropic.claude-sonnet-4-5-20250929-v1:0")
```

For a self-hosted model, build the model object yourself and pass it to
`set_agent(build_agent(model))`.

## Caching and rate limiting

```python
from hier_config_ai import ResponseCache, RateLimiter

workflow.set_model(
    "anthropic:claude-sonnet-4-5",
    cache=ResponseCache(ttl_seconds=3600),
    rate_limiter=RateLimiter(max_requests=60, time_window_seconds=60),
)
```

Both wrap the model rather than the client, so they cover tool calls and retries
as well as the first request. Cached payloads contain device configurations, so
the cache directory is created private to your user.

## Failover and consensus

For ordered failover across providers, use PydanticAI directly:

```python
from pydantic_ai.models.fallback import FallbackModel

workflow.set_agent(build_agent(FallbackModel("anthropic:claude-sonnet-4-5", "openai:gpt-4.1")))
```

To ask several models the same question and accept only an answer they agree
on, use `consensus_plan()`. Votes are counted on parsed configuration, so two
models that write the same configuration differently still agree.

## Evaluating changes

Retrieval, prompt edits, and model changes can make output worse as easily as
better. `evals/` measures whether plans actually converge:

```bash
poetry install --with dev,evals --all-extras
poetry run python evals/run_evals.py --model anthropic:claude-sonnet-4-5
```

This calls a real provider and costs money, so it is not part of CI.

## Development

```bash
poetry install --with dev --all-extras
poetry run python scripts/build.py lint-and-test
```

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

Apache 2.0. See [LICENSE](LICENSE).
