# Contributing to hier-config-ai

Thank you for your interest in contributing to hier-config-ai! We welcome contributions from the community.

## Getting Started

1. **Fork the repository** on GitHub
2. **Clone your fork** locally:
   ```bash
   git clone https://github.com/YOUR_USERNAME/hier-config-ai.git
   cd hier-config-ai
   ```

3. **Install dependencies** using Poetry:
   ```bash
   # Install Poetry if you haven't already
   curl -sSL https://install.python-poetry.org | python3 -

   # Install project dependencies
   poetry install --with dev --all-extras
   ```

4. **Create a branch** for your changes:
   ```bash
   git checkout -b feature/your-feature-name
   ```

## Development Guidelines

### Code Style

We use several tools to maintain code quality, all run through the
`scripts/build.py` runner (they execute in parallel):

- **Ruff**: linting (`select = ["ALL"]` with preview) and formatting
- **mypy** (strict) and **pyright** (strict): type checking
- **pylint**: additional linting
- **yamllint**: YAML syntax
- **flynt**: f-string enforcement

Run checks before committing:

```bash
# Full lint + test suite (what CI runs)
poetry run python scripts/build.py lint-and-test

# Lint only
poetry run python scripts/build.py lint

# Auto-fix formatting and safe lint violations
poetry run python scripts/build.py lint --fix
```

All code (including tests) must carry full type annotations. Do not loosen the
lint or coverage configuration to make a change pass.

### Testing

We use pytest for testing. Please ensure all tests pass before submitting a PR:

```bash
# Run all tests with the enforced coverage gate (95%)
poetry run python scripts/build.py pytest --coverage

# Run all tests directly
poetry run pytest

# Run specific test file
poetry run pytest tests/test_workflows.py
```

### Writing Tests

- Write a failing test first (TDD), confirm it fails for the right reason,
  then implement minimally
- Tests are flat function-based (no test classes) with full type annotations
- Test coverage must stay at or above 95% (enforced in CI)
- Use descriptive test names that explain what is being tested
- Mock external dependencies (API calls, file system, etc.); no API keys are
  needed to run the suite

Example test structure:

```python
def test_feature_name_expected_behavior():
    """Test that feature X behaves correctly when Y."""
    # Arrange
    setup_data = ...

    # Act
    result = function_under_test(setup_data)

    # Assert
    assert result == expected_value
```

### Documentation

- Add docstrings to all public functions, classes, and methods
- Follow Google-style docstring format
- Update README.md if adding new features
- Add examples for new functionality

Example docstring:

```python
def my_function(param1: str, param2: int) -> bool:
    """Short description of what the function does.

    Longer description if needed, explaining the behavior
    and any important details.

    Args:
        param1: Description of param1.
        param2: Description of param2.

    Returns:
        Description of the return value.

    Raises:
        ValueError: When param2 is negative.
    """
    pass
```

## Pull Request Process

1. **Update documentation**: Ensure all documentation is up to date
2. **Add tests**: Include tests for new features or bug fixes
3. **Update CHANGELOG.md**: Add an entry describing your changes
4. **Run all checks**: Ensure linting, type checking, and tests pass
5. **Create a pull request**:
   - Use a clear, descriptive title
   - Reference any related issues
   - Describe what changed and why
   - Include screenshots for UI changes (if applicable)

### PR Title Format

Use conventional commit format for PR titles:

- `feat: Add new feature X`
- `fix: Resolve bug in Y`
- `docs: Update documentation for Z`
- `test: Add tests for W`
- `refactor: Improve code structure in V`
- `chore: Update dependencies`

### Code Review

- Be respectful and constructive in code reviews
- Address all review comments
- Request re-review after making changes

## Releasing

Releases are automated by two GitHub Actions workflows (maintainers with
admin permission only):

1. Run the **Prepare Release** workflow (`Actions` → `Prepare Release` →
   `Run workflow`), picking the branch to release from in the branch
   dropdown and a bump type (`major`, `minor`, `patch`, or `prerelease`).
   It bumps the version with `poetry version`, rotates
   `## [Unreleased]` in `CHANGELOG.md` into a dated release section (skipped
   for prereleases), opens a `chore(release): prepare X.Y.Z` PR against the
   chosen branch, and creates a draft `vX.Y.Z` GitHub release.
2. Merge the release PR.
3. Publish the draft release.
4. The **Release** workflow fires on publish and pushes the package to PyPI
   with `poetry publish --build`.

## Reporting Issues

When reporting issues, please include:

1. **Description**: Clear description of the issue
2. **Steps to reproduce**: Detailed steps to reproduce the problem
3. **Expected behavior**: What you expected to happen
4. **Actual behavior**: What actually happened
5. **Environment**:
   - Python version
   - hier-config-ai version
   - OS and version
   - Relevant dependencies
6. **Code samples**: Minimal code to reproduce the issue
7. **Error messages**: Full error messages and stack traces

## Feature Requests

We welcome feature requests! Please:

1. Check if the feature already exists or is planned
2. Clearly describe the feature and its use case
3. Explain why it would be valuable
4. Provide examples if possible

## Code of Conduct

###Our Pledge

We pledge to make participation in our project a harassment-free experience for everyone, regardless of age, body size, disability, ethnicity, gender identity and expression, level of experience, nationality, personal appearance, race, religion, or sexual identity and orientation.

### Our Standards

**Positive behavior includes:**

- Using welcoming and inclusive language
- Being respectful of differing viewpoints
- Gracefully accepting constructive criticism
- Focusing on what is best for the community
- Showing empathy towards other community members

**Unacceptable behavior includes:**

- Trolling, insulting/derogatory comments, and personal attacks
- Public or private harassment
- Publishing others' private information without permission
- Other conduct which could reasonably be considered inappropriate

## Questions?

If you have questions about contributing, please:

- Open a GitHub Discussion
- Check existing issues and discussions
- Reach out to the maintainers

## License

By contributing to hier-config-ai, you agree that your contributions will be licensed under the Apache License 2.0.

Thank you for contributing! 🎉
