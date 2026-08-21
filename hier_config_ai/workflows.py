"""Remediation workflow driven by a language model."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from hier_config import HConfig, WorkflowRemediation

from .agent import DEFAULT_RETRIES, build_agent
from .deps import RemediationDeps, Retriever
from .exceptions import AIClientInitializationError, RemediationError
from .models import AIPlanResponse, AIRemediationContext
from .prompt_template import PromptTemplate

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

    from hier_config.models import MatchRule
    from pydantic_ai import Agent
    from pydantic_ai.models import Model
    from pydantic_ai.settings import ModelSettings
    from pydantic_ai.usage import RunUsage

    from .cache import ResponseCache
    from .models import AIRemediationRule
    from .rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

DEFAULT_MAX_CONCURRENCY = 4


def scoped_config(config: HConfig, lineage: tuple[MatchRule, ...]) -> HConfig:
    """Return only the part of `config` that `lineage` selects.

    Each rule owns one section, so convergence is judged inside that section.
    Judging a rule against the whole configuration would fail it for
    differences another rule is responsible for fixing.
    """
    scoped = HConfig(config.driver)
    for child in config.get_children_deep(lineage):
        # The parent chain has to come along. `get_children_deep` yields the
        # matched nodes, so copying them straight onto a bare root reparents a
        # nested match to the top level: a lineage of
        # (interface, mtu) would scope to a bare `mtu 9000` with no interface
        # above it, and no plan could ever converge against that.
        node = scoped.add_ancestor_copy_of(child)
        for descendant in child.children:
            node.add_deep_copy_of(descendant)
    return scoped


def build_context(
    rule: AIRemediationRule,
    running_config: HConfig,
    generated_config: HConfig,
) -> AIRemediationContext:
    """Build the prompt context for one rule.

    A module function so the evaluation harness scores the same prompt the
    library ships. Rebuilding it there would let the two drift, and the eval
    would stop measuring prompt changes.
    """
    return AIRemediationContext(
        running_config="\n".join(running_config.to_lines()),
        generated_config="\n".join(generated_config.to_lines()),
        description=rule.description,
        example=rule.example,
    )


class AIWorkflowRemediation(WorkflowRemediation):
    """Extends WorkflowRemediation with model-generated remediation."""

    def __init__(
        self,
        running_config: HConfig,
        generated_config: HConfig,
        plugins: Iterable[Callable[[HConfig], None]] = (),
        *,
        prompt_template: PromptTemplate | None = None,
        max_concurrency: int = DEFAULT_MAX_CONCURRENCY,
    ) -> None:
        """Initialize the workflow.

        Args:
            running_config: The device's current configuration.
            generated_config: The configuration the device should have.
            plugins: hier-config plugins applied to the configs.
            prompt_template: Template used to build each rule's prompt.
                Defaults to `PromptTemplate()`.
            max_concurrency: How many rules may be sent to the model at once.

        """
        super().__init__(running_config, generated_config, plugins)
        self.rules: list[AIRemediationRule] = []
        self.prompt_template = prompt_template or PromptTemplate()
        self.max_concurrency = max_concurrency
        self.retriever: Retriever | None = None
        self._agent: Agent[RemediationDeps, AIPlanResponse] | None = None
        self._usage: list[RunUsage] = []

    def set_model(
        self,
        model: Model | str,
        *,
        settings: ModelSettings | None = None,
        cache: ResponseCache | None = None,
        rate_limiter: RateLimiter | None = None,
        retries: int = DEFAULT_RETRIES,
    ) -> None:
        """Build an agent for `model` and use it for remediation.

        The running config's driver is handed to the agent, so the system
        prompt describes the real platform's indentation and negation rules.
        For options beyond these, build the agent yourself with `build_agent`
        and pass it to `set_agent`.
        """
        self._agent = build_agent(
            model,
            driver=self.running_config.driver,
            settings=settings,
            cache=cache,
            rate_limiter=rate_limiter,
            retriever=self.retriever,
            retries=retries,
            max_concurrency=self.max_concurrency,
        )

    def set_agent(self, agent: Agent[RemediationDeps, AIPlanResponse]) -> None:
        """Use a pre-built agent, bypassing `build_agent`."""
        self._agent = agent

    def add_rule(self, rule: AIRemediationRule) -> None:
        """Add a remediation rule to the workflow."""
        self.rules.append(rule)

    def clear_rules(self) -> None:
        """Remove every remediation rule from the workflow."""
        self.rules.clear()

    @property
    def usage(self) -> list[RunUsage]:
        """Per-rule token usage from the most recent run."""
        return list(self._usage)

    def _require_agent(self) -> Agent[RemediationDeps, AIPlanResponse]:
        """Return the configured agent, or explain that none was set."""
        if self._agent is None:
            msg = "No model is configured. Call set_model() or set_agent() first."
            raise AIClientInitializationError(msg)
        return self._agent

    def build_context(self, rule: AIRemediationRule) -> AIRemediationContext:
        """Build the prompt context for one rule."""
        return build_context(
            rule,
            scoped_config(self.running_config, rule.lineage),
            scoped_config(self.generated_config, rule.lineage),
        )

    async def _run_rule(self, rule: AIRemediationRule) -> AIPlanResponse:
        """Generate and validate the plan for a single rule.

        The section is scoped once and used for both the prompt and the
        convergence target, so the model is judged against exactly the
        configuration it was shown.
        """
        agent = self._require_agent()
        running = scoped_config(self.running_config, rule.lineage)
        generated = scoped_config(self.generated_config, rule.lineage)

        if not running.children and not generated.children:
            # Neither config has this section, so there is nothing to
            # remediate. Asking anyway guarantees failure: an empty plan is
            # rejected for being empty and any non-empty plan is rejected as
            # unwanted, so the rule would burn every retry and then take the
            # whole device's remediation down with it.
            logger.debug("Rule %r matched nothing; skipping", rule.description)
            return AIPlanResponse(plan=[])

        prompt = self.prompt_template.build(build_context(rule, running, generated))
        deps = RemediationDeps(
            running_config=running,
            generated_config=generated,
            full_running_config=self.running_config,
            full_generated_config=self.generated_config,
            retriever=self.retriever,
        )

        result = await agent.run(prompt, deps=deps)
        self._usage.append(result.usage)
        logger.debug(
            "Rule %r produced %d commands",
            rule.description,
            len(result.output.plan),
        )
        return result.output

    async def aai_remediation_config(self) -> HConfig:
        """Generate the remediation config, running every rule concurrently.

        Returns:
            An HConfig holding the commands that remediate the device.

        Raises:
            RemediationError: No rules were loaded, or the model produced
                nothing usable. `_require_agent` raises
                `AIClientInitializationError` when no model is configured.

        """
        self._require_agent()

        if not self.rules:
            msg = "No remediation rules loaded. Call add_rule() first."
            raise RemediationError(msg)

        self._usage = []

        # return_exceptions keeps a failing rule from leaving its siblings
        # running unwatched: without it gather propagates the first error while
        # the other provider calls continue, and their answers are paid for and
        # discarded.
        results = await asyncio.gather(
            *(self._run_rule(rule) for rule in self.rules),
            return_exceptions=True,
        )

        responses: list[AIPlanResponse] = []
        for result in results:
            if isinstance(result, RemediationError):
                raise result
            if isinstance(result, BaseException):
                msg = f"Failed to generate remediation plan: {result}"
                raise RemediationError(msg) from result
            responses.append(result)

        commands = [command for response in responses for command in response.plan]
        if not commands:
            msg = "The remediation plan is empty."
            raise RemediationError(msg)

        return HConfig.from_lines(self.running_config.driver, commands)

    def ai_remediation_config(self) -> HConfig:
        """Generate the remediation config from synchronous code.

        Raises:
            RuntimeError: Called from inside a running event loop. Await
                `aai_remediation_config()` instead.

        """
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self.aai_remediation_config())

        msg = (
            "ai_remediation_config() cannot run inside an event loop. "
            "Await aai_remediation_config() instead."
        )
        raise RuntimeError(msg)
