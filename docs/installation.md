# Installation

## Install

Install with the extra for the provider you use:

```bash
pip install "hier-config-ai[anthropic]"
pip install "hier-config-ai[openai]"
pip install "hier-config-ai[google]"
pip install "hier-config-ai[bedrock]"
pip install "hier-config-ai[groq]"
pip install "hier-config-ai[mistral]"
pip install "hier-config-ai[all]"
```

Ollama, Azure OpenAI, and OpenRouter all speak the OpenAI-compatible API, so
they are served by the `openai` extra:

```bash
pip install "hier-config-ai[ollama]"
```

## What comes with the core install

The core package depends only on `pydantic`, `hier-config`, and
`pydantic-ai-slim`. Provider SDKs are optional, and nothing is imported until
you name a model, so `import hier_config_ai` works with no provider installed.

!!! note "Extras in 0.1.x installed nothing"
    Version 0.1.0 declared its extras against optional Poetry *groups*, which
    are never published. The wheel advertised four extras and required none of
    them, so `pip install hier-config-gpt[all]` brought in no provider SDK. CI
    now fails the build if any extra ships without requirements.

## API keys

Set the environment variable your provider expects:

```bash
export ANTHROPIC_API_KEY="..."
export OPENAI_API_KEY="..."
export GEMINI_API_KEY="..."
```

Never commit keys. See [SECURITY.md](https://github.com/netdevops/hier-config-ai/blob/main/SECURITY.md).

## Development install

```bash
git clone https://github.com/netdevops/hier-config-ai.git
cd hier-config-ai
poetry install --with dev,evals --all-extras
poetry run python scripts/build.py lint-and-test
```

Add `--with evals` to run the evaluation harness.
