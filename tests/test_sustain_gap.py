"""Sampled-sustain-gap detection.

A held note on a non-looping sample that runs out before the note ends decays
to silence the author never wrote. Under the project's "failure should be loud
and local" rule this must surface (warn) or block (forbid), never render
silently.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from audioforge import library as libmod
from audioforge.plan import build_render_plan
from audioforge.sdk import AudioForge
from audioforge.schema import SpecError

_LIB = ("VSCO-2-CE-1.1.0@"
        "ff140e8b5c5d6916ccf8088b0fc7dfb632f434d056aa764400905fdbd5824b0e")
_LIB_DIR = Path(__file__).resolve().parent.parent / "libraries"

pytestmark = pytest.mark.skipif(
    not (_LIB_DIR / "VSCO-2-CE-1.1.0" / "library.manifest.json").exists(),
    reason="VSCO-2-CE library not present")


@pytest.fixture(autouse=True)
def _register_library():
    libmod.add_library_path(_LIB_DIR)


def _spec_src(dur_beats: float) -> str:
    # 60 bpm -> 1 beat == 1 second, so dur_beats is the held seconds.
    return (
        "asset gap_probe {\n"
        "  kind: cue\n"
        "  duration: 60s\n"
        "  tempo: 60bpm\n"
        "  key: C major\n"
        f'  library: "{_LIB}"\n'
        "  layer strs : instrument {\n"
        "    instrument: CelloEnsSusVib\n"
        "    gain: -10db\n"
        f"    notes: C3 @ 0b for {dur_beats}b\n"
        "  }\n"
        "  master {\n"
        "    peak: -1db\n"
        "  }\n"
        "}\n"
    )


def _spec(dur_beats: float, routing: str | None = None) -> dict:
    """Compiled IR spec; ``routing`` is an IR-only policy, not DSL-authored."""
    spec = AudioForge().compile(_spec_src(dur_beats)).assets[0].spec
    if routing:
        spec["routing"] = {"sustain_gaps": routing}
    return spec


def _gap_diags(plan_result):
    return [d for d in plan_result.diagnostics
            if d["code"] == "render_plan_sustain_gap"]


def test_long_hold_warns():
    # A ~7-12s cello sustain sample cannot cover a 40s hold.
    result = build_render_plan(_spec(40))
    gaps = _gap_diags(result)
    assert gaps, "40s hold on a non-looping sample must warn"
    assert gaps[0]["severity"] == "warning"
    assert "silence before the note ends" in gaps[0]["message"]


def test_short_hold_is_clean():
    result = build_render_plan(_spec(2))
    assert not _gap_diags(result), "a 2s hold fits inside the sample"


def test_forbid_blocks_render():
    with pytest.raises(SpecError, match="render_plan_sustain_gap"):
        build_render_plan(_spec(40, routing="forbid"))


def test_allow_is_silent():
    result = build_render_plan(_spec(40, routing="allow"))
    assert not _gap_diags(result), "allow opts out of the advisory"


def test_validate_surfaces_gap():
    asset = AudioForge().compile(_spec_src(40)).assets[0]
    msgs = [d.message for d in asset.validate() if d.severity == "warning"]
    assert any("silence before the note ends" in m for m in msgs)
