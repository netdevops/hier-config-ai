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
    def process_response(response: Message) -> GPTPlanResponse:
        """Extract and clean the response content, returning it as a list."""
        payload = parse_plan_payload(response.content)
        metadata = {
            "provider": "anthropic",
            "model": response.model,
            "usage": response.usage.model_dump() if response.usage else {},
        }
        metadata.update(payload.get("metadata", {}))

        return GPTPlanResponse(plan=payload.get("plan", []), metadata=metadata)

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
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": "Return only valid JSON following the schema {\"plan\": [\"command\"]}.",
                            },
                            {"type": "text", "text": prompt},
                        ],
                    }
                ],
                max_tokens=self.max_tokens,
                temperature=self.temp,
            )
        )

        return self.process_response(response)
