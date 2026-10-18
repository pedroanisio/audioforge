"""Layer-scope `pitch_cents` automation must be rendered on notes layers.

The IR keeps layer-scope pitch automation at layer scope (DSL_SPEC §curves);
the notes path multiplies it into every note's pitch-ratio envelope, for
synth and physical voices alike. A layer ride over a note starting at 0 s is
sample-for-sample the note-scope curve with the same points, so the two
renders must be byte-identical.
"""
import numpy as np

from audioforge.sequencer import TempoMap, render_note_track


def _track(osc, automation=None, curves=None):
    ev = {"note": "A4", "start_beat": 0.0, "dur_beats": 2.0}
    if curves:
        ev["curves"] = curves
    track = {
        "type": "notes",
        "osc": osc,
        "env": {"attack": 0.001, "decay": 0.01, "sustain": 1.0,
                "release": 0.01},
        "notes": [ev],
    }
    if automation:
        track["automation"] = automation
    return track


DROP_LAYER = [{"target": "pitch_cents",
               "points": [[0.0, 0.0], [1.0, -1200.0]]}]
DROP_NOTE = [{"target": "pitch_cents", "time_basis": "note_seconds",
              "points": [[0.0, 0.0], [1.0, -1200.0]]}]


def _peak_hz(signal, sr):
    sig = signal - np.mean(signal)
    spectrum = np.abs(np.fft.rfft(sig * np.hanning(sig.size)))
    freqs = np.fft.rfftfreq(sig.size, 1.0 / sr)
    spectrum[freqs < 30.0] = 0.0
    return float(freqs[int(np.argmax(spectrum))])


def test_layer_pitch_automation_drops_synth_frequency():
    sr = 8000
    tm = TempoMap([[0.0, 120.0]])
    total = int(1.1 * sr)
    plain = render_note_track(_track("sine"), total, sr, tm)
    dropped = render_note_track(_track("sine", automation=DROP_LAYER),
                                total, sr, tm)
    assert dropped.size == plain.size
    early = slice(int(0.10 * sr), int(0.40 * sr))
    late = slice(int(0.62 * sr), int(0.92 * sr))
    # linear -1200 c/s ride: mean ratio 0.10-0.40 s ≈ 0.846, 0.62-0.92 s ≈ 0.590 → ≈ 0.70
    assert _peak_hz(dropped[late], sr) < _peak_hz(dropped[early], sr) * 0.78
    assert _peak_hz(plain[late], sr) > _peak_hz(plain[early], sr) * 0.9


def test_layer_pitch_automation_matches_note_curve_for_note_at_zero():
    sr = 16000
    tm = TempoMap([[0.0, 120.0]])
    total = int(1.1 * sr)
    for osc in ("sine", "bowed"):
        via_layer = render_note_track(_track(osc, automation=DROP_LAYER),
                                      total, sr, tm)
        via_note = render_note_track(_track(osc, curves=DROP_NOTE),
                                     total, sr, tm)
        assert np.array_equal(via_layer, via_note), osc


def test_layer_pitch_automation_is_deterministic_on_physical_voice():
    sr = 16000
    tm = TempoMap([[0.0, 120.0]])
    total = int(1.1 * sr)
    a = render_note_track(_track("bowed", automation=DROP_LAYER),
                          total, sr, tm)
    b = render_note_track(_track("bowed", automation=DROP_LAYER),
                          total, sr, tm)
    assert np.array_equal(a, b)
