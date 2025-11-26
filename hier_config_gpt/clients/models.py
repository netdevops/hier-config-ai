from abc import ABC, abstractmethod

from pydantic import BaseModel, field_validator


class GPTPlanResponse(BaseModel):
    """Pydantic model describing the remediation plan returned by GPT clients."""

    plan: list[str]

    @field_validator("plan")
    @classmethod
    def strip_and_filter_plan(cls, plan: list[str]) -> list[str]:
        """Ensure plan commands are clean strings without empty entries."""

        filtered_plan = [str(command).strip("\n") for command in plan if str(command).strip()]
        return filtered_plan


class GPTClient(ABC):
    """Abstract base class for GPT client implementation."""

    @abstractmethod
    def chat(self, prompt: str) -> str:
        """Send a prompt to a GPT and recieve a textual response."""

    @abstractmethod
    def generate_plan(self, prompt: str) -> GPTPlanResponse:
        """Generate remediation plan from prompt."""
