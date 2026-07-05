"""Deterministic render analysis for AI feedback loops."""
from __future__ import annotations

import math

import numpy as np


def _db(x: float) -> float:
    return 20.0 * math.log10(max(float(x), 1e-12))


def _silence_metrics(mono: np.ndarray, sample_rate: int,
                     hop_s: float = 0.25) -> dict:
    """Windowed dead-air detection.

    A render can be technically valid yet mostly silent — a lane that failed to
    sound, an accidental mute, or (as happens) a filter automated into removing
    all signal. Global RMS hides this when a few loud passages lift the average,
    so we scan a short-window envelope and report the longest continuous dead
    run and the dead share of the interior (fade in/out excluded). "Dead" is
    both near-absolute-silent and far below the track's own loud level, so a
    uniformly quiet-but-audible piece is not flagged.
    """
    n = max(1, int(hop_s * sample_rate))
    usable = mono.size - (mono.size % n)
    if usable < n * 4:
        return {"silence_share": 0.0, "longest_silence_s": 0.0}
    frames = mono[:usable].reshape(-1, n)
    wdb = 10.0 * np.log10(np.maximum(np.mean(frames * frames, axis=1), 1e-24))
    loud_ref = float(np.percentile(wdb, 90))
    floor = min(-48.0, loud_ref - 30.0)
    dead = wdb < floor
    edge = int(round(1.0 / hop_s))              # ignore ~1 s fade edges
    if dead.size > 2 * edge:
        dead[:edge] = False
        dead[-edge:] = False
    longest = cur = 0
    for d in dead:
        cur = cur + 1 if d else 0
        longest = max(longest, cur)
    return {
        "silence_share": round(float(np.mean(dead)), 4),
        "longest_silence_s": round(longest * hop_s, 3),
    }


def analyze_audio(stereo: np.ndarray, sample_rate: int) -> dict:
    """Return structured, deterministic features for an already-rendered buffer.

    Analysis lives outside the render path: it observes audio and annotates the
    manifest/agent loop, but it never feeds hidden state back into synthesis.
    """
    arr = np.asarray(stereo, dtype=np.float64)
    if arr.ndim == 1:
        arr = np.stack([arr, arr], axis=1)
    if arr.size == 0:
        raise ValueError("cannot analyze empty audio")
    mono = arr.mean(axis=1)
    peak = float(np.max(np.abs(arr)))
    rms = float(np.sqrt(np.mean(arr * arr)))
    crest = _db(peak / max(rms, 1e-12))
    win = np.hanning(mono.size) if mono.size > 1 else np.ones(mono.size)
    spec = np.abs(np.fft.rfft(mono * win))
    freqs = np.fft.rfftfreq(mono.size, 1.0 / sample_rate)
    mag_sum = float(np.sum(spec))
    centroid = float(np.sum(freqs * spec) / mag_sum) if mag_sum else 0.0
    cumulative = np.cumsum(spec)
    roll_idx = int(np.searchsorted(cumulative, 0.85 * mag_sum)) if mag_sum else 0
    rolloff = float(freqs[min(roll_idx, freqs.size - 1)]) if freqs.size else 0.0
    low = float(np.sum(spec[freqs < 250.0]) / mag_sum) if mag_sum else 0.0
    if arr.shape[1] >= 2 and np.std(arr[:, 0]) > 1e-12 and np.std(arr[:, 1]) > 1e-12:
        corr = float(np.corrcoef(arr[:, 0], arr[:, 1])[0, 1])
    else:
        corr = 1.0
    width = float(max(0.0, min(2.0, 1.0 - corr)))
    report = {
        "duration_s": round(arr.shape[0] / float(sample_rate), 6),
        "peak_dbfs": round(_db(peak), 3),
        "rms_dbfs": round(_db(rms), 3),
        "crest_db": round(crest, 3),
        "spectral_centroid_hz": round(centroid, 3),
        "spectral_rolloff85_hz": round(rolloff, 3),
        "low_band_share": round(low, 6),
        "stereo_width": round(width, 6),
    }
    report.update(_silence_metrics(mono, sample_rate))
    report["recommendations"] = _recommend(report)
    return report


def _recommend(r: dict) -> list[dict]:
    recs = []
    if r["low_band_share"] < 0.04:
        recs.append({
            "code": "low_foundation_weak",
            "severity": "warning",
            "message": "Low-frequency foundation is weak.",
            "suggestion": "Add or raise a bass/sub layer, or use ensemble octaves.",
        })
    if r["stereo_width"] < 0.08:
        recs.append({
            "code": "mono_image",
            "severity": "info",
            "message": "Stereo image is very narrow.",
            "suggestion": "Increase space depth, width, unison spread, or pan layers.",
        })
    if r["spectral_centroid_hz"] > 5500:
        recs.append({
            "code": "very_bright",
            "severity": "warning",
            "message": "Spectral centroid is high; the render may read as bright.",
            "suggestion": "Lower oscillator brightness, add lowpass automation, or rebalance low layers.",
        })
    if r["crest_db"] > 22:
        recs.append({
            "code": "high_crest",
            "severity": "info",
            "message": "Transient crest factor is high.",
            "suggestion": "Use bus compression, saturation, or lower transient layers.",
        })
    if r["peak_dbfs"] > -0.2:
        recs.append({
            "code": "near_ceiling",
            "severity": "info",
            "message": "Peak is very close to 0 dBFS.",
            "suggestion": "Use a lower master peak target for delivery headroom.",
        })
    if r.get("longest_silence_s", 0.0) >= 4.0 or r.get("silence_share", 0.0) >= 0.2:
        recs.append({
            "code": "dead_air",
            "severity": "warning",
            "message": (
                f"Unexpected silence: longest dead run "
                f"{r.get('longest_silence_s', 0.0):.1f}s, "
                f"{r.get('silence_share', 0.0) * 100:.0f}% of the interior is "
                f"near-silent."),
            "suggestion": (
                "A lane may be muted or filtered out — check gain automation "
                "and that 'auto cutoff' targets the intended filter (it drives "
                "the first filter in the chain)."),
        })
    return recs
