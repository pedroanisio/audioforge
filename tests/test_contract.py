"""The validate/render contract (v2.14, from the 2026-06-10 review).

Property under test: **if validate() returns no errors, render() succeeds;
if render() raises a SpecError, validate() already reported it.** Plus the
resolve pass's specific diagnostics — placeholder pins, missing libraries
and instruments, hash mismatches — and the DSL ergonomics fixes (multiline
auto, targeted notes:/play diagnostics, slur-of-plays), exercised against
the review's three fixtures where applicable.
"""
import io
import sys
import wave as wavemod
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from audioforge import AudioForge  # noqa: E402
from audioforge import samples as smod  # noqa: E402
from audioforge.schema import SpecError  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).resolve().parent / "fixtures"
AF = AudioForge()

MINI = """
asset c_{n} {{ kind: cue
  duration: 3s
  tempo: 100bpm
  layer t : tone {{ osc: sine
    note: A4
    duration: 1s
    env: a=0.01s d=0.1s s=0.8 r=0.1s
    gain: -10db {extra}
  }}
  master {{ peak: -1db }}
}}
"""


def _wav_bytes():
    buf = io.BytesIO()
    with wavemod.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(48000)
        w.writeframes((np.zeros(4800) + 0.1 * 32767).astype("<i2").tobytes())
    return buf.getvalue()


def test_property_validate_implies_renders():
    """Over the preset corpus: no validate errors => render succeeds."""
    have_vsco = (ROOT / "libraries" / "vsco2-ce-subset").exists()
    checked = rendered = 0
    for f in sorted((ROOT / "presets").glob("*.af")):
        if not have_vsco and "vsco2-ce-subset" in f.read_text():
            continue
        res = AF.compile(f.read_text())
        if not res.ok:
            continue
        for asset in res.assets:
            checked += 1
            errs = [d for d in asset.validate() if d.severity == "error"]
            if errs:
                continue
            if asset.spec["duration_s"] > 12 or rendered >= 3:
                continue                            # keep the suite fast
            asset.render()                          # must not raise
            rendered += 1
    assert checked >= 5 and rendered >= 1, (checked, rendered)
    print(f"PASS  property: {checked} preset assets validated; every "
          f"clean one that was rendered ({rendered}) rendered without error")


def test_property_render_error_implies_validate_error():
    """Mutated specs: when render raises SpecError, validate said so."""
    pin0 = "0" * 64
    mutants = [
        MINI.format(n=1, extra="") .replace(
            "layer t : tone {", "library: \"nolib@" + pin0 + "\"\n"
            "  layer t : tone {"),
        MINI.format(n=2, extra="\n    fx: convolve(file=\"missing_ir.wav\", "
                    "sha256=\"" + "1" * 64 + "\")"),
    ]
    for src in mutants:
        res = AF.compile(src)
        assert res.ok, [d.message for d in res.diagnostics]
        a = res.assets[0]
        v_errs = [d.message for d in a.validate() if d.severity == "error"]
        try:
            a.render()
            raised = None
        except SpecError as e:
            raised = str(e)
        except Exception as e:                     # raw escape = failure
            raise AssertionError(f"raw exception escaped render: "
                                 f"{type(e).__name__}: {e}")
        if raised:
            assert v_errs, f"render raised but validate was clean: {raised}"
    print("PASS  property: render-time SpecErrors are pre-reported by "
          "validate; no raw exceptions escape")


def test_placeholder_pin_distinct_diagnostic():
    src = MINI.format(n=3, extra="").replace(
        "layer t : tone {",
        "library: \"vstobaroque@" + "0" * 64 + "\"\n  layer t : tone {")
    a = AF.compile(src).assets[0]
    msgs = [d.message for d in a.validate() if d.severity == "error"]
    assert any("unbound placeholder" in m for m in msgs), msgs
    print("PASS  placeholder pins get the distinct 'unbound placeholder' "
          "diagnostic, not a generic not-found")


def test_resolve_hash_mismatch_and_missing_instrument():
    sha = smod.register_sample("contract_probe.wav", _wav_bytes())
    bad = MINI.format(
        n=4, extra="\n    fx: convolve(file=\"contract_probe.wav\", "
        "sha256=\"" + "ab12" * 16 + "\")")
    a = AF.compile(bad).assets[0]
    msgs = [d.message for d in a.validate() if d.severity == "error"]
    assert any("hash mismatch" in m for m in msgs), msgs
    good = MINI.format(
        n=5, extra="\n    fx: convolve(file=\"contract_probe.wav\", "
        "sha256=\"" + sha + "\")")
    a2 = AF.compile(good).assets[0]
    assert not [d for d in a2.validate() if d.severity == "error"]
    print("PASS  resolve: IR hash mismatch reported with both hashes; "
          "correct pin passes")


def test_multiline_auto_continuation():
    src = MINI.format(n=6, extra="\n    auto gain: 0s=-20db, 1s=-12db,\n"
                      "               2s=-8db, 3s=-20db")
    res = AF.compile(src)
    assert res.ok, [d.message for d in res.diagnostics]
    auto = [a for a in res.assets[0].spec["layers"][0]["automation"]
            if a["target"] == "gain_db"][0]
    assert len(auto["points"]) == 4
    print("PASS  auto: comma-newline continuation parses (4 breakpoints)")


def test_targeted_grammar_diagnostics_on_fixtures():
    for fx, frag in (("bwv949.af", "layer-body lines"),
                     ("unser_leben.af", "layer-body lines")):
        res = AF.compile((FIXTURES / fx).read_text())
        assert not res.ok
        msgs = " ".join(d.message for d in res.diagnostics)
        assert frag in msgs, (fx, msgs[:200])
    print("PASS  fixtures: the notes:/play trap now explains itself with "
          "the fix, on both fixtures that hit it")


def test_slur_of_plays():
    src = """
asset sp { kind: cue
  duration: 6s
  tempo: 100bpm
  key: C major
  motif m { C4 @ 0b for 1b
            E4 @ 1b for 1b }
  layer v : notes { osc: sine
    env: a=0.01s d=0.1s s=0.8 r=0.1s
    notes: slur(
      play m @ 0b,
      play m @ 4b diatonic +1
    ), G4 @ 9b for 1b
  }
  master { peak: -1db }
}"""
    res = AF.compile(src)
    assert res.ok, [d.message for d in res.diagnostics]
    evs = res.assets[0].spec["layers"][0]["notes"]
    ids = {e.get("slur") for e in evs if e["start_beat"] < 9}
    assert len(ids) == 1 and None not in ids        # one shared group
    assert [e.get("slur") for e in evs if e["start_beat"] >= 9] == [None]
    print("PASS  slur(play …): motif expansions share one slur group; "
          "notes outside stay unslurred")


def test_validate_warns_for_notes_past_asset_end():
    src = """
asset late { kind: cue
  duration: 1s
  tempo: 60bpm
  layer v : notes { osc: sine
    env: a=0.01s d=0.1s s=0.8 r=0.1s
    notes: C4 @ 2b for 1b
  }
  master { peak: -1db }
}"""
    asset = AF.compile(src).assets[0]
    warnings = [d for d in asset.validate() if d.severity == "warning"]
    assert any("extends past asset duration" in d.message
               and d.path == "layers.0.notes.0" for d in warnings)
    print("PASS  validate: note events beyond asset duration produce a "
          "structured warning")


if __name__ == "__main__":
    test_property_validate_implies_renders()
    test_property_render_error_implies_validate_error()
    test_placeholder_pin_distinct_diagnostic()
    test_resolve_hash_mismatch_and_missing_instrument()
    test_multiline_auto_continuation()
    test_targeted_grammar_diagnostics_on_fixtures()
    test_slur_of_plays()
    test_validate_warns_for_notes_past_asset_end()
    print("\nAll validate/render contract tests passed.")
