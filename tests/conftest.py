"""Shared fixtures and test doubles for the hier-config-ai test suite."""

# Fixture functions take parameters named after other fixtures. That is how
# pytest injects them, not accidental shadowing.
# pylint: disable=redefined-outer-name

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from hier_config import HConfig, Platform, get_hconfig_driver
from hier_config.models import MatchRule
from pydantic_ai.messages import ModelResponse, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from hier_config_ai.deps import RemediationDeps
from hier_config_ai.models import AIRemediationExample, AIRemediationRule
from hier_config_ai.workflows import AIWorkflowRemediation

if TYPE_CHECKING:
    from collections.abc import Sequence

    from pydantic_ai.messages import ModelMessage

INTERFACE = "interface GigabitEthernet0/1"
LINEAGE: tuple[MatchRule, ...] = (MatchRule(equals=INTERFACE),)

# The plan that turns the running config below into the generated one.
CORRECT_PLAN: list[str] = [
    INTERFACE,
    "  ip address 10.0.1.1 255.255.255.0",
    "  no shutdown",
]
# Enables the interface but never sets the address, so it does not converge.
INCOMPLETE_PLAN: list[str] = [INTERFACE, "  no shutdown"]


def build_running_config() -> HConfig:
    """Build the device's current configuration."""
    config = HConfig(get_hconfig_driver(Platform.GENERIC))
    config.add_child("hostname ROUTER1")
    interface_g00 = config.add_child("interface GigabitEthernet0/0")
    interface_g00.add_child("ip address 10.0.0.1 255.255.255.0")
    interface_g00.add_child("no shutdown")
    interface_g01 = config.add_child(INTERFACE)
    interface_g01.add_child("shutdown")
    return config


def build_generated_config() -> HConfig:
    """Build the configuration the device should have."""
    config = HConfig(get_hconfig_driver(Platform.GENERIC))
    config.add_child("hostname ROUTER1")
    interface_g00 = config.add_child("interface GigabitEthernet0/0")
    interface_g00.add_child("ip address 10.0.0.1 255.255.255.0")
    interface_g00.add_child("no shutdown")
    interface_g01 = config.add_child(INTERFACE)
    interface_g01.add_child("ip address 10.0.1.1 255.255.255.0")
    interface_g01.add_child("no shutdown")
    return config


def build_remediation_example() -> AIRemediationExample:
    """Build a sample remediation example."""
    return AIRemediationExample(
        running_config=f"{INTERFACE}\n shutdown",
        remediation_config=(
            f"{INTERFACE}\n no shutdown\n ip address 192.168.1.1 255.255.255.0"
        ),
    )


def scripted_model(*plans: Sequence[str]) -> FunctionModel:
    """Return a model that emits `plans` in order, one per request.

    This replaces the old provider-SDK mocks. Nothing is patched: the model is
    a real PydanticAI model that happens to answer from a script, so the agent,
    the tools, and the output validators all run exactly as they do in
    production.
    """
    remaining = [list(plan) for plan in plans]

    def respond(_messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        plan = remaining.pop(0) if remaining else list(plans[-1])
        return ModelResponse(
            parts=[
                ToolCallPart(
                    tool_name=info.output_tools[0].name,
                    args={
                        "plan": plan,
                        "reasoning": "scripted",
                        "confidence": "high",
                        "commands_requiring_review": [],
                        "metadata": {},
                    },
                )
            ]
        )

    return FunctionModel(respond)


@pytest.fixture
def running_config() -> HConfig:
    """Return the device's current configuration."""
    return build_running_config()


@pytest.fixture
def generated_config() -> HConfig:
    """Return the configuration the device should have."""
    return build_generated_config()


@pytest.fixture
def remediation_example() -> AIRemediationExample:
    """Return a sample remediation example."""
    return build_remediation_example()


@pytest.fixture
def rule(remediation_example: AIRemediationExample) -> AIRemediationRule:
    """Return a rule covering the interface that needs remediation."""
    return AIRemediationRule(
        description="Bring the interface up and give it an address.",
        lineage=LINEAGE,
        example=remediation_example,
    )


@pytest.fixture
def deps(running_config: HConfig, generated_config: HConfig) -> RemediationDeps:
    """Return deps scoped to the whole configuration."""
    return RemediationDeps(
        running_config=running_config,
        generated_config=generated_config,
    )


@pytest.fixture
def workflow(
    running_config: HConfig,
    generated_config: HConfig,
) -> AIWorkflowRemediation:
    """Return a workflow with no model configured yet."""
    return AIWorkflowRemediation(running_config, generated_config)


class StubRetriever:
    """Retriever that records its calls and returns nothing.

    0.2.0 ships no retrieval, so this exists to prove the seams accept one:
    `RemediationDeps` carries it, `build_tools` is handed it, and the retry
    message helper sees it. The signatures match `Retriever` exactly, so it
    also checks that the protocol is implementable.
    """

    def __init__(self) -> None:
        self.queries: list[str] = []

    async def search(
        self,
        query: str,
        *,
        platform: Platform,
        k: int = 5,
    ) -> list[str]:
        """Record the query and return no context."""
        self.queries.append(f"{platform}:{query}:{k}")
        return []

    async def similar_remediations(
        self,
        running_config: HConfig,
        generated_config: HConfig,
        *,
        platform: Platform,
        k: int = 3,
    ) -> list[AIRemediationExample]:
        """Record the call and return no examples."""
        self.queries.append(
            f"{platform}:{len(list(running_config.to_lines()))}:"
            f"{len(list(generated_config.to_lines()))}:{k}"
        )
        return []


def failing_model(message: str = "provider unavailable") -> FunctionModel:
    """Return a model whose every request raises.

    A real `FunctionModel` rather than a duck-typed `Agent` stand-in, so the
    failure travels the real request path and callers stay typed as `Agent`.
    """

    def fail(_messages: list[ModelMessage], _info: AgentInfo) -> ModelResponse:
        raise RuntimeError(message)

    return FunctionModel(fail)
