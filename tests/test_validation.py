"""Tests for the plan validation loop."""

from __future__ import annotations

import pytest
from hier_config import HConfig, Platform, get_hconfig_driver
from pydantic_ai import ModelRetry, RunContext
from pydantic_ai.models.test import TestModel
from pydantic_ai.usage import RunUsage

from hier_config_ai.deps import RemediationDeps
from hier_config_ai.models import AIPlanResponse
from hier_config_ai.validation import (
    check_converges,
    check_guardrails,
    check_shape,
    format_difference,
    parse_plan,
    plan_converges,
    remaining_difference,
    review_patterns,
    validate_plan,
)
from tests.conftest import (
    CORRECT_PLAN,
    INCOMPLETE_PLAN,
    INTERFACE,
    StubRetriever,
)


def run_context(deps: RemediationDeps) -> RunContext[RemediationDeps]:
    """Build a minimal run context carrying `deps`."""
    return RunContext(deps=deps, model=TestModel(), usage=RunUsage())


def plan(*commands: str) -> AIPlanResponse:
    """Build a plan response from raw commands."""
    return AIPlanResponse(plan=list(commands))


def test_correct_plan_converges(deps: RemediationDeps) -> None:
    """A plan reaching the target reports no difference.

    `no shutdown` is the interesting part: `future()` applies it by removing
    `shutdown`, so the result lacks the literal line the target states. A
    textual diff would call that a difference and no plan could ever pass.
    """
    missing, unwanted = remaining_difference(deps, CORRECT_PLAN)
    assert not missing
    assert not unwanted


def test_incomplete_plan_reports_missing_config(deps: RemediationDeps) -> None:
    """A plan that stops short names the config it failed to produce."""
    missing, unwanted = remaining_difference(deps, INCOMPLETE_PLAN)
    assert any("ip address 10.0.1.1" in line for line in missing)
    assert not unwanted


def test_plan_adding_unwanted_config_is_detected(deps: RemediationDeps) -> None:
    """Config the plan adds but the target does not want is reported."""
    missing, unwanted = remaining_difference(
        deps,
        [*CORRECT_PLAN, "interface GigabitEthernet0/5", "  shutdown"],
    )
    assert not missing
    assert any("GigabitEthernet0/5" in line for line in unwanted)


def test_converged_plan_passes(deps: RemediationDeps) -> None:
    """The convergence check accepts a plan that reaches the target."""
    assert check_converges(deps, parse_plan(deps, CORRECT_PLAN)) is None


def test_unconverged_plan_is_reported(deps: RemediationDeps) -> None:
    """The convergence check describes what an incomplete plan left undone."""
    problem = check_converges(deps, parse_plan(deps, INCOMPLETE_PLAN))
    assert problem is not None
    assert "does not produce the intended" in problem


def test_plan_converges_reports_a_verdict(deps: RemediationDeps) -> None:
    """The convenience predicate agrees with the underlying comparison."""
    assert plan_converges(deps, CORRECT_PLAN)
    assert not plan_converges(deps, INCOMPLETE_PLAN)


def test_plan_converges_treats_invalid_config_as_failure(
    deps: RemediationDeps,
) -> None:
    """Config the driver cannot parse does not count as converged."""
    assert not plan_converges(deps, [None])  # type: ignore[list-item]


def test_empty_plan_is_rejected() -> None:
    """An empty plan is sent back rather than returned."""
    problem = check_shape(plan())
    assert problem is not None
    assert "empty" in problem


def test_tab_characters_are_rejected() -> None:
    """Tabs break the hierarchy, so they are sent back."""
    problem = check_shape(AIPlanResponse(plan=[INTERFACE, "\tno shutdown"]))
    assert problem is not None
    assert "tab characters" in problem


def test_valid_shape_passes() -> None:
    """A non-empty, tab-free plan passes the shape check."""
    assert check_shape(plan(*CORRECT_PLAN)) is None


@pytest.mark.parametrize(
    "command",
    (
        "reload",
        "write erase",
        "erase startup-config",
        "  reload in 5",
        "reboot",
        # `do` runs an exec command from config mode on IOS-style platforms,
        # so `do reload` reloads the device just as `reload` does.
        "do reload",
        "  do write erase",
        "request system zeroize",
        "execute factoryreset",
    ),
)
def test_destructive_commands_are_rejected(
    deps: RemediationDeps,
    command: str,
) -> None:
    """Commands that reload or wipe the device are never allowed."""
    problem = check_guardrails(deps, plan(*CORRECT_PLAN, command))
    assert problem is not None
    assert "reload or wipe" in problem


def test_risky_commands_are_flagged_not_rejected(deps: RemediationDeps) -> None:
    """A risky but legitimate command is surfaced for review, not blocked."""
    response = plan(INTERFACE, "  shutdown")
    assert check_guardrails(deps, response) is None
    assert response.commands_requiring_review == ["  shutdown"]


def test_safe_plan_flags_nothing(deps: RemediationDeps) -> None:
    """A plan with no risky commands leaves the review list empty."""
    response = plan(*CORRECT_PLAN)
    assert check_guardrails(deps, response) is None
    assert not response.commands_requiring_review


@pytest.mark.parametrize(
    ("platform", "command"),
    (
        (Platform.CISCO_IOS, "no interface Vlan10"),
        (Platform.JUNIPER_JUNOS, "delete interfaces ge-0/0/0"),
        (Platform.VYOS, "delete firewall name FOO"),
        (Platform.HUAWEI_VRP, "undo local-user admin"),
        (Platform.HP_COMWARE5, "undo snmp-server community public"),
        (Platform.FORTINET_FORTIOS, "unset interface port1"),
    ),
)
def test_review_patterns_follow_the_platform(
    platform: Platform,
    command: str,
) -> None:
    """Risky removals are recognised on every platform, not just Cisco.

    The patterns are built from the driver's negation prefix. Hardcoding `no `
    left the review list matching nothing on six of the thirteen platforms, and
    an empty review list reads to an operator as "nothing risky here".
    """
    driver = get_hconfig_driver(platform)
    patterns = review_patterns(driver.negation_prefix)
    assert any(pattern.search(command) for pattern in patterns)


def test_format_difference_describes_both_directions() -> None:
    """The report separates missing config from unwanted config."""
    report = format_difference(["a"], ["b"])
    assert "still missing" in report
    assert "left behind" in report


def test_format_difference_is_empty_when_converged() -> None:
    """Nothing is reported when there is no difference."""
    assert not format_difference([], [])


def test_retriever_is_accepted_on_deps(deps: RemediationDeps) -> None:
    """A retriever can be carried now even though 0.2.0 does not use it."""
    with_retriever = RemediationDeps(
        running_config=deps.running_config,
        generated_config=deps.generated_config,
        retriever=StubRetriever(),
    )
    assert with_retriever.retriever is not None


def test_convergence_target_is_computed_once(deps: RemediationDeps) -> None:
    """The canonical target is cached across checks.

    It is derived from configs that cannot change during a run, and it was
    previously rebuilt on every validation pass and every tool call.
    """
    assert deps.canonical_future is deps.canonical_future
    assert deps.canonical_lines is deps.canonical_lines


ACL_RUNNING = "ip access-list extended TEST\n  12 permit ip 10.0.0.0 0.0.0.7 any"
ACL_GENERATED = (
    "ip access-list extended TEST\n"
    "  10 permit ip 10.0.1.0 0.0.0.255 any\n"
    "  20 permit ip 10.0.0.0 0.0.0.7 any"
)
ACL_CORRECT = [
    "ip access-list extended TEST",
    "  no 12 permit ip 10.0.0.0 0.0.0.7 any",
    "  10 permit ip 10.0.1.0 0.0.0.255 any",
    "  20 permit ip 10.0.0.0 0.0.0.7 any",
]


def acl_deps() -> RemediationDeps:
    """Build deps for the access-list resequencing case."""
    driver = get_hconfig_driver(Platform.CISCO_IOS)
    return RemediationDeps(
        running_config=HConfig.from_lines(driver, ACL_RUNNING),
        generated_config=HConfig.from_lines(driver, ACL_GENERATED),
    )


def test_acl_resequencing_is_accepted_when_correct() -> None:
    """A plan that renumbers the access list correctly converges."""
    assert plan_converges(acl_deps(), ACL_CORRECT)


def test_acl_left_unresequenced_is_caught() -> None:
    """A plan that adds an entry but never renumbers the old one is rejected.

    `HConfig.difference` treats access-list entries as equal whatever their
    sequence numbers, so it passes this plan. Access-list resequencing is the
    case this library exists for, so the check compares two futures instead.
    """
    missing, unwanted = remaining_difference(
        acl_deps(),
        ["ip access-list extended TEST", "  10 permit ip 10.0.1.0 0.0.0.255 any"],
    )
    assert any("20 permit" in line for line in missing)
    assert any("12 permit" in line for line in unwanted)


def test_acl_commands_in_a_different_order_still_pass() -> None:
    """Order in the plan text does not matter; the sequence numbers do.

    Rejecting on position would fail correct plans and trap the model in a
    retry loop it could not escape.
    """
    reordered = [
        "ip access-list extended TEST",
        "  no 12 permit ip 10.0.0.0 0.0.0.7 any",
        "  20 permit ip 10.0.0.0 0.0.0.7 any",
        "  10 permit ip 10.0.1.0 0.0.0.255 any",
    ]
    assert plan_converges(acl_deps(), reordered)


def test_validate_plan_accepts_a_converging_plan(
    deps: RemediationDeps,
) -> None:
    """The validator returns the plan unchanged when it converges."""
    response = plan(*CORRECT_PLAN)
    ctx = run_context(deps)
    assert validate_plan(ctx, response) is response


@pytest.mark.parametrize(
    ("commands", "expected"),
    (
        ((), "empty"),
        ((INTERFACE, "\tno shutdown"), "tab characters"),
        ((*CORRECT_PLAN, "reload"), "reload or wipe"),
        (tuple(INCOMPLETE_PLAN), "does not produce the intended"),
    ),
)
def test_validate_plan_sends_bad_plans_back(
    deps: RemediationDeps,
    commands: tuple[str, ...],
    expected: str,
) -> None:
    """Each check hands its problem back through ModelRetry."""
    with pytest.raises(ModelRetry, match=expected):
        validate_plan(run_context(deps), plan(*commands))


def test_validate_plan_reports_unparseable_config(
    deps: RemediationDeps,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A plan the driver cannot read is described to the model, not raised.

    The driver accepts almost any line, so the failure is forced here rather
    than contrived from config text.
    """

    def explode(*_args: object, **_kwargs: object) -> HConfig:
        msg = "unsupported command"
        raise ValueError(msg)

    monkeypatch.setattr("hier_config_ai.validation.parse_plan", explode)
    with pytest.raises(ModelRetry, match="not valid configuration"):
        validate_plan(run_context(deps), plan(*CORRECT_PLAN))
