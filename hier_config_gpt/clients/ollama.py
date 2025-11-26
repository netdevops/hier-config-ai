import json
from typing import Dict, Any

import ollama

from .models import GPTClient, GPTPlanResponse


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
        """Extract and clean the response content, returning it as a list."""
        content = response.get("message", {}).get("content") if response else None

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
            response = self.client.chat(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                options={"num_predict": self.max_tokens, "temperature": self.temp},
            )

            return GPTPlanResponse(plan=self.process_response(response))
        except Exception as e:
            return GPTPlanResponse(plan=[f"Error generating plan: {str(e)}"])
