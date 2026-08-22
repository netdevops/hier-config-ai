# Quick Start

This walks the case hier-config cannot resolve on its own: resequencing an
access list without dropping traffic while it is being rewritten.

## The configuration

```python
from hier_config import HConfig, Platform

running = HConfig.from_text(Platform.CISCO_IOS, """
ip access-list extended TEST
 12 permit ip 10.0.0.0 0.0.0.7 any
""")

intended = HConfig.from_text(Platform.CISCO_IOS, """
ip access-list extended TEST
 10 permit ip 10.0.1.0 0.0.0.255 any
 20 permit ip 10.0.0.0 0.0.0.7 any
""")
```

The existing entry has to move from 12 to 20 so the new entry can take 10.

## The rule

```python
from hier_config.models import MatchRule
from hier_config_ai import (
    AIRemediationExample,
    AIRemediationRule,
    AIWorkflowRemediation,
)

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

remediation = await workflow.aai_remediation_config()
print("\n".join(remediation.to_lines()))
```

Output:

```
ip access-list extended TEST
  1 permit ip any any
  no 12
  10 permit ip 10.0.1.0 0.0.0.255 any
  20 permit ip 10.0.0.0 0.0.0.7 any
  no 1
```

`ai_remediation_config()` is available for synchronous callers.

## What happened

1. The rule's `lineage` selected the access list in both configurations.
2. That section became a prompt, built from the rule and the platform's own
   rules, read from the hier-config driver.
3. The model answered with a structured plan, not free text.
4. The plan was applied and re-diffed. Had it not produced the intended access
   list, the difference would have gone back to the model to correct.
5. The verified commands came back as an `HConfig`.

The temporary `1 permit ip any any` and its `no 1` are recognised as a pair
whose net effect is nothing. Forgetting the cleanup would have been rejected.

## Writing a rule

- `description` — what to achieve, as an instruction. **State constraints on
  ordering here.** Convergence proves the end state, not that the path was safe.
- `lineage` — `MatchRule`s selecting the section, exactly as in hier-config.
- `example` — a worked running/remediation pair. This is few-shot input, so keep
  it internally consistent; see
  [Prompt Templates](user-guide/prompt-templates.md).

Add one rule per section that needs judgment. Leave everything else to
hier-config's deterministic remediation, which is free, instant, and correct.

## Next

- [Replacing a Custom Workflow](user-guide/custom-workflows.md) — this case
  against the hand-written version.
- [Models and Agents](user-guide/models.md) — including running it on Ollama.
- [Validation and Guardrails](user-guide/validation.md).
