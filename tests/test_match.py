"""Tests for audio -> editable patch matching (audioforge.match)."""
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from audioforge import AudioForge, render  # noqa: E402
from audioforge.match import match_patch  # noqa: E402


def _target(osc: str, note: str = "A3", cutoff: float | None = None,
            env=None, dur: float = 1.6):
    layer = {"name": "v", "type": "tone", "osc": osc, "note": note,
             "gain_db": -6.0,
             "env": env or {"attack": 0.01, "decay": 0.3,
                            "sustain": 0.5, "release": 0.3}}
    if cutoff is not None:
        layer["fx"] = [{"type": "filter", "mode": "lowpass",
                        "cutoff_hz": float(cutoff)}]
    spec = {"id": "t", "kind": "cue", "duration_s": dur, "bpm": 120,
            "key": "C major", "layers": [layer],
            "master": {"target_peak_dbfs": -1.0}}
    audio, sr, _ = render(spec)
    return audio, sr


def test_recovers_pitch():
    audio, sr = _target("saw", note="C4")
    res = match_patch(audio, sr)
    assert res["note"] == "C4"
    assert res["harmonicity"] > 0.7


def test_recovers_oscillator_family_and_brightness():
    # a dark saw: the matcher should pick saw (or a near sibling) and a
    # low-ish cutoff, with a small verified distance.
    audio, sr = _target("saw", note="A3", cutoff=2500.0)
    res = match_patch(audio, sr)
    assert res["ranking"][0]["osc"] in {"saw", "square"}
    assert res["verified_distance"] < 0.2
    assert res["confidence"] > 0.6


def test_sine_target_picks_sine():
    audio, sr = _target("sine", note="A4")
    res = match_patch(audio, sr)
    assert res["ranking"][0]["osc"] == "sine"


def test_emitted_patch_round_trips_and_renders():
    audio, sr = _target("triangle", note="E4")
    res = match_patch(audio, sr)
    assert "note: E4" in res["dsl"]
    compiled = AudioForge().compile(res["dsl"])
    assert compiled.ok, [d.message for d in compiled.diagnostics]
    out, _sr, _m = render(compiled.assets[0].spec)
    assert out.shape[1] == 2 and np.max(np.abs(out)) > 0


def test_verification_is_independent_and_consistent():
    audio, sr = _target("saw", note="A3", cutoff=3000.0)
    res = match_patch(audio, sr)
    # the chosen patch's verified distance is finite and matches the search
    # score for that spec (the optimiser is not trusted on its own word).
    assert res["verified_distance"] == pytest.approx(res["distance"], abs=1e-9)
    assert 0.0 <= res["confidence"] <= 1.0


def test_determinism():
    audio, sr = _target("square", note="D3", cutoff=4000.0)
    a = match_patch(audio, sr)
    b = match_patch(audio, sr)
    assert a["dsl"] == b["dsl"]
    assert a["verified_distance"] == b["verified_distance"]
    assert a["ranking"] == b["ranking"]


def test_inharmonic_target_reports_low_confidence():
    spec = {"id": "n", "kind": "cue", "duration_s": 1.2, "bpm": 120,
            "layers": [{"name": "air", "type": "noise", "color": "white",
                        "gain_db": -6,
                        "env": {"attack": 0.01, "decay": 0.3,
                                "sustain": 0.7, "release": 0.2}}],
            "master": {"target_peak_dbfs": -1.0}}
    audio, sr, _ = render(spec)
    res = match_patch(audio, sr)
    # noise is not strongly pitched: confidence must be tempered, not faked.
    assert res["harmonicity"] < 0.6
    assert res["confidence"] < 0.7


def test_empty_raises():
    with pytest.raises(ValueError):
        match_patch(np.zeros((0, 2)), 48000)
