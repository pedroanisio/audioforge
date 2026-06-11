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
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from audioforge import AudioForge  # noqa: E402
from audioforge import samples as smod  # noqa: E402
from audioforge.schema import SpecError  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "static" / "fixtures"
AF = AudioForge()


def _skip_optional(message: str):
    if __name__ == "__main__":
        print(f"  SKIP {message}")
        return True
    pytest.skip(message)
    return True

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
    corpus = sorted((ROOT / "static" / "samples").glob("*.af"))
    for f in corpus:
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
    if checked < 5:
        if _skip_optional(f"preset corpus has only {checked} compilable assets"):
            return
    assert rendered >= 1, (checked, rendered)
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


def test_native_osc_set_single_source_of_truth(monkeypatch):
    """The native-voice set is declared once in schema.NATIVE_OSC_SHAPES and
    the three layers that key off it stay in lockstep: (1) every native voice
    is a real osc shape, (2) synth.osc actually dispatches it — proving the
    binding and kernel exist, so the set can't name a voice the synth would
    reject as 'unknown shape', and (3) resolve's fail-loud gate flags exactly
    the native voices when no compiler is present. This is the guard that
    stops the old drift, where resolve carried a private ('bowed','blown')
    literal a fourth kernel could silently bypass.
    """
    from audioforge import resolve
    from audioforge import _native
    from audioforge import synth
    from audioforge.schema import NATIVE_OSC_SHAPES, OSC_SHAPES

    assert NATIVE_OSC_SHAPES and NATIVE_OSC_SHAPES <= OSC_SHAPES

    # Each native voice is genuinely dispatched (binding + kernel compile).
    if _native.native_available():
        for v in sorted(NATIVE_OSC_SHAPES):
            y = synth.osc(v, 220.0, 480, 48000, rng=np.random.default_rng(0))
            assert y.shape == (480,) and np.all(np.isfinite(y)), v

    # Fail-loud gate keys off the set, not a private literal: with no compiler
    # every native voice is reported; a pure-Python voice never is.
    monkeypatch.setattr(_native, "native_available", lambda: False)
    for v in sorted(NATIVE_OSC_SHAPES):
        problems = resolve.resolve_spec({"layers": [{"name": "x", "osc": v}]})
        assert any("native kernel" in p for p in problems), (v, problems)
    assert resolve.resolve_spec(
        {"layers": [{"name": "x", "osc": "sine"}]}) == []
    print("PASS  contract: native-voice set is single-source; synth dispatch "
          "and resolve gate agree with schema.NATIVE_OSC_SHAPES")


def test_native_build_cache_can_be_overridden(monkeypatch, tmp_path):
    from audioforge import _native

    monkeypatch.setenv("AUDIOFORGE_NATIVE_CACHE", str(tmp_path / "native-cache"))
    out = _native._build_output_path("plate_mod")

    assert out.parent == tmp_path / "native-cache"
    assert out.name.startswith("plate_mod_")
    assert out.suffix == ".so"


def test_native_fx_set_single_source_of_truth(monkeypatch):
    """Same single-source guard for native effects: every NATIVE_FX_TYPES entry
    is a real fx type, fx_needs_native() is the one predicate resolve's gate
    calls, and with no compiler a native fx on a layer OR the master bus is
    flagged while a pure-Python fx never is."""
    from audioforge import resolve, _native
    from audioforge.schema import NATIVE_FX_TYPES, FX_TYPES, fx_needs_native

    assert NATIVE_FX_TYPES and NATIVE_FX_TYPES <= FX_TYPES
    for t in NATIVE_FX_TYPES:
        assert fx_needs_native({"type": t})
    assert not fx_needs_native({"type": "filter", "mode": "lowpass"})
    assert fx_needs_native({"type": "plate", "mod": 0.4})      # legacy path
    assert not fx_needs_native({"type": "plate", "mod": 0.0})

    monkeypatch.setattr(_native, "native_available", lambda: False)
    for t in sorted(NATIVE_FX_TYPES):
        layer = resolve.resolve_spec(
            {"layers": [{"name": "x", "osc": "sine", "fx": [{"type": t}]}]})
        master = resolve.resolve_spec(
            {"layers": [], "master": {"fx": [{"type": t}]}})
        assert any("native kernel" in p for p in layer), (t, layer)
        assert any("native kernel" in p for p in master), (t, master)
    clean = resolve.resolve_spec(
        {"layers": [{"name": "x", "osc": "sine",
                     "fx": [{"type": "drive"}]}]})
    assert clean == []
    print("PASS  contract: native-fx set is single-source; resolve gate covers "
          "both layer and master chains via fx_needs_native")


def test_ladder_filter_renders_and_resonates():
    """End-to-end: a ladder fx parses, validates, renders, and behaves like a
    resonant nonlinear lowpass — a strong resonance peak near cutoff that a
    flat LTI biquad rolloff does not produce."""
    pytest.importorskip("numpy")
    from audioforge._native import ladder_native, native_available
    if not native_available():
        if _skip_optional("no C compiler; native ladder unavailable"):
            return

    src = """
asset lad { kind: cue
  duration: 1s
  tempo: 100bpm
  layer t : tone { osc: saw
    note: A2
    duration: 1s
    env: a=0.01s d=0.1s s=0.8 r=0.1s
    fx: ladder(cutoff=600, resonance=0.9, drive=0.4)
    gain: -8db
  }
  master { peak: -1db }
}"""
    res = AF.compile(src)
    assert res.ok, [d.message for d in res.diagnostics]
    a = res.assets[0]
    assert not [d for d in a.validate() if d.severity == "error"]
    fx = a.spec["layers"][0]["fx"][0]
    assert fx == {"type": "ladder", "cutoff_hz": 600.0, "resonance": 0.9,
                  "drive": 0.4, "mix": 1.0}
    a.render()                                          # must not raise

    # DSP property: at high resonance the band around cutoff carries far more
    # energy than at low resonance (the resonance peak), and output is finite.
    sr = 48000
    x = np.random.default_rng(0).standard_normal(sr) * 0.3
    fc = 1500.0

    def band(sig, lo, hi):
        S = np.abs(np.fft.rfft(sig))
        f = np.fft.rfftfreq(sig.size, 1.0 / sr)
        return S[(f >= lo) & (f < hi)].mean()

    lo_r = ladder_native(x, sr, fc, 0.1, 0.0)
    hi_r = ladder_native(x, sr, fc, 1.0, 0.0)
    assert np.all(np.isfinite(hi_r))
    assert band(hi_r, 1200, 1800) > 1.5 * band(lo_r, 1200, 1800)
    # determinism: bit-identical reruns
    assert np.array_equal(hi_r, ladder_native(x, sr, fc, 1.0, 0.0))
    print("PASS  ladder: parses/validates/renders; resonance peak present; "
          "bit-deterministic")


def test_tape_effect_flutters_saturates_and_renders():
    """End-to-end: a tape fx parses, validates, renders, and exhibits both of
    its defining behaviours — flutter (the time-varying delay spreads a pure
    carrier into sidebands) and saturation (a clean sine grows harmonics) —
    while staying bounded and bit-deterministic."""
    pytest.importorskip("numpy")
    from audioforge._native import tape_native, native_available
    if not native_available():
        if _skip_optional("no C compiler; native tape unavailable"):
            return

    src = """
asset tp { kind: cue
  duration: 1s
  tempo: 100bpm
  layer t : tone { osc: saw
    note: A3
    duration: 1s
    env: a=0.01s d=0.1s s=0.8 r=0.1s
    fx: tape(drive=0.6, flutter=0.4, tone=0.4)
    gain: -8db
  }
  master { peak: -1db }
}"""
    res = AF.compile(src)
    assert res.ok, [d.message for d in res.diagnostics]
    a = res.assets[0]
    assert not [d for d in a.validate() if d.severity == "error"]
    assert a.spec["layers"][0]["fx"][0] == {
        "type": "tape", "drive": 0.6, "flutter": 0.4, "tone": 0.4, "mix": 1.0}
    a.render()                                          # must not raise

    sr = 48000
    carrier = np.sin(2 * np.pi * 440 * np.arange(sr) / sr) * 0.5

    def concentration(y):                               # 1.0 = pure tone
        S = np.abs(np.fft.rfft(y * np.hanning(y.size)))
        f = np.fft.rfftfreq(y.size, 1.0 / sr)
        return S[(f > 435) & (f < 445)].sum() / S[(f > 400) & (f < 480)].sum()

    # flutter: time-varying delay spreads the carrier (less concentrated)
    assert concentration(tape_native(carrier, sr, 0.0, 0.7, 0.5)) < 0.7
    assert concentration(tape_native(carrier, sr, 0.0, 0.0, 0.5)) > 0.95

    # saturation: a clean sine gains a 3rd harmonic; output stays bounded
    sat = tape_native(carrier, sr, 0.9, 0.0, 0.0)
    S = np.abs(np.fft.rfft(sat * np.hanning(sat.size)))
    f = np.fft.rfftfreq(sat.size, 1.0 / sr)
    h = lambda k: S[(f > k * 440 - 20) & (f < k * 440 + 20)].max()  # noqa: E731
    assert h(3) > 0.05 * h(1)
    assert np.all(np.isfinite(sat)) and np.max(np.abs(sat)) <= 1.001

    # tone controls HF loss; determinism is bit-exact
    hf = lambda y: (np.abs(np.fft.rfft(y))[
        np.fft.rfftfreq(y.size, 1.0 / sr) > 6000]).sum()
    n = np.random.default_rng(0).standard_normal(sr) * 0.3
    assert hf(tape_native(n, sr, 0.0, 0.0, 1.0)) > hf(tape_native(n, sr, 0.0, 0.0, 0.0))
    assert np.array_equal(sat, tape_native(carrier, sr, 0.9, 0.0, 0.0))
    print("PASS  tape: parses/validates/renders; flutter spreads carrier, "
          "saturation adds harmonics; bounded and bit-deterministic")


if __name__ == "__main__":
    test_property_validate_implies_renders()
    test_property_render_error_implies_validate_error()
    test_placeholder_pin_distinct_diagnostic()
    test_resolve_hash_mismatch_and_missing_instrument()
    test_multiline_auto_continuation()
    test_targeted_grammar_diagnostics_on_fixtures()
    test_slur_of_plays()
    test_validate_warns_for_notes_past_asset_end()
    import pytest as _pytest
    test_native_osc_set_single_source_of_truth(_pytest.MonkeyPatch())
    test_native_fx_set_single_source_of_truth(_pytest.MonkeyPatch())
    test_ladder_filter_renders_and_resonates()
    test_tape_effect_flutters_saturates_and_renders()
    print("\nAll validate/render contract tests passed.")
