"""Canonical DSL corpus, independent of Git's staging state and local renders."""
import json
from pathlib import Path


def source_paths(root: Path) -> list[Path]:
    catalog = json.loads((root / "docs/examples/catalog.json").read_text())
    paths = {root / item["source"] for item in catalog["examples"]}
    for directory in ("static/fixtures", "tests/golden/audio", "tests/fixtures"):
        paths.update((root / directory).rglob("*.af"))
    assert paths, "the DSL corpus must not silently become empty"
    for path in paths:
        assert path.is_file(), f"missing cataloged DSL source: {path}"
    return sorted(paths)
