"""Composite client that can use multiple providers with optional quorum."""

from __future__ import annotations

import logging
from collections import Counter
from typing import TYPE_CHECKING

from hier_config_gpt.exceptions import RemediationError

from .models import GPTClient, GPTPlanResponse
from .utils import retry_with_backoff

if TYPE_CHECKING:
    from collections.abc import Iterable

logger = logging.getLogger(__name__)


class MultiProviderGPTClient(GPTClient):
    """GPT client that fans out to multiple providers with optional quorum."""

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
            msg = "At least one provider must be supplied."
            raise ValueError(msg)

        if enable_quorum and len(provider_list) % 2 == 0:
            msg = "Quorum mode requires an odd number of providers."
            raise ValueError(msg)

        self.providers = provider_list
        self.enable_quorum = enable_quorum
        self.retries = retries
        self.backoff_seconds = backoff_seconds

    def _try_chat(self, provider: GPTClient, prompt: str) -> tuple[str | None, str]:
        """Call one provider's chat, returning the response or an error message."""
        try:
            response = retry_with_backoff(
                lambda: provider.chat(prompt),
                retries=self.retries,
                backoff_seconds=self.backoff_seconds,
            )
        # Provider failures fall through to the next provider / quorum accounting.
        except Exception as exc:  # ruff:ignore[blind-except]  # pylint: disable=broad-exception-caught
            error_message = f"{type(provider).__name__} failed: {exc}"
            logger.warning(error_message)
            return None, error_message

        return response, ""

    def chat(self, prompt: str) -> str:
        """Return the first successful chat response across providers."""
        errors: list[str] = []
        for provider in self.providers:
            response, error_message = self._try_chat(provider, prompt)
            if response is not None:
                return response
            errors.append(error_message)

        msg = f"All providers failed: {'; '.join(errors)}"
        raise RemediationError(msg)

    def _try_generate_plan(
        self,
        provider: GPTClient,
        prompt: str,
    ) -> tuple[GPTPlanResponse | None, str]:
        """Call one provider's generate_plan, returning the response or an error."""
        try:
            response = retry_with_backoff(
                lambda: provider.generate_plan(prompt),
                retries=self.retries,
                backoff_seconds=self.backoff_seconds,
            )
        # Provider failures fall through to the next provider / quorum accounting.
        except Exception as exc:  # ruff:ignore[blind-except]  # pylint: disable=broad-exception-caught
            error_message = f"{type(provider).__name__} failed: {exc}"
            logger.warning(error_message)
            return None, error_message

        return response, ""

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
            response, error_message = self._try_generate_plan(provider, prompt)
            if response is not None:
                responses.append(response)
            else:
                errors.append(error_message)

        if not responses:
            msg = (
                "All providers failed to generate remediation plans: "
                f"{'; '.join(errors)}"
            )
            raise RemediationError(msg)

        if not self.enable_quorum:
            logger.debug("Quorum disabled, using first provider's response")
            return responses[0]

        return self._select_quorum_response(responses)

    @staticmethod
    def _select_quorum_response(responses: list[GPTPlanResponse]) -> GPTPlanResponse:
        """Pick the majority plan from provider responses or raise an error."""
        plan_strings = ["\n".join(plan.plan) for plan in responses if plan.plan]
        if not plan_strings:
            msg = "All providers returned empty remediation plans."
            raise RemediationError(msg)

        plan_counter = Counter(plan_strings)
        top_plan, count = plan_counter.most_common(1)[0]

        # Require majority (>50%) consensus
        majority_threshold = len(plan_strings) / 2
        if count <= majority_threshold:
            vote_summary = ", ".join(
                f"{votes} vote(s) for plan #{index + 1}"
                for index, (_, votes) in enumerate(plan_counter.most_common())
            )
            msg = (
                f"Quorum enabled but no majority reached among {len(plan_strings)} "
                f"provider(s). Need >{majority_threshold:.1f} votes, got {count}. "
                f"Vote distribution: {vote_summary}"
            )
            raise RemediationError(msg)

        logger.info(
            "Quorum reached: %d/%d providers agreed on the winning plan",
            count,
            len(plan_strings),
        )

        winning_response = next(
            response for response in responses if "\n".join(response.plan) == top_plan
        )
        winning_response.metadata.setdefault("quorum_votes", count)
        winning_response.metadata.setdefault("quorum_total", len(plan_strings))
        winning_response.metadata.setdefault("quorum_threshold", majority_threshold)
        return winning_response
