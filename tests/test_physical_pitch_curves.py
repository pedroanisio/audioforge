"""Pitch curves on physical-model voices (varispeed semantics).

Physical models cannot retune their resonators mid-note, so the engine
realises pitch curves on them by deterministic variable-rate resampling of
the rendered voice (tape semantics): the scheduled duration is preserved and
the read rate follows 2**(cents/1200). Synth voices keep oscillator-level
retuning. These tests pin both the compile acceptance and the audible drop.
"""
import numpy as np

from audioforge import AudioForge
from audioforge.sequencer import TempoMap, render_note_track


def _base_track(note="A4", curves=None, osc="bowed"):
    ev = {"note": note, "start_beat": 0.0, "dur_beats": 2.0}
    if curves:
        ev["curves"] = curves
    return {
        "type": "notes",
        "osc": osc,
        "env": {"attack": 0.001, "decay": 0.01, "sustain": 1.0,
                "release": 0.01},
        "notes": [ev],
    }


def _peak_hz(signal, sr):
    """Dominant frequency above 30 Hz (physical voices may carry DC offset)."""
    sig = signal - np.mean(signal)
    spectrum = np.abs(np.fft.rfft(sig * np.hanning(sig.size)))
    freqs = np.fft.rfftfreq(sig.size, 1.0 / sr)
    spectrum[freqs < 30.0] = 0.0
    return float(freqs[int(np.argmax(spectrum))])


DROP = [{"target": "pitch_cents", "time_basis": "note_seconds",
         "points": [[0.0, 0.0], [1.0, -1200.0]]}]


def test_compile_accepts_pitch_curve_on_physical_voice():
    src = """
asset tape_drop {
  kind: cue
  duration: 3s
  tempo: 120bpm
  layer cello : notes {
    osc: bowed
    env: a=0.01s d=0.1s s=0.8 r=0.2s
    notes: A3 @ 0b for 2b
    auto pitch_cents: 0s=0, 1s=-1200
  }
}
"""
    result = AudioForge().compile(src)
    assert result.ok, [d.message for d in result.diagnostics]
    layer = result.assets[0].spec["layers"][0]
    targets = [a["target"] for a in layer.get("automation", [])]
    assert "pitch_cents" in targets


def test_compile_accepts_note_pitch_curve_on_physical_voice():
    src = """
asset bend_note {
  kind: cue
  duration: 3s
  tempo: 120bpm
  layer horn : notes {
    osc: brass
    env: a=0.02s d=0.1s s=0.8 r=0.2s
    vibrato: rate=5hz depth=30c delay=0.1s
    notes: C3 @ 0b for 2b
  }
}
"""
    result = AudioForge().compile(src)
    assert result.ok, [d.message for d in result.diagnostics]
    note = result.assets[0].spec["layers"][0]["notes"][0]
    assert any(c["target"] == "pitch_cents" for c in note.get("curves", []))


def test_render_physical_pitch_drop_lowers_frequency_and_keeps_length():
    sr = 16000
    tm = TempoMap([[0.0, 120.0]])
    total = int(1.1 * sr)          # the 1.0 s note ends inside the render
    plain = render_note_track(_base_track(), total, sr, tm)
    dropped = render_note_track(_base_track(curves=DROP), total, sr, tm)
    assert dropped.size == plain.size
    early = slice(int(0.10 * sr), int(0.40 * sr))
    late = slice(int(0.62 * sr), int(0.92 * sr))
    assert _peak_hz(plain[late], sr) > _peak_hz(plain[early], sr) * 0.9
    drop_ratio = _peak_hz(dropped[late], sr) / _peak_hz(dropped[early], sr)
    assert drop_ratio < 0.75


def test_render_physical_pitch_curve_is_deterministic():
    sr = 8000
    tm = TempoMap([[0.0, 120.0]])
    a = render_note_track(_base_track(curves=DROP), sr, sr, tm)
    b = render_note_track(_base_track(curves=DROP), sr, sr, tm)
    assert np.array_equal(a, b)


def test_render_struck_pitch_drop_also_supported():
    sr = 8000
    tm = TempoMap([[0.0, 120.0]])
    plain = render_note_track(_base_track(osc="struck"), sr, sr, tm)
    dropped = render_note_track(_base_track(osc="struck", curves=DROP),
                                sr, sr, tm)
    assert dropped.size == plain.size
    assert not np.array_equal(dropped, plain)
