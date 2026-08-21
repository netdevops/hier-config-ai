# Contributing

For detailed contribution guidelines, please see [CONTRIBUTING.md](https://github.com/netdevops/hier-config-ai/blob/main/CONTRIBUTING.md) in the main repository.

## Quick Links

- [Report a Bug](https://github.com/netdevops/hier-config-ai/issues/new?labels=bug&template=bug_report.md)
- [Request a Feature](https://github.com/netdevops/hier-config-ai/issues/new?labels=enhancement&template=feature_request.md)
- [Ask a Question](https://github.com/netdevops/hier-config-ai/discussions)

## Development Setup

1. Clone the repository:
```bash
git clone https://github.com/netdevops/hier-config-ai.git
cd hier-config-ai
```

2. Install dependencies with Poetry:
```bash
poetry install --with dev,evals --all-extras
```

3. Run tests (95% coverage enforced):
```bash
poetry run python scripts/build.py pytest --coverage
```

4. Run linters (ruff, mypy, pyright, pylint, yamllint, flynt in parallel):
```bash
poetry run python scripts/build.py lint
```

Or run everything at once, exactly like CI:
```bash
poetry run python scripts/build.py lint-and-test
```

## Submitting Changes

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Run linters and tests
6. Submit a pull request

For more details, see the full [CONTRIBUTING.md](https://github.com/netdevops/hier-config-ai/blob/main/CONTRIBUTING.md).
