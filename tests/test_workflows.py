"""Tests for the model-driven remediation workflow."""

from __future__ import annotations

import asyncio

import pytest
from hier_config import HConfig, Platform, get_hconfig_driver
from hier_config.models import MatchRule
from pydantic_ai import RunContext
from pydantic_ai.models.test import TestModel
from pydantic_ai.usage import RunUsage

from hier_config_ai.agent import build_agent
from hier_config_ai.deps import RemediationDeps
from hier_config_ai.exceptions import AIClientInitializationError, RemediationError
from hier_config_ai.models import AIRemediationExample, AIRemediationRule
from hier_config_ai.prompt_template import PromptTemplate
from hier_config_ai.tools import get_config_section
from hier_config_ai.workflows import AIWorkflowRemediation, scoped_config
from tests.conftest import (
    CORRECT_PLAN,
    INCOMPLETE_PLAN,
    INTERFACE,
    LINEAGE,
    StubRetriever,
    build_generated_config,
    build_running_config,
    failing_model,
    scripted_model,
)


def configured(
    workflow: AIWorkflowRemediation,
    rule: AIRemediationRule,
    *plans: list[str],
) -> AIWorkflowRemediation:
    """Attach a scripted model and one rule to the workflow."""
    workflow.set_agent(build_agent(scripted_model(*plans)))
    workflow.add_rule(rule)
    return workflow


async def test_remediation_returns_the_plan_as_config(
    workflow: AIWorkflowRemediation,
    rule: AIRemediationRule,
) -> None:
    """A converging plan comes back as an HConfig."""
    configured(workflow, rule, CORRECT_PLAN)
    config = await workflow.aai_remediation_config()
    assert list(config.to_lines()) == CORRECT_PLAN


async def test_model_corrects_a_rejected_plan(
    workflow: AIWorkflowRemediation,
    rule: AIRemediationRule,
) -> None:
    """A plan that does not converge is sent back and the retry is accepted.

    This is the behaviour the whole design exists for: the plan is checked
    against hier-config, and the model fixes its own mistake rather than the
    run failing or returning config that does not work.
    """
    configured(workflow, rule, INCOMPLETE_PLAN, CORRECT_PLAN)
    config = await workflow.aai_remediation_config()
    assert list(config.to_lines()) == CORRECT_PLAN


async def test_run_without_a_model_is_refused(
    workflow: AIWorkflowRemediation,
    rule: AIRemediationRule,
) -> None:
    """The workflow explains that no model was configured."""
    workflow.add_rule(rule)
    with pytest.raises(AIClientInitializationError, match="No model is configured"):
        await workflow.aai_remediation_config()


async def test_run_without_rules_is_refused(
    workflow: AIWorkflowRemediation,
) -> None:
    """The workflow explains that no rules were loaded."""
    workflow.set_agent(build_agent(scripted_model(CORRECT_PLAN)))
    with pytest.raises(RemediationError, match="No remediation rules loaded"):
        await workflow.aai_remediation_config()


async def test_empty_plan_raises_remediation_error(
    workflow: AIWorkflowRemediation,
    rule: AIRemediationRule,
) -> None:
    """A model that only ever returns nothing fails the run."""
    configured(workflow, rule, [])
    with pytest.raises(RemediationError):
        await workflow.aai_remediation_config()


async def test_usage_is_recorded_per_rule(
    workflow: AIWorkflowRemediation,
    rule: AIRemediationRule,
) -> None:
    """Token usage is captured so callers can see what a run cost."""
    configured(workflow, rule, CORRECT_PLAN)
    await workflow.aai_remediation_config()
    assert len(workflow.usage) == 1


def test_rules_can_be_cleared(
    workflow: AIWorkflowRemediation,
    rule: AIRemediationRule,
) -> None:
    """Clearing the rules empties the rule list."""
    workflow.add_rule(rule)
    workflow.clear_rules()
    assert not workflow.rules


def test_scoping_limits_each_rule_to_its_section(
    workflow: AIWorkflowRemediation,
    rule: AIRemediationRule,
) -> None:
    """A rule sees only its own section.

    Without scoping, a rule covering one interface would be judged against the
    whole configuration and could never converge, because differences owned by
    other rules would still be outstanding.
    """
    scoped = scoped_config(workflow.running_config, rule.lineage)
    assert list(scoped.to_lines()) == [INTERFACE, "  shutdown"]


def test_custom_prompt_template_is_used(
    running_config: HConfig,
    generated_config: HConfig,
    rule: AIRemediationRule,
) -> None:
    """A custom template reaches the model.

    The previous release documented a `prompt_template` argument that the
    workflow never accepted, so every documented example raised TypeError.
    """
    marker = "MARKER-TOKEN"
    template = PromptTemplate(
        template=(
            f"{marker} {{running_config}} {{generated_config}} {{description}} "
            "{example_running_config} {example_remediation_config}"
        )
    )
    workflow = AIWorkflowRemediation(
        running_config,
        generated_config,
        prompt_template=template,
    )
    built = workflow.prompt_template.build(workflow.build_context(rule))
    assert built.startswith(marker)


async def test_sync_wrapper_refuses_to_run_inside_a_loop(
    workflow: AIWorkflowRemediation,
    rule: AIRemediationRule,
) -> None:
    """Calling the sync method from inside a loop is refused with advice.

    This test is async on purpose: the guard only fires when an event loop is
    already running, which is exactly the situation it protects against.
    """
    await asyncio.sleep(0)
    configured(workflow, rule, CORRECT_PLAN)
    with pytest.raises(RuntimeError, match="cannot run inside an event loop"):
        workflow.ai_remediation_config()


def test_sync_wrapper_works_outside_an_event_loop(
    running_config: HConfig,
    generated_config: HConfig,
    rule: AIRemediationRule,
) -> None:
    """Synchronous callers get a plan without touching asyncio."""
    workflow = AIWorkflowRemediation(running_config, generated_config)
    configured(workflow, rule, CORRECT_PLAN)
    assert list(workflow.ai_remediation_config().to_lines()) == CORRECT_PLAN


def test_retriever_is_passed_to_the_agent(
    workflow: AIWorkflowRemediation,
) -> None:
    """A retriever set on the workflow reaches the agent it builds."""
    workflow.retriever = StubRetriever()
    workflow.set_model(scripted_model(CORRECT_PLAN))
    assert workflow.retriever is not None


async def test_set_model_builds_an_agent(
    workflow: AIWorkflowRemediation,
    rule: AIRemediationRule,
) -> None:
    """set_model is enough to run the workflow end to end."""
    workflow.set_model(scripted_model(CORRECT_PLAN))
    workflow.add_rule(rule)
    config = await workflow.aai_remediation_config()
    assert list(config.to_lines()) == CORRECT_PLAN


async def test_model_failure_becomes_a_remediation_error(
    workflow: AIWorkflowRemediation,
    rule: AIRemediationRule,
) -> None:
    """A provider failure is reported as a RemediationError."""
    workflow.set_agent(build_agent(failing_model()))
    workflow.add_rule(rule)
    with pytest.raises(RemediationError, match="Failed to generate"):
        await workflow.aai_remediation_config()


NESTED_LINEAGE = (MatchRule(startswith="interface"), MatchRule(startswith="mtu"))


def nested_config(mtu: int) -> HConfig:
    """Build a config whose interesting command sits two levels deep."""
    return HConfig.from_lines(
        get_hconfig_driver(Platform.CISCO_IOS),
        f"interface Vlan2\n  mtu {mtu}\n  ip address 10.0.2.1 255.255.255.0",
    )


def test_nested_lineage_keeps_its_parent() -> None:
    """A multi-level lineage scopes with its parent chain intact.

    `get_children_deep` yields the matched nodes, so copying them onto a bare
    root reparented a nested match to the top level. The section became a bare
    `mtu 9000` with no interface above it, and no plan could ever converge
    against that -- every such rule burned its retries and then failed the
    whole workflow.
    """
    scoped = scoped_config(nested_config(9000), NESTED_LINEAGE)
    assert list(scoped.to_lines()) == ["interface Vlan2", "  mtu 9000"]


async def test_nested_lineage_can_converge() -> None:
    """A correct plan for a nested lineage is accepted."""
    workflow = AIWorkflowRemediation(nested_config(9000), nested_config(9100))
    # The old value has to be negated first: this driver does not treat `mtu`
    # as idempotent here, so a bare `mtu 9100` would stack with `mtu 9000`.
    plan = ["interface Vlan2", "  no mtu 9000", "  mtu 9100"]
    workflow.set_agent(build_agent(scripted_model(plan)))
    workflow.add_rule(
        AIRemediationRule(
            description="Set the MTU.",
            lineage=NESTED_LINEAGE,
            example=AIRemediationExample(running_config="x", remediation_config="y"),
        )
    )
    assert list((await workflow.aai_remediation_config()).to_lines()) == plan


async def test_rule_matching_nothing_is_skipped(
    workflow: AIWorkflowRemediation,
    rule: AIRemediationRule,
) -> None:
    """A rule whose section is absent is a no-op, not a failed run.

    Both scoped configs come out empty, so an empty plan is rejected for being
    empty and any non-empty plan is rejected as unwanted. The rule would
    exhaust its retries and take every sibling rule's work down with it.
    """
    absent = AIRemediationRule(
        description="Fix an access list this device does not have.",
        lineage=(MatchRule(startswith="ip access-list"),),
        example=AIRemediationExample(running_config="x", remediation_config="y"),
    )
    workflow.set_agent(build_agent(scripted_model(CORRECT_PLAN)))
    workflow.add_rule(absent)
    workflow.add_rule(rule)

    config = await workflow.aai_remediation_config()
    assert list(config.to_lines()) == CORRECT_PLAN


def test_config_section_tool_reaches_outside_the_scoped_section() -> None:
    """The lookup tool can see config the rule's section does not include.

    Deps carried only the scoped section, so the tool could only ever return a
    subset of what the prompt already inlined -- while the system prompt told
    the model to call it for more.
    """
    running, generated = build_running_config(), build_generated_config()
    scoped = scoped_config(running, LINEAGE)
    deps = RemediationDeps(
        running_config=scoped,
        generated_config=scoped_config(generated, LINEAGE),
        full_running_config=running,
        full_generated_config=generated,
    )
    section = get_config_section(
        RunContext(deps=deps, model=TestModel(), usage=RunUsage()),
        (MatchRule(equals="interface GigabitEthernet0/0"),),
    )
    assert "10.0.0.1" in section
