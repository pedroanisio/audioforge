"""Regression guard for drift-risk-map Finding #3 — public quick-start / demo
paths must point at corpora that actually exist.

History: the README advertised `presets/cosmic_awe_cue.af` and a dozen
`presets/*_demo.af` files plus `tests/fixtures/`, none of which shipped, while
the real corpus lives in `docs/examples/sound-design/transition-sweep/` (+ diagnostic fixtures in
`static/fixtures/`). New users following the quick start hit file-not-found,
and corpus-based tests silently skipped on an empty directory.

These tests fail loudly if any README `.af` reference goes dangling again, or
if the canonical corpus loses its render-ready spec.
"""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
SAMPLES = ROOT / "docs" / "examples" / "sound-design" / "transition-sweep"
FIXTURES = ROOT / "docs" / "examples"

_AF_TOKEN = re.compile(r"[A-Za-z0-9_./-]+\.af")


def _af_exists(ref: str) -> bool:
    """A README .af reference resolves if it exists relative to the repo root,
    or — for a bare filename — anywhere in the canonical corpus directories."""
    if (ROOT / ref).exists():
        return True
    if "/" not in ref:
        return (SAMPLES / ref).exists() or any(FIXTURES.rglob(ref))
    return False


def test_readme_af_references_all_exist():
    """Every `.af` path mentioned in the README must resolve to a real file."""
    text = README.read_text()
    refs = sorted(set(_AF_TOKEN.findall(text)))
    assert refs, "expected the README to reference at least one .af spec"
    missing = [r for r in refs if not _af_exists(r)]
    assert not missing, (
        f"README references nonexistent .af paths (Finding #3): {missing}"
    )


def test_canonical_corpus_is_nonempty():
    """The canonical corpus directory must exist and hold at least one spec —
    otherwise corpus-based tests silently no-op."""
    assert SAMPLES.is_dir(), f"canonical corpus {SAMPLES} is missing"
    assert sorted(SAMPLES.glob("*.af")), (
        f"{SAMPLES} has no .af specs — corpus coverage would be a silent no-op"
    )


def test_quickstart_command_path_exists_and_is_render_ready():
    """The exact spec named in the README `validate` quick-start command must
    exist and compile+validate clean — fail loudly, never skip (Finding #3)."""
    text = README.read_text()
    m = re.search(r"audioforge\.cli\s+validate\s+(\S+\.af)", text)
    assert m, "no `cli validate <spec>.af` quick-start command found in README"
    rel = m.group(1)
    spec_path = ROOT / rel
    assert spec_path.exists(), f"quick-start path '{rel}' does not exist"

    pytest.importorskip("numpy")
    from audioforge import AudioForge
    res = AudioForge().compile(spec_path.read_text())
    assert res.ok, [d.message for d in res.diagnostics if d.severity == "error"]
    errs = [d for a in res.assets for d in a.validate() if d.severity == "error"]
    assert not errs, (
        f"quick-start spec '{rel}' is not render-ready: "
        f"{[e.message for e in errs]}"
    )


def test_corpus_has_at_least_one_render_ready_spec():
    """Coverage guard: at least one canonical-corpus spec must compile and
    validate clean, so the determinism/property suites have real material to
    exercise rather than skipping over an empty/broken corpus."""
    pytest.importorskip("numpy")
    from audioforge import AudioForge
    forge = AudioForge()
    ready = 0
    for f in sorted(SAMPLES.glob("*.af")):
        res = forge.compile(f.read_text())
        if res.ok and not any(
            d.severity == "error" for a in res.assets for d in a.validate()
        ):
            ready += 1
    assert ready >= 1, (
        "no render-ready spec in docs/examples/sound-design/transition-sweep — corpus coverage is a "
        "silent no-op (Finding #3)"
    )


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-q"]))
