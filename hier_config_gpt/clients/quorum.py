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
                    lambda: provider.chat(prompt),
                    retries=self.retries,
                    backoff_seconds=self.backoff_seconds,
                )
            except Exception as exc:  # pragma: no cover - defensive
                error_message = f"{provider.__class__.__name__} failed: {exc}"
                logger.warning(error_message)
                errors.append(error_message)

        raise RemediationError("; ".join(errors))

    def generate_plan(self, prompt: str) -> GPTPlanResponse:
        """Collect plans from providers and optionally enforce quorum."""

        responses: list[GPTPlanResponse] = []
        errors: list[str] = []

        for provider in self.providers:
            try:
                response = retry_with_backoff(
                    lambda: provider.generate_plan(prompt),
                    retries=self.retries,
                    backoff_seconds=self.backoff_seconds,
                )
                responses.append(response)
            except Exception as exc:  # pragma: no cover - defensive
                error_message = f"{provider.__class__.__name__} failed: {exc}"
                logger.warning(error_message)
                errors.append(error_message)

        if not responses:
            raise RemediationError("All providers failed to generate remediation plans.")

        if not self.enable_quorum:
            return responses[0]

        plan_strings = ["\n".join(plan.plan) for plan in responses if plan.plan]
        if not plan_strings:
            raise RemediationError("All providers returned empty remediation plans.")

        plan_counter = Counter(plan_strings)
        top_plan, count = plan_counter.most_common(1)[0]
        if count == 1:
            raise RemediationError(
                "Quorum enabled but no agreement reached among providers."
            )

        winning_response = next(
            response for response in responses if "\n".join(response.plan) == top_plan
        )
        winning_response.metadata.setdefault("quorum_votes", plan_counter[top_plan])
        winning_response.metadata.setdefault("quorum_total", len(plan_strings))
        return winning_response
