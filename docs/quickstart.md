# Quick Start

## A working remediation

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
hostname aggr-example.rtr
!
ip access-list extended TEST
 12 permit ip 10.0.0.0 0.0.0.7 any
""")

intended = HConfig.from_text(Platform.CISCO_IOS, """
hostname aggr-example.rtr
!
ip access-list extended TEST
 10 permit ip 10.0.1.0 0.0.0.255 any
 20 permit ip 10.0.0.0 0.0.0.7 any
""")

workflow = AIWorkflowRemediation(running, intended)
workflow.set_model("anthropic:claude-sonnet-4-5")
workflow.add_rule(
    AIRemediationRule(
        description=(
            "Rewrite the access list so its entries end up in the intended "
            "order with the intended sequence numbers. Remove entries that are "
            "no longer wanted before adding their replacements."
        ),
        lineage=(MatchRule(startswith="ip access-list"),),
        example=AIRemediationExample(
            running_config="ip access-list extended EXAMPLE\n 20 permit ip any any",
            remediation_config=(
                "ip access-list extended EXAMPLE\n"
                " no 20 permit ip any any\n"
                " 10 permit ip 192.0.2.0 0.0.0.255 any\n"
                " 20 permit ip any any"
            ),
        ),
    )
)

remediation = asyncio.run(workflow.aai_remediation_config())
print("\n".join(remediation.to_lines()))
```

## What happened

1. Each rule's `lineage` selected one section of both configurations.
2. That section became a prompt, built from the
   [prompt template](user-guide/prompt-templates.md) and the platform's own
   rules, read from the hier-config driver.
3. The model answered with a structured `AIPlanResponse`, not free text.
4. The plan was applied to the running config and re-diffed. Had it not
   converged, the difference would have gone back to the model to correct.
5. The verified commands came back as an `HConfig`.

## Rules

A rule names a section and explains what to do with it:

- `description` — what the model should achieve. Write it as an instruction.
- `lineage` — `MatchRule`s selecting the section, exactly as in hier-config.
- `example` — a worked running/remediation pair in the shape you want.

Add one rule per section that needs judgment. Leave everything else to
hier-config's deterministic remediation, which is cheaper and always correct.

## Synchronous callers

```python
remediation = workflow.ai_remediation_config()
```

Use the async form when you already have an event loop, or when you are
remediating many devices at once. Rules within one workflow always run
concurrently.

## Next

- [Models and Agents](user-guide/models.md)
- [Validation and Guardrails](user-guide/validation.md)
