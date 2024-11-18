import json

from .models import GPTClient

from anthropic import Anthropic


class AnthropicGPTClient(GPTClient):
    def __init__(
        self, api_key: str, model: str = "claude-3-opus-20240229", max_tokens: int = 1024
    ) -> None:
        """Anthropic GPT Client for generating remediation plans."""
        self.client = Anthropic(api_key=api_key)
        self.model = model
        self.max_tokens = max_tokens

    def chat(self, prompt: str) -> str:
        message = self.client.message.creat(
            max_tokens=self.max_tokens,
            message=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            model=self.model,
        )

        return message or "No content available."
