"""Drift-map Finding #5 — every engine-version literal must agree.

`audioforge/version.py` is the single source of truth. `test_docs_regression`
already locks the docs/README/release-note banners to it; this test closes the
remaining mirrors the report named: `pyproject.toml`, the `audioforge/score.py`
provenance fallback, the runtime hashing constant, and the render manifest.
A render-affecting engine bump that updates one but not the others fails here.
"""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

pytest.importorskip("numpy")
from audioforge import version as _v  # noqa: E402
from audioforge import determinism as _det  # noqa: E402

TRUTH = _v.ENGINE_VERSION


def test_pyproject_version_matches_source_of_truth():
    text = (ROOT / "pyproject.toml").read_text()
    m = re.search(r'(?m)^\s*version\s*=\s*"([^"]+)"', text)
    assert m, "no [project] version in pyproject.toml"
    assert m.group(1) == TRUTH, (
        f"pyproject version {m.group(1)!r} != version.ENGINE_VERSION {TRUTH!r}"
    )


def test_runtime_hashing_constant_matches():
    assert _det.ENGINE_VERSION == TRUTH


def test_score_provenance_fallback_literal_matches():
    """score.py keeps a defensive fallback literal for when determinism cannot
    be imported; it must not silently drift from the real version."""
    src = (ROOT / "audioforge" / "score.py").read_text()
    # the fallback assignment: `ENGINE_VERSION = "X"` inside the except branch
    lits = re.findall(r'ENGINE_VERSION\s*=\s*"([^"]+)"', src)
    assert lits, "expected a fallback `ENGINE_VERSION = \"...\"` literal in score.py"
    for lit in lits:
        assert lit == TRUTH, (
            f"score.py fallback literal {lit!r} != {TRUTH!r} (Finding #5)"
        )


def test_capability_manifest_engine_version_matches():
    from audioforge import capability_manifest
    assert capability_manifest()["engine_version"] == TRUTH


def test_render_manifest_engine_version_matches(tmp_path):
    """A real (tiny) render must stamp the manifest with the same version."""
    from audioforge import AudioForge
    dsl = (
        "asset v_probe {\n"
        "  kind: cue\n  duration: 0.25s\n  tempo: 120bpm\n  key: C major\n"
        "  layer l : notes { osc: sine\n    env: a=0.01s d=0.05s s=0.5 r=0.05s\n"
        "    notes: C4 @ 0b for 0.5b }\n}\n"
    )
    res = AudioForge().compile(dsl)
    assert res.ok, [d.message for d in res.diagnostics if d.severity == "error"]
    meta = res.assets[0].export(str(tmp_path))
    assert meta["engine_version"] == TRUTH


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-q"]))
