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


async def search_knowledge(
    ctx: RunContext[RemediationDeps],
    query: str,
) -> str:
    """Look up documentation and past changes relevant to this remediation.

    Args:
        ctx: The run context carrying the retriever and the configs.
        query: What to look for, phrased as the question you want answered.
            "resequence an extended ACL without dropping traffic" retrieves
            better than "ACL".

    Returns:
        Relevant snippets, or a note saying nothing was found.

    """
    retriever = ctx.deps.retriever
    if retriever is None:
        return "No knowledge source is configured for this run."

    platform = ctx.deps.platform
    if platform is None:
        return (
            "The platform for this run could not be identified, so no lookup was made."
        )

    try:
        snippets = await retriever.search(query, platform=platform)
    # A retrieval failure must not sink the run. The model can still answer
    # without context, and saying so is better than raising.
    except Exception as exc:  # ruff: ignore[blind-except]  # pylint: disable=broad-exception-caught
        return f"The knowledge lookup failed, so answer without it: {exc}"

    if not snippets:
        return f"Nothing found for {query!r}."

    body = "\n\n".join(f"- {snippet}" for snippet in snippets)
    return f"Found for {query!r}:\n\n{body}"


def build_tools(retriever: Retriever | None = None) -> list[Tool[RemediationDeps]]:
    """Return the tools the agent should be given.

    Tools are assembled into a list rather than registered with decorators so
    that retrieval-backed tools appear only when a retriever is present. A tool
    the model cannot use should never reach its tool list: it spends tokens and
    invites calls that can only fail.
    """
    tools: list[Tool[RemediationDeps]] = [
        Tool(test_remediation, takes_ctx=True),
        Tool(get_config_section, takes_ctx=True),
    ]
    if retriever is not None:
        tools.append(Tool(search_knowledge, takes_ctx=True))
    return tools
