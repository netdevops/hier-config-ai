# hier-config-ai

Network configuration remediation driven by a language model, built on
[hier-config](https://github.com/netdevops/hier-config) and
[PydanticAI](https://ai.pydantic.dev/).

## What it is for

hier-config already produces correct remediation for most configuration
differences. Some it cannot. Resequencing an access list needs an entry moved
from one sequence number to another before a new entry can take its place, and
there is no deterministic rule for that.

This library sends those sections to a model, then checks the answer.

## The plan is verified, not trusted

The model's plan is applied to the running configuration with `HConfig.future`
and re-checked against the intended configuration. If it does not converge, the
remaining difference goes back to the model through `ModelRetry` and the model
corrects its own work.

That loop is the point of the library. A plan that reads well and still leaves
the device misconfigured is worse than no plan at all.

## Where to start

- [Installation](installation.md) — pick the extra for your provider.
- [Quick Start](quickstart.md) — a working remediation in about twenty lines.
- [Models and Agents](user-guide/models.md) — choosing and configuring a model.
- [Validation and Guardrails](user-guide/validation.md) — how plans are checked.
- [Prompt Templates](user-guide/prompt-templates.md) — customising the prompt.
- [Advanced Features](user-guide/advanced-features.md) — caching, rate limiting,
  failover, consensus, and evaluation.
- [API Reference](api-reference.md).

## Requirements

- Python 3.10 or later
- hier-config 4.0.0b1 or later
- An API key for your chosen provider, or a self-hosted model
