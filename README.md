# hier-config-gpt

[![PyPI version](https://badge.fury.io/py/hier-config-gpt.svg)](https://badge.fury.io/py/hier-config-gpt)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Documentation](https://img.shields.io/badge/docs-readthedocs-brightgreen.svg)](https://hier-config-gpt.readthedocs.io/)

An enhanced hierarchical configuration library that integrates Large Language Model (LLM) capabilities for advanced network configuration analysis and remediation.

## Overview

`hier-config-gpt` extends the powerful [hier-config](https://github.com/netdevops/hier-config) library by adding AI-driven custom remediation workflows. It addresses complex network configuration edge cases that fall outside standard negation and idempotency workflows by leveraging LLMs to dynamically generate remediation plans.

### Key Features

- **Multi-Provider LLM Support**: Works with OpenAI GPT, Anthropic Claude, and Ollama (self-hosted) models
- **Intelligent Remediation**: Automatically generates complex configuration remediation steps
- **Quorum Mode**: Optional consensus mechanism across multiple LLM providers for increased reliability
- **Response Caching**: Built-in caching to reduce API costs and improve performance
- **Rate Limiting**: Token bucket algorithm to prevent API throttling
- **Configurable Prompts**: Customize prompt templates for your specific needs
- **Production Ready**: Comprehensive error handling, retry logic, and logging

## Installation

### Basic Installation

```bash
pip install hier-config-gpt
```

### Install with Specific Provider(s)

```bash
# OpenAI GPT models
pip install hier-config-gpt[openai]

# Anthropic Claude models
pip install hier-config-gpt[anthropic]

# Ollama (self-hosted) models
pip install hier-config-gpt[ollama]

# All providers
pip install hier-config-gpt[all]
```

## Quick Start

### Basic Example with OpenAI

```python
import os
from hier_config import get_hconfig, Platform
from hier_config.models import MatchRule
from hier_config_gpt import GPTWorkflowRemediation
from hier_config_gpt.models import GPTRemediationRule, GPTRemediationExample
from hier_config_gpt.clients import ChatGPTClient

# Load configurations
running_config = open("running_config.conf").read()
generated_config = open("desired_config.conf").read()

# Initialize workflow
wfr = GPTWorkflowRemediation(
    running_config=get_hconfig(Platform.CISCO_IOS, running_config),
    generated_config=get_hconfig(Platform.CISCO_IOS, generated_config)
)

# Define remediation rule
description = """When remediating an access-list on Cisco IOS devices:
1. Resequence the access-list so each sequence number is a multiple of 10
2. Add a temporary 'permit any' statement at sequence 1
3. Apply the required changes from the generated configuration
4. Remove the temporary permit statement
"""

lineage = (MatchRule(startswith="ip access-list"),)
example = GPTRemediationExample(
    running_config="ip access-list extended TEST\n  12 permit ip host 10.0.0.1 any",
    remediation_config="ip access-list resequence TEST 10 10\nip access-list extended TEST\n  1 permit ip any any\n  no 10\n  10 permit ip host 10.0.0.2 any\n  no 1"
)

gpt_rule = GPTRemediationRule(
    description=description,
    lineage=lineage,
    example=example
)

# Add rule and set up client
wfr.add_gpt_rule(gpt_rule)
client = ChatGPTClient(api_key=os.getenv("OPENAI_API_KEY"), model="gpt-4o")
wfr.set_gpt_client(client)

# Generate remediation plan
remediation = wfr.gpt_remediation_config()
print(remediation)
```

### Using Anthropic Claude

```python
from hier_config_gpt.clients import ClaudeGPTClient

client = ClaudeGPTClient(
    api_key=os.getenv("ANTHROPIC_API_KEY"),
    model="claude-3-5-sonnet-20241022"
)
wfr.set_gpt_client(client)
```

### Using Ollama (Self-Hosted)

```python
from hier_config_gpt.clients import OllamaGPTClient

client = OllamaGPTClient(
    host="http://localhost:11434",
    model="llama3.2"
)
wfr.set_gpt_client(client)
```

## Advanced Features

### Response Caching

Reduce API costs and improve performance with built-in caching:

```python
from hier_config_gpt.clients import ChatGPTClient, CachedGPTClient, ResponseCache

# Create base client
base_client = ChatGPTClient(api_key=os.getenv("OPENAI_API_KEY"))

# Wrap with caching (1 hour TTL)
cache = ResponseCache(ttl_seconds=3600)
client = CachedGPTClient(base_client, cache=cache)

wfr.set_gpt_client(client)
```

### Rate Limiting

Prevent API throttling with automatic rate limiting:

```python
from hier_config_gpt.clients import ChatGPTClient, RateLimitedGPTClient

# Create base client
base_client = ChatGPTClient(api_key=os.getenv("OPENAI_API_KEY"))

# Wrap with rate limiting (60 requests per minute)
client = RateLimitedGPTClient(
    base_client,
    max_requests=60,
    time_window_seconds=60.0
)

wfr.set_gpt_client(client)
```

### Combining Caching and Rate Limiting

```python
from hier_config_gpt.clients import (
    ChatGPTClient,
    CachedGPTClient,
    RateLimitedGPTClient,
    ResponseCache
)

# Create layered client: rate limiting -> caching -> base client
base_client = ChatGPTClient(api_key=os.getenv("OPENAI_API_KEY"))
cached_client = CachedGPTClient(base_client, cache=ResponseCache())
client = RateLimitedGPTClient(cached_client, max_requests=60)

wfr.set_gpt_client(client)
```

### Quorum Mode (Multi-Provider Consensus)

Use multiple LLM providers with majority voting for critical operations:

```python
from hier_config_gpt.clients import (
    ChatGPTClient,
    ClaudeGPTClient,
    OllamaGPTClient,
    MultiProviderGPTClient
)

# Create multiple provider clients
openai_client = ChatGPTClient(api_key=os.getenv("OPENAI_API_KEY"))
claude_client = ClaudeGPTClient(api_key=os.getenv("ANTHROPIC_API_KEY"))
ollama_client = OllamaGPTClient()

# Create quorum client (requires majority agreement)
client = MultiProviderGPTClient(
    providers=[openai_client, claude_client, ollama_client],
    enable_quorum=True
)

wfr.set_gpt_client(client)
```

### Custom Prompt Templates

Customize the prompt structure for your specific needs:

```python
from hier_config_gpt import PromptTemplate, GPTWorkflowRemediation

# Define custom template
custom_template = """
Generate network commands to transform the configuration.

CURRENT STATE:
{running_config}

DESIRED STATE:
{generated_config}

RULES:
{description}

EXAMPLE:
Running: {example_running_config}
Remediation: {example_remediation_config}

Return JSON with "plan" array of command strings.
"""

# Use custom template
template = PromptTemplate(template=custom_template)
wfr = GPTWorkflowRemediation(
    running_config=running,
    generated_config=generated,
    prompt_template=template
)
```

## Configuration Timeouts

All clients support configurable timeouts:

```python
# OpenAI with 30-second timeout
client = ChatGPTClient(
    api_key=os.getenv("OPENAI_API_KEY"),
    timeout=30.0
)

# Claude with custom timeout
client = ClaudeGPTClient(
    api_key=os.getenv("ANTHROPIC_API_KEY"),
    timeout=45.0
)
```

## Use Cases

- **Access List Resequencing**: Automatically handle complex ACL resequencing with temporary permit statements
- **Interface Configuration**: Generate safe interface configuration changes with proper ordering
- **Routing Protocol Updates**: Handle complex routing protocol transitions
- **VLAN Reconfiguration**: Manage VLAN changes across multiple switches
- **QoS Policy Updates**: Coordinate policy-map and class-map changes

## Documentation

Full documentation is available at [hier-config-gpt.readthedocs.io](https://hier-config-gpt.readthedocs.io/)

## Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## Security

For security considerations and best practices, see [SECURITY.md](SECURITY.md).

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

## Credits

- Built on top of [hier-config](https://github.com/netdevops/hier-config) by James Williams
- Supports [OpenAI GPT](https://openai.com/), [Anthropic Claude](https://www.anthropic.com/), and [Ollama](https://ollama.ai/)

## Support

- **Issues**: [GitHub Issues](https://github.com/netdevops/hier-config-gpt/issues)
- **Discussions**: [GitHub Discussions](https://github.com/netdevops/hier-config-gpt/discussions)
- **Documentation**: [ReadTheDocs](https://hier-config-gpt.readthedocs.io/)
