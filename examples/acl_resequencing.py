"""Resequence an access list by describing the rule, not by coding it.

hier-config's custom-workflows guide handles this by hand: build an HConfig,
insert a temporary `1 permit ip any any`, walk the default remediation rounding
each `no <seq>` to a new number, then `no 1` to clean up. That is real code to
write, test, and maintain for every edge case of this shape.

Here the same requirement is written as a rule description. The model proposes
the commands, and the plan is applied and re-diffed before it is returned, so a
plan that does not produce the intended access list is rejected rather than
handed back.

    poetry run python examples/acl_resequencing.py qwen2.5-coder:7b

Use a capable model. Resequencing needs the model to work out that an entry
cannot be renumbered in place; small local models often cannot, and will
exhaust their retries instead of returning something wrong.
"""

import asyncio
import sys

from hier_config import HConfig, Platform, WorkflowRemediation
from hier_config.models import MatchRule
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from hier_config_ai import (
    AIRemediationExample,
    AIRemediationRule,
    AIWorkflowRemediation,
)

MODEL_NAME = sys.argv[1] if len(sys.argv) > 1 else "qwen2.5-coder:7b"

model = OpenAIChatModel(
    MODEL_NAME,
    provider=OpenAIProvider(base_url="http://localhost:11434/v1", api_key="ollama"),
)

running = HConfig.from_text(
    Platform.CISCO_IOS,
    "ip access-list extended TEST\n 12 permit ip 10.0.0.0 0.0.0.7 any\n",
)
intended = HConfig.from_text(
    Platform.CISCO_IOS,
    "ip access-list extended TEST\n"
    " 10 permit ip 10.0.1.0 0.0.0.255 any\n"
    " 20 permit ip 10.0.0.0 0.0.0.7 any\n",
)

# Everything the custom workflow encodes in Python is stated here instead.
RULE = AIRemediationRule(
    description=(
        "Rewrite the access list so its entries end up with the intended "
        "sequence numbers using the command:\n"
        "ip access-list resequence <acl_name> 10 10\n"
        "An entry cannot be renumbered in place: remove the old one with "
        "'no <seq>', then add it back at its new number.\n"
        "The list must never deny live traffic while it is being rewritten. "
        "Add '1 permit ip any any' as the first command, and remove it with "
        "'no 1' as the last."
    ),
    lineage=(MatchRule(startswith="ip access-list"),),
    example=AIRemediationExample(
        running_config="ip access-list extended EXAMPLE\n 15 permit ip any any",
        remediation_config=(
            "ip access-list resequence TEST 10 10\n"
            "ip access-list extended EXAMPLE\n"
            "  1 permit ip any any\n"
            "  no 15\n"
            "  10 permit ip 192.0.2.0 0.0.0.255 any\n"
            "  20 permit ip any any\n"
            "  no 1"
        ),
    ),
)

workflow = AIWorkflowRemediation(running, intended)
workflow.set_model(
    model,
    settings={"temperature": 0.0, "timeout": 180.0},
    output_mode="native",
)
workflow.add_rule(RULE)


async def main() -> None:
    """Show the deterministic remediation, then the model's."""
    deterministic = WorkflowRemediation(running, intended).remediation_config
    print("hier-config on its own:")
    for line in deterministic.to_lines():
        print(f"   {line}")
    print("   ^ correct end state, but it denies traffic between the removal")
    print("     and the re-add, which is why the custom workflow exists.\n")

    try:
        remediation = await workflow.aai_remediation_config()
    # An example should report a failure plainly rather than traceback.
    except Exception as exc:  # ruff: ignore[blind-except]  # pylint: disable=broad-exception-caught
        print(f"FAILED: {type(exc).__name__}: {exc}")
        print("Try a more capable model; this task defeats small ones.")
        return

    print(f"hier-config-ai with {MODEL_NAME} (validated to converge):")
    for line in remediation.to_lines():
        print(f"   {line}")


asyncio.run(main())
