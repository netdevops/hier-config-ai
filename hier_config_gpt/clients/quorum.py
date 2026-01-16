"""Composite client that can use multiple providers with optional quorum."""

from __future__ import annotations

import logging
from collections import Counter
from typing import Iterable

from ..exceptions import RemediationError
from .models import GPTClient, GPTPlanResponse
from .utils import retry_with_backoff


logger = logging.getLogger(__name__)


class MultiProviderGPTClient(GPTClient):
    def __init__(
        self,
        providers: Iterable[GPTClient],
        *,
        enable_quorum: bool = False,
        retries: int = 1,
        backoff_seconds: float = 0.5,
    ) -> None:
        provider_list = list(providers)
        if not provider_list:
            raise ValueError("At least one provider must be supplied.")

        if enable_quorum and len(provider_list) % 2 == 0:
            raise ValueError("Quorum mode requires an odd number of providers.")

        self.providers = provider_list
        self.enable_quorum = enable_quorum
        self.retries = retries
        self.backoff_seconds = backoff_seconds

    def chat(self, prompt: str) -> str:
        errors: list[str] = []
        for provider in self.providers:
            try:
                return retry_with_backoff(
                    lambda p=provider: p.chat(prompt),
                    retries=self.retries,
                    backoff_seconds=self.backoff_seconds,
                )
            except Exception as exc:  # pragma: no cover - defensive
                error_message = f"{provider.__class__.__name__} failed: {exc}"
                logger.warning(error_message)
                errors.append(error_message)

        raise RemediationError(f"All providers failed: {'; '.join(errors)}")

    def generate_plan(self, prompt: str) -> GPTPlanResponse:
        """Collect plans from providers and optionally enforce quorum.

        Args:
            prompt: The prompt to send to all providers.

        Returns:
            GPTPlanResponse: The winning plan (first provider if quorum disabled,
                           or the majority consensus if quorum enabled).

        Raises:
            RemediationError: If all providers fail, return empty plans, or
                            no majority is reached when quorum is enabled.
        """
        responses: list[GPTPlanResponse] = []
        errors: list[str] = []

        for provider in self.providers:
            try:
                response = retry_with_backoff(
                    lambda p=provider: p.generate_plan(prompt),
                    retries=self.retries,
                    backoff_seconds=self.backoff_seconds,
                )
                responses.append(response)
            except Exception as exc:  # pragma: no cover - defensive
                error_message = f"{provider.__class__.__name__} failed: {exc}"
                logger.warning(error_message)
                errors.append(error_message)

        if not responses:
            raise RemediationError(
                f"All providers failed to generate remediation plans: {'; '.join(errors)}"
            )

        if not self.enable_quorum:
            logger.debug("Quorum disabled, using first provider's response")
            return responses[0]

        plan_strings = ["\n".join(plan.plan) for plan in responses if plan.plan]
        if not plan_strings:
            raise RemediationError("All providers returned empty remediation plans.")

        plan_counter = Counter(plan_strings)
        top_plan, count = plan_counter.most_common(1)[0]

        # Require majority (>50%) consensus
        majority_threshold = len(plan_strings) / 2
        if count <= majority_threshold:
            vote_summary = ", ".join(
                f"{votes} vote(s) for plan #{i+1}"
                for i, (_, votes) in enumerate(plan_counter.most_common())
            )
            raise RemediationError(
                f"Quorum enabled but no majority reached among {len(plan_strings)} "
                f"provider(s). Need >{majority_threshold:.1f} votes, got {count}. "
                f"Vote distribution: {vote_summary}"
            )

        logger.info(
            "Quorum reached: %d/%d providers agreed on the winning plan",
            count,
            len(plan_strings)
        )

        winning_response = next(
            response for response in responses if "\n".join(response.plan) == top_plan
        )
        winning_response.metadata.setdefault("quorum_votes", count)
        winning_response.metadata.setdefault("quorum_total", len(plan_strings))
        winning_response.metadata.setdefault("quorum_threshold", majority_threshold)
        return winning_response
