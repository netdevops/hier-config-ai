"""Tests for the tools the agent uses to check its own work."""

from __future__ import annotations

from typing import TYPE_CHECKING

from hier_config.models import MatchRule
from pydantic_ai import RunContext
from pydantic_ai.models.test import TestModel
from pydantic_ai.usage import RunUsage

# Imported under an alias: pytest would otherwise collect `test_remediation`
# as a test case rather than treating it as the tool under test.
from hier_config_ai.tools import build_tools, get_config_section
from hier_config_ai.tools import test_remediation as check_remediation
from tests.conftest import (
    CORRECT_PLAN,
    INCOMPLETE_PLAN,
    INTERFACE,
    StubRetriever,
)

if TYPE_CHECKING:
    from hier_config_ai.deps import RemediationDeps


def context(deps: RemediationDeps) -> RunContext[RemediationDeps]:
    """Build a minimal run context carrying `deps`."""
    return RunContext(deps=deps, model=TestModel(), usage=RunUsage())


def test_tool_list_excludes_search_without_a_retriever() -> None:
    """Only the two always-available tools are offered by default.

    A tool the model cannot use should never reach its tool list: it spends
    tokens on the schema and invites calls that can only fail.
    """
    assert [tool.name for tool in build_tools()] == [
        "test_remediation",
        "get_config_section",
    ]


def test_converging_commands_are_reported_as_correct(
    deps: RemediationDeps,
) -> None:
    """The tool confirms commands that reach the intended configuration."""
    assert "produce the intended configuration" in check_remediation(
        context(deps), CORRECT_PLAN
    )


def test_incomplete_commands_report_what_is_missing(
    deps: RemediationDeps,
) -> None:
    """The tool tells the model exactly what its commands failed to do."""
    report = check_remediation(context(deps), INCOMPLETE_PLAN)
    assert "still missing" in report
    assert "ip address 10.0.1.1" in report


def test_no_commands_is_reported_plainly(deps: RemediationDeps) -> None:
    """An empty command list is not treated as success."""
    assert "nothing was tested" in check_remediation(context(deps), [])


def test_invalid_commands_are_reported_not_raised(
    deps: RemediationDeps,
) -> None:
    """A plan the driver rejects becomes advice rather than an exception."""
    report = check_remediation(context(deps), ["\tbad indentation"])
    assert "not valid configuration" in report or "still missing" in report


def test_config_section_returns_both_sides(deps: RemediationDeps) -> None:
    """Fetching a section shows the running and generated config."""
    section = get_config_section(context(deps), (MatchRule(equals=INTERFACE),))
    assert "Running config:" in section
    assert "Generated config:" in section
    assert "shutdown" in section


def test_unmatched_lineage_says_so(deps: RemediationDeps) -> None:
    """A lineage that matches nothing returns a clear message."""
    section = get_config_section(context(deps), (MatchRule(equals="nope"),))
    assert "matched nothing" in section


def test_retriever_reserves_a_place_for_search() -> None:
    """A retriever is accepted now so 0.3.0 can add its tool without rework."""
    assert len(build_tools(StubRetriever())) == 2
