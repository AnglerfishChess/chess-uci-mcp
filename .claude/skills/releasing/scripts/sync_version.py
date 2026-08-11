#!/usr/bin/env python3
"""
Propagate the version in pyproject.toml into the files that repeat it.

`pyproject.toml` is the single source of truth; every other occurrence is a copy
that can go stale. The copies are declared once, in `HOMES` below, and both
modes -- rewrite and `--check` -- walk that same declaration, so adding a new
place the version lives means adding one line rather than another branch.

    python .claude/skills/releasing/scripts/sync_version.py          # rewrite the copies
    python .claude/skills/releasing/scripts/sync_version.py --check  # exit 1 if any is stale

`uv.lock` is deliberately absent: `uv sync` owns it.

Kept free of tomllib so it runs on the project's own 3.10 floor, where that
module does not exist yet.
"""

import json
import re
import sys
from pathlib import Path

# .claude/skills/releasing/scripts/sync_version.py -> four levels up is the repository root.
ROOT = Path(__file__).resolve().parents[4]
PYPROJECT = ROOT / "pyproject.toml"


class TextHome:
    """A version copy matched by a regex whose single group is the version."""

    def __init__(self, path: Path, pattern: str, label: str):
        self.path = path
        self.pattern = re.compile(pattern, re.MULTILINE)
        self.label = label

    def current(self) -> list[tuple[str, str]]:
        text = self.path.read_text(encoding="utf-8")
        found = self.pattern.findall(text)
        if not found:
            sys.exit(f"{self.path.relative_to(ROOT)}: no match for {self.pattern.pattern}")
        return [(self.label, value) for value in found]

    def apply(self, version: str) -> None:
        text = self.path.read_text(encoding="utf-8")
        rewritten = self.pattern.sub(
            lambda m: m.group(0).replace(m.group(1), version), text
        )
        self.path.write_text(rewritten, encoding="utf-8")


class JsonHome:
    """Version copies at fixed keys of a JSON document.

    `server.json` names the version twice: once for the server and once for the
    PyPI package, which the MCP registry resolves against a real published
    release. Both must move together.
    """

    def __init__(self, path: Path):
        self.path = path

    def _sites(self, document: dict) -> list[tuple[str, dict, str]]:
        sites = [("version", document, "version")]
        for index, package in enumerate(document.get("packages", [])):
            sites.append((f"packages[{index}].version", package, "version"))
        return sites

    def current(self) -> list[tuple[str, str]]:
        document = json.loads(self.path.read_text(encoding="utf-8"))
        return [(label, holder.get(key)) for label, holder, key in self._sites(document)]

    def apply(self, version: str) -> None:
        document = json.loads(self.path.read_text(encoding="utf-8"))
        for _, holder, key in self._sites(document):
            holder[key] = version
        self.path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")


HOMES = [
    TextHome(ROOT / "chess_uci_mcp" / "__init__.py", r'^__version__ = "([^"]*)"', "__version__"),
    JsonHome(ROOT / "server.json"),
]


def source_of_truth() -> str:
    """Read `version` from the [project] table, ignoring every other table's."""
    in_project = False
    for line in PYPROJECT.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            in_project = stripped == "[project]"
            continue
        if in_project:
            match = re.match(r'version\s*=\s*"([^"]+)"', stripped)
            if match:
                return match.group(1)
    sys.exit(f"No version found in the [project] table of {PYPROJECT}")


def main() -> None:
    check = "--check" in sys.argv[1:]
    version = source_of_truth()

    stale = [
        (home, label, found)
        for home in HOMES
        for label, found in home.current()
        if found != version
    ]

    if check:
        if stale:
            print(f"Stale against pyproject.toml ({version}):", file=sys.stderr)
            for home, label, found in stale:
                print(f"  {home.path.relative_to(ROOT)}: {label} is {found!r}", file=sys.stderr)
            print("Run: python .claude/skills/releasing/scripts/sync_version.py", file=sys.stderr)
            sys.exit(1)
        print(f"All {version} copies agree with pyproject.toml")
        return

    for home in {id(home): home for home, _, _ in stale}.values():
        home.apply(version)
    for home, label, found in stale:
        print(f"{home.path.relative_to(ROOT)}: {label} {found!r} -> {version!r}")
    if not stale:
        print(f"Already at {version}; nothing to update")


if __name__ == "__main__":
    main()
