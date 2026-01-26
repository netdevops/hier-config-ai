# Contributing

For detailed contribution guidelines, please see [CONTRIBUTING.md](https://github.com/netdevops/hier-config-gpt/blob/main/CONTRIBUTING.md) in the main repository.

## Quick Links

- [Report a Bug](https://github.com/netdevops/hier-config-gpt/issues/new?labels=bug&template=bug_report.md)
- [Request a Feature](https://github.com/netdevops/hier-config-gpt/issues/new?labels=enhancement&template=feature_request.md)
- [Ask a Question](https://github.com/netdevops/hier-config-gpt/discussions)

## Development Setup

1. Clone the repository:
```bash
git clone https://github.com/netdevops/hier-config-gpt.git
cd hier-config-gpt
```

2. Install dependencies with Poetry:
```bash
poetry install --with dev,chatgpt,anthropic,ollama
```

3. Run tests:
```bash
poetry run pytest
```

4. Run linters:
```bash
poetry run ruff check .
poetry run mypy .
```

## Submitting Changes

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Run linters and tests
6. Submit a pull request

For more details, see the full [CONTRIBUTING.md](https://github.com/netdevops/hier-config-gpt/blob/main/CONTRIBUTING.md).
