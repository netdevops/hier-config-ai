from openai import OpenAI
from openai.types.chat import ChatCompletion

from .models import GPTClient, GPTPlanResponse
from .utils import parse_plan_payload, retry_with_backoff


class ChatGPTClient(GPTClient):
    def __init__(
        self, api_key: str, model: str = "gpt-4", temp: int = 0, max_tokens: int = 1000
    ) -> None:
        """OpenAI GPT Client for generating remediation plans."""
        super().__init__()
        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.temp = temp
        self.max_tokens = max_tokens

    @staticmethod
    def process_response(response: ChatCompletion) -> GPTPlanResponse:
        """Extract and clean the response content, returning it as a list."""
        message = response.choices[0].message
        payload = parse_plan_payload(message.content)
        metadata = {
            "provider": "openai",
            "model": response.model,
            "usage": response.usage.model_dump() if response.usage else {},
        }
        metadata.update(payload.get("metadata", {}))

        return GPTPlanResponse(plan=payload.get("plan", []), metadata=metadata)

    def chat(self, prompt: str) -> str:
        """Interact with ChatGPT textually."""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=self.max_tokens,
            temperature=self.temp,
        )

        return response.choices[0].message.content or "Not content available"

    def generate_plan(self, prompt: str) -> GPTPlanResponse:
        """Generate remediation plan from prompt using OpenAI's GPT chat model."""
        response = retry_with_backoff(
            lambda: self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "Return only valid JSON following the schema {\"plan\": [\"command\"]}.",
                    },
                    {"role": "user", "content": prompt},
                ],
                max_tokens=self.max_tokens,
                temperature=self.temp,
                response_format={"type": "json_object"},
            )
        )

        return self.process_response(response)
