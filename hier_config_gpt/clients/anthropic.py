import json

from anthropic import Anthropic
from anthropic.types import Message

from .models import GPTClient, GPTPlanResponse


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
        """Extract and clean the response content, returning it as a list."""
        content = response.content[0].text if response.content else None

        if content is None:
            return []

        start = content.find("[")
        end = content.rfind("]") + 1
        list_str = content[start:end] if start != -1 and end != -1 else ""

        try:
            return json.loads(list_str) if list_str else []
        except json.JSONDecodeError:
            return []

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
        response = self.client.messages.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=self.max_tokens,
            temperature=self.temp,
        )

        return GPTPlanResponse(plan=self.process_response(response))
