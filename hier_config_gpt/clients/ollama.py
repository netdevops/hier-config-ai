from typing import Dict, Any

import ollama
from typing import Any, Dict

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
    def process_response(response: Dict[str, Any]) -> list[str]:
        """Extract and clean the response content, returning just the plan."""
        payload = parse_plan_payload(response.get("message", {}).get("content"))
        return payload.get("plan", [])

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
        try:
            response = retry_with_backoff(
                lambda: self.client.chat(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    options={"num_predict": self.max_tokens, "temperature": self.temp},
                )
            )
            plan = self.process_response(response)
            metadata = {
                "provider": "ollama",
                "model": response.get("model", ""),
                "total_duration": response.get("total_duration"),
            }
            return GPTPlanResponse(plan=plan, metadata=metadata)
        except Exception as exc:
            return GPTPlanResponse(plan=[f"Error generating plan: {exc}"], metadata={"provider": "ollama"})
