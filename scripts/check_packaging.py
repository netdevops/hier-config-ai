"""Check that every declared extra actually publishes its requirements.

Poetry accepts `[tool.poetry.extras]` entries that point at packages declared
only in optional *groups*. Groups are a development-time construct and are
never published, so the built wheel ends up advertising extras that install
nothing. Version 0.1.0 shipped that way: `pip install hier-config-ai[all]`
brought in no provider SDK at all.

The test suite cannot catch this, because the fault is in the built artifact
rather than in the source. Run this after `poetry build`.
"""

from __future__ import annotations

import re
import sys
import zipfile
from pathlib import Path

EXTRA_MARKER = re.compile(r'extra == "([^"]+)"')
PROVIDES_EXTRA = re.compile(r"^Provides-Extra: (.+)$", re.MULTILINE)
REQUIRES_DIST = re.compile(r"^Requires-Dist: .+$", re.MULTILINE)


def read_metadata(wheel: Path) -> str:
    """Return the METADATA document from a built wheel."""
    with zipfile.ZipFile(wheel) as archive:
        name = next(n for n in archive.namelist() if n.endswith("METADATA"))
        return archive.read(name).decode()


def find_empty_extras(metadata: str) -> list[str]:
    """Return extras that are advertised but carry no requirements."""
    provided = {extra.strip() for extra in PROVIDES_EXTRA.findall(metadata)}

    satisfied: set[str] = set()
    for line in REQUIRES_DIST.findall(metadata):
        satisfied.update(EXTRA_MARKER.findall(line))

    return sorted(provided - satisfied)


def main() -> int:
    """Check the most recently built wheel and report the result."""
    wheels = sorted(Path("dist").glob("*.whl"))
    if not wheels:
        print("No wheel found in dist/. Run `poetry build` first.")
        return 1

    wheel = wheels[-1]
    empty = find_empty_extras(read_metadata(wheel))

    if empty:
        print(f"{wheel.name}: these extras install nothing: {', '.join(empty)}")
        print("Declare the packages in [tool.poetry.dependencies] with")
        print("optional = true, then reference them from [tool.poetry.extras].")
        return 1

    print(f"{wheel.name}: every extra publishes its requirements.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
