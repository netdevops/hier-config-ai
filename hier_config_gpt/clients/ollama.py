from typing import Any, Dict

import ollama

from .models import GPTClient, GPTPlanResponse
from .utils import parse_plan_payload, retry_with_backoff


class OllamaGPTClient(GPTClient):
    def __init__(
        self,
        host: str = "http://localhost:11434",
        model: str = "llama3.2",
        temp: float = 0.0,
        max_tokens: int = 1024,
        timeout: float = 60.0,
    ) -> None:
        """Ollama GPT Client for self-hosted model inference.

        Args:
            host: Ollama server URL (default: http://localhost:11434).
            model: Model identifier (default: llama3.2). Other options: llama3.1, mistral, etc.
            temp: Temperature for response randomness (0.0-2.0, default: 0.0).
            max_tokens: Maximum tokens in the response (default: 1024).
            timeout: Request timeout in seconds (default: 60.0).
        """
        super().__init__()
        self.client = ollama.Client(host=host, timeout=timeout)
        self.model = model
        self.temp = temp
        self.max_tokens = max_tokens
        self.timeout = timeout

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
        """Generate remediation plan from prompt using Ollama models.

        Args:
            prompt: The prompt to send to the Ollama model.

        Returns:
            GPTPlanResponse: The generated plan with metadata.

        Raises:
            Exception: If the Ollama API call fails or returns invalid data.
        """
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
            "model": response.get("model", self.model),
            "total_duration": response.get("total_duration"),
            "prompt_eval_count": response.get("prompt_eval_count"),
            "eval_count": response.get("eval_count"),
        }
        return GPTPlanResponse(plan=plan, metadata=metadata)
