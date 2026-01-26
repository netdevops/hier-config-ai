# Installation

## Requirements

- Python 3.10 or higher
- pip or poetry package manager

## Basic Installation

The simplest way to install hier-config-gpt is via pip:

```bash
pip install hier-config-gpt
```

This installs the core library with support for the [hier-config](https://github.com/netdevops/hier-config) framework. However, to use LLM providers, you'll need to install additional dependencies.

## Installing with LLM Providers

Since different users may want to use different LLM providers, the library offers optional dependencies for each supported provider.

### OpenAI GPT Models

To use OpenAI's GPT models (GPT-4, GPT-4o, etc.):

```bash
pip install hier-config-gpt[openai]
```

### Anthropic Claude Models

To use Anthropic's Claude models (Claude 3.5 Sonnet, etc.):

```bash
pip install hier-config-gpt[anthropic]
```

### Ollama (Self-Hosted Models)

To use Ollama for self-hosted open-source models:

```bash
pip install hier-config-gpt[ollama]
```

### All Providers

To install support for all LLM providers at once:

```bash
pip install hier-config-gpt[all]
```

## Installation with Poetry

If you're using Poetry for dependency management:

```bash
poetry add hier-config-gpt
```

With optional dependencies:

```bash
# OpenAI
poetry add hier-config-gpt[openai]

# Anthropic
poetry add hier-config-gpt[anthropic]

# Ollama
poetry add hier-config-gpt[ollama]

# All providers
poetry add hier-config-gpt[all]
```

## Installing from Source

To install the latest development version from GitHub:

```bash
git clone https://github.com/netdevops/hier-config-gpt.git
cd hier-config-gpt
pip install -e .
```

With optional dependencies:

```bash
pip install -e ".[all]"
```

## Verifying Installation

After installation, verify that the library is properly installed:

```python
import hier_config_gpt
print(hier_config_gpt.__version__)
```

## Next Steps

- Set up your [LLM client](user-guide/clients.md) with API keys
- Follow the [Quick Start guide](quickstart.md) for your first implementation
- Explore [advanced features](user-guide/advanced-features.md) like caching and rate limiting
