# Replacing a custom workflow

hier-config resolves most configuration differences deterministically. A few it
cannot, and its
[custom workflows guide](https://hier-config.readthedocs.io/en/latest/user/custom-workflows/)
shows how to handle those: inspect the default remediation, decide it is wrong,
and build the correct one yourself in Python.

This page walks the canonical case — resequencing an access list — and shows the
same result described rather than coded.

## The problem

An access list needs a new entry ahead of an existing one:

```
running                                intended
ip access-list extended TEST           ip access-list extended TEST
 12 permit ip 10.0.0.0 0.0.0.7 any      10 permit ip 10.0.1.0 0.0.0.255 any
                                        20 permit ip 10.0.0.0 0.0.0.7 any
```

The existing entry has to move from sequence 12 to 20 so the new entry can take
10. hier-config produces this on its own:

```
ip access-list extended TEST
  no 12 permit ip 10.0.0.0 0.0.0.7 any
  10 permit ip 10.0.1.0 0.0.0.255 any
  20 permit ip 10.0.0.0 0.0.0.7 any
```

The end state is right. The path is not: between the removal and the re-add the
list matches nothing, so an implicit deny drops live traffic. On a production
edge that is an outage.

## The manual workflow

The guide's answer is to build the remediation by hand — insert a temporary
allow-all, walk the default remediation renumbering each entry, then clean up:

```python
custom_remediation = HConfig(wfr.running_config.driver)
acl = custom_remediation.get_child(equals="ip access-list extended TEST")
acl.add_child("1 permit ip any any")          # temporary allow-all

for line in remediation.all_children():
    if line.text.startswith("no "):
        parts = line.text.split()
        rounded_number = round(int(parts[1]), -1)
        acl.add_child(f"{parts[0]} {rounded_number}")
    else:
        acl.add_child(line.text)

acl.add_child("no 1")                          # cleanup
```

That works. It is also code you own: it hardcodes one access list by name,
assumes rounding to the nearest ten is the right renumbering, and has to be
written again for the next section that needs judgment. Every such rule is
another branch to test and maintain.

## The same thing, described

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

The rule matches `ip access-list` generally rather than one list by name, and
the renumbering is worked out per case instead of assuming a rounding rule.

`examples/ollama_acl.py` in the repository runs exactly this against a local
Ollama model. It was verified end to end with `qwen2.5-coder:7b` on a laptop, so
it does not need a frontier model.

## Why the output can be trusted

The model's plan is not returned as written. It is applied to the running config
with `HConfig.future`, and the result is compared against the intended
configuration. A plan that does not converge goes back to the model with the
difference, and the model corrects it. See
[Validation and Guardrails](validation.md).

The scaffolding is understood: `1 permit ip any any` followed by `no 1` is
recognised as a pair whose net effect is nothing. **Forgetting the cleanup is
rejected** — a `permit ip any any` left in a live access list is a hole, and the
allowance for scaffolding must not become a way to smuggle one through.

## What this does not do for you

**Convergence proves the end state, not the path.** Both plans above produce the
same access list; only one of them is safe to apply. If the traffic-safety
requirement is left out of the description, the model returns the same unsafe
plan hier-config generates, and validation accepts it. **The ordering
requirement has to be stated.** It is prose rather than Python, but it is not
inferred for you.

**Only send the sections that need judgment.** hier-config's deterministic
remediation is correct for most configuration, and it is free, instant, and
never wrong. Write rules for the cases it cannot resolve and leave the rest
alone.

**Do not name a command the task cannot use.** Mentioning
`ip access-list resequence` here would invite the model to reach for it, and it
cannot produce this target — it renumbers every entry by a fixed stride, while
this change needs 12 to become 20 with a new 10 inserted ahead of it. The model
would spend retries discovering that.

**The model has to be capable enough.** This task defeats a 3B model. See
[Models and Agents](models.md) for what works locally.
