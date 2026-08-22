"""Tests for the packaging guard.

The guard exists because 0.1.0 shipped extras that installed nothing, and no
test could see it: the fault was in the built wheel, not in the source.
"""

from __future__ import annotations

from pathlib import Path

import hier_config_ai
from scripts.check_packaging import find_empty_extras

BROKEN = """\
Name: hier-config-gpt
Provides-Extra: all
Provides-Extra: anthropic
Provides-Extra: ollama
Provides-Extra: openai
Requires-Dist: hier-config (>=3.2.0,<4.0.0)
Requires-Dist: pydantic (>=2.9.2,<3.0.0)
"""

FIXED = """\
Name: hier-config-ai
Provides-Extra: all
Provides-Extra: anthropic
Requires-Dist: anthropic (>=1.0.0) ; extra == "anthropic" or extra == "all"
Requires-Dist: pydantic (>=2.12,<3.0)
"""


def test_the_original_broken_metadata_is_caught() -> None:
    """The exact metadata 0.1.0 published is reported as broken."""
    assert find_empty_extras(BROKEN) == ["all", "anthropic", "ollama", "openai"]


def test_correct_metadata_passes() -> None:
    """Extras backed by real requirements are accepted."""
    assert find_empty_extras(FIXED) == []


def test_metadata_without_extras_passes() -> None:
    """A distribution with no extras has nothing to get wrong."""
    assert find_empty_extras("Name: x\nRequires-Dist: pydantic\n") == []


def test_version_is_not_hardcoded_in_the_package() -> None:
    """`__version__` is read from metadata rather than written in the source.

    Releases bump `pyproject.toml` with `poetry version` and nothing updated a
    hardcoded literal, so the two disagreed after every release. Asserting
    `__version__ == version(...)` would only restate the implementation, so
    this checks the source carries no literal instead.
    """
    source = (
        Path(__file__).resolve().parent.parent / "hier_config_ai" / "_version.py"
    ).read_text(encoding="utf-8")
    assert '__version__ = version("hier-config-ai")' in source
    assert hier_config_ai.__version__
