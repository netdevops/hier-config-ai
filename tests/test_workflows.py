"""Tests for GPTWorkflowRemediation."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from hier_config_gpt.clients.models import GPTPlanResponse
from hier_config_gpt.exceptions import GPTClientInitializationError, RemediationError
from tests.conftest import StubGPTClient

if TYPE_CHECKING:
    from hier_config import HConfig

    from hier_config_gpt.models import GPTRemediationRule
    from hier_config_gpt.workflows import GPTWorkflowRemediation


def test_init(
    remediation_workflow: GPTWorkflowRemediation,
    running_config: HConfig,
    generated_config: HConfig,
) -> None:
    assert remediation_workflow.running_config == running_config
    assert remediation_workflow.generated_config == generated_config
    assert remediation_workflow.gpt_rules == []


def test_add_and_clear_gpt_rules(
    remediation_workflow: GPTWorkflowRemediation,
    gpt_rule: GPTRemediationRule,
) -> None:
    remediation_workflow.add_gpt_rule(gpt_rule)
    assert remediation_workflow.gpt_rules == [gpt_rule]

    remediation_workflow.clear_gpt_rules()
    assert remediation_workflow.gpt_rules == []


def test_gpt_remediation_config_no_client(
    remediation_workflow: GPTWorkflowRemediation,
) -> None:
    with pytest.raises(
        GPTClientInitializationError, match="No GPT client is initialized"
    ):
        remediation_workflow.gpt_remediation_config()


def test_gpt_remediation_config_no_rules(
    remediation_workflow: GPTWorkflowRemediation,
) -> None:
    remediation_workflow.set_gpt_client(StubGPTClient())

    with pytest.raises(RemediationError, match="No GPT remediation rules loaded"):
        remediation_workflow.gpt_remediation_config()


def test_gpt_remediation_config_success(
    remediation_workflow: GPTWorkflowRemediation,
    gpt_rule: GPTRemediationRule,
) -> None:
    plan = GPTPlanResponse(
        plan=[
            "interface GigabitEthernet0/1",
            "  ip address 10.0.1.1 255.255.255.0",
            "  no shutdown",
        ],
        metadata={"provider": "stub"},
    )
    client = StubGPTClient(plan_responses=(plan,))
    remediation_workflow.set_gpt_client(client)
    remediation_workflow.add_gpt_rule(gpt_rule)

    result = remediation_workflow.gpt_remediation_config()

    assert tuple(result.to_lines()) == (
        "interface GigabitEthernet0/1",
        "  ip address 10.0.1.1 255.255.255.0",
        "  no shutdown",
    )


def test_gpt_remediation_config_prompt_contents(
    remediation_workflow: GPTWorkflowRemediation,
    gpt_rule: GPTRemediationRule,
) -> None:
    plan = GPTPlanResponse(plan=["interface GigabitEthernet0/1", "  no shutdown"])
    client = StubGPTClient(plan_responses=(plan,))
    remediation_workflow.set_gpt_client(client)
    remediation_workflow.add_gpt_rule(gpt_rule)

    remediation_workflow.gpt_remediation_config()

    assert len(client.prompts) == 1
    prompt = client.prompts[0]
    assert "Network Configuration Remediation Plan Generation" in prompt
    assert "interface GigabitEthernet0/1" in prompt
    assert "Configure IP address and enable interface" in prompt
    # The rule's example config appears in the prompt.
    assert "ip address 192.168.1.1 255.255.255.0" in prompt
    # The matched running config section appears in the prompt.
    assert "shutdown" in prompt


def test_gpt_remediation_config_multiple_rules(
    remediation_workflow: GPTWorkflowRemediation,
    gpt_rule: GPTRemediationRule,
) -> None:
    first_plan = GPTPlanResponse(
        plan=["interface GigabitEthernet0/1", "  ip address 10.0.1.1 255.255.255.0"]
    )
    second_plan = GPTPlanResponse(
        plan=["router ospf 1", "  network 10.0.0.0 0.0.0.255 area 0"]
    )
    client = StubGPTClient(plan_responses=(first_plan, second_plan))
    remediation_workflow.set_gpt_client(client)
    remediation_workflow.add_gpt_rule(gpt_rule)
    remediation_workflow.add_gpt_rule(gpt_rule)

    result = remediation_workflow.gpt_remediation_config()

    assert len(client.prompts) == 2
    assert tuple(result.to_lines()) == (
        "interface GigabitEthernet0/1",
        "  ip address 10.0.1.1 255.255.255.0",
        "router ospf 1",
        "  network 10.0.0.0 0.0.0.255 area 0",
    )


def test_gpt_remediation_config_client_error(
    remediation_workflow: GPTWorkflowRemediation,
    gpt_rule: GPTRemediationRule,
) -> None:
    client = StubGPTClient(error=RuntimeError("API error"))
    remediation_workflow.set_gpt_client(client)
    remediation_workflow.add_gpt_rule(gpt_rule)

    with pytest.raises(
        RemediationError, match="Failed to generate remediation plan: API error"
    ):
        remediation_workflow.gpt_remediation_config()


def test_gpt_remediation_config_empty_plan(
    remediation_workflow: GPTWorkflowRemediation,
    gpt_rule: GPTRemediationRule,
) -> None:
    client = StubGPTClient(plan_responses=(GPTPlanResponse(plan=[]),))
    remediation_workflow.set_gpt_client(client)
    remediation_workflow.add_gpt_rule(gpt_rule)

    with pytest.raises(RemediationError, match="GPT remediation plan is empty"):
        remediation_workflow.gpt_remediation_config()


def test_gpt_remediation_config_rejects_tab_characters(
    remediation_workflow: GPTWorkflowRemediation,
    gpt_rule: GPTRemediationRule,
) -> None:
    plan = GPTPlanResponse(plan=["interface GigabitEthernet0/1", "\tno shutdown"])
    client = StubGPTClient(plan_responses=(plan,))
    remediation_workflow.set_gpt_client(client)
    remediation_workflow.add_gpt_rule(gpt_rule)

    with pytest.raises(
        RemediationError, match="Commands must not contain tab characters"
    ):
        remediation_workflow.gpt_remediation_config()
