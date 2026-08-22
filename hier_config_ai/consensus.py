"""Consensus across several models.

The old quorum client compared plans as joined strings, so two providers that
produced the same configuration in a different order never agreed and quorum
almost always failed. Votes are counted on parsed configuration instead, which
is insensitive to ordering and whitespace.

For plain failover, prefer `pydantic_ai.models.fallback.FallbackModel`. This
module exists for the different job of asking several models the same question
and only accepting an answer they agree on.
"""

from __future__ import annotations

import asyncio
import logging
from collections import Counter
from typing import TYPE_CHECKING

from hier_config import HConfig

from .exceptions import ConsensusError

if TYPE_CHECKING:
    from collections.abc import Sequence

    from hier_config.platforms.driver_base import HConfigDriverBase
    from pydantic_ai import Agent

    from .deps import RemediationDeps
    from .models import AIPlanResponse

logger = logging.getLogger(__name__)


def plan_fingerprint(driver: HConfigDriverBase, plan: Sequence[str]) -> frozenset[str]:
    """Reduce a plan to a value that ignores ordering and whitespace.

    The plan is parsed with the platform driver and rendered back to canonical
    lines, so two plans that configure the same device the same way compare
    equal even when the models wrote them differently.
    """
    parsed = HConfig.from_lines(driver, list(plan))
    return frozenset(parsed.to_lines())


async def gather_plans(
    agents: Sequence[Agent[RemediationDeps, AIPlanResponse]],
    prompt: str,
    deps: RemediationDeps,
) -> tuple[list[AIPlanResponse], list[str]]:
    """Run every agent on the same prompt at once.

    Returns:
        The successful responses, and a message for each agent that failed.
        Agents run concurrently, so the wait is the slowest single agent rather
        than the sum of all of them.

    """
    results = await asyncio.gather(
        *(agent.run(prompt, deps=deps) for agent in agents),
        return_exceptions=True,
    )

    responses: list[AIPlanResponse] = []
    errors: list[str] = []
    for agent, result in zip(agents, results, strict=True):
        name = agent.name or type(agent).__name__
        if isinstance(result, BaseException):
            logger.warning("Agent %s failed: %s", name, result)
            errors.append(f"{name}: {result}")
        else:
            responses.append(result.output)

    return responses, errors


async def consensus_plan(
    agents: Sequence[Agent[RemediationDeps, AIPlanResponse]],
    prompt: str,
    deps: RemediationDeps,
) -> AIPlanResponse:
    """Return the plan a majority of agents agree on.

    The majority is measured against the number of agents asked, not the number
    that answered. Dividing by survivors would let a single agent that happened
    to answer carry the vote unopposed, which is the opposite of what quorum is
    for.

    Raises:
        ValueError: No agents were supplied.
        ConsensusError: Every agent failed, or no plan reached a majority.

    """
    if not agents:
        # A caller mistake, not a disagreement between models, so it must not
        # be caught by `except ConsensusError`.
        msg = "At least one agent must be supplied."
        raise ValueError(msg)

    responses, errors = await gather_plans(agents, prompt, deps)
    if not responses:
        msg = f"Every agent failed to produce a plan: {'; '.join(errors)}"
        raise ConsensusError(msg)

    votes: Counter[frozenset[str]] = Counter()
    by_fingerprint: dict[frozenset[str], AIPlanResponse] = {}
    for response in responses:
        if not response.plan:
            continue
        fingerprint = plan_fingerprint(deps.driver, response.plan)
        votes[fingerprint] += 1
        by_fingerprint.setdefault(fingerprint, response)

    if not votes:
        msg = "Every agent returned an empty plan."
        raise ConsensusError(msg)

    winner, count = votes.most_common(1)[0]
    threshold = len(agents) / 2

    if count <= threshold:
        distribution = ", ".join(f"{tally} vote(s)" for _, tally in votes.most_common())
        msg = (
            f"No majority among {len(agents)} agent(s). Needed more than "
            f"{threshold:.1f} votes, best was {count}. Distribution: "
            f"{distribution}."
        )
        if errors:
            msg = f"{msg} Failures: {'; '.join(errors)}"
        raise ConsensusError(msg)

    logger.info("Consensus reached: %d of %d agents agreed", count, len(agents))

    response = by_fingerprint[winner]
    response.metadata.setdefault("consensus_votes", count)
    response.metadata.setdefault("consensus_agents", len(agents))
    return response
