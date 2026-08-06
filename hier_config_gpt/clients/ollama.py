import ollama

from .models import GPTClient, GPTPlanResponse
from .utils import parse_plan_commands, retry_with_backoff


class OllamaGPTClient(GPTClient):
    """Ollama-backed GPT client for self-hosted model inference."""

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
    def process_response(response: ollama.ChatResponse) -> list[str]:
        """Extract and clean the response content, returning just the plan."""
        return parse_plan_commands(response.message.content)

    def _chat(self, prompt: str) -> ollama.ChatResponse:
        """Send a chat request to the Ollama server."""
        # The ollama SDK's `tools` parameter is typed with a bare Callable,
        # which pyright strict reports as a partially unknown overload.
        return self.client.chat(  # pyright: ignore[reportUnknownMemberType]
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            options={"num_predict": self.max_tokens, "temperature": self.temp},
        )

    def chat(self, prompt: str) -> str:
        """Interact with Ollama textually."""
        try:
            response = self._chat(prompt)
        # Surface provider errors as text instead of raising to the caller.
        except Exception as exc:  # ruff:ignore[blind-except]  # pylint: disable=broad-exception-caught
            return f"Error communicating with Ollama API: {exc}"

        return response.message.content or "No content available."

    def generate_plan(self, prompt: str) -> GPTPlanResponse:
        """Generate remediation plan from prompt using Ollama models.

        Args:
            prompt: The prompt to send to the Ollama model.

        Returns:
            GPTPlanResponse: The generated plan with metadata.

        """
        response = retry_with_backoff(lambda: self._chat(prompt))

        plan = self.process_response(response)
        metadata = {
            "provider": "ollama",
            "model": response.model or self.model,
            "total_duration": response.total_duration,
            "prompt_eval_count": response.prompt_eval_count,
            "eval_count": response.eval_count,
        }
        return GPTPlanResponse(plan=plan, metadata=metadata)
