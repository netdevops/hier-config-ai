from unittest.mock import patch, MagicMock

from hier_config_gpt.clients.openai import ChatGPTClient
from hier_config_gpt.clients.anthropic import ClaudeGPTClient
from hier_config_gpt.clients.ollama import OllamaGPTClient
from hier_config_gpt.clients.models import GPTPlanResponse


class TestChatGPTClient:
    @patch(
        "hier_config_gpt.clients.openai.OpenAI"
    )  # Patch the import path, not the module
    def test_init(self, mock_openai_class):
        """Test ChatGPTClient initialization"""
        client = ChatGPTClient(api_key="test-key", model="gpt-4")

        # Check attributes were set correctly
        assert client.model == "gpt-4"
        assert client.max_tokens == 1000
        assert client.temp == 0

        # Check constructor was called
        mock_openai_class.assert_called_once_with(api_key="test-key")

    @patch("hier_config_gpt.clients.openai.OpenAI")
    def test_chat(self, mock_openai_class):
        """Test ChatGPTClient chat method"""
        # Set up mock response
        mock_message = MagicMock()
        mock_message.content = "Test response"

        mock_choice = MagicMock()
        mock_choice.message = mock_message

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        # Configure the mock chain
        mock_completions = MagicMock()
        mock_completions.create.return_value = mock_response

        mock_chat = MagicMock()
        mock_chat.completions = mock_completions

        mock_client = MagicMock()
        mock_client.chat = mock_chat

        mock_openai_class.return_value = mock_client

        # Create client and call method
        client = ChatGPTClient(api_key="test-key")
        result = client.chat("Test prompt")

        # Verify result
        assert result == "Test response"

        # Verify mock was called with correct parameters
        mock_completions.create.assert_called_once_with(
            model="gpt-4",
            messages=[{"role": "user", "content": "Test prompt"}],
            max_tokens=1000,
            temperature=0,
        )

    @patch("hier_config_gpt.clients.openai.OpenAI")
    def test_generate_plan(self, mock_openai_class):
        """Test ChatGPTClient generate_plan method"""
        # Set up mock response with content that can be parsed as a JSON list
        mock_message = MagicMock()
        mock_message.content = 'Here is the plan: ["command1", "command2"]'

        mock_choice = MagicMock()
        mock_choice.message = mock_message

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        # Configure the mock chain
        mock_completions = MagicMock()
        mock_completions.create.return_value = mock_response

        mock_chat = MagicMock()
        mock_chat.completions = mock_completions

        mock_client = MagicMock()
        mock_client.chat = mock_chat

        mock_openai_class.return_value = mock_client

        # Create client and call method
        client = ChatGPTClient(api_key="test-key")
        result = client.generate_plan("Test prompt")

        # Verify result
        assert result.plan == ["command1", "command2"]

        # Verify mock was called with correct parameters
        mock_completions.create.assert_called_once_with(
            model="gpt-4",
            messages=[{"role": "user", "content": "Test prompt"}],
            max_tokens=1000,
            temperature=0,
        )

    def test_process_response(self):
        """Test ChatGPTClient process_response method"""
        # Create a mock response with JSON content
        mock_message = MagicMock()
        mock_message.content = (
            'Some text before ["command1", "command2", "command3"] some text after'
        )

        mock_choice = MagicMock()
        mock_choice.message = mock_message

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        # Process the response
        result = ChatGPTClient.process_response(mock_response)

        # Verify the result
        assert result == ["command1", "command2", "command3"]


def test_gpt_plan_response_filters_empty_entries():
    """GPTPlanResponse should strip newlines and drop empty plan entries."""

    response = GPTPlanResponse(plan=["command1\n", "  ", "command2", "", " command3 \n"])

    assert response.plan == ["command1", "command2", " command3 "]


class TestClaudeGPTClient:
    @patch("hier_config_gpt.clients.anthropic.Anthropic")
    def test_init(self, mock_anthropic_class):
        """Test ClaudeGPTClient initialization"""
        client = ClaudeGPTClient(api_key="test-key", model="claude-3-opus-20240229")

        # Check attributes were set correctly
        assert client.model == "claude-3-opus-20240229"
        assert client.max_tokens == 1024
        assert client.temp == 0

        # Check constructor was called
        mock_anthropic_class.assert_called_once_with(api_key="test-key")

    @patch("hier_config_gpt.clients.anthropic.Anthropic")
    def test_chat(self, mock_anthropic_class):
        """Test ClaudeGPTClient chat method"""
        # Set up mock content
        mock_content = MagicMock()
        mock_content.text = "Test response"

        # Set up mock response
        mock_response = MagicMock()
        mock_response.content = [mock_content]

        # Configure the mock chain
        mock_messages = MagicMock()
        mock_messages.create.return_value = mock_response

        mock_client = MagicMock()
        mock_client.messages = mock_messages

        mock_anthropic_class.return_value = mock_client

        # Create client and call method
        client = ClaudeGPTClient(api_key="test-key")
        result = client.chat("Test prompt")

        # Verify result
        assert result == "Test response"

        # Verify mock was called with correct parameters
        mock_messages.create.assert_called_once_with(
            model="claude-3-opus-20240229",
            messages=[{"role": "user", "content": "Test prompt"}],
            max_tokens=1024,
            temperature=0,
        )

    @patch("hier_config_gpt.clients.anthropic.Anthropic")
    def test_generate_plan(self, mock_anthropic_class):
        """Test ClaudeGPTClient generate_plan method"""
        # Set up mock content with JSON list
        mock_content = MagicMock()
        mock_content.text = 'Here is the plan: ["command1", "command2"]'

        # Set up mock response
        mock_response = MagicMock()
        mock_response.content = [mock_content]

        # Configure the mock chain
        mock_messages = MagicMock()
        mock_messages.create.return_value = mock_response

        mock_client = MagicMock()
        mock_client.messages = mock_messages

        mock_anthropic_class.return_value = mock_client

        # Create client and call method
        client = ClaudeGPTClient(api_key="test-key")
        result = client.generate_plan("Test prompt")

        # Verify result
        assert result.plan == ["command1", "command2"]

        # Verify mock was called with correct parameters
        mock_messages.create.assert_called_once_with(
            model="claude-3-opus-20240229",
            messages=[{"role": "user", "content": "Test prompt"}],
            max_tokens=1024,
            temperature=0,
        )

    def test_process_response(self):
        """Test ClaudeGPTClient process_response method"""
        # Create mock content
        mock_content = MagicMock()
        mock_content.text = (
            'Some text before ["command1", "command2", "command3"] some text after'
        )

        # Create mock response
        mock_response = MagicMock()
        mock_response.content = [mock_content]

        # Process the response
        result = ClaudeGPTClient.process_response(mock_response)

        # Verify the result
        assert result == ["command1", "command2", "command3"]


class TestOllamaGPTClient:
    @patch("hier_config_gpt.clients.ollama.ollama")
    def test_init(self, mock_ollama):
        """Test OllamaGPTClient initialization"""
        client = OllamaGPTClient(host="http://localhost:12345", model="llama3")

        # Check attributes were set correctly
        assert client.model == "llama3"
        assert client.max_tokens == 1024
        assert client.temp == 0

        # Check client was created correctly
        mock_ollama.Client.assert_called_once_with(host="http://localhost:12345")

    @patch("hier_config_gpt.clients.ollama.ollama")
    def test_chat(self, mock_ollama):
        """Test OllamaGPTClient chat method"""
        # Set up mock response
        mock_response = {"message": {"content": "Test response"}}

        # Configure the mock
        mock_client = MagicMock()
        mock_client.chat.return_value = mock_response

        mock_ollama.Client.return_value = mock_client

        # Create client and call method
        client = OllamaGPTClient()
        result = client.chat("Test prompt")

        # Verify result
        assert result == "Test response"

        # Verify mock was called with correct parameters
        mock_client.chat.assert_called_once_with(
            model="llama3",
            messages=[{"role": "user", "content": "Test prompt"}],
            options={"num_predict": 1024, "temperature": 0},
        )

    @patch("hier_config_gpt.clients.ollama.ollama")
    def test_generate_plan(self, mock_ollama):
        """Test OllamaGPTClient generate_plan method"""
        # Set up mock response with JSON content
        mock_response = {
            "message": {"content": 'Here is the plan: ["command1", "command2"]'}
        }

        # Configure the mock
        mock_client = MagicMock()
        mock_client.chat.return_value = mock_response

        mock_ollama.Client.return_value = mock_client

        # Create client and call method
        client = OllamaGPTClient()
        result = client.generate_plan("Test prompt")

        # Verify result
        assert result.plan == ["command1", "command2"]

        # Verify mock was called with correct parameters
        mock_client.chat.assert_called_once_with(
            model="llama3",
            messages=[{"role": "user", "content": "Test prompt"}],
            options={"num_predict": 1024, "temperature": 0},
        )

    def test_process_response(self):
        """Test OllamaGPTClient process_response method"""
        # Create a mock response
        mock_response = {
            "message": {
                "content": 'Some text before ["command1", "command2", "command3"] some text after'
            }
        }

        # Process the response
        result = OllamaGPTClient.process_response(mock_response)

        # Verify the result
        assert result == ["command1", "command2", "command3"]

    @patch("hier_config_gpt.clients.ollama.ollama")
    def test_chat_exception_handling(self, mock_ollama):
        """Test OllamaGPTClient exception handling in chat method"""
        # Configure the mock to raise an exception
        mock_client = MagicMock()
        mock_client.chat.side_effect = Exception("Connection error")

        mock_ollama.Client.return_value = mock_client

        # Create client and call method
        client = OllamaGPTClient()
        result = client.chat("Test prompt")

        # Verify expectations
        assert "Error communicating with Ollama API: Connection error" in result

    @patch("hier_config_gpt.clients.ollama.ollama")
    def test_generate_plan_exception_handling(self, mock_ollama):
        """Test OllamaGPTClient exception handling in generate_plan method"""
        # Configure the mock to raise an exception
        mock_client = MagicMock()
        mock_client.chat.side_effect = Exception("Connection error")

        mock_ollama.Client.return_value = mock_client

        # Create client and call method
        client = OllamaGPTClient()
        result = client.generate_plan("Test prompt")

        # Verify expectations
        assert len(result.plan) == 1
        assert "Error generating plan: Connection error" in result.plan[0]
