from typing import TYPE_CHECKING

from openai import OpenAI

from .models import GPTClient, GPTPlanResponse
from .utils import parse_plan_commands, retry_with_backoff

if TYPE_CHECKING:
    from openai.types.chat import ChatCompletion


class ChatGPTClient(GPTClient):
    """OpenAI-backed GPT client for generating remediation plans."""

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o",
        temp: float = 0.0,
        max_tokens: int = 1000,
        timeout: float = 60.0,
    ) -> None:
        """OpenAI GPT Client for generating remediation plans.

        Args:
            api_key: OpenAI API key for authentication.
            model: Model identifier (default: gpt-4o). Other options: gpt-4o-mini, gpt-4-turbo.
            temp: Temperature for response randomness (0.0-2.0, default: 0.0).
            max_tokens: Maximum tokens in the response (default: 1000).
            timeout: Request timeout in seconds (default: 60.0).

        """
        super().__init__()
        self.client = OpenAI(api_key=api_key, timeout=timeout)
        self.model = model
        self.temp = temp
        self.max_tokens = max_tokens
        self.timeout = timeout

    @staticmethod
    def process_response(response: "ChatCompletion") -> list[str]:
        """Extract and clean the response content, returning just the plan."""
        message = response.choices[0].message
        return parse_plan_commands(message.content)

    def chat(self, prompt: str) -> str:
        """Interact with ChatGPT textually."""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=self.max_tokens,
            temperature=self.temp,
        )

        return response.choices[0].message.content or "No content available"

    def generate_plan(self, prompt: str) -> GPTPlanResponse:
        """Generate remediation plan from prompt using OpenAI's GPT chat model."""
        response = retry_with_backoff(
            lambda: self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=self.max_tokens,
                temperature=self.temp,
            )
        )

        plan = self.process_response(response)
        metadata = {
            "provider": "openai",
            "model": response.model,
            "usage": response.usage.model_dump() if response.usage else {},
        }
        return GPTPlanResponse(plan=plan, metadata=metadata)
