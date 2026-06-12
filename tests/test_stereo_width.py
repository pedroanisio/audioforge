"""Tests for master stereo-width widening (stereo_width > 1.0).

The DSP already scaled the side signal by `stereo_width`; the schema previously
clamped it to [0, 1] so an author could only collapse toward mono, never widen
beyond the as-mixed image. These tests lock the widening behaviour and its
mono-safety (the mid — and therefore the mono sum — is preserved).
"""
import io
import sys
import wave
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from audioforge import render_to_wav, validate_spec, SpecError  # noqa: E402


def _spec(width: float) -> dict:
    """Two layers panned hard L/R on different notes — real side content for the
    M/S widener to act on."""
    return {
        "id": f"widen_{str(width).replace('.', '_')}",
        "kind": "cue",
        "duration_s": 1.2,
        "bpm": 120,
        "bitdepth": 24,
        "layers": [
            {"name": "left", "type": "notes", "osc": "triangle", "pan": -0.9,
             "gain_db": -6,
             "env": {"attack": 0.005, "decay": 0.3, "sustain": 0.2, "release": 0.1},
             "notes": [{"note": "C3", "start_beat": 0.0, "dur_beats": 2.0}]},
            {"name": "right", "type": "notes", "osc": "triangle", "pan": +0.9,
             "gain_db": -6,
             "env": {"attack": 0.005, "decay": 0.3, "sustain": 0.2, "release": 0.1},
             "notes": [{"note": "G5", "start_beat": 0.0, "dur_beats": 2.0}]},
        ],
        "master": {"target_peak_dbfs": -3.0, "fade_out_s": 0.05,
                   "stereo_width": width},
    }


def _render_stereo(spec: dict, tmp_path: Path) -> tuple[np.ndarray, np.ndarray]:
    meta = render_to_wav(spec, str(tmp_path))
    wav = Path(tmp_path) / meta["file"]
    with wave.open(io.BytesIO(wav.read_bytes())) as w:
        ch, sw, n = w.getnchannels(), w.getsampwidth(), w.getnframes()
        raw = w.readframes(n)
    if sw == 3:
        b = np.frombuffer(raw, dtype=np.uint8).reshape(-1, 3)
        v = (b[:, 0].astype(np.int32) | (b[:, 1].astype(np.int32) << 8)
             | (b[:, 2].astype(np.int32) << 16))
        x = (v - ((v >> 23) & 1) * (1 << 24)) / float(1 << 23)
    else:
        x = np.frombuffer(raw, dtype="<i2").astype(np.float64) / 32768.0
    x = x.reshape(-1, ch)
    return x[:, 0], x[:, 1]


def test_schema_accepts_widening_and_rejects_beyond_max():
    validate_spec(_spec(1.0))
    validate_spec(_spec(1.8))
    validate_spec(_spec(2.0))
    with pytest.raises(SpecError):
        validate_spec(_spec(2.5))
    with pytest.raises(SpecError):
        validate_spec(_spec(-0.1))


def test_widening_decorrelates_more_than_as_mixed(tmp_path):
    l1, r1 = _render_stereo(_spec(1.0), tmp_path / "w10")
    l2, r2 = _render_stereo(_spec(1.8), tmp_path / "w18")
    corr_mixed = float(np.corrcoef(l1, r1)[0, 1])
    corr_wide = float(np.corrcoef(l2, r2)[0, 1])
    # widening pushes L and R further apart (lower correlation = wider image)
    assert corr_wide < corr_mixed


def test_widening_preserves_mono_sum(tmp_path):
    """M/S widening scales the side only; the mid (L+R) must be unchanged up to
    the loudness normalisation, so the render stays mono-compatible."""
    l1, r1 = _render_stereo(_spec(1.0), tmp_path / "m10")
    l2, r2 = _render_stereo(_spec(1.8), tmp_path / "m18")
    mid1, mid2 = l1 + r1, l2 + r2
    # normalise each mid to unit RMS, then compare shape: near-identical.
    mid1 /= np.sqrt(np.mean(mid1 ** 2)) + 1e-12
    mid2 /= np.sqrt(np.mean(mid2 ** 2)) + 1e-12
    n = min(len(mid1), len(mid2))
    assert float(np.corrcoef(mid1[:n], mid2[:n])[0, 1]) > 0.999


def test_widening_is_deterministic(tmp_path):
    a = render_to_wav(_spec(1.8), str(tmp_path / "a"))
    b = render_to_wav(_spec(1.8), str(tmp_path / "b"))
    assert a["output_sha256"] == b["output_sha256"]
