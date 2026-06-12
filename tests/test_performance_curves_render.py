import numpy as np

import audioforge.sequencer as seqmod
from audioforge import library as libmod
from audioforge.determinism import rng_for
from audioforge.sampler import render_instrument_track
from audioforge.sequencer import TempoMap, render_note_track
from test_dynamics import build_p2_library


def _base_track(note="A4", curves=None, osc="sine"):
    ev = {"note": note, "start_beat": 0.0, "dur_beats": 2.0}
    if curves:
        ev["curves"] = curves
    return {
        "type": "notes",
        "osc": osc,
        "env": {"attack": 0.001, "decay": 0.01, "sustain": 1.0, "release": 0.01},
        "notes": [ev],
    }


def _zero_crossings(signal):
    body = signal[np.abs(signal) > 1e-4]
    return int(np.sum(np.diff(np.signbit(body)) != 0))


def _rms(signal):
    return float(np.sqrt(np.mean(signal ** 2)))


def _centroid(signal, sr):
    windowed = signal * np.hanning(signal.size)
    spectrum = np.abs(np.fft.rfft(windowed)) ** 2
    freqs = np.fft.rfftfreq(windowed.size, 1 / sr)
    return float((spectrum * freqs).sum() / max(spectrum.sum(), 1e-12))


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


def test_no_curve_note_renders_do_not_evaluate_curve_fast_path(monkeypatch, tmp_path):
    def fail_evaluate_curve(*_args, **_kwargs):
        raise AssertionError("no-curve render should not evaluate note curves")

    monkeypatch.setattr(seqmod, "evaluate_curve", fail_evaluate_curve)

    sr = 8000
    tm = TempoMap([[0.0, 120.0]])
    synth = render_note_track(_base_track(), sr, sr, tm)
    assert synth.shape == (sr,)

    root = tmp_path / "minilib2"
    pin = build_p2_library(root)
    lib = libmod.load_library(f"minilib2@{pin}")
    sampled = render_instrument_track({
        "name": "v",
        "type": "instrument",
        "instrument": "testviolin",
        "notes": [{"note": "C4", "start_beat": 0.0, "dur_beats": 1.0}],
    }, sr, sr, tm, lambda sub: rng_for("p3", "fast", sub), lib)
    assert sampled.shape == (sr,)


def test_render_note_track_note_gain_curve_sums_with_dynamic_level():
    sr = 8000
    tm = TempoMap([[0.0, 120.0]])
    quiet = render_note_track(_base_track(curves=[
        {
            "target": "dynamic",
            "time_basis": "note_seconds",
            "points": [[0.0, 0.0]],
        },
    ]), sr, sr, tm)
    boosted = render_note_track(_base_track(curves=[
        {
            "target": "dynamic",
            "time_basis": "note_seconds",
            "points": [[0.0, 0.0]],
        },
        {
            "target": "gain_db",
            "time_basis": "note_seconds",
            "points": [[0.0, 12.0]],
        },
    ]), sr, sr, tm)

    assert _rms(boosted) > _rms(quiet) * 3.5


def test_render_note_track_cutoff_curve_filters_one_note_voice():
    sr = 16000
    tm = TempoMap([[0.0, 120.0]])
    open_voice = render_note_track(_base_track(osc="saw"), sr, sr, tm)
    dark_voice = render_note_track(_base_track(osc="saw", curves=[{
        "target": "cutoff_hz",
        "time_basis": "note_seconds",
        "points": [[0.0, 500.0]],
    }]), sr, sr, tm)

    body = slice(int(0.05 * sr), int(0.75 * sr))
    assert _centroid(open_voice[body], sr) > _centroid(dark_voice[body], sr) * 2.0


def test_render_note_track_scan_curve_morphs_one_note_voice():
    sr = 16000
    tm = TempoMap([[0.0, 120.0]])
    sine_zone = render_note_track(_base_track(osc="morph", curves=[{
        "target": "scan",
        "time_basis": "note_seconds",
        "points": [[0.0, 0.0]],
    }]), sr, sr, tm)
    square_zone = render_note_track(_base_track(osc="morph", curves=[{
        "target": "scan",
        "time_basis": "note_seconds",
        "points": [[0.0, 1.0]],
    }]), sr, sr, tm)

    body = slice(int(0.05 * sr), int(0.75 * sr))
    assert _centroid(square_zone[body], sr) > _centroid(sine_zone[body], sr) * 1.5


def test_render_instrument_track_note_gain_curve_changes_sampled_note_level(tmp_path):
    root = tmp_path / "minilib2"
    pin = build_p2_library(root)
    lib = libmod.load_library(f"minilib2@{pin}")
    sr = 16000
    tm = TempoMap([[0.0, 120.0]])

    def track(curves=None):
        note = {"note": "C4", "start_beat": 0.0, "dur_beats": 2.0}
        if curves:
            note["curves"] = curves
        return {
            "name": "v",
            "type": "instrument",
            "instrument": "testviolin",
            "notes": [note],
        }

    plain = render_instrument_track(
        track(), sr, sr, tm, lambda sub: rng_for("p3", "gain", sub), lib)
    boosted = render_instrument_track(track([{
        "target": "gain_db",
        "time_basis": "note_seconds",
        "points": [[0.0, 6.0]],
    }]), sr, sr, tm, lambda sub: rng_for("p3", "gain", sub), lib)

    body = slice(int(0.1 * sr), int(0.8 * sr))
    assert _rms(boosted[body]) > _rms(plain[body]) * 1.8
