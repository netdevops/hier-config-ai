# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

hier-config-ai extends [hier-config](https://github.com/netdevops/hier-config) with LLM-driven network configuration remediation, built on [PydanticAI](https://ai.pydantic.dev/). It targets the config sections hier-config cannot resolve deterministically. Access-list resequencing is the canonical case and the documented flagship: `examples/ollama_acl.py` and `docs/user-guide/custom-workflows.md` put it against the hand-written workflow from hier-config's own guide. Python 3.10+, managed with Poetry.

The distinguishing feature is that plans are **verified, not trusted**: every plan is applied with `HConfig.future` and re-checked, and failures go back to the model through `ModelRetry`.

## Common Commands

```bash
# Install (dev + evals + every provider extra).
# The evals group is not optional for development: lint covers evals/.
poetry install --with dev,evals --all-extras

# Full lint + test suite (equivalent to CI)
poetry run python scripts/build.py lint-and-test

# Lint only (ruff, mypy, pyright, pylint, yamllint, flynt - run in parallel)
poetry run python scripts/build.py lint
poetry run python scripts/build.py lint --fix

# Tests only (95% coverage required)
poetry run python scripts/build.py pytest --coverage
poetry run pytest tests/test_validation.py -k acl

# Packaging guard - catches extras that publish no requirements
poetry build && poetry run python scripts/check_packaging.py

# Evaluation harness (calls real providers, costs money, not in CI)
poetry run python evals/run_evals.py --model anthropic:claude-sonnet-4-5

# Docs
poetry run mkdocs serve
poetry run mkdocs build --strict
```

## Architecture

### Core flow

`AIWorkflowRemediation` (extends hier-config's `WorkflowRemediation`) orchestrates:

1. Add `AIRemediationRule`s (lineage + description + example).
2. `set_model("anthropic:claude-sonnet-4-5")` or `set_agent(build_agent(...))`.
3. `await aai_remediation_config()` builds one prompt per rule, runs them concurrently, validates each plan, and returns an `HConfig`.

```
AIRemediationRule
  → scoped_config()          # only this rule's section
    → AIRemediationContext
      → PromptTemplate.build()
        → Agent.run()        # structured output, tools available
          → validate_plan()  # ModelRetry on failure
            → HConfig
```

### Modules (`hier_config_ai/`, flat — there is no `clients/` package)

- `agent.py` — `build_agent()`, and `describe_driver()` which reads platform rules off the hier-config driver into the system prompt.
- `validation.py` — the output validator and the convergence check. **The most important module.**
- `tools.py` — `test_remediation` and `get_config_section`, registered via `build_tools()`.
- `workflows.py` — `AIWorkflowRemediation`, `scoped_config()`.
- `deps.py` — `RemediationDeps` and the `Retriever` protocol.
- `models.py` — `AIPlanResponse`, `AIRemediationRule`, `AIRemediationExample`, `AIRemediationContext`.
- `model_wrappers.py` — `CachedModel`, `RateLimitedModel` (PydanticAI `WrapperModel`s).
- `cache.py`, `rate_limiter.py`, `consensus.py`, `prompt_template.py`, `exceptions.py`.

## Things that are easy to get wrong

**The convergence check must compare two futures.** `remaining_difference()` compares `running.future(plan)` against `running.future(deterministic_remediation)`. Do not "simplify" this:

- `HConfig.difference` alone treats access-list entries as equal regardless of sequence number, so it passes a plan that never renumbers — the exact case this library exists for.
- A textual diff against the generated config alone fails every correct plan, because `future()` applies `no shutdown` by removing `shutdown`, so the result lacks the literal line the target states.

Comparison is by membership, not position, deliberately. `tests/test_validation.py` locks all of this in.

**Types used in tool signatures must be importable at runtime.** PydanticAI calls `get_type_hints()` when building tool schemas, so `RemediationDeps` and `MatchRule` cannot move into `TYPE_CHECKING` blocks in `tools.py`. Same for `MatchRule` in `models.py`, which pydantic resolves at model-build time.

**Cache keys must exclude per-run fields.** `timestamp`, `id`, `conversation_id`, and `run_id` change every request. Including them makes the cache silently never hit.

**Extras must be declared in `[tool.poetry.dependencies]` with `optional = true`.** Declaring them in optional *groups* produces published extras with no requirements — the 0.1.0 bug. `scripts/check_packaging.py` guards this in CI; the test suite cannot, because the fault is in the built wheel.

**Never hardcode platform behaviour in prompts.** Indent width, negation prefixes, and section exits come from `driver.rules`. Cisco IOS indents by two, not four.

## Testing

Flat function-based tests, fully annotated, no test classes. **No `unittest.mock` anywhere** — provider behaviour is scripted with PydanticAI's `FunctionModel` via `scripted_model()` in `tests/conftest.py`, so the agent, tools, and validators all run for real. `HConfig` fixtures are real objects on the GENERIC driver, with CISCO_IOS used for access-list cases.

TDD is expected. Coverage must stay at or above 95% (currently ~98%).

Lint hides runtime faults in this codebase: a sync function with `await` at its call sites passed every linter. Exercise new agent wiring by running it, not just by type-checking it.

## Code Standards

- Ruff `select = ["ALL"]`, preview mode, line length 88. The ignore list in `pyproject.toml` mirrors hier-config's and **must not be loosened** to make a change pass. Prefer a targeted `# ruff: ignore[rule]` with a comment saying why.
- mypy strict (pydantic plugin) and pyright strict. Full annotations everywhere, including tests.
- pylint with `pylint_pydantic`, at 10.00.
- Every PR adds a `CHANGELOG.md` entry under `## [Unreleased]`.

## CI

GitHub Actions on Ubuntu across Python 3.10-3.14. Each job runs `scripts/build.py lint` and `scripts/build.py pytest --coverage`. A `packaging` job builds the wheel and runs `scripts/check_packaging.py`. A docs job runs `mkdocs build --strict`. All blocking.

Release: `prepare-release.yml` (admin-only `workflow_dispatch`) bumps the version, rotates the changelog, opens a release PR, and drafts a release; `release.yml` publishes to PyPI when that release is published.

## Dependencies

Core: `pydantic`, `hier-config`, `pydantic-ai-slim`. Provider SDKs are optional extras: `openai` (also serves Ollama, Azure, OpenRouter), `anthropic`, `google`, `bedrock`, `groq`, `mistral`, `all`. Nothing is imported until a model is named, so `import hier_config_ai` works with no provider installed.

## Planned (0.3.0)

Retrieval. The seams already exist and should not be removed: `RemediationDeps.retriever`, the `Retriever` protocol, list-based tool registration in `build_tools()`, and the single `build_retry_message()` helper that every `ModelRetry` routes through.
