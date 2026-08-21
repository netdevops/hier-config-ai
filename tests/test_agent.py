"""Tests for agent construction and the driver-derived prompt."""

from __future__ import annotations

import pytest
from hier_config import Platform, get_hconfig_driver
from hier_config.models import MatchRule, NegationRule, NegationStrategy

from hier_config_ai.agent import (
    SYSTEM_PROMPT,
    build_agent,
    describe_driver,
    negation_bullet,
    render_match_rules,
)
from hier_config_ai.cache import ResponseCache
from hier_config_ai.model_wrappers import CachedModel, RateLimitedModel
from hier_config_ai.rate_limiter import RateLimiter
from tests.conftest import CORRECT_PLAN, scripted_model


def test_driver_description_states_the_real_indent_width() -> None:
    """The indent width comes from the driver, not from a hardcoded guess.

    Cisco IOS indents by two, so a prompt asserting four would teach the model
    to produce config the same driver then parses differently.
    """
    described = describe_driver(get_hconfig_driver(Platform.CISCO_IOS))
    assert "by 2 spaces" in described


def test_driver_description_lists_section_exits() -> None:
    """Platforms with explicit section exits say so."""
    described = describe_driver(get_hconfig_driver(Platform.CISCO_IOS))
    assert "exit-address-family" in described


def test_driver_description_lists_replacement_negations() -> None:
    """Commands negated by replacement rather than `no` are called out."""
    described = describe_driver(get_hconfig_driver(Platform.CISCO_IOS))
    assert "logging console debugging" in described


def test_driver_description_lists_idempotent_commands() -> None:
    """Commands that overwrite rather than stack are called out."""
    described = describe_driver(get_hconfig_driver(Platform.CISCO_IOS))
    assert "overwrite the existing value" in described


def test_generic_driver_still_describes_indentation() -> None:
    """A driver with few rules still yields usable guidance."""
    described = describe_driver(get_hconfig_driver(Platform.GENERIC))
    assert "spaces" in described


def test_match_rules_render_as_a_command_path() -> None:
    """A lineage renders as a readable parent/child path."""
    rendered = render_match_rules(
        (MatchRule(startswith="interface "), MatchRule(startswith="ip address "))
    )
    assert rendered == "interface  > ip address "


def test_regex_match_rules_keep_their_pattern() -> None:
    """A regex rule shows its pattern rather than collapsing to a wildcard.

    Rendering these as `*` discarded real information: several drivers carry
    regex rules, and the model was shown a bare wildcard for each.
    """
    assert render_match_rules((MatchRule(re_search="^x"),)) == "/^x/"


def test_driver_rules_are_added_to_the_prompt() -> None:
    """Passing a driver extends the system prompt with its rules."""
    agent = build_agent(
        scripted_model(CORRECT_PLAN),
        driver=get_hconfig_driver(Platform.CISCO_IOS),
    )
    assert agent is not None


def test_cache_wraps_the_model() -> None:
    """Supplying a cache puts a CachedModel in front of the provider."""
    cache = ResponseCache(enabled=False)
    agent = build_agent(scripted_model(CORRECT_PLAN), cache=cache)
    assert isinstance(agent.model, CachedModel)


def test_rate_limiter_wraps_the_model() -> None:
    """Supplying a rate limiter wraps the model in a RateLimitedModel."""
    agent = build_agent(
        scripted_model(CORRECT_PLAN),
        rate_limiter=RateLimiter(10, 60.0),
    )
    assert isinstance(agent.model, RateLimitedModel)


def test_cache_sits_outside_rate_limiting() -> None:
    """The cache is consulted before the limiter, so hits cost no budget."""
    agent = build_agent(
        scripted_model(CORRECT_PLAN),
        cache=ResponseCache(enabled=False),
        rate_limiter=RateLimiter(10, 60.0),
    )
    assert isinstance(agent.model, CachedModel)
    assert isinstance(agent.model.wrapped, RateLimitedModel)


def test_system_prompt_points_the_model_at_its_tools() -> None:
    """The prompt tells the model to verify before answering."""
    assert "test_remediation" in SYSTEM_PROMPT
    assert "Never use tab\ncharacters" in SYSTEM_PROMPT


@pytest.mark.parametrize(
    ("strategy", "expected"),
    (
        (NegationStrategy.REPLACE, "writing"),
        (NegationStrategy.REGEX_SUB, "replacing"),
        (NegationStrategy.DEFAULT, "default negation"),
    ),
)
def test_every_negation_strategy_is_described(
    strategy: NegationStrategy,
    expected: str,
) -> None:
    """All three negation strategies reach the prompt.

    Filtering on whether `use` was set silently dropped the DEFAULT and
    REGEX_SUB strategies, so Arista showed no negation rules at all and NXOS
    showed three of seven.
    """
    rule = NegationRule(
        match_rules=(MatchRule(startswith="logging console "),),
        strategy=strategy,
        use="logging console debugging",
        search="a",
        replace="b",
    )
    assert expected in negation_bullet(rule)


def test_dropped_driver_rules_are_reported() -> None:
    """Truncating the rule list says how much was left out.

    NXOS carries 56 idempotent commands against a cap of 12. Cutting silently
    left the model believing it had seen them all.
    """
    described = describe_driver(get_hconfig_driver(Platform.CISCO_NXOS))
    assert "more not shown" in described


def test_platform_prefixes_reach_the_prompt() -> None:
    """Junos is told about `set` and `delete`, not Cisco's `no`."""
    described = describe_driver(get_hconfig_driver(Platform.JUNIPER_JUNOS))
    assert "`delete`" in described
    assert "`set`" in described
