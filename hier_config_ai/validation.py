"""Validation of model-generated remediation plans.

The model is asked to emit config for a live network device, so its output is
checked against hier-config itself rather than trusted. When a check fails the
plan is handed back through `ModelRetry`, which lets the model correct its own
work instead of failing the run.
"""

from __future__ import annotations

import re
from functools import cache
from typing import TYPE_CHECKING, NoReturn

from hier_config import HConfig
from pydantic_ai import ModelRetry

if TYPE_CHECKING:
    from pydantic_ai import RunContext

    from .deps import RemediationDeps
    from .models import AIPlanResponse

# Commands that reload, wipe, or otherwise take a device out of service. Every
# platform's spelling is matched on every platform: matching one too many is
# harmless, whereas missing one lets a plan reboot a router mid-change.
#
# `do ` is allowed for on IOS-style platforms, where it runs an exec command
# from config mode -- `do reload` is a reload. The convergence check happens to
# reject these too, but the guardrail is the control the documentation promises,
# so it does not lean on the second layer.
_DESTRUCTIVE_COMMANDS: tuple[str, ...] = (
    r"reload\b",
    r"reboot\b",
    r"erase\b",
    r"write\s+erase\b",
    r"format\b",
    r"delete\s+/force\b",
    # `boot system flash:...` is ordinary golden-config content, not a
    # reload, so it is deliberately absent: hard-rejecting it would make
    # any intended config that sets a boot image unreachable.
    r"request\s+system\s+(reboot|halt|zeroize|power-off)\b",
    r"execute\s+(reboot|shutdown|factoryreset|formatlogdisk)\b",
    r"reset\s+saved-configuration\b",
    r"restore\s+factory-default\b",
)

DESTRUCTIVE_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(rf"^\s*(do\s+)?{command}", re.IGNORECASE)
    for command in _DESTRUCTIVE_COMMANDS
)

# Command families whose removal can cut management reachability, drop routing,
# or disable authentication. The hazard is the family; the syntax that removes
# it is the platform's, so the negation prefix comes from the driver.
_REVIEW_TARGETS: tuple[str, ...] = (
    r"interfaces?\b",
    r"router\b",
    r"routing-(instance|options)\b",
    r"ip\s+route\b",
    r"static-routes?\b",
    r"line\s+vty\b",
    r"(ip\s+)?access-list\b",
    r"firewall\b",
    r"snmp-server\b",
    r"aaa\b",
    r"username\b",
    r"local-user\b",
    r"system\s+login\b",
    r"management\b",
)

# Risky commands that are not spelled as a negation on any platform.
_REVIEW_LITERALS: tuple[str, ...] = (
    r"^\s*shutdown\b",
    r"^\s*disable\b",
)


@cache
def review_patterns(negation_prefix: str) -> tuple[re.Pattern[str], ...]:
    """Build the review patterns for a platform's negation syntax.

    Keyed on the prefix rather than the platform because that is what decides
    the spelling: `no `, `undo `, `delete `, and `unset ` all remove things.
    Hardcoding `no ` would leave the review list matching nothing on Junos,
    VyOS, SR Linux, VRP, Comware, and FortiOS — and an empty review list reads
    to an operator as "nothing risky here", which is worse than no check.
    """
    prefix = re.escape(negation_prefix.strip())
    return tuple(
        re.compile(pattern, re.IGNORECASE)
        for pattern in (
            *(rf"^\s*{prefix}\s+{target}" for target in _REVIEW_TARGETS),
            *_REVIEW_LITERALS,
        )
    )


def build_retry_message(deps: RemediationDeps, problem: str) -> str:
    """Build the message returned to the model when a plan is rejected.

    Every `ModelRetry` in this module routes through here. In 0.3.0 this
    queries `deps.retriever` and appends the retrieved context: a failed
    convergence check names precisely what the model got wrong, which makes it
    the sharpest retrieval query available anywhere in the run. Until then
    `problem` is returned unchanged.
    """
    del deps
    return problem


def reject(deps: RemediationDeps, problem: str) -> NoReturn:
    """Hand a rejected plan back to the model."""
    raise ModelRetry(build_retry_message(deps, problem))


def parse_plan(deps: RemediationDeps, plan: list[str]) -> HConfig:
    """Parse plan commands into an HConfig using the running config's driver."""
    return HConfig.from_lines(deps.driver, plan)


def transient_commands(plan: list[str], negation_prefix: str) -> set[str]:
    """Return commands the plan adds and then removes again.

    A remediation may need scaffolding that does not survive it. Resequencing
    an access list is the standard case: a temporary `permit ip any any` goes
    in first so the list never denies live traffic while its entries are
    renumbered, and comes out at the end.

    The plan is parsed into a tree before it is compared, which loses the order
    the commands are applied in, so both halves of that pair look like
    configuration the plan leaves behind. Their net effect on the device is
    nothing, so they are excluded from the comparison.
    """
    stripped = [command.strip() for command in plan]
    prefix = negation_prefix.strip()

    transient: set[str] = set()
    for command in stripped:
        if not command.startswith(f"{prefix} "):
            continue
        added = command[len(prefix) :].strip()
        if added in stripped:
            transient.add(added)
            transient.add(command)
    return transient


def difference_for_config(
    deps: RemediationDeps,
    plan_config: HConfig,
    plan: list[str] | None = None,
) -> tuple[list[str], list[str]]:
    """Compare what a parsed plan would produce against what it must produce.

    Returns:
        A `(missing, unwanted)` pair. `missing` is configuration the plan fails
        to produce; `unwanted` is configuration it leaves behind or introduces.
        Both empty means the plan converges.

    Note:
        Neither obvious primitive works alone. `HConfig.difference` treats
        access-list entries as equal regardless of their sequence numbers, so it
        passes a plan that never renumbers them, and ACL resequencing is exactly
        what this library exists for. A textual diff against the generated
        config has the opposite fault: `future()` applies `no shutdown` by
        removing `shutdown`, so a converging plan yields a config lacking the
        literal `no shutdown` line the target states, and no plan could ever be
        accepted. Comparing two futures avoids both, because the same
        normalization is applied to each side.

        Comparison is by membership, not position: access-list order is carried
        by the sequence numbers in the command text, and rejecting on position
        would fail correct plans and trap the model in a retry loop.

    """
    actual = list(deps.running_config.future(plan_config).to_lines())
    actual_set = frozenset(actual)

    missing = [line for line in deps.canonical_lines if line not in actual_set]
    unwanted = [line for line in actual if line not in deps.canonical_line_set]

    if plan is not None:
        transient = transient_commands(plan, deps.driver.negation_prefix)
        if transient:
            unwanted = [line for line in unwanted if line.strip() not in transient]

    return missing, unwanted


def remaining_difference(
    deps: RemediationDeps,
    plan: list[str],
) -> tuple[list[str], list[str]]:
    """Parse `plan` and compare it against the intended configuration."""
    missing, unwanted = difference_for_config(deps, parse_plan(deps, plan))
    transient = transient_commands(plan, deps.driver.negation_prefix)
    if transient:
        unwanted = [line for line in unwanted if line.strip() not in transient]
    return missing, unwanted


def plan_converges(deps: RemediationDeps, plan: list[str]) -> bool:
    """Report whether `plan` produces the intended configuration.

    Invalid configuration counts as not converging, so callers scoring a plan
    do not each need their own guard.
    """
    try:
        missing, unwanted = remaining_difference(deps, plan)
    # Any driver failure means the plan is not valid configuration.
    except Exception:  # ruff: ignore[blind-except]  # pylint: disable=broad-exception-caught
        return False
    return not missing and not unwanted


def format_difference(missing: list[str], unwanted: list[str]) -> str:
    """Describe a failed convergence check in terms the model can act on."""
    report: list[str] = []
    if missing:
        report.append(
            "This configuration is still missing after your plan runs:\n"
            + "\n".join(missing)
        )
    if unwanted:
        report.append(
            "This configuration would be left behind or wrongly added:\n"
            + "\n".join(unwanted)
        )
    return "\n\n".join(report)


def check_shape(output: AIPlanResponse) -> str | None:
    """Reject an empty plan, or commands containing tab characters."""
    if not output.plan:
        return "The plan was empty. Return at least one command."

    tabbed = [command for command in output.plan if "\t" in command]
    if tabbed:
        return (
            "These commands contain tab characters, which break the config "
            f"hierarchy. Indent with spaces instead: {tabbed}"
        )
    return None


def check_guardrails(deps: RemediationDeps, output: AIPlanResponse) -> str | None:
    """Reject destructive commands and flag risky ones for human review."""
    destructive = [
        command
        for command in output.plan
        if any(pattern.search(command) for pattern in DESTRUCTIVE_PATTERNS)
    ]

    patterns = review_patterns(deps.driver.negation_prefix)
    flagged = [
        command
        for command in output.plan
        if any(pattern.search(command) for pattern in patterns)
    ]
    # Merged, not replaced: the model may flag a risky command no pattern
    # covers, and overwriting would drop it while still reading as complete.
    output.commands_requiring_review = [
        *output.commands_requiring_review,
        *(c for c in flagged if c not in output.commands_requiring_review),
    ]

    if destructive:
        return (
            "These commands would reload or wipe the device and must never "
            f"appear in a remediation plan. Remove them: {destructive}"
        )
    return None


def check_converges(
    deps: RemediationDeps,
    plan: list[str],
    plan_config: HConfig,
) -> str | None:
    """Reject a plan that does not turn the running config into the target.

    Takes the raw commands as well as the parsed tree, because the tree has
    lost the order they are applied in and scaffolding can only be recognised
    from the original list.
    """
    missing, unwanted = difference_for_config(deps, plan_config, plan)
    if not missing and not unwanted:
        return None

    return (
        "Applying this plan does not produce the intended configuration.\n\n"
        + format_difference(missing, unwanted)
    )


def validate_plan(
    ctx: RunContext[RemediationDeps],
    output: AIPlanResponse,
) -> AIPlanResponse:
    """Validate a plan, raising ModelRetry so the model can correct itself.

    Checks run cheapest-first, and the plan is parsed once and reused, so the
    convergence check never re-parses what the syntax check already read.
    """
    deps = ctx.deps

    if problem := check_shape(output):
        reject(deps, problem)

    try:
        plan_config = parse_plan(deps, output.plan)
    # Any driver failure means the plan is not valid configuration.
    except Exception as exc:  # ruff: ignore[blind-except]  # pylint: disable=broad-exception-caught
        reject(deps, f"The plan is not valid configuration for this platform: {exc}")

    if problem := check_guardrails(deps, output):
        reject(deps, problem)

    if problem := check_converges(deps, output.plan, plan_config):
        reject(deps, problem)

    return output
