"""Objective render-quality metrics for engine-vs-engine A/B comparison.

`analysis.py` answers a *musical* question (centroid, width, foundation) to
steer an authoring loop. This module answers an *engineering* question: how
clean and well-formed is a finished render, measured the way an audio engineer
would measure one — true-peak headroom, noise floor, dynamic spread, spectral
bandwidth and balance, DC, and stereo geometry.

Every metric is deterministic (numpy/scipy only) and annotated with the
direction that counts as "more professional", so two renders can be compared
without smuggling in a hidden aesthetic preference: where a direction is genui-
nely neutral (timbre, width) it is labelled `descriptive`, not scored.

These are production-consistent measurements, not certified-meter readings —
the same honest-limits caveat the engine applies to its LUFS meter applies
here (see README "Honest limits").
"""
from __future__ import annotations

import math

import numpy as np
from scipy.signal import resample_poly

# Metric direction semantics. `compare_quality` uses these to decide whether a
# delta favours A or B; `descriptive` metrics are reported but never scored.
DIRECTIONS: dict[str, str] = {
    "true_peak_dbtp": "neutral",          # closeness to 0 dBTP is delivery-dependent
    "noise_floor_dbfs": "lower_is_cleaner",
    "dynamic_range_db": "higher_is_more_dynamic",
    "crest_db": "higher_is_more_dynamic",
    "dc_offset_dbfs": "lower_is_cleaner",
    "ultrasonic_share_db": "descriptive",  # bandlimited synth vs sampled air/noise
}


def _db(x: float) -> float:
    return 20.0 * math.log10(max(float(x), 1e-12))


def _as_stereo(buf: np.ndarray) -> np.ndarray:
    arr = np.asarray(buf, dtype=np.float64)
    if arr.ndim == 1:
        arr = np.stack([arr, arr], axis=1)
    if arr.ndim != 2 or arr.shape[1] < 2:
        arr = np.column_stack([arr[:, 0], arr[:, 0]])
    if arr.size == 0:
        raise ValueError("cannot analyze empty audio")
    return arr


def _frame_rms(mono: np.ndarray, frame: int, hop: int) -> np.ndarray:
    """RMS of non-overlapping-ish frames; the distribution of these drives the
    noise-floor and dynamic-range estimates below."""
    if mono.size < frame:
        return np.array([np.sqrt(np.mean(mono * mono) + 1e-24)])
    n = 1 + (mono.size - frame) // hop
    idx = np.arange(frame)[None, :] + hop * np.arange(n)[:, None]
    blocks = mono[idx]
    return np.sqrt(np.mean(blocks * blocks, axis=1) + 1e-24)


def _true_peak_dbtp(arr: np.ndarray, oversample: int = 4) -> float:
    """Inter-sample (true) peak via ≥4x polyphase oversampling — the estimator
    BS.1770-4 specifies for true-peak. Reported in dBTP."""
    tp = 0.0
    for ch in range(arr.shape[1]):
        up = resample_poly(arr[:, ch], oversample, 1)
        tp = max(tp, float(np.max(np.abs(up))))
    return round(_db(tp), 3)


def _avg_spectrum(mono: np.ndarray, sr: int, frame: int = 8192):
    """Welch-style averaged magnitude spectrum: stable centroid/rolloff/band
    statistics on a whole render rather than one giant transform."""
    if mono.size < frame:
        win = np.hanning(mono.size) if mono.size > 1 else np.ones(mono.size)
        spec = np.abs(np.fft.rfft(mono * win))
        freqs = np.fft.rfftfreq(mono.size, 1.0 / sr)
        return freqs, spec
    hop = frame // 2
    n = 1 + (mono.size - frame) // hop
    win = np.hanning(frame)
    acc = np.zeros(frame // 2 + 1)
    for i in range(n):
        seg = mono[i * hop:i * hop + frame] * win
        acc += np.abs(np.fft.rfft(seg))
    freqs = np.fft.rfftfreq(frame, 1.0 / sr)
    return freqs, acc / n


def render_quality(stereo: np.ndarray, sample_rate: int) -> dict:
    """Structured engineering-fidelity features for a finished render.

    Returns a flat dict of scalar metrics plus a `bands` sub-dict (fractional
    spectral energy) and a `meta` block (units/directions) so a comparison can
    be reproduced and audited.
    """
    arr = _as_stereo(stereo)
    sr = int(sample_rate)
    mono = arr.mean(axis=1)
    n = arr.shape[0]

    peak = float(np.max(np.abs(arr)))
    rms = float(np.sqrt(np.mean(arr * arr)))
    crest = _db(peak / max(rms, 1e-12))

    # noise floor / dynamic spread from a frame-RMS distribution (~43 ms frames)
    frame = max(256, int(0.043 * sr))
    hop = max(128, frame // 2)
    fr = _frame_rms(mono, frame, hop)
    fr_db = 20.0 * np.log10(np.maximum(fr, 1e-12))
    noise_floor = float(np.percentile(fr_db, 5))
    # dynamic range: spread between loud and quiet active frames. p95 anchors
    # the loud body; p20 the quiet (post-decay) body, above the absolute floor.
    dynamic_range = float(np.percentile(fr_db, 95) - np.percentile(fr_db, 20))

    dc = float(np.max(np.abs(arr.mean(axis=0))))

    freqs, spec = _avg_spectrum(mono, sr)
    mag_sum = float(np.sum(spec)) or 1.0
    centroid = float(np.sum(freqs * spec) / mag_sum)
    cumulative = np.cumsum(spec)
    rolloff85 = float(freqs[min(int(np.searchsorted(cumulative, 0.85 * mag_sum)),
                                freqs.size - 1)])
    rolloff99 = float(freqs[min(int(np.searchsorted(cumulative, 0.99 * mag_sum)),
                                freqs.size - 1)])

    def band_share(lo: float, hi: float) -> float:
        m = (freqs >= lo) & (freqs < hi)
        return round(float(np.sum(spec[m]) / mag_sum), 6)

    bands = {
        "sub_20_60": band_share(20, 60),
        "low_60_250": band_share(60, 250),
        "lowmid_250_2k": band_share(250, 2000),
        "highmid_2k_6k": band_share(2000, 6000),
        "high_6k_16k": band_share(6000, 16000),
        "ultra_16k_nyq": band_share(16000, sr / 2 + 1),
    }
    ultra = bands["ultra_16k_nyq"]
    ultrasonic_db = round(10.0 * math.log10(max(ultra, 1e-12)), 3)

    # stereo geometry
    l, r = arr[:, 0], arr[:, 1]
    if np.std(l) > 1e-12 and np.std(r) > 1e-12:
        corr = float(np.corrcoef(l, r)[0, 1])
    else:
        corr = 1.0
    width = float(max(0.0, min(2.0, 1.0 - corr)))
    side = (l - r) / 2.0
    mid = (l + r) / 2.0
    side_mid = _db(np.sqrt(np.mean(side * side)) / max(np.sqrt(np.mean(mid * mid)), 1e-12))

    return {
        "duration_s": round(n / float(sr), 6),
        "sample_rate": sr,
        "peak_dbfs": round(_db(peak), 3),
        "true_peak_dbtp": _true_peak_dbtp(arr),
        "rms_dbfs": round(_db(rms), 3),
        "crest_db": round(crest, 3),
        "noise_floor_dbfs": round(noise_floor, 3),
        "dynamic_range_db": round(dynamic_range, 3),
        "dc_offset_dbfs": round(_db(dc), 3),
        "spectral_centroid_hz": round(centroid, 3),
        "spectral_rolloff85_hz": round(rolloff85, 3),
        "spectral_rolloff99_hz": round(rolloff99, 3),
        "ultrasonic_share_db": ultrasonic_db,
        "stereo_correlation": round(corr, 6),
        "stereo_width": round(width, 6),
        "side_mid_db": round(side_mid, 3),
        "bands": bands,
        "meta": {
            "directions": dict(DIRECTIONS),
            "notes": (
                "true_peak via 4x oversampling (BS.1770-4); noise_floor = 5th "
                "percentile of 43 ms frame RMS; dynamic_range = p95-p20 of frame "
                "RMS. Production-consistent measurements, not certified meters."
            ),
        },
    }


def compare_quality(a: dict, b: dict, *, label_a: str = "A",
                    label_b: str = "B") -> dict:
    """Compare two `render_quality` reports metric-by-metric.

    For each scored scalar metric, reports the value of each render, the delta
    (b - a), and which render the delta favours given the metric's direction.
    `descriptive` and `neutral` metrics are reported with `favours: null` —
    they are differences, not verdicts.
    """
    directions = a.get("meta", {}).get("directions", DIRECTIONS)
    scalar_keys = [k for k, v in a.items()
                   if isinstance(v, (int, float)) and k != "sample_rate"]
    metrics = {}
    favoured = {label_a: 0, label_b: 0}
    for k in scalar_keys:
        if k not in b:
            continue
        va, vb = float(a[k]), float(b[k])
        delta = round(vb - va, 4)
        direction = directions.get(k, "descriptive")
        favours = None
        if direction == "lower_is_cleaner":
            favours = label_b if vb < va else label_a if va < vb else None
        elif direction == "higher_is_more_dynamic":
            favours = label_b if vb > va else label_a if va > vb else None
        if favours is not None:
            favoured[favours] += 1
        metrics[k] = {
            label_a: round(va, 3),
            label_b: round(vb, 3),
            "delta_b_minus_a": delta,
            "direction": direction,
            "favours": favours,
        }
    return {
        "labels": {"a": label_a, "b": label_b},
        "metrics": metrics,
        "bands": {label_a: a.get("bands", {}), label_b: b.get("bands", {})},
        "scored_metric_wins": favoured,
    }
