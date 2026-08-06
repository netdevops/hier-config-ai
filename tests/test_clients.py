"""Tests for the provider-specific GPT clients."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast
from unittest.mock import MagicMock, patch

import ollama
import pytest

from hier_config_gpt.clients.anthropic import ClaudeGPTClient
from hier_config_gpt.clients.models import GPTPlanResponse
from hier_config_gpt.clients.ollama import OllamaGPTClient
from hier_config_gpt.clients.openai import ChatGPTClient

if TYPE_CHECKING:
    from anthropic.types import Message
    from openai.types.chat import ChatCompletion


def _openai_response(content: str) -> MagicMock:
    """Build a mocked OpenAI chat completion response."""
    response = MagicMock()
    response.choices = [MagicMock(message=MagicMock(content=content))]
    response.model = "gpt-4o"
    response.usage = None
    return response


def _anthropic_response(text: str) -> MagicMock:
    """Build a mocked Anthropic message response."""
    content_block = MagicMock()
    content_block.text = text
    response = MagicMock()
    response.content = [content_block]
    response.model = "claude-3-5-sonnet-20241022"
    response.usage = None
    return response


def _ollama_response(content: str) -> ollama.ChatResponse:
    """Build a real ollama ChatResponse for mocking the transport."""
    return ollama.ChatResponse(
        model="llama3",
        message=ollama.Message(role="assistant", content=content),
    )


def test_gpt_plan_response_filters_empty_entries() -> None:
    """GPTPlanResponse should strip newlines and drop empty plan entries."""
    response = GPTPlanResponse(
        plan=["command1\n", "  ", "command2", "", " command3 \n"]
    )

    assert response.plan == ["command1", "command2", " command3 "]


def test_chatgpt_client_init() -> None:
    with patch("hier_config_gpt.clients.openai.OpenAI") as mock_openai_class:
        client = ChatGPTClient(api_key="test-key", model="gpt-4")

    assert client.model == "gpt-4"
    assert client.max_tokens == 1000
    assert client.temp == 0
    mock_openai_class.assert_called_once_with(api_key="test-key", timeout=60.0)


def test_chatgpt_client_chat() -> None:
    with patch("hier_config_gpt.clients.openai.OpenAI") as mock_openai_class:
        mock_openai_class.return_value.chat.completions.create.return_value = (
            _openai_response("Test response")
        )
        client = ChatGPTClient(api_key="test-key")
        result = client.chat("Test prompt")

    assert result == "Test response"
    mock_openai_class.return_value.chat.completions.create.assert_called_once_with(
        model="gpt-4o",
        messages=[{"role": "user", "content": "Test prompt"}],
        max_tokens=1000,
        temperature=0,
    )


def test_chatgpt_client_chat_no_content() -> None:
    with patch("hier_config_gpt.clients.openai.OpenAI") as mock_openai_class:
        mock_openai_class.return_value.chat.completions.create.return_value = (
            _openai_response("")
        )
        client = ChatGPTClient(api_key="test-key")
        result = client.chat("Test prompt")

    assert result == "No content available"


def test_chatgpt_client_generate_plan() -> None:
    with patch("hier_config_gpt.clients.openai.OpenAI") as mock_openai_class:
        mock_openai_class.return_value.chat.completions.create.return_value = (
            _openai_response('Here is the plan: ["command1", "command2"]')
        )
        client = ChatGPTClient(api_key="test-key")
        result = client.generate_plan("Test prompt")

    assert result.plan == ["command1", "command2"]
    assert result.metadata["provider"] == "openai"
    assert result.metadata["usage"] == {}


def test_chatgpt_client_process_response() -> None:
    response = _openai_response(
        'Some text before ["command1", "command2", "command3"] some text after'
    )

    result = ChatGPTClient.process_response(cast("ChatCompletion", response))

    assert result == ["command1", "command2", "command3"]


def test_claude_client_init() -> None:
    with patch("hier_config_gpt.clients.anthropic.Anthropic") as mock_anthropic_class:
        client = ClaudeGPTClient(api_key="test-key", model="claude-3-opus-20240229")

    assert client.model == "claude-3-opus-20240229"
    assert client.max_tokens == 1024
    assert client.temp == 0
    mock_anthropic_class.assert_called_once_with(api_key="test-key", timeout=60.0)


def test_claude_client_chat() -> None:
    with patch("hier_config_gpt.clients.anthropic.Anthropic") as mock_anthropic_class:
        mock_anthropic_class.return_value.messages.create.return_value = (
            _anthropic_response("Test response")
        )
        client = ClaudeGPTClient(api_key="test-key")
        result = client.chat("Test prompt")

    assert result == "Test response"
    mock_anthropic_class.return_value.messages.create.assert_called_once_with(
        model="claude-3-5-sonnet-20241022",
        messages=[{"role": "user", "content": "Test prompt"}],
        max_tokens=1024,
        temperature=0,
    )


def test_claude_client_chat_no_content() -> None:
    with patch("hier_config_gpt.clients.anthropic.Anthropic") as mock_anthropic_class:
        response = MagicMock()
        response.content = []
        mock_anthropic_class.return_value.messages.create.return_value = response
        client = ClaudeGPTClient(api_key="test-key")
        result = client.chat("Test prompt")

    assert result == "No content available."


def test_claude_client_generate_plan() -> None:
    with patch("hier_config_gpt.clients.anthropic.Anthropic") as mock_anthropic_class:
        mock_anthropic_class.return_value.messages.create.return_value = (
            _anthropic_response('Here is the plan: ["command1", "command2"]')
        )
        client = ClaudeGPTClient(api_key="test-key")
        result = client.generate_plan("Test prompt")

    assert result.plan == ["command1", "command2"]
    assert result.metadata["provider"] == "anthropic"


def test_claude_client_process_response() -> None:
    response = _anthropic_response(
        'Some text before ["command1", "command2", "command3"] some text after'
    )

    result = ClaudeGPTClient.process_response(cast("Message", response))

    assert result == ["command1", "command2", "command3"]


def test_ollama_client_init() -> None:
    with patch("hier_config_gpt.clients.ollama.ollama.Client") as mock_client_class:
        client = OllamaGPTClient(host="http://localhost:12345", model="llama3")

    assert client.model == "llama3"
    assert client.max_tokens == 1024
    assert client.temp == 0
    mock_client_class.assert_called_once_with(
        host="http://localhost:12345", timeout=60.0
    )


def test_ollama_client_chat() -> None:
    with patch("hier_config_gpt.clients.ollama.ollama.Client") as mock_client_class:
        mock_client_class.return_value.chat.return_value = _ollama_response(
            "Test response"
        )
        client = OllamaGPTClient()
        result = client.chat("Test prompt")

    assert result == "Test response"
    mock_client_class.return_value.chat.assert_called_once_with(
        model="llama3.2",
        messages=[{"role": "user", "content": "Test prompt"}],
        options={"num_predict": 1024, "temperature": 0.0},
    )


def test_ollama_client_chat_no_content() -> None:
    with patch("hier_config_gpt.clients.ollama.ollama.Client") as mock_client_class:
        mock_client_class.return_value.chat.return_value = _ollama_response("")
        client = OllamaGPTClient()
        result = client.chat("Test prompt")

    assert result == "No content available."


def test_ollama_client_chat_exception_handling() -> None:
    with patch("hier_config_gpt.clients.ollama.ollama.Client") as mock_client_class:
        mock_client_class.return_value.chat.side_effect = RuntimeError(
            "Connection error"
        )
        client = OllamaGPTClient()
        result = client.chat("Test prompt")

    assert "Error communicating with Ollama API: Connection error" in result


def test_ollama_client_generate_plan() -> None:
    with patch("hier_config_gpt.clients.ollama.ollama.Client") as mock_client_class:
        mock_client_class.return_value.chat.return_value = _ollama_response(
            'Here is the plan: ["command1", "command2"]'
        )
        client = OllamaGPTClient()
        result = client.generate_plan("Test prompt")

    assert result.plan == ["command1", "command2"]
    assert result.metadata["provider"] == "ollama"
    assert result.metadata["model"] == "llama3"


def test_ollama_client_generate_plan_exception_handling() -> None:
    with (
        patch("hier_config_gpt.clients.ollama.ollama.Client") as mock_client_class,
        patch("hier_config_gpt.clients.utils.time.sleep") as mock_sleep,
    ):
        mock_client_class.return_value.chat.side_effect = RuntimeError(
            "Connection error"
        )
        client = OllamaGPTClient()
        with pytest.raises(RuntimeError, match="Connection error"):
            client.generate_plan("Test prompt")

    # The default retry policy retried twice before failing.
    assert mock_sleep.call_count == 2


def test_ollama_client_process_response() -> None:
    response = _ollama_response(
        'Some text before ["command1", "command2", "command3"] some text after'
    )

    result = OllamaGPTClient.process_response(response)

    assert result == ["command1", "command2", "command3"]
