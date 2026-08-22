"""The installed distribution version.

Read from package metadata rather than written here, because releases bump
`pyproject.toml` with `poetry version` and nothing updates a hardcoded literal.
The two drifted apart on every release before this.
"""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("hier-config-ai")
except PackageNotFoundError:  # pragma: no cover - source tree, nothing installed
    __version__ = "0.0.0"
