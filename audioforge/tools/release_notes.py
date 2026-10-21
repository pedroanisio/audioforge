"""Release tag gate + notes extractor (used by `.github/workflows/release.yml`).

Release tags follow `engine-X.Y.Z` (and `dsl-X.Y`; HARNESS-REL-003). A release
built from a tag that disagrees with `audioforge/version.py` would publish one
version under another's name, so the tag is checked against the single source
of truth before anything is built, and the release body is the matching
`CHANGELOG.md` section — never hand-written at release time.

    python -m audioforge.tools.release_notes --tag engine-3.3.0   # gate + print notes
    python -m audioforge.tools.release_notes --version 3.3.0      # print notes only
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CHANGELOG = ROOT / "CHANGELOG.md"

_TAG_RE = re.compile(r"(?:refs/tags/)?engine-([0-9]+\.[0-9]+\.[0-9]+)")


def tag_version(tag: str) -> str:
    m = _TAG_RE.fullmatch(tag)
    if not m:
        raise ValueError(f"{tag!r} is not an engine release tag (engine-X.Y.Z)")
    return m.group(1)


def section(changelog: str, version: str) -> str:
    """Body of `## [version]` up to the next `## [` heading, stripped."""
    m = re.search(rf"(?m)^## \[{re.escape(version)}\][^\n]*\n(.*?)(?=^## \[|\Z)",
                  changelog, re.S)
    if not m or not m.group(1).strip():
        raise LookupError(f"CHANGELOG.md has no non-empty section for [{version}]")
    return m.group(1).strip() + "\n"


def main(argv: list[str] | None = None) -> int:
    from audioforge.version import ENGINE_VERSION

    parser = argparse.ArgumentParser(prog="python -m audioforge.tools.release_notes",
                                     description=__doc__.splitlines()[0])
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--tag", help="release tag; must equal engine-<ENGINE_VERSION>")
    group.add_argument("--version", help="print the notes for this version")
    args = parser.parse_args(argv)
    try:
        version = tag_version(args.tag) if args.tag else args.version
        if args.tag and version != ENGINE_VERSION:
            raise ValueError(f"tag {args.tag} != engine-{ENGINE_VERSION} "
                             f"(ENGINE_VERSION in audioforge/version.py)")
        notes = section(CHANGELOG.read_text(encoding="utf-8"), version)
    except (ValueError, LookupError) as e:
        print(f"release-notes: {e}", file=sys.stderr)
        return 1
    sys.stdout.write(notes)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
