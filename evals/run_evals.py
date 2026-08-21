"""Run the remediation evaluation against a real model.

This calls a live provider and costs money, so it is deliberately not part of
the blocking CI job.

    poetry install --with dev,evals --all-extras
    poetry run python evals/run_evals.py --model anthropic:claude-sonnet-4-5

Compare runs before and after a change to a prompt, a model, or the validation
loop. The score that matters is `Converges`: whether the plan, once applied,
actually produces the intended configuration.
"""

from __future__ import annotations

import argparse
import asyncio
from typing import TYPE_CHECKING

from evals.dataset import RemediationTask, build_dataset
from hier_config_ai.workflows import AIWorkflowRemediation

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable


def make_runner(model: str) -> Callable[[RemediationTask], Awaitable[list[str]]]:
    """Return a coroutine that produces a plan for one task.

    The task goes through `AIWorkflowRemediation`, the same path callers use.
    Rebuilding the prompt and agent here instead would score code the library
    does not ship, and a change to the real prompt would not move the number.
    """

    async def run(task: RemediationTask) -> list[str]:
        running, generated = task.configs()
        workflow = AIWorkflowRemediation(running, generated)
        workflow.set_model(model)
        workflow.add_rule(task.rule)
        remediation = await workflow.aai_remediation_config()
        return list(remediation.to_lines())

    return run


def main() -> None:
    """Parse arguments and run the evaluation."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--model",
        default="anthropic:claude-sonnet-4-5",
        help="PydanticAI model name to evaluate.",
    )
    args = parser.parse_args()

    dataset = build_dataset()
    report = asyncio.run(dataset.evaluate(make_runner(args.model)))
    report.print(include_input=False, include_output=True)


if __name__ == "__main__":
    main()
