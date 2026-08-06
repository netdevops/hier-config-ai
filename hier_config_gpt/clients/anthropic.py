from typing import TYPE_CHECKING

from anthropic import Anthropic

from .models import GPTClient, GPTPlanResponse
from .utils import parse_plan_commands, retry_with_backoff

if TYPE_CHECKING:
    from anthropic.types import Message


class ClaudeGPTClient(GPTClient):
    """Anthropic-backed GPT client for generating remediation plans."""

    def __init__(
        self,
        api_key: str,
        model: str = "claude-3-5-sonnet-20241022",
        temp: float = 0.0,
        max_tokens: int = 1024,
        timeout: float = 60.0,
    ) -> None:
        """Anthropic Claude Client for generating remediation plans.

        Args:
            api_key: Anthropic API key for authentication.
            model: Model identifier (default: claude-3-5-sonnet-20241022).
                   Other options: claude-3-5-haiku-20241022, claude-3-opus-20240229.
            temp: Temperature for response randomness (0.0-1.0, default: 0.0).
            max_tokens: Maximum tokens in the response (default: 1024).
            timeout: Request timeout in seconds (default: 60.0).

        """
        super().__init__()
        self.client = Anthropic(api_key=api_key, timeout=timeout)
        self.model = model
        self.temp = temp
        self.max_tokens = max_tokens
        self.timeout = timeout

    @staticmethod
    def process_response(response: "Message") -> list[str]:
        """Extract and clean the response content, returning just the plan."""
        return parse_plan_commands(response.content)

    def chat(self, prompt: str) -> str:
        """Interact with Claude textually."""
        response = self.client.messages.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=self.max_tokens,
            temperature=self.temp,
        )

        if not response.content:
            return "No content available."

        content_block = response.content[0]
        text: object = getattr(content_block, "text", None)
        return str(text) if text is not None else "No content available."

    def generate_plan(self, prompt: str) -> GPTPlanResponse:
        """Generate remediation plan from prompt using Anthropic's Claude model."""
        response = retry_with_backoff(
            lambda: self.client.messages.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=self.max_tokens,
                temperature=self.temp,
            )
        )

        plan = self.process_response(response)
        metadata = {
            "provider": "anthropic",
            "model": response.model,
            "usage": response.usage.model_dump() if response.usage else {},
        }
        return GPTPlanResponse(plan=plan, metadata=metadata)
