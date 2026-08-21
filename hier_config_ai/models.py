"""Pydantic models describing remediation rules, context, and LLM output."""

from __future__ import annotations

from typing import Any, Literal

# Imported at runtime, not under TYPE_CHECKING: pydantic resolves this
# annotation when it builds the model, so it must be a real module global.
from hier_config.models import MatchRule  # ruff: ignore[typing-only-third-party-import]
from pydantic import BaseModel, Field, field_validator

Confidence = Literal["high", "medium", "low"]


class AIRemediationExample(BaseModel):
    """Example running/remediation config pair used to guide the LLM."""

    running_config: str
    remediation_config: str


class AIRemediationRule(BaseModel):
    """Rule describing a config section to remediate with LLM assistance."""

    description: str
    lineage: tuple[MatchRule, ...]
    example: AIRemediationExample


class AIRemediationContext(BaseModel):
    """Context passed to the LLM when building a remediation prompt."""

    description: str
    running_config: str
    generated_config: str
    example: AIRemediationExample


class AIPlanResponse(BaseModel):
    """Remediation plan returned by the model.

    `plan` carries the commands to apply. The remaining fields exist so an
    operator can judge the plan before applying it, which matters more here
    than in most domains: these commands change live network devices.
    """

    plan: list[str]
    reasoning: str = ""
    confidence: Confidence = "medium"
    commands_requiring_review: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("plan")
    @classmethod
    def strip_and_filter_plan(cls, plan: list[str]) -> list[str]:
        r"""Drop blank commands and trailing newlines, keeping indentation.

        Only `\n` is stripped, never leading spaces. Indentation carries the
        command hierarchy, so stripping it would flatten child commands into
        their parent's scope.
        """
        return [str(command).strip("\n") for command in plan if str(command).strip()]
