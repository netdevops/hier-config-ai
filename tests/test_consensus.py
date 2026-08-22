"""Tests for multi-model consensus."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from hier_config import Platform, get_hconfig_driver

from hier_config_ai.agent import build_agent
from hier_config_ai.consensus import consensus_plan, plan_fingerprint
from hier_config_ai.exceptions import ConsensusError
from tests.conftest import (
    CORRECT_PLAN,
    INTERFACE,
    failing_model,
    scripted_model,
)

if TYPE_CHECKING:
    from pydantic_ai import Agent

    from hier_config_ai.deps import RemediationDeps
    from hier_config_ai.models import AIPlanResponse

DRIVER = get_hconfig_driver(Platform.GENERIC)
OTHER_PLAN = [INTERFACE, "  ip address 10.9.9.9 255.255.255.0"]


def agents(*plans: list[str]) -> list[Agent[RemediationDeps, AIPlanResponse]]:
    """Build one agent per supplied plan."""
    return [build_agent(scripted_model(plan)) for plan in plans]


def test_ordering_does_not_change_the_fingerprint() -> None:
    """Two plans with the same commands in a different order agree.

    The previous quorum compared joined strings, so any difference in ordering
    or whitespace prevented agreement and quorum almost always failed.
    """
    reordered = [INTERFACE, "  no shutdown", "  ip address 10.0.1.1 255.255.255.0"]
    assert plan_fingerprint(DRIVER, CORRECT_PLAN) == plan_fingerprint(DRIVER, reordered)


def test_different_plans_have_different_fingerprints() -> None:
    """Genuinely different configuration does not compare equal."""
    assert plan_fingerprint(DRIVER, CORRECT_PLAN) != plan_fingerprint(
        DRIVER, OTHER_PLAN
    )


async def test_majority_wins(deps: RemediationDeps) -> None:
    """Two agents out of three agreeing carries the vote."""
    result = await consensus_plan(
        agents(CORRECT_PLAN, CORRECT_PLAN, OTHER_PLAN),
        "remediate",
        deps,
    )
    assert result.plan == CORRECT_PLAN
    assert result.metadata["consensus_votes"] == 2
    assert result.metadata["consensus_agents"] == 3


async def test_no_majority_is_refused(deps: RemediationDeps) -> None:
    """Three different answers reach no majority."""
    third = [INTERFACE, "  ip address 10.8.8.8 255.255.255.0"]
    with pytest.raises(ConsensusError, match="No majority"):
        await consensus_plan(
            agents(CORRECT_PLAN, OTHER_PLAN, third),
            "remediate",
            deps,
        )


async def test_lone_survivor_cannot_win_unopposed(deps: RemediationDeps) -> None:
    """One answer out of three agents asked is not a majority.

    The previous quorum divided by the number of agents that answered, so if
    two of three providers failed the single survivor won the vote by itself.
    """
    working = build_agent(scripted_model(CORRECT_PLAN))

    with pytest.raises(ConsensusError, match="No majority"):
        await consensus_plan(
            [working, build_agent(failing_model()), build_agent(failing_model())],
            "remediate",
            deps,
        )


async def test_all_agents_failing_is_reported(deps: RemediationDeps) -> None:
    """When nothing answers, the failures are surfaced."""
    with pytest.raises(ConsensusError, match="Every agent failed"):
        await consensus_plan([build_agent(failing_model())], "remediate", deps)


async def test_no_agents_is_refused(deps: RemediationDeps) -> None:
    """No agents is a caller mistake, not a disagreement between models."""
    with pytest.raises(ValueError, match="At least one agent"):
        await consensus_plan([], "remediate", deps)
