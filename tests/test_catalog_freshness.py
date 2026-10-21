"""Drift-map Finding #6 — the committed instrument catalog must stay fresh.

`libraries/catalog.json` is a generated inventory of `libraries/`. Adding,
deleting, or renaming SFZ/sample files can leave it stale with no signal. This
test rescans `libraries/` with the same `Catalog` generator and asserts the
committed inventory still matches (library set + instrument/renderable counts).

It is opportunistic on the *presence* of `libraries/` (gitignored and large; it
exists only where the libraries were built) — but when the libraries ARE present it
FAILS rather than skips, which is the whole point of a freshness guard.
"""
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
LIBS = ROOT / "libraries"
CATALOG = LIBS / "catalog.json"

pytest.importorskip("numpy")


def _have_libraries() -> bool:
    return LIBS.is_dir() and any(LIBS.rglob("*.sfz"))


# `libraries/` is gitignored, so `catalog.json` and `current.txt` exist only
# where the libraries were built; a clone (and CI) has neither and nothing can
# be stale. Asserting presence made `make check` fail on every machine but one.
# Absent → a loud, explicit skip; present → stale or missing inventories FAIL.
requires_libraries = pytest.mark.skipif(
    not _have_libraries(),
    reason="libraries/ (gitignored, built locally) is absent — no catalog to keep fresh")


@requires_libraries
def test_committed_catalog_matches_a_fresh_rescan():
    assert CATALOG.is_file(), (
        "libraries/ is present but libraries/catalog.json is missing — "
        "regenerate it (scripts/catalog_instruments.py)"
    )
    committed = json.loads(CATALOG.read_text())

    from audioforge import AudioForge
    cat = AudioForge().catalog(LIBS)

    live_names = sorted(lib.name for lib in cat.libraries)
    committed_names = sorted(lib["name"] for lib in committed["libraries"])
    assert live_names == committed_names, (
        "library set drifted from libraries/catalog.json (Finding #6): "
        f"added={sorted(set(live_names) - set(committed_names))} "
        f"removed={sorted(set(committed_names) - set(live_names))} — "
        "regenerate the catalog"
    )

    assert len(cat) == committed["instrument_count"], (
        f"instrument_count stale: live {len(cat)} != committed "
        f"{committed['instrument_count']} — regenerate libraries/catalog.json"
    )
    assert len(cat.renderable()) == committed["renderable_count"], (
        f"renderable_count stale: live {len(cat.renderable())} != committed "
        f"{committed['renderable_count']} — regenerate libraries/catalog.json"
    )
    assert len(cat.libraries) == committed["library_count"]


@requires_libraries
def test_current_txt_matches_fresh_tree_snapshot():
    current = LIBS / "current.txt"
    assert current.is_file(), (
        "libraries/current.txt is missing — regenerate it with "
        "`cd libraries && LC_ALL=C tree -a --charset=UTF-8 > current.txt`"
    )
    tree = shutil.which("tree")
    assert tree, "tree executable is required to verify libraries/current.txt"
    fresh = subprocess.run(
        [tree, "-a", "--charset=UTF-8"],
        env={**os.environ, "LC_ALL": "C"},
        cwd=LIBS,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    ).stdout
    assert current.read_text() == fresh, (
        "libraries/current.txt drifted from a fresh `tree -a` snapshot — "
        "regenerate it with `cd libraries && LC_ALL=C tree -a --charset=UTF-8 > current.txt`"
    )


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-q"]))
