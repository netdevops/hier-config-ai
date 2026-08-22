# hier-config-ai

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

But between the removal and the re-add the list matches nothing, and an implicit
deny drops live traffic. Avoiding that is what the manual workflow exists for —
a temporary allow-all, a renumbering loop, a cleanup.

Stated as a rule instead, the same requirement produces:

```
ip access-list extended TEST
  1 permit ip any any
  no 12
  10 permit ip 10.0.1.0 0.0.0.255 any
  20 permit ip 10.0.0.0 0.0.0.7 any
  no 1
```

[Replacing a Custom Workflow](user-guide/custom-workflows.md) walks it in full.

## The plan is verified, not trusted

The model's plan is applied to the running configuration with `HConfig.future`
and re-checked against the intended one. If it does not converge, the remaining
difference goes back to the model and it corrects its own work.

A plan that reads well and still leaves the device misconfigured is worse than
no plan at all, so nothing is returned until it provably reaches the target.

## Where to start

- [Installation](installation.md) — pick the extra for your provider.
- [Quick Start](quickstart.md) — the access-list workflow, end to end.
- [Replacing a Custom Workflow](user-guide/custom-workflows.md) — the manual
  approach and this one, side by side.
- [Models and Agents](user-guide/models.md) — choosing a model, including self-hosted.
- [Validation and Guardrails](user-guide/validation.md) — how plans are checked.
- [Prompt Templates](user-guide/prompt-templates.md) — writing rules well.
- [Advanced Features](user-guide/advanced-features.md) — caching, rate limiting,
  failover, consensus, evaluation.
- [API Reference](api-reference.md).

## Requirements

- Python 3.10 or later
- hier-config 4.0.0b1 or later
- An API key for your chosen provider, or a self-hosted model
