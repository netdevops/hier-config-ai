# LLM Clients

hier-config-gpt supports multiple LLM providers, giving you flexibility in choosing the best model for your needs. Each provider has its own strengths, costs, and deployment options.

## Overview of Supported Providers

| Provider | Models | Deployment | Best For |
|----------|--------|------------|----------|
| **OpenAI** | GPT-4, GPT-4o, GPT-4o-mini | Cloud (API) | High accuracy, production use |
| **Anthropic** | Claude 3.5 Sonnet, Claude 3 Opus | Cloud (API) | Complex reasoning, safety |
| **Ollama** | Llama, Mistral, Qwen, and more | Self-hosted | Privacy, no API costs |

## OpenAI ChatGPT Client

OpenAI's GPT models are widely used and offer excellent performance for configuration remediation tasks.

### Installation

```bash
pip install hier-config-gpt[openai]
```

### Basic Usage

```python
from hier_config_gpt.clients import ChatGPTClient

client = ChatGPTClient(
    api_key="your-openai-api-key",
    model="gpt-4o"
)
```

### Recommended Models

- **gpt-4o**: Best balance of performance and cost (recommended)
- **gpt-4o-mini**: Faster and cheaper, good for simpler tasks
- **gpt-4**: High accuracy, slower and more expensive
- **gpt-4-turbo**: Faster than gpt-4, similar quality

### Configuration Options

```python
client = ChatGPTClient(
    api_key="your-openai-api-key",
    model="gpt-4o",
    timeout=30.0,           # Request timeout in seconds
    max_retries=3,          # Number of retry attempts
    temperature=0.0         # Lower = more deterministic
)
```

### Environment Variables

Store your API key securely:

```bash
export OPENAI_API_KEY="your-api-key-here"
```

Then use it in code:

```python
import os
client = ChatGPTClient(api_key=os.getenv("OPENAI_API_KEY"))
```

## Anthropic Claude Client

Anthropic's Claude models excel at complex reasoning and following detailed instructions.

### Installation

```bash
pip install hier-config-gpt[anthropic]
```

### Basic Usage

```python
from hier_config_gpt.clients import ClaudeGPTClient

client = ClaudeGPTClient(
    api_key="your-anthropic-api-key",
    model="claude-3-5-sonnet-20241022"
)
```

### Recommended Models

- **claude-3-5-sonnet-20241022**: Latest, best overall (recommended)
- **claude-3-opus-20240229**: Highest accuracy for complex tasks
- **claude-3-sonnet-20240229**: Good balance of speed and quality
- **claude-3-haiku-20240307**: Fastest and most affordable

### Configuration Options

```python
client = ClaudeGPTClient(
    api_key="your-anthropic-api-key",
    model="claude-3-5-sonnet-20241022",
    timeout=30.0,
    max_retries=3,
    max_tokens=4096         # Maximum response length
)
```

### Environment Variables

```bash
export ANTHROPIC_API_KEY="your-api-key-here"
```

```python
import os
client = ClaudeGPTClient(api_key=os.getenv("ANTHROPIC_API_KEY"))
```

## Ollama Client (Self-Hosted)

Ollama allows you to run open-source LLMs locally, providing privacy and eliminating API costs.

### Installation

First, install Ollama on your system:

```bash
# macOS
brew install ollama

# Linux
curl -fsSL https://ollama.ai/install.sh | sh

# Windows
# Download from https://ollama.ai
```

Then install the Python client:

```bash
pip install hier-config-gpt[ollama]
```

### Pull a Model

```bash
# Pull a model (one-time setup)
ollama pull llama3.2
ollama pull mistral
ollama pull qwen2.5:7b
```

### Basic Usage

```python
from hier_config_gpt.clients import OllamaGPTClient

client = OllamaGPTClient(
    host="http://localhost:11434",
    model="llama3.2"
)
```

### Recommended Models

- **llama3.2**: Good general-purpose model (recommended)
- **llama3.1:8b**: Larger, more capable version
- **mistral**: Fast and efficient
- **qwen2.5:7b**: Strong for technical tasks
- **codellama**: Optimized for code generation

### Configuration Options

```python
client = OllamaGPTClient(
    host="http://localhost:11434",
    model="llama3.2",
    timeout=60.0,           # Longer timeout for local models
    keep_alive="5m"         # Keep model in memory
)
```

### Remote Ollama Server

You can also connect to a remote Ollama instance:

```python
client = OllamaGPTClient(
    host="http://your-server:11434",
    model="llama3.2"
)
```

## Choosing the Right Client

### Use OpenAI When:
- You need the highest accuracy
- You're building a production system
- Budget allows for API costs
- You want the easiest setup

### Use Anthropic Claude When:
- You need detailed reasoning
- Safety and instruction-following are critical
- You want strong performance with complex rules
- You prefer Claude's longer context window

### Use Ollama When:
- Privacy is a concern (on-premise deployment)
- You want to avoid API costs
- You have sufficient local compute resources
- You're experimenting or developing

## Client Interface

All clients implement the same interface, making it easy to switch between providers:

```python
class GPTClient:
    def generate_plan(
        self,
        prompt: str,
        context: Dict[str, Any]
    ) -> List[str]:
        """Generate remediation commands from prompt."""
        pass
```

This means you can swap clients without changing your application code:

```python
# Easy to switch providers
# client = ChatGPTClient(...)
# client = ClaudeGPTClient(...)
client = OllamaGPTClient(...)

wfr.set_gpt_client(client)
```

## Error Handling

All clients include built-in error handling and retry logic:

```python
from hier_config_gpt.exceptions import GPTError

try:
    remediation = wfr.gpt_remediation_config()
except GPTError as e:
    print(f"LLM error: {e}")
```

## Next Steps

- Learn about [advanced features](advanced-features.md) like caching and rate limiting
- Explore [quorum mode](advanced-features.md#quorum-mode) for multi-provider consensus
- Customize [prompt templates](prompt-templates.md) for better results
