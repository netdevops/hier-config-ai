"""Tools the agent can call while it builds a remediation plan.

These turn plan generation from a single blind guess into a loop the model can
close by itself: it proposes commands, sees what they would actually do to the
device, and corrects course before returning an answer.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

# PydanticAI calls get_type_hints() on every tool when it builds the tool
# schema, so these annotations must resolve at runtime. Moving them into a
# TYPE_CHECKING block raises NameError when the agent is constructed.
from hier_config.models import MatchRule  # ruff: ignore[typing-only-third-party-import]
from pydantic_ai import RunContext, Tool

from .deps import RemediationDeps  # ruff: ignore[typing-only-first-party-import]
from .validation import format_difference, remaining_difference

if TYPE_CHECKING:
    from .deps import Retriever


def test_remediation(
    ctx: RunContext[RemediationDeps],
    commands: list[str],
) -> str:
    """Check what a candidate list of commands would do to the device.

    Args:
        ctx: The run context carrying the running and generated configs.
        commands: Candidate remediation commands, indented with spaces to show
            the command hierarchy.

    Returns:
        A report saying whether the commands produce the intended
        configuration, and if not, a unified diff of what is still wrong.
        Lines marked '+' are missing; lines marked '-' should not be there.

    """
    if not commands:
        return "No commands supplied, so nothing was tested."

    try:
        missing, unwanted = remaining_difference(ctx.deps, commands)
    # A driver failure is information the model can act on, so it is
    # reported back rather than raised.
    except Exception as exc:  # ruff: ignore[blind-except]  # pylint: disable=broad-exception-caught
        return f"Those commands are not valid configuration for this platform: {exc}"

    if not missing and not unwanted:
        return "These commands produce the intended configuration."

    return (
        "These commands do not yet produce the intended configuration.\n\n"
        + format_difference(missing, unwanted)
    )


def get_config_section(
    ctx: RunContext[RemediationDeps],
    lineage: tuple[MatchRule, ...],
) -> str:
    """Fetch a further section of the running and generated configs.

    Args:
        ctx: The run context carrying the running and generated configs.
        lineage: Match rules selecting the section to fetch.

    Returns:
        The matching running and generated config sections, or a note saying
        the lineage matched nothing.

    """
    running = ctx.deps.whole_running_config.get_children_deep(lineage)
    generated = ctx.deps.whole_generated_config.get_children_deep(lineage)

    running_text = "\n".join(str(line) for line in running)
    generated_text = "\n".join(str(line) for line in generated)

    if not running_text and not generated_text:
        return "That lineage matched nothing in either config."

    return (
        f"Running config:\n{running_text or '(empty)'}\n\n"
        f"Generated config:\n{generated_text or '(empty)'}"
    )


def build_tools(retriever: Retriever | None = None) -> list[Tool[RemediationDeps]]:
    """Return the tools the agent should be given.

    Tools are assembled into a list rather than registered with decorators so
    that retrieval-backed tools appear only when a retriever is present. A tool
    the model cannot use should never reach its tool list: it spends tokens and
    invites calls that can only fail.
    """
    del retriever  # 0.3.0 appends `search_knowledge` when this is not None.
    return [
        Tool(test_remediation, takes_ctx=True),
        Tool(get_config_section, takes_ctx=True),
    ]
