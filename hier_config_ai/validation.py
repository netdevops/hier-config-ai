"""Validation of model-generated remediation plans.

The model is asked to emit config for a live network device, so its output is
checked against hier-config itself rather than trusted. When a check fails the
plan is handed back through `ModelRetry`, which lets the model correct its own
work instead of failing the run.
"""

from __future__ import annotations

import logging
import re
from collections import defaultdict
from functools import cache
from typing import TYPE_CHECKING, NoReturn

from hier_config import HConfig
from pydantic_ai import ModelRetry

if TYPE_CHECKING:
    from pydantic_ai import RunContext

    from .deps import RemediationDeps
    from .models import AIPlanResponse

logger = logging.getLogger(__name__)

# Commands that reload, wipe, or otherwise take a device out of service. Every
# platform's spelling is matched on every platform: matching one too many is
# harmless, whereas missing one lets a plan reboot a router mid-change.
#
# `do ` is allowed for on IOS-style platforms, where it runs an exec command
# from config mode -- `do reload` is a reload. The convergence check happens to
# reject these too, but the guardrail is the control the documentation promises,
# so it does not lean on the second layer.
# Matched as stems, not whole words. IOS accepts any unambiguous abbreviation,
# so `relo` reloads a router and `wr era` wipes it; requiring the full spelling
# let both straight through.
#
# `boot system flash:...` is deliberately absent: it is ordinary golden-config
# content, and hard-rejecting it would make any intended config that sets a
# boot image unreachable.
_DESTRUCTIVE_COMMANDS: tuple[str, ...] = (
    r"relo",
    r"reboo",
    r"era",
    r"wri?t?e?\s+era",
    r"forma",
    r"delete\s+/force",
    r"request\s+system\s+(reboo|halt|zeroiz|power-off)",
    r"execute\s+(reboo|shutdown|factoryreset|formatlogdisk)",
    r"reset\s+saved-config",
    r"restore\s+factory-default",
    r"crypto\s+key\s+zeroiz",
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


async def build_retry_message(deps: RemediationDeps, problem: str) -> str:
    """Build the message returned to the model when a plan is rejected.

    Every `ModelRetry` in this module routes through here, and it is the best
    retrieval query in the whole run: a rejection names precisely what the
    model got wrong, where the opening query is written before anything is
    known to have gone wrong.

    Retrieval failures are swallowed. A second attempt without context is worth
    far more than no second attempt, and the rejection itself is already useful
    on its own.
    """
    retriever = deps.retriever
    platform = deps.platform
    if retriever is None or platform is None:
        return problem

    try:
        snippets = await retriever.search(problem, platform=platform)
    # Retrieval is an enhancement to the retry, never a precondition for it.
    except Exception:  # pylint: disable=broad-exception-caught
        logger.debug("Retrieval failed while building a retry message", exc_info=True)
        return problem

    if not snippets:
        return problem

    context = "\n\n".join(f"- {snippet}" for snippet in snippets)
    return f"{problem}\n\nThis may help:\n\n{context}"


async def reject(deps: RemediationDeps, problem: str) -> NoReturn:
    """Hand a rejected plan back to the model."""
    raise ModelRetry(await build_retry_message(deps, problem))


def parse_plan(deps: RemediationDeps, plan: list[str]) -> HConfig:
    """Parse plan commands into an HConfig using the running config's driver."""
    return HConfig.from_lines(deps.driver, plan)


def scaffolding(plan: list[str], negation_prefix: str) -> set[str]:
    """Return commands the plan adds and then removes, in that order.

    A remediation may need commands that do not survive it. Resequencing an
    access list wants a temporary `permit ip any any` first so the list never
    denies live traffic while its entries are renumbered, removed again at the
    end. Their net effect on the device is nothing, so they are excluded from
    the comparison.

    Two things keep that allowance narrow, and both are load-bearing.

    The addition must come *before* its removal. A plan that deletes an
    access-list entry and puts it straight back has renumbered nothing, and
    without the ordering check it would read as a cancelled pair.

    The removal must name its target exactly, or by sequence number. Anything
    looser lets a plan hide a command behind a negation that does not actually
    undo it: `no ip` cancels `ip route 0.0.0.0 0.0.0.0 198.51.100.66` in a
    prediction, while on the device it is `% Incomplete command` and the route
    stays. Cancellation in a model is not cancellation on a router.
    """
    prefix = f"{negation_prefix.strip()} "
    added: set[str] = set()
    added_by_sequence: dict[str, list[str]] = defaultdict(list)
    pairs: set[str] = set()

    for raw in plan:
        command = raw.strip()
        if command.startswith(prefix):
            target = command[len(prefix) :].strip()
            matched = {target} & added
            if target.isdigit():
                matched.update(added_by_sequence.get(target, ()))
            if matched:
                pairs |= matched | {command}
            continue

        added.add(command)
        head, separator, _ = command.partition(" ")
        if separator and head.isdigit():
            added_by_sequence[head].append(command)

    return pairs


def difference_for_config(
    deps: RemediationDeps,
    plan_config: HConfig,
    plan: list[str],
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
    transient = scaffolding(plan, deps.driver.negation_prefix)

    missing = [line for line in deps.canonical_lines if line not in actual_set]
    unwanted = [
        line
        for line in actual
        if line not in deps.canonical_line_set and line.strip() not in transient
    ]
    return missing, unwanted


def remaining_difference(
    deps: RemediationDeps,
    plan: list[str],
) -> tuple[list[str], list[str]]:
    """Parse `plan` and compare it against the intended configuration."""
    return difference_for_config(deps, parse_plan(deps, plan), plan)


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
    # Scaffolding is excluded from the convergence comparison because it leaves
    # nothing behind, but it does run on the device. An operator has to see it.
    transient = scaffolding(output.plan, deps.driver.negation_prefix)
    flagged = [
        command
        for command in output.plan
        if command.strip() in transient
        or any(pattern.search(command) for pattern in patterns)
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
    """Reject a plan that does not turn the running config into the target."""
    missing, unwanted = difference_for_config(deps, plan_config, plan)
    if not missing and not unwanted:
        return None

    return (
        "Applying this plan does not produce the intended configuration.\n\n"
        + format_difference(missing, unwanted)
    )


async def validate_plan(
    ctx: RunContext[RemediationDeps],
    output: AIPlanResponse,
) -> AIPlanResponse:
    """Validate a plan, raising ModelRetry so the model can correct itself.

    Checks run cheapest-first, and the plan is parsed once and reused, so the
    convergence check never re-parses what the syntax check already read.
    """
    deps = ctx.deps

    if problem := check_shape(output):
        await reject(deps, problem)

    try:
        plan_config = parse_plan(deps, output.plan)
    # Any driver failure means the plan is not valid configuration.
    except Exception as exc:  # ruff: ignore[blind-except]  # pylint: disable=broad-exception-caught
        await reject(
            deps, f"The plan is not valid configuration for this platform: {exc}"
        )

    if problem := check_guardrails(deps, output):
        await reject(deps, problem)

    if problem := check_converges(deps, output.plan, plan_config):
        await reject(deps, problem)

    return output
