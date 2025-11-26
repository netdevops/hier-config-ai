from typing import Dict, Any

import ollama

from .models import GPTClient, GPTPlanResponse
from .utils import parse_plan_payload, retry_with_backoff


class OllamaGPTClient(GPTClient):
    def __init__(
        self,
        host: str = "http://localhost:11434",
        model: str = "llama3",
        temp: float = 0,
        max_tokens: int = 1024,
    ) -> None:
        """Ollama GPT Client for generating remediation plans."""
        super().__init__()
        self.client = ollama.Client(host=host)
        self.model = model
        self.temp = temp
        self.max_tokens = max_tokens

    @staticmethod
    def process_response(response: Dict[str, Any]) -> GPTPlanResponse:
        """Extract and clean the response content, returning it as a list."""
        payload = parse_plan_payload(response.get("message", {}).get("content"))
        metadata = {
            "provider": "ollama",
            "model": response.get("model", ""),
            "total_duration": response.get("total_duration"),
        }
        metadata.update(payload.get("metadata", {}))

        return GPTPlanResponse(plan=payload.get("plan", []), metadata=metadata)

    def chat(self, prompt: str) -> str:
        """Interact with Ollama textually."""
        try:
            response = self.client.chat(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                options={"num_predict": self.max_tokens, "temperature": self.temp},
            )

            return response.get("message", {}).get("content", "No content available.")
        except Exception as e:
            return f"Error communicating with Ollama API: {str(e)}"

    def generate_plan(self, prompt: str) -> GPTPlanResponse:
        """Generate remediation plan from prompt using Ollama models."""
        response = retry_with_backoff(
            lambda: self.client.chat(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "Return only valid JSON following the schema {\"plan\": [\"command\"]}.",
                    },
                    {"role": "user", "content": prompt},
                ],
                options={"num_predict": self.max_tokens, "temperature": self.temp},
            )
        )

        return self.process_response(response)
