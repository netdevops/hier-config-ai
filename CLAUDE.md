# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

hier-config-gpt extends the [hier-config](https://github.com/netdevops/hier-config) library with LLM-driven network configuration remediation. It provides a provider-agnostic interface for OpenAI, Anthropic Claude, and Ollama to generate remediation plans from hierarchical network configs. Python 3.10+, managed with Poetry.

## Common Commands

```bash
# Install all dependencies (dev + all LLM providers)
poetry install --with dev,chatgpt,anthropic,ollama

# Full lint + test suite (equivalent to CI)
poetry run python scripts/build.py lint-and-test

# Lint only (ruff, mypy, pyright, pylint, yamllint, flynt - run in parallel)
poetry run python scripts/build.py lint

# Auto-fix formatting and safe lint violations
poetry run python scripts/build.py lint --fix

# Tests only (95% coverage required)
poetry run python scripts/build.py pytest --coverage

# Run a single test file or test
poetry run pytest tests/test_workflows.py
poetry run pytest tests/test_clients.py -k "test_chatgpt_client_generate_plan"

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

Tests are flat function-based (no test classes) with full type annotations. External LLM API calls are mocked (`unittest.mock.patch` for provider SDKs, plus a typed `StubGPTClient` in `tests/conftest.py`); real `HConfig` objects use the GENERIC platform driver. No API keys needed to run tests. TDD is expected: write a failing test first, then implement. Coverage must stay at or above 95% (enforced by `scripts/build.py pytest --coverage`).

## Code Standards

- Ruff with `select = ["ALL"]` and preview mode, line length 88; the ignore list in `pyproject.toml` mirrors hier-config's and must not be loosened to make a change pass.
- mypy strict (with the pydantic plugin) and pyright strict; full annotations everywhere, including tests.
- pylint with the same extension plugins as hier-config (including `pylint_pydantic`).
- Every PR adds a `CHANGELOG.md` entry under `## [Unreleased]`.

## CI

GitHub Actions runs on Ubuntu across Python 3.10-3.14. Each job runs `poetry run python scripts/build.py lint` and `poetry run python scripts/build.py pytest --coverage`; all checks are blocking. A separate docs job builds with `mkdocs build --strict`.

Two release workflows exist: `prepare-release.yml` (`workflow_dispatch`, admin-only) bumps the version with `poetry version`, rotates the changelog, opens a release PR, and creates a draft `vX.Y.Z` release; `release.yml` publishes to PyPI (`poetry publish --build`) when a GitHub release is published. Process: run Prepare Release (pick branch + bump) → merge the release PR → publish the draft release. See "Releasing" in CONTRIBUTING.md.

## Dependencies

LLM provider packages (`openai`, `anthropic`, `ollama`) are optional extras. Core dependencies are only `pydantic` and `hier-config`. Install specific providers with `poetry install --with chatgpt` or all with `--with chatgpt,anthropic,ollama`.
