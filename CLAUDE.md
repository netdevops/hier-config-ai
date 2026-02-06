# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

hier-config-gpt extends the [hier-config](https://github.com/netdevops/hier-config) library with LLM-driven network configuration remediation. It provides a provider-agnostic interface for OpenAI, Anthropic Claude, and Ollama to generate remediation plans from hierarchical network configs. Python 3.10+, managed with Poetry.

## Common Commands

```bash
# Install all dependencies (dev + all LLM providers)
poetry install --with dev,chatgpt,anthropic,ollama

# Run all tests with coverage
poetry run pytest --cov=hier_config_gpt --cov-report=term

# Run a single test file or test
poetry run pytest tests/test_workflows.py
poetry run pytest tests/test_clients.py -k "test_chat_gpt_client_generate_plan"

# Linting & formatting (these are enforced in CI)
poetry run ruff check .
poetry run ruff format --check .

# Type checking (non-blocking in CI)
poetry run mypy hier_config_gpt

# Pylint (non-blocking in CI)
poetry run pylint hier_config_gpt

# Docs
poetry run mkdocs serve    # local preview
poetry run mkdocs build --strict
```

## Architecture

### Core Flow

`GPTWorkflowRemediation` (extends hier-config's `WorkflowRemediation`) is the central orchestrator:
1. Add `GPTRemediationRule`s defining lineage patterns, descriptions, and examples
2. Attach a `GPTClient` implementation via `set_gpt_client()`
3. Call `gpt_remediation_config()` which builds contexts per rule, constructs prompts, calls the LLM, and returns an `HConfig` object with remediation commands

### LLM Client Layer (`hier_config_gpt/clients/`)

**Strategy pattern** — all clients implement the abstract `GPTClient` base class (`clients/models.py`) with `chat()` and `generate_plan()` methods:
- `ChatGPTClient` (openai.py) — OpenAI
- `ClaudeGPTClient` (anthropic.py) — Anthropic
- `OllamaGPTClient` (ollama.py) — self-hosted models
- `MultiProviderGPTClient` (quorum.py) — majority-vote consensus across multiple providers

**Decorator wrappers** — composable around any client:
- `CachedGPTClient` — file-based response cache with TTL (`~/.hier_config_gpt/cache/`)
- `RateLimitedGPTClient` — token-bucket rate limiting

Wrappers stack: `RateLimitedGPTClient(CachedGPTClient(ChatGPTClient(...)))`

### Key Modules

- `models.py` — Pydantic v2 models: `GPTRemediationRule`, `GPTRemediationContext`, `GPTRemediationExample`
- `prompt_template.py` — `PromptTemplate` with required placeholders and file loading
- `exceptions.py` — `GPTClientInitializationError`, `RemediationError`
- `clients/utils.py` — JSON parsing from LLM responses, retry with exponential backoff

### Data Flow

```
GPTRemediationRule (lineage + description + example)
  → GPTRemediationContext (running_config + generated_config sections)
    → Prompt string (built from template + context)
      → GPTClient.generate_plan() → GPTPlanResponse (plan: list[str])
        → HConfig (parsed remediation commands)
```

## Testing

Tests use `unittest.mock.patch` to mock all external LLM API calls. Fixtures in `tests/conftest.py` provide mock responses, sample rules, and real `HConfig` objects with a mock driver. No API keys needed to run tests.

## CI

GitHub Actions runs on Ubuntu + macOS across Python 3.10/3.11/3.12. Ruff lint/format and pytest are blocking; mypy and pylint are non-blocking (`continue-on-error: true`).

## Dependencies

LLM provider packages (`openai`, `anthropic`, `ollama`) are optional extras. Core dependencies are only `pydantic` and `hier-config`. Install specific providers with `poetry install --with chatgpt` or all with `--with chatgpt,anthropic,ollama`.
