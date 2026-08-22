# Validation and Guardrails

A plan that reads well and still leaves the device misconfigured is worse than
no plan at all. Every plan is checked before it is returned.

## The checks

They run cheapest-first, so a malformed plan never reaches the expensive one.

1. **Shape.** The plan is not empty and contains no tab characters. Tabs break
   the command hierarchy.
2. **Parses.** The platform driver can read the plan as configuration.
3. **Guardrails.** See below.
4. **Convergence.** Applying the plan produces the intended configuration.

A failed check raises `ModelRetry`, which returns the problem to the model so it
can correct its own work. It is not an error the caller sees unless the model
runs out of retries.

## Convergence

```python
predicted = running_config.future(plan_as_hconfig)
intended = running_config.future(hier_config_deterministic_remediation)
# compare predicted against intended
```

Both sides pass through `HConfig.future`, which matters more than it looks.

!!! note "Why not compare against the generated config directly"
    Neither obvious approach works alone.

    `HConfig.difference` treats access-list entries as equal whatever their
    sequence numbers, so it accepts a plan that adds an entry but never
    renumbers the existing one. Access-list resequencing is precisely what this
    library exists for, so that blindspot is disqualifying.

    A textual diff has the opposite fault. `future()` applies `no shutdown` by
    removing `shutdown`, so a correct plan yields a configuration that lacks the
    literal `no shutdown` line the generated config states. A textual diff calls
    that a difference, and no plan could ever be accepted.

    Comparing two futures avoids both, because the same normalization is applied
    to each side.

Comparison is by membership rather than position, so a plan whose commands
appear in a different order still passes. Access-list order is carried by the
sequence numbers in the command text, which membership does compare. Rejecting
on position would fail correct plans and trap the model in a retry loop.

## Scoping

Each rule is judged only against its own section. A rule covering one interface
compared against the whole configuration could never converge, because
differences owned by other rules would still be outstanding.

The section keeps its parent chain, so a multi-level lineage such as
`(interface, mtu)` scopes to the `mtu` command *under* its interface rather
than to a bare `mtu` line with no parent.

A rule whose lineage matches nothing in either configuration is skipped. There
is nothing to remediate, and asking anyway could only fail.

`get_config_section` reaches the whole device configuration, not just the
section under remediation — that is the point of having it.

## Scaffolding

A remediation may need commands that do not survive it. Resequencing an access
list is the standard case: a temporary `1 permit ip any any` goes in first so
the list never denies live traffic while its entries are renumbered, and comes
out at the end.

Commands the plan adds and then removes are excluded from the comparison, since
their net effect on the device is nothing. Both spellings of the removal are
recognised: `no <command>`, which repeats the line, and `no <sequence>`, which
names only its number — the way an engineer actually deletes an access-list
entry.

Forgetting the cleanup is still rejected. A `permit ip any any` left in a live
access list is a hole, and the allowance must not become a way to smuggle one
through. So is `no 20` for an entry the plan never added, which is a real
deletion rather than scaffolding.

## Guardrails

Commands that would take the device out of service are rejected outright and
never reach you: `reload`, `reboot`, `erase`, `write erase`, `format`,
`boot system`, `request system zeroize`, `execute factoryreset`, and similar.
Every platform's spelling is matched on every platform, because matching one too
many is harmless while missing one lets a plan reboot a router mid-change.

Commands that are risky but can be legitimate are surfaced instead of blocked:
removals of interfaces, routing processes, static routes, VTY lines, access
lists, firewall policy, SNMP, AAA, and user accounts.

!!! note "The removal syntax follows the platform"
    The review patterns are built from the driver's negation prefix, so they
    match `no ` on Cisco and Arista, `delete ` on Junos, VyOS, and SR Linux,
    `undo ` on VRP and Comware, and `unset ` on FortiOS. Hardcoding `no ` left
    the review list matching nothing on six of the thirteen platforms — and an
    empty `commands_requiring_review` reads to an operator as "nothing risky
    here", which is worse than no check at all.

They appear in `AIPlanResponse.commands_requiring_review`:

```python
if plan.commands_requiring_review:
    print("Review before applying:")
    for command in plan.commands_requiring_review:
        print(" ", command)
```

A correct remediation may genuinely need to shut an interface, so blocking these
would be wrong. Showing them to an operator is not.

## Tools

The model can check its own work before answering.

`test_remediation(commands)` applies candidate commands and reports what they
would do to the device. `get_config_section(lineage)` fetches more of the
configuration on demand.

Giving the model the same check that will judge it means most corrections happen
inside a single run, before the validator ever rejects anything.
