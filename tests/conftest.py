"""Shared fixtures and test doubles for the hier-config-gpt test suite."""

from __future__ import annotations

import pytest
from hier_config import HConfig, Platform, get_hconfig_driver
from hier_config.models import MatchRule

from hier_config_gpt.clients.models import GPTClient, GPTPlanResponse
from hier_config_gpt.models import GPTRemediationExample, GPTRemediationRule
from hier_config_gpt.workflows import GPTWorkflowRemediation


class StubGPTClient(GPTClient):
    """Deterministic GPT client used in place of real provider clients."""

    def __init__(
        self,
        plan_responses: tuple[GPTPlanResponse, ...] = (),
        chat_response: str = "stub chat response",
        error: Exception | None = None,
    ) -> None:
        self.plan_responses = list(plan_responses)
        self.chat_response = chat_response
        self.error = error
        self.prompts: list[str] = []

    def chat(self, prompt: str) -> str:
        """Return the canned chat response or raise the configured error."""
        self.prompts.append(prompt)
        if self.error is not None:
            raise self.error
        return self.chat_response

    def generate_plan(self, prompt: str) -> GPTPlanResponse:
        """Return the next canned plan response or raise the configured error."""
        self.prompts.append(prompt)
        if self.error is not None:
            raise self.error
        return self.plan_responses.pop(0)


def build_running_config() -> HConfig:
    """Build a small running config used across workflow tests."""
    config = HConfig(get_hconfig_driver(Platform.GENERIC))
    config.add_child("hostname ROUTER1")
    interface_g00 = config.add_child("interface GigabitEthernet0/0")
    interface_g00.add_child("ip address 10.0.0.1 255.255.255.0")
    interface_g00.add_child("no shutdown")
    interface_g01 = config.add_child("interface GigabitEthernet0/1")
    interface_g01.add_child("shutdown")
    return config


def build_generated_config() -> HConfig:
    """Build the intended config used across workflow tests."""
    config = HConfig(get_hconfig_driver(Platform.GENERIC))
    config.add_child("hostname ROUTER1")
    interface_g00 = config.add_child("interface GigabitEthernet0/0")
    interface_g00.add_child("ip address 10.0.0.1 255.255.255.0")
    interface_g00.add_child("no shutdown")
    interface_g01 = config.add_child("interface GigabitEthernet0/1")
    interface_g01.add_child("ip address 10.0.1.1 255.255.255.0")
    interface_g01.add_child("no shutdown")
    return config


def build_gpt_remediation_example() -> GPTRemediationExample:
    """Build a sample GPT remediation example."""
    return GPTRemediationExample(
        running_config="interface GigabitEthernet0/1\n shutdown",
        remediation_config=(
            "interface GigabitEthernet0/1\n"
            " no shutdown\n"
            " ip address 192.168.1.1 255.255.255.0"
        ),
    )


@pytest.fixture
def running_config() -> HConfig:
    """A running config instance built fresh for each test."""
    return build_running_config()


@pytest.fixture
def generated_config() -> HConfig:
    """A generated config instance built fresh for each test."""
    return build_generated_config()


@pytest.fixture
def gpt_remediation_example() -> GPTRemediationExample:
    """A sample GPT remediation example."""
    return build_gpt_remediation_example()


@pytest.fixture
def gpt_rule() -> GPTRemediationRule:
    """A sample GPT remediation rule."""
    return GPTRemediationRule(
        lineage=(MatchRule(equals="interface GigabitEthernet0/1"),),
        description="Configure IP address and enable interface",
        example=build_gpt_remediation_example(),
    )


@pytest.fixture
def remediation_workflow() -> GPTWorkflowRemediation:
    """A GPTWorkflowRemediation instance with real HConfig objects."""
    return GPTWorkflowRemediation(
        running_config=build_running_config(),
        generated_config=build_generated_config(),
    )
