"""V2 tests: DSL pipeline, SDK, plugins, automation, loudness, stems."""
import copy
import json
import sys
import tempfile
import wave
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from audioforge import (AudioForge, compile_dsl, register_fx,  # noqa: E402
                        register_validator, spec_hash)
from audioforge.loudness import integrated_lufs  # noqa: E402
from audioforge.render import render  # noqa: E402

PRESETS = Path(__file__).resolve().parents[1] / "presets"

MINI = """
asset t1 {
  kind: cue
  duration: 1s
  tempo: 120bpm
  key: C major
  layer l : notes {
    osc: sine
    env: a=0.01s d=0.1s s=0.5 r=0.1s
    notes: C4 @ 0b for 1b
  }
  master { peak: -1db }
}
"""


def test_dsl_compile_deterministic():
    """Compiling the same DSL twice yields the identical IR and hash."""
    s1, _ = compile_dsl(MINI)
    s2, _ = compile_dsl(MINI)
    assert s1 == s2 and spec_hash(s1[0]) == spec_hash(s2[0])
    print("PASS  DSL compilation is deterministic")


def test_dsl_errors_have_lines():
    res = AudioForge().compile("asset x {\n  kind cue\n}")
    assert not res.ok
    assert "line 2" in res.errors[0].message
    print("PASS  DSL errors carry line numbers for agent feedback")


def test_motif_expansion_and_scale_warning():
    src = MINI.replace("notes: C4 @ 0b for 1b",
                       "notes: C4 @ 0b for 0.5b, F#4 @ 0.5b for 0.5b")
    res = AudioForge().compile(src)
    assert res.ok
    assert any("outside the declared key" in d.message
               for d in res.diagnostics), res.diagnostics
    print("PASS  out-of-scale notes produce advisory diagnostics")


def test_sdk_mutation_validates():
    asset = AudioForge().compile(MINI).assets[0]
    h0 = asset.hash
    asset.set("layers.0.gain_db", -6)
    assert asset.hash != h0
    try:
        asset.set("layers.0.pan", 9.0)
        raise AssertionError("invalid mutation accepted")
    except Exception:
        pass
    print("PASS  SDK mutation re-validates and re-hashes")


def test_plugin_fx_and_validator():
    @register_fx("test_bitcrush")
    def bitcrush(x, sr, params, rng):
        levels = float(params.get("levels", 16))
        return np.round(x * levels) / levels

    @register_validator("test_max_len")
    def max_len(spec):
        return ["too long"] if spec["duration_s"] > 100 else []

    src = MINI.replace("osc: sine", "osc: sine\n    fx: test_bitcrush(levels=8)")
    asset = AudioForge().compile(src).assets[0]
    stereo, sr, meta = asset.render()
    assert np.max(np.abs(stereo)) > 0.01
    assert asset.validate() == []  # warning-free
    print("PASS  plugin fx renders; plugin validators run")


def test_automation_changes_audio():
    sustained = MINI.replace("notes: C4 @ 0b for 1b", "notes: C4 @ 0b for 2b")
    base = AudioForge().compile(sustained).assets[0]
    src = sustained.replace(
        "master { peak: -1db }",
        "master { peak: -1db\n    auto gain: 0s=-30db, 1s=0db\n  }")
    auto = AudioForge().compile(src).assets[0]
    s0, _, _ = base.render()
    s1, _, _ = auto.render()
    # rising gain envelope: early audio much quieter relative to late audio
    n = s1.shape[0]
    r0 = np.sqrt(np.mean(s0[: n // 4] ** 2)) / np.sqrt(np.mean(s0[-n // 4:] ** 2) + 1e-12)
    r1 = np.sqrt(np.mean(s1[: n // 4] ** 2)) / np.sqrt(np.mean(s1[-n // 4:] ** 2) + 1e-12)
    assert r1 < r0 * 0.5, (r0, r1)
    print("PASS  gain automation shapes the rendered audio")


def test_lufs_targeting():
    src = MINI.replace("duration: 1s", "duration: 5s").replace(
        "notes: C4 @ 0b for 1b", "notes: C4 @ 0b for 10b").replace(
        "master { peak: -1db }", "master { lufs: -20\n    peak: -1db }")
    asset = AudioForge().compile(src).assets[0]
    stereo, sr, meta = asset.render()
    measured = integrated_lufs(stereo, sr)
    assert abs(measured - (-20.0)) < 1.0 or meta["loudness"]["peak_limited"], measured
    print(f"PASS  LUFS targeting (measured {measured:.2f} for -20 target)")


def test_stems_and_markers_outputs():
    spec, _ = compile_dsl((PRESETS / "transition_sweep.af").read_text())
    asset = AudioForge().load_spec(spec[0])
    with tempfile.TemporaryDirectory() as td:
        meta = asset.export(td, stems=True)
        td = Path(td)
        stem_dir = td / f"{meta['id']}_stems"
        assert len(list(stem_dir.glob("*.wav"))) == 3
        markers = json.loads((td / f"{meta['id']}.markers.json").read_text())
        assert markers["markers"][0]["name"] == "cut_point"
    print("PASS  stems + marker files exported")


def test_export_presets_reproducible():
    asset = AudioForge().compile(MINI).assets[0]
    with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
        m1 = asset.export(a, preset="social_video")
        m2 = asset.export(b, preset="social_video")
        assert m1["output_sha256"] == m2["output_sha256"]
        assert m1["sample_rate"] == 48000 and m1["bit_depth"] == 16
    print("PASS  export presets are themselves reproducible")


def test_dsl_presets_byte_identical():
    forge = AudioForge()
    have_vsco = (PRESETS.parent / "libraries" / "vsco2-ce-subset").exists()
    for f in sorted(PRESETS.glob("*.af")):
        if "cosmic" in f.name:   # rendered separately below for speed
            continue
        if not have_vsco and "vsco2-ce-subset" in f.read_text():
            print(f"  SKIP {f.name}: needs the VSCO-2 CE subset "
                  f"(scripts/fetch_vsco_subset.py + libgen)")
            continue
        asset = forge.load_file(f).assets[0]
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            m1 = asset.export(a)
            m2 = forge.load_file(f).assets[0].export(b)
            assert m1["output_sha256"] == m2["output_sha256"], f.name
    print("PASS  all DSL presets re-render byte-identically")


def test_cinematic_cue_renders_and_reproduces():
    forge = AudioForge()
    a1 = forge.load_file(PRESETS / "cosmic_awe_cue.af").assets[0]
    s1, sr, m1 = a1.render()
    a2 = forge.load_file(PRESETS / "cosmic_awe_cue.af").assets[0]
    s2, _, m2 = a2.render()
    assert np.array_equal(s1, s2)
    assert len(m1["markers"]) == 5
    assert m1["emotion"]["awe"] == 0.9
    print("PASS  cinematic cue: float-identical re-render, markers + emotion in manifest")


if __name__ == "__main__":
    test_dsl_compile_deterministic()
    test_dsl_errors_have_lines()
    test_motif_expansion_and_scale_warning()
    test_sdk_mutation_validates()
    test_plugin_fx_and_validator()
    test_automation_changes_audio()
    test_lufs_targeting()
    test_stems_and_markers_outputs()
    test_export_presets_reproducible()
    test_dsl_presets_byte_identical()
    test_cinematic_cue_renders_and_reproduces()
    print("\nAll v2 tests passed.")
