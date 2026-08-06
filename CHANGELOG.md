# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Ported hier-config's development, testing, and linting standards: strict
  ruff (`select = ["ALL"]` with preview), mypy strict (pydantic plugin),
  pyright strict, pylint (with `pylint_pydantic`), yamllint, and flynt,
  all orchestrated by the new parallel `scripts/build.py` runner
  (`poetry run python scripts/build.py lint-and-test`)
- Enforced 95% test coverage gate (suite currently covers 99%) with new
  flat, fully type-annotated tests for the cache, cached client, rate
  limiter, rate-limited client, quorum client, prompt template, and client
  utility helpers
- CI now runs the full lint suite and coverage-gated tests on Python
  3.10-3.14 with all checks blocking (mypy/pylint were previously
  non-blocking)
- `parse_plan_commands()` helper in `hier_config_gpt.clients.utils` for
  extracting a typed command list from provider payloads
- Response caching functionality to reduce API costs and improve performance
- Rate limiting using token bucket algorithm
- Configurable timeout support for all LLM clients
- Custom prompt template support via `PromptTemplate` class
- `CachedGPTClient` wrapper for adding caching to any client
- `RateLimitedGPTClient` wrapper for rate limiting
- `ResponseCache` class for managing cached responses
- `RateLimiter` class for token bucket rate limiting
- Version info (`__version__`) to main package
- Comprehensive README.md with examples for all providers
- CONTRIBUTING.md with development guidelines
- SECURITY.md with API key handling best practices
- CHANGELOG.md for tracking project changes

### Changed
- Migrated to hier_config v4 (`hier-config >=4.0.0b1`): replaced
  `get_hconfig_fast_load()` with `HConfig.from_lines()` in
  `GPTWorkflowRemediation`, and updated all documentation examples from
  `get_hconfig()` to `HConfig.from_text()`
- Updated default OpenAI model from `gpt-4` to `gpt-4o`
- Updated default Anthropic model to `claude-3-5-sonnet-20241022`
- Updated default Ollama model to `llama3.2`
- Fixed return type bugs in `clear_gpt_rules()` and `add_gpt_rule()` methods
- Fixed lambda closure bug in quorum.py that could cause issues during retries
- `OllamaGPTClient.process_response()` now takes the typed
  `ollama.ChatResponse` instead of a plain dict, matching what the ollama
  SDK (>=0.4) actually returns
- Payloads of the wrong JSON type now raise `TypeError` instead of
  `ValueError` from the plan-parsing helpers (wrong payload/plan type);
  behavior for missing or invalid JSON is unchanged
- `GPTWorkflowRemediation` now exposes an explicit
  `(running_config, generated_config, plugins=())` signature instead of
  `*args/**kwargs`
- Improved quorum logic to require majority (>50%) instead of just count > 1
- Enhanced error messages throughout the codebase for better debugging
- Improved docstrings for all client classes with parameter descriptions
- Temperature parameter type changed from `int` to `float` for consistency

### Fixed
- Typo in openai.py: "Not content available" → "No content available"
- Typo in clients/models.py: "recieve" → "receive"
- Duplicate imports in ollama.py
- Improper error handling in OllamaGPTClient.generate_plan()
- Lambda closure issues in MultiProviderGPTClient

### Improved
- Error messages now include more context and actionable information
- Quorum mode now provides detailed vote distribution in error messages
- Metadata consistency across all provider clients
- Logging throughout the codebase with appropriate log levels
- pyproject.toml with proper classifiers, keywords, and [all] extras group
- Dependency version constraints for better stability

## [0.1.0] - 2024-XX-XX

### Added
- Initial release of hier-config-gpt
- Support for OpenAI GPT models via `ChatGPTClient`
- Support for Anthropic Claude models via `ClaudeGPTClient`
- Support for Ollama self-hosted models via `OllamaGPTClient`
- Multi-provider quorum mode via `MultiProviderGPTClient`
- `GPTWorkflowRemediation` class for LLM-based remediation
- `GPTRemediationRule` for defining custom remediation rules
- `GPTRemediationContext` for passing context to LLMs
- Retry logic with exponential backoff
- Comprehensive test suite using pytest
- Documentation with mkdocs
- Apache 2.0 license

[Unreleased]: https://github.com/netdevops/hier-config-gpt/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/netdevops/hier-config-gpt/releases/tag/v0.1.0
