import numpy as np

from audioforge.sequencer import TempoMap, render_note_track


def _base_track(note="A4", curves=None):
    ev = {"note": note, "start_beat": 0.0, "dur_beats": 2.0}
    if curves:
        ev["curves"] = curves
    return {
        "type": "notes",
        "osc": "sine",
        "env": {"attack": 0.001, "decay": 0.01, "sustain": 1.0, "release": 0.01},
        "notes": [ev],
    }


def _zero_crossings(signal):
    body = signal[np.abs(signal) > 1e-4]
    return int(np.sum(np.diff(np.signbit(body)) != 0))


def test_render_note_track_pitch_curve_changes_rendered_frequency():
    sr = 8000
    tm = TempoMap([[0.0, 120.0]])
    plain = render_note_track(_base_track(), sr, sr, tm)
    bent = render_note_track(_base_track(curves=[{
        "target": "pitch_cents",
        "time_basis": "note_seconds",
        "points": [[0.0, 1200.0]],
    }]), sr, sr, tm)

    assert _zero_crossings(bent) > _zero_crossings(plain) * 1.8


def test_render_note_track_note_dynamic_curve_changes_level():
    sr = 8000
    tm = TempoMap([[0.0, 120.0]])
    quiet = render_note_track(_base_track(curves=[{
        "target": "dynamic",
        "time_basis": "note_seconds",
        "points": [[0.0, 0.0]],
    }]), sr, sr, tm)
    loud = render_note_track(_base_track(curves=[{
        "target": "dynamic",
        "time_basis": "note_seconds",
        "points": [[0.0, 1.0]],
    }]), sr, sr, tm)

    assert np.sqrt(np.mean(loud ** 2)) > np.sqrt(np.mean(quiet ** 2)) * 2.0
