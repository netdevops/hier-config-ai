"""Run hier-config-ai against a local Ollama model.

    ollama pull llama3.2:3b
    poetry run python examples/ollama_quickstart.py llama3.2:3b

Two settings decide whether a small local model works at all.
`output_mode="native"`, because these models are unreliable at tool
calling and the default mode asks for structured output through one. And
`temperature: 0.0`, because Ollama defaults to 0.8, at which the same
prompt succeeds on one run and fails the next.
"""

import asyncio
import sys

from hier_config import HConfig, Platform
from hier_config.models import MatchRule
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from hier_config_ai import (
    AIRemediationExample,
    AIRemediationRule,
    AIWorkflowRemediation,
    build_agent,
)

MODEL_NAME = sys.argv[1] if len(sys.argv) > 1 else "llama3.2:3b"

# Ollama speaks the OpenAI-compatible API, so it goes through OpenAIChatModel.
# The api_key is a required placeholder; Ollama ignores it.
model = OpenAIChatModel(
    MODEL_NAME,
    provider=OpenAIProvider(base_url="http://localhost:11434/v1", api_key="ollama"),
)

running = HConfig.from_text(
    Platform.CISCO_IOS,
    "ip access-list extended TEST\n  12 permit ip 10.0.0.0 0.0.0.7 any",
)
intended = HConfig.from_text(
    Platform.CISCO_IOS,
    "ip access-list extended TEST\n  10 permit ip 10.0.1.0 0.0.0.255 any\n  20 permit ip 10.0.0.0 0.0.0.7 any",
)

workflow = AIWorkflowRemediation(running, intended)
workflow.set_agent(
    build_agent(
        model,
        driver=running.driver,
        settings={"temperature": 0.0},
        output_mode="native",
    )
)
workflow.add_rule(
    AIRemediationRule(
        description=(
            "Bring the access-list into line with the intended configuration: "
            "- Use the `ip access-list resequence` command to resequence the sequence numbers"
            "- Enable all traffice with `permit ip any any` with sequence 1"
            "- At the end, remove sequence number 1"
        ),
        lineage=(MatchRule(startswith="ip access-list"),),
        example=AIRemediationExample(
            running_config=(
                "ip access-list extended TEST\n  14 permit ip 10.0.0.0 0.0.0.7 any"
            ),
            remediation_config=(
                "ip access-list resequence TEST 10 10\n"
                "ip access-list extended TEST\n"
                "  1 permit ip any any\n"
                "  no 10\n"
                "  10 permit ip 10.0.2.0 0.0.0.255 any\n"
                "  20 permit ip 10.0.1.0 0.0.0.7 any\n"
                "  no 1"
            ),
        ),
    )
)


async def main() -> None:
    """Generate a remediation plan and report the result."""
    print(f"model: {MODEL_NAME}")
    print(f"running:  {list(running.to_lines())}")
    print(f"intended: {list(intended.to_lines())}\n")
    try:
        remediation = await workflow.aai_remediation_config()
    # An example should report any failure plainly rather than traceback.
    except Exception as exc:  # ruff: ignore[blind-except]  # pylint: disable=broad-exception-caught
        print(f"FAILED: {type(exc).__name__}: {exc}")
        return

    print("PLAN (validated -- it provably converges):")
    for line in remediation.to_lines():
        print(f"   {line}")
    for usage in workflow.usage:
        print(
            f"\ntokens: in={usage.input_tokens} out={usage.output_tokens} "
            f"requests={usage.requests}"
        )


asyncio.run(main())
