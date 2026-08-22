# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- `output_mode` on `build_agent()` and `set_model()`, selecting how the model
  returns structured output: `"tool"` (default), `"native"`, or `"prompted"`.
  Small self-hosted models are frequently unreliable at tool calling, so the
  default failed against every local model tested. `"native"` asks for a JSON
  schema on the response instead, which they handle.
- `enable_tools` on `build_agent()` and `set_model()`, for models that cannot
  cope with tools being offered.
- Plans may add scaffolding and take it away again. Resequencing an access list
  safely needs a temporary allow-all so the list never denies live traffic
  mid-change; the plan is parsed into a tree before comparison, which loses
  command order, so both halves of that pair looked like configuration left
  behind and every traffic-safe plan was rejected. Scaffolding the plan itself
  removes is now excluded from the comparison, whether the removal repeats the
  command or names only its sequence number (`no 1`). Forgetting the cleanup is
  still caught, so a `permit ip any any` cannot be smuggled into a live access
  list, and removing a sequence the plan never added still counts as a real
  deletion.
- `examples/acl_resequencing.py` and `examples/ollama_quickstart.py`, both
  runnable.
- "Replacing a Custom Workflow" documentation, putting access-list resequencing
  against the hand-written version from hier-config's custom workflows guide.
  The README, home page, quick start, and examples now lead with that case
  rather than a toy interface change.

## [0.2.1a0] - 2026-08-21

Prerelease of the 0.2.0 rewrite below.

## [0.2.0] - 2026-08-21

Renamed from `hier-config-gpt` to `hier-config-ai`, and rebuilt on
[PydanticAI](https://ai.pydantic.dev/). This release breaks compatibility with
0.1.x on purpose and ships no compatibility shims.

### Why

The provider layer hand-rolled the three hardest parts of an LLM integration:
provider abstraction, structured output, and retries. PydanticAI does all three
better. Removing that layer also removed the bugs living in it.

### Added
- **Plan validation against hier-config.** Every plan is applied to the running
  config with `HConfig.future` and re-checked. If it does not produce the
  intended configuration the difference goes back to the model through
  `ModelRetry`, and the model corrects its own work. Previously a plan was
  never checked for whether it actually worked.
- **Tools the model can call.** `test_remediation` reports what candidate
  commands would do to the device; `get_config_section` fetches more
  configuration on demand.
- **Guardrails.** Plans containing `reload`, `write erase`, and similar are
  rejected. Risky but legitimate commands are surfaced in
  `AIPlanResponse.commands_requiring_review` instead of being blocked.
- **Platform rules in the prompt**, read from the hier-config driver: the real
  indent width, section exit commands, replacement negations, and idempotent
  commands. Previously the prompt hardcoded four-space indentation, which is
  wrong for every platform that indents by two.
- **Async support.** `aai_remediation_config()` runs rules concurrently;
  `ai_remediation_config()` remains for synchronous callers.
- **Token accounting** through `AIWorkflowRemediation.usage`.
- **Richer output**: `AIPlanResponse` gains `reasoning`, `confidence`, and
  `commands_requiring_review`.
- **Evaluation harness** in `evals/`, built on `pydantic-evals` and seeded from
  the access-list fixtures that previously sat unused.
- **Packaging guard** (`scripts/check_packaging.py`, run in CI) that fails the
  build if any extra is published without requirements.
- **Retrieval seams** for 0.3.0: `RemediationDeps.retriever`, a `Retriever`
  protocol, tool registration through a list, and a single retry-message
  helper. None are used yet; they exist so retrieval can be added without
  reshaping every signature.
- `plan_converges()`, so callers scoring a plan do not each need their own
  guard around invalid configuration.

### Changed
- Package renamed `hier_config_gpt` → `hier_config_ai`; distribution renamed
  `hier-config-gpt` → `hier-config-ai`.
- Public names drop the GPT prefix: `AIWorkflowRemediation`,
  `AIRemediationRule`, `AIRemediationExample`, `AIRemediationContext`,
  `AIPlanResponse`, `AIClientInitializationError`.
- Methods renamed: `set_gpt_client()` → `set_model()` / `set_agent()`,
  `add_gpt_rule()` → `add_rule()`, `clear_gpt_rules()` → `clear_rules()`,
  `gpt_remediation_config()` → `ai_remediation_config()`.
- Providers now come from PydanticAI. One extra replaces three, and OpenAI,
  Anthropic, Google, Bedrock, Groq, and Mistral are all supported. Ollama,
  Azure OpenAI, and OpenRouter are served by the `openai` extra.
- `CachedGPTClient` and `RateLimitedGPTClient` become `CachedModel` and
  `RateLimitedModel`, wrapping the model rather than the client, so they apply
  to tool calls and retries too.
- Quorum is split in two: ordered failover is PydanticAI's `FallbackModel`, and
  consensus moves to `consensus_plan()`, which runs agents concurrently.
- The cache directory moves to `~/.hier_config_ai/cache`. Old entries are not
  migrated.
- Guardrails follow the platform. Review patterns are built from the driver's
  negation prefix, so they match `no `, `delete `, `undo `, and `unset `.
- `consensus_plan()` takes its driver from `deps` rather than as a separate
  argument, which made it possible to fingerprint votes with one driver while
  validating with another. Supplying no agents now raises `ValueError` rather
  than `ConsensusError`, since it is a caller mistake and not a disagreement.
- The workflow's `retriever` is a plain attribute; `set_retriever()` is gone.
- Concurrency is delegated to PydanticAI's `Agent(max_concurrency=...)` instead
  of a hand-rolled semaphore.

### Removed
- `hier_config_gpt.clients` in full: `ChatGPTClient`, `ClaudeGPTClient`,
  `OllamaGPTClient`, `MultiProviderGPTClient`, the `GPTClient` base class, the
  JSON-scraping helpers in `clients/utils.py`, and `retry_with_backoff`.
- Direct dependencies on `openai`, `anthropic`, and `ollama`.

### Fixed
- **Extras installed nothing.** `[tool.poetry.extras]` referenced packages
  declared only in optional groups, which are never published. The 0.1.0 wheel
  advertised four extras and required none of them, so
  `pip install hier-config-gpt[all]` brought in no provider SDK.
- **Importing anything required every SDK.** `clients/__init__.py` imported all
  three providers eagerly with no guards, so installing one extra was not
  enough to import the package.
- **The cache could return an empty plan as success.** Keys were derived from
  the prompt and model only, ignoring the call type, so a `chat()` answer could
  be served to `generate_plan()`. Keys now cover the provider, model, settings,
  message history, and request shape, and exclude per-run fields such as
  timestamps and conversation ids that would otherwise stop the cache ever
  hitting.
- **Quorum could not reach agreement.** Votes were counted on exact joined
  strings, so two providers producing the same configuration in a different
  order never agreed. Voting is now on parsed configuration.
- **A single surviving provider won quorum unopposed**, because the majority
  threshold divided by the providers that answered rather than those asked.
- **`PromptTemplate` was never wired in.** The README and API reference showed
  a `prompt_template=` argument the workflow did not accept, so every
  documented example raised `TypeError`.
- **`anthropic = "^0.39.0,<1.0"`** resolved to `<0.40.0`, pinning a Nov-2024
  SDK that could not reach any current Claude model.
- **Ollama errors were returned as text**, so failover never triggered.
- **Retries were applied to the wrong failures**: authentication errors and
  malformed requests were retried, malformed model output was not, and quorum
  nested its retries with the client's for six attempts.
- **The rate limiter slept while holding its lock**, serialising every waiter.
- **The cache wrote device configurations with default permissions.** The
  directory is now created `0o700` and entries `0o600`.
- **Guardrails matched nothing on six of the thirteen platforms.** Every review
  pattern was anchored on `^\s*no\s+`, so on Junos, VyOS, SR Linux, VRP,
  Comware, and FortiOS `commands_requiring_review` always came back empty —
  indistinguishable from a plan with nothing risky in it.
- **No multi-turn request ever hit the cache.** Keys were built by stripping
  fields whose names looked volatile, which still left `usage` and
  `provider_response_id` on every `ModelResponse` in the history. Since tools
  and retries make every run multi-turn, the cache only ever served the first
  request of a run. Keys are now a structural projection over each part's own
  `part_kind`, which also stops the key derivation reaching into tool `args`.
- **Negation rules were filtered on whether `use` was set**, silently dropping
  the `DEFAULT` and `REGEX_SUB` strategies. Arista showed no negation rules at
  all; NXOS showed three of seven.
- **Driver rules were truncated silently.** NXOS carries 56 idempotent commands
  against a cap of 12, and the model was left believing it had seen them all.
  What is cut is now reported.
- **The system prompt never mentioned the platform's negation or declaration
  prefix**, so Junos, VyOS, SR Linux, VRP, Comware, and FortiOS were given
  Cisco-flavoured instructions.
- **Regex match rules rendered as a bare `*`** in the prompt, discarding the
  pattern.
- **A failing rule left its siblings running unwatched.** `asyncio.gather`
  propagated the first error while the other provider calls continued, and
  their answers were paid for and discarded.
- **The convergence target was rebuilt on every validation pass and every tool
  call**, and the plan was parsed twice per pass. Both are now computed once.
- **The line comparison was quadratic**, scanning a list for every line.
- **Multi-level lineages could never converge.** `scoped_config` copied the
  matched nodes onto a bare root, so a lineage of `(interface, mtu)` scoped to
  a parentless `mtu 9000`. No plan could satisfy that, so the rule burned every
  retry and then failed the whole workflow.
- **A rule matching nothing killed the entire run.** Both scoped configs came
  out empty, so an empty plan was rejected for being empty and any non-empty
  plan was rejected as unwanted. One stale rule took every sibling rule's work
  down with it. Such rules are now skipped.
- **Cache hits still spent rate-limit budget.** The limiter wrapped the cache
  rather than the other way round, so it charged before the cache was
  consulted and a fleet run was throttled on requests that never left the
  process.
- **`get_config_section` could not see past the section under remediation**,
  though the system prompt told the model to call it for more. Deps now carry
  the full configuration alongside the scoped section.
- **The default prompt template told the model to reply with raw JSON**, which
  is carried over from the pre-agent client and stops it calling the structured
  output tool. It also asserted four-space indentation while the driver reports
  the real width. Both are gone; the template now carries only the task.
- **Streaming bypassed the rate limiter**, since `WrapperModel.request_stream`
  delegates straight through.
- **`boot system` was on the hard-reject list**, making any intended config
  that sets a boot image unreachable. It is ordinary golden-config content.
- **`commands_requiring_review` was overwritten rather than merged**, discarding
  anything the model itself flagged that no pattern covered.
- **Asking the rate limiter for more tokens than the bucket holds waited
  forever.** It now raises `ValueError`.
- Destructive-command patterns now also match the `do ` prefix, so `do reload`
  is rejected by the guardrail rather than only by the convergence check.

## [0.1.1a0] - 2026-08-18


### Added
- Release automation workflows: `prepare-release.yml`
  (admin-gated `workflow_dispatch`) bumps the version with `poetry version`,
  rotates the changelog, opens a release PR, and creates a draft GitHub
  release; `release.yml` builds and publishes to PyPI when a release is
  published
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
- `parse_plan_commands()` helper in `hier_config_ai.clients.utils` for
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
  `AIWorkflowRemediation`, and updated all documentation examples from
  `get_hconfig()` to `HConfig.from_text()`
- Updated default OpenAI model from `gpt-4` to `gpt-4o`
- Updated default Anthropic model to `claude-3-5-sonnet-20241022`
- Updated default Ollama model to `llama3.2`
- Fixed return type bugs in `clear_rules()` and `add_rule()` methods
- Fixed lambda closure bug in quorum.py that could cause issues during retries
- `OllamaGPTClient.process_response()` now takes the typed
  `ollama.ChatResponse` instead of a plain dict, matching what the ollama
  SDK (>=0.4) actually returns
- Payloads of the wrong JSON type now raise `TypeError` instead of
  `ValueError` from the plan-parsing helpers (wrong payload/plan type);
  behavior for missing or invalid JSON is unchanged
- `AIWorkflowRemediation` now exposes an explicit
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
- Initial release of hier-config-ai
- Support for OpenAI GPT models via `ChatGPTClient`
- Support for Anthropic Claude models via `ClaudeGPTClient`
- Support for Ollama self-hosted models via `OllamaGPTClient`
- Multi-provider quorum mode via `MultiProviderGPTClient`
- `AIWorkflowRemediation` class for LLM-based remediation
- `AIRemediationRule` for defining custom remediation rules
- `AIRemediationContext` for passing context to LLMs
- Retry logic with exponential backoff
- Comprehensive test suite using pytest
- Documentation with mkdocs
- Apache 2.0 license

[Unreleased]: https://github.com/netdevops/hier-config-ai/compare/v0.2.1a0...HEAD
[0.2.1a0]: https://github.com/netdevops/hier-config-ai/compare/v0.2.0...v0.2.1a0
[0.2.0]: https://github.com/netdevops/hier-config-ai/compare/v0.1.1a0...v0.2.0
[0.1.1a0]: https://github.com/netdevops/hier-config-ai/compare/v0.1.0...v0.1.1a0
[0.1.0]: https://github.com/netdevops/hier-config-ai/releases/tag/v0.1.0
