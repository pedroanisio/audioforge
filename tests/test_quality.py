"""Tests for the render-quality metrics module (audioforge.quality)."""
from __future__ import annotations

import numpy as np
import pytest

from audioforge.quality import compare_quality, render_quality


def _sine(freq, sr, dur, amp=0.5, stereo=True):
    t = np.arange(int(sr * dur)) / sr
    x = amp * np.sin(2 * np.pi * freq * t)
    return np.stack([x, x], axis=1) if stereo else x


def test_levels_of_known_sine():
    sr = 48000
    buf = _sine(1000.0, sr, 1.0, amp=0.5)
    q = render_quality(buf, sr)
    # peak of a 0.5-amplitude sine is -6.02 dBFS; RMS is 3.01 dB below that.
    assert q["peak_dbfs"] == pytest.approx(-6.02, abs=0.1)
    assert q["rms_dbfs"] == pytest.approx(-9.03, abs=0.2)
    assert q["crest_db"] == pytest.approx(3.01, abs=0.2)
    assert q["duration_s"] == pytest.approx(1.0, abs=1e-3)
    assert q["sample_rate"] == sr


def test_true_peak_not_below_sample_peak():
    sr = 48000
    buf = _sine(997.0, sr, 0.5, amp=0.9)
    q = render_quality(buf, sr)
    # inter-sample peak can only meet or exceed the sample peak.
    assert q["true_peak_dbtp"] >= q["peak_dbfs"] - 1e-6


def test_spectral_centroid_tracks_tone():
    sr = 48000
    low = render_quality(_sine(500.0, sr, 1.0), sr)["spectral_centroid_hz"]
    high = render_quality(_sine(4000.0, sr, 1.0), sr)["spectral_centroid_hz"]
    assert low == pytest.approx(500, rel=0.15)
    assert high == pytest.approx(4000, rel=0.15)
    assert high > low


def test_mono_input_has_zero_width():
    sr = 48000
    q = render_quality(_sine(440.0, sr, 0.5, stereo=False), sr)
    assert q["stereo_width"] == 0.0
    assert q["stereo_correlation"] == pytest.approx(1.0)


def test_decorrelated_stereo_is_wide():
    sr = 48000
    rng = np.random.default_rng(0)
    n = sr // 2
    buf = np.stack([rng.standard_normal(n), rng.standard_normal(n)], axis=1) * 0.1
    q = render_quality(buf, sr)
    assert q["stereo_correlation"] < 0.1
    assert q["stereo_width"] > 0.9


def test_dc_offset_detected():
    sr = 48000
    buf = _sine(300.0, sr, 0.5, amp=0.3) + 0.1   # +0.1 DC on both channels
    q = render_quality(buf, sr)
    # 0.1 linear DC == -20 dBFS
    assert q["dc_offset_dbfs"] == pytest.approx(-20.0, abs=0.5)


def test_noise_floor_below_signal():
    sr = 48000
    # loud tone for 0.5 s then digital silence for 0.5 s
    tone = _sine(1000.0, sr, 0.5, amp=0.7)
    sil = np.zeros((sr // 2, 2))
    q = render_quality(np.vstack([tone, sil]), sr)
    assert q["noise_floor_dbfs"] < q["rms_dbfs"] - 20.0


def test_bands_sum_to_about_one():
    sr = 48000
    rng = np.random.default_rng(1)
    buf = rng.standard_normal((sr, 2)) * 0.05
    q = render_quality(buf, sr)
    assert sum(q["bands"].values()) == pytest.approx(1.0, abs=1e-3)


def test_determinism():
    sr = 48000
    buf = _sine(600.0, sr, 0.7, amp=0.4)
    assert render_quality(buf, sr) == render_quality(buf, sr)


def test_empty_raises():
    with pytest.raises(ValueError):
        render_quality(np.zeros((0, 2)), 48000)


def test_compare_directions_and_tally():
    base = render_quality(_sine(1000.0, 48000, 1.0, amp=0.5), 48000)
    # craft a clear difference: B is cleaner (lower floor) and more dynamic.
    a = json_roundtrip(base)
    b = json_roundtrip(base)
    a["noise_floor_dbfs"] = -60.0
    b["noise_floor_dbfs"] = -90.0          # B cleaner -> favours b
    a["dynamic_range_db"] = 10.0
    b["dynamic_range_db"] = 20.0           # B more dynamic -> favours b
    cmp = compare_quality(a, b, label_a="A", label_b="B")
    assert cmp["metrics"]["noise_floor_dbfs"]["favours"] == "B"
    assert cmp["metrics"]["dynamic_range_db"]["favours"] == "B"
    # descriptive metric is reported but never scored
    assert cmp["metrics"]["spectral_centroid_hz"]["favours"] is None
    assert cmp["scored_metric_wins"]["B"] >= 2


def json_roundtrip(d):
    import json
    return json.loads(json.dumps(d))
