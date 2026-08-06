"""Tests for the multi-provider quorum client."""

from __future__ import annotations

import pytest

from hier_config_gpt.clients.models import GPTPlanResponse
from hier_config_gpt.clients.quorum import MultiProviderGPTClient
from hier_config_gpt.exceptions import RemediationError
from tests.conftest import StubGPTClient


def _plan(*commands: str) -> GPTPlanResponse:
    """Build a plan response from commands."""
    return GPTPlanResponse(plan=list(commands))


def test_quorum_requires_at_least_one_provider() -> None:
    with pytest.raises(ValueError, match="At least one provider must be supplied"):
        MultiProviderGPTClient(providers=())


def test_quorum_requires_odd_number_of_providers() -> None:
    providers = (StubGPTClient(), StubGPTClient())

    with pytest.raises(ValueError, match="odd number of providers"):
        MultiProviderGPTClient(providers=providers, enable_quorum=True)


def test_chat_returns_first_successful_response() -> None:
    providers = (
        StubGPTClient(chat_response="first"),
        StubGPTClient(chat_response="second"),
    )
    client = MultiProviderGPTClient(providers=providers, retries=0, backoff_seconds=0)

    assert client.chat("prompt") == "first"


def test_chat_falls_back_to_next_provider() -> None:
    providers = (
        StubGPTClient(error=RuntimeError("provider down")),
        StubGPTClient(chat_response="fallback"),
    )
    client = MultiProviderGPTClient(providers=providers, retries=0, backoff_seconds=0)

    assert client.chat("prompt") == "fallback"


def test_chat_all_providers_fail() -> None:
    providers = (
        StubGPTClient(error=RuntimeError("down 1")),
        StubGPTClient(error=RuntimeError("down 2")),
    )
    client = MultiProviderGPTClient(providers=providers, retries=0, backoff_seconds=0)

    with pytest.raises(RemediationError, match="All providers failed"):
        client.chat("prompt")


def test_generate_plan_without_quorum_uses_first_provider() -> None:
    providers = (
        StubGPTClient(plan_responses=(_plan("command1"),)),
        StubGPTClient(plan_responses=(_plan("command2"),)),
    )
    client = MultiProviderGPTClient(providers=providers, retries=0, backoff_seconds=0)

    assert client.generate_plan("prompt").plan == ["command1"]


def test_generate_plan_all_providers_fail() -> None:
    providers = (
        StubGPTClient(error=RuntimeError("down 1")),
        StubGPTClient(error=RuntimeError("down 2")),
    )
    client = MultiProviderGPTClient(providers=providers, retries=0, backoff_seconds=0)

    with pytest.raises(RemediationError, match="All providers failed to generate"):
        client.generate_plan("prompt")


def test_generate_plan_quorum_majority_wins() -> None:
    providers = (
        StubGPTClient(plan_responses=(_plan("winner"),)),
        StubGPTClient(plan_responses=(_plan("winner"),)),
        StubGPTClient(plan_responses=(_plan("loser"),)),
    )
    client = MultiProviderGPTClient(
        providers=providers,
        enable_quorum=True,
        retries=0,
        backoff_seconds=0,
    )

    response = client.generate_plan("prompt")

    assert response.plan == ["winner"]
    assert response.metadata["quorum_votes"] == 2
    assert response.metadata["quorum_total"] == 3


def test_generate_plan_quorum_no_majority() -> None:
    providers = (
        StubGPTClient(plan_responses=(_plan("plan a"),)),
        StubGPTClient(plan_responses=(_plan("plan b"),)),
        StubGPTClient(plan_responses=(_plan("plan c"),)),
    )
    client = MultiProviderGPTClient(
        providers=providers,
        enable_quorum=True,
        retries=0,
        backoff_seconds=0,
    )

    with pytest.raises(RemediationError, match="no majority reached"):
        client.generate_plan("prompt")


def test_generate_plan_quorum_all_empty_plans() -> None:
    providers = (
        StubGPTClient(plan_responses=(_plan(),)),
        StubGPTClient(plan_responses=(_plan(),)),
        StubGPTClient(plan_responses=(_plan(),)),
    )
    client = MultiProviderGPTClient(
        providers=providers,
        enable_quorum=True,
        retries=0,
        backoff_seconds=0,
    )

    with pytest.raises(RemediationError, match="empty remediation plans"):
        client.generate_plan("prompt")
