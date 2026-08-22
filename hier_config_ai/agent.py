"""Construction of the remediation agent."""

from __future__ import annotations

from typing import TYPE_CHECKING

from hier_config.models import NegationStrategy
from pydantic_ai import Agent, NativeOutput, PromptedOutput
from pydantic_ai.output import StructuredOutputMode

from .deps import RemediationDeps
from .model_wrappers import CachedModel, RateLimitedModel
from .models import AIPlanResponse
from .tools import build_tools
from .validation import validate_plan

if TYPE_CHECKING:
    from hier_config.models import MatchRule, NegationRule
    from hier_config.platforms.driver_base import HConfigDriverBase
    from pydantic_ai.models import Model
    from pydantic_ai.settings import ModelSettings

    from .cache import ResponseCache
    from .deps import Retriever
    from .rate_limiter import RateLimiter

TOOL_INSTRUCTIONS = """\
Call `test_remediation` to check your commands before you answer. It reports
exactly what your commands would do to the device. Use `get_config_section` when
you need to see more of the configuration than you were given.
"""

SYSTEM_PROMPT = """\
You are a network engineer producing configuration remediation for a live device.

Return the commands that transform the running configuration into the intended
configuration, and nothing else. Do not include rollback steps, verification
steps, or commentary in the plan.

Indent child commands with spaces to show the command hierarchy. Never use tab
characters.

Your plan is applied to the device and re-checked. If it does not produce the
intended configuration you are told what is still wrong, and you must correct it.
"""

# How many driver rules to show. The full set runs to dozens of entries on some
# platforms, which would crowd out the configuration itself. Whatever is cut is
# reported, so the model knows the list it sees is partial.
_MAX_RULES_SHOWN = 12

# How many times the model may correct a rejected plan.
DEFAULT_RETRIES = 3

# PydanticAI's own name for this axis; aliased so callers of this package
# do not have to import from it.
OutputMode = StructuredOutputMode


def output_spec(
    mode: OutputMode,
) -> (
    type[AIPlanResponse] | NativeOutput[AIPlanResponse] | PromptedOutput[AIPlanResponse]
):
    """Return the output specification for a mode.

    `"tool"` suits the hosted providers, which are reliable at tool calling.
    Small self-hosted models frequently are not: they answer with the tool-call
    envelope nested inside the arguments, or emit the call as plain text, and
    the run dies after exhausting its retries. Those models usually do far
    better with `"native"`, a JSON schema on the response itself.
    """
    if mode == "native":
        return NativeOutput(AIPlanResponse)
    if mode == "prompted":
        return PromptedOutput(AIPlanResponse)
    return AIPlanResponse


def render_match_rules(match_rules: tuple[MatchRule, ...]) -> str:
    """Render a lineage of match rules as a readable command path."""
    return " > ".join(
        str(
            rule.equals
            or rule.startswith
            or rule.contains
            or rule.endswith
            or (f"/{rule.re_search}/" if rule.re_search else "*")
        )
        for rule in match_rules
    )


def _bullets(heading: str, bullets: list[str]) -> str | None:
    """Render a heading and its bullets, saying how many were left out."""
    if not bullets:
        return None

    shown = bullets[:_MAX_RULES_SHOWN]
    dropped = len(bullets) - len(shown)
    body = "\n".join(shown)
    section = f"{heading}\n{body}"
    if dropped:
        section += (
            f"\n- ...and {dropped} more not shown. If a command behaves "
            "unexpectedly, call test_remediation to check it."
        )
    return section


def negation_bullet(rule: NegationRule) -> str:
    """Describe one negation rule in the terms the model needs."""
    path = render_match_rules(rule.match_rules)
    if rule.strategy is NegationStrategy.REPLACE:
        return f"- `{path}` is removed by writing `{rule.use}` instead"
    if rule.strategy is NegationStrategy.REGEX_SUB:
        return (
            f"- `{path}` is removed by replacing `{rule.search}` with `{rule.replace}`"
        )
    return f"- `{path}` is removed with the default negation"


def describe_driver(driver: HConfigDriverBase) -> str:
    """Summarise the platform's own rules for the system prompt.

    hier-config already knows how each platform indents, negates, and closes
    sections, so these facts are read off the driver rather than restated by
    hand. Restating them invites drift between the prompt and the parser that
    validates the answer.
    """
    rules = driver.rules

    syntax = [
        f"Indent each level of the command hierarchy by {rules.indentation} spaces.",
        f"Remove a command by prefixing it with `{driver.negation_prefix.strip()}`.",
    ]
    if driver.declaration_prefix:
        syntax.append(
            f"Introduce a command by prefixing it with "
            f"`{driver.declaration_prefix.strip()}`."
        )

    exits = sorted({entry.exit_text for entry in rules.sectional_exiting})
    if exits:
        listed = ", ".join(f"`{text}`" for text in exits)
        syntax.append(f"Close sections with the matching exit command: {listed}.")

    sections = [
        " ".join(syntax),
        _bullets(
            "These commands are not removed the usual way:",
            [negation_bullet(rule) for rule in rules.negation],
        ),
        _bullets(
            "These commands overwrite the existing value rather than stacking, so "
            "set them directly instead of negating first:",
            [
                f"- `{render_match_rules(entry.match_rules)}`"
                for entry in rules.idempotent_commands
            ],
        ),
    ]
    return "\n\n".join(section for section in sections if section)


def build_agent(  # ruff: ignore[too-many-arguments] - an options object would read worse here
    model: Model | str,
    *,
    driver: HConfigDriverBase | None = None,
    settings: ModelSettings | None = None,
    cache: ResponseCache | None = None,
    rate_limiter: RateLimiter | None = None,
    retriever: Retriever | None = None,
    retries: int = DEFAULT_RETRIES,
    max_concurrency: int | None = None,
    output_mode: OutputMode = "tool",
    enable_tools: bool = True,
) -> Agent[RemediationDeps, AIPlanResponse]:
    """Build an agent that returns validated remediation plans.

    Args:
        model: A PydanticAI model, or a model name such as
            `"anthropic:claude-sonnet-4-5"` or `"openai:gpt-4.1"`.
        driver: Platform driver whose rules are added to the system prompt.
            Optional, but the model does markedly better with them.
        settings: Model settings such as temperature and max tokens.
        cache: Reuse identical requests from this on-disk cache.
        rate_limiter: Hold requests back to stay within this budget.
        retriever: Reserved for 0.3.0. Retrieval-backed tools appear only when
            this is supplied.
        retries: How many times the model may correct a rejected plan.
        max_concurrency: Limit on concurrent runs of this agent.
        output_mode: How the model returns structured output. Use "native"
            for a small self-hosted model, which is often unreliable at tool
            calling.
        enable_tools: Whether the model may call `test_remediation` and
            `get_config_section`. Small models sometimes cannot answer at all
            while tools are offered; turning them off loses the check-your-work
            loop but keeps the run viable.

    Returns:
        An agent whose output is an `AIPlanResponse` already checked against
        hier-config.

    """
    # The cache goes outermost so a hit never reaches the limiter. Wrapping the
    # other way round charges budget before the cache is consulted, which
    # throttles a fleet run on requests that never leave the process.
    wrapped: Model | str = model
    if rate_limiter is not None:
        wrapped = RateLimitedModel(wrapped, rate_limiter)
    if cache is not None:
        wrapped = CachedModel(wrapped, cache)

    # The prompt describes the tools the agent actually has. Telling a model to
    # call `test_remediation` when it was given no tools is the confusion
    # `enable_tools=False` exists to avoid.
    tools = build_tools(retriever) if enable_tools else []
    instructions = SYSTEM_PROMPT
    if tools:
        instructions = f"{instructions}\n{TOOL_INSTRUCTIONS}"
    if driver is not None:
        instructions = f"{instructions}\n{describe_driver(driver)}\n"

    agent: Agent[RemediationDeps, AIPlanResponse] = Agent(
        wrapped,
        output_type=output_spec(output_mode),
        deps_type=RemediationDeps,
        instructions=instructions,
        model_settings=settings,
        tools=tools,
        retries=retries,
        max_concurrency=max_concurrency,
    )
    agent.output_validator(validate_plan)
    return agent
