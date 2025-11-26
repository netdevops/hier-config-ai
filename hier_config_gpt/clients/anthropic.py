from anthropic import Anthropic
from anthropic.types import Message

from .models import GPTClient, GPTPlanResponse
from .utils import parse_plan_payload, retry_with_backoff


class ClaudeGPTClient(GPTClient):
    def __init__(
        self,
        api_key: str,
        model: str = "claude-3-opus-20240229",
        temp: float = 0,
        max_tokens: int = 1024,
    ) -> None:
        """Anthropic GPT Client for generating remediation plans."""
        super().__init__()
        self.client = Anthropic(api_key=api_key)
        self.model = model
        self.temp = temp
        self.max_tokens = max_tokens

    @staticmethod
    def process_response(response: Message) -> list[str]:
        """Extract and clean the response content, returning just the plan."""
        payload = parse_plan_payload(response.content)
        return payload.get("plan", [])

    def chat(self, prompt: str) -> str:
        """Interact with Claude textually."""
        response = self.client.messages.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=self.max_tokens,
            temperature=self.temp,
        )

        return response.content[0].text if response.content else "No content available."

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
