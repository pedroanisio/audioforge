"""Integrated loudness (LUFS) measurement and normalization.

Implements the structure of ITU-R BS.1770: K-weighting pre-filter
(high-shelf + high-pass), 400 ms blocks with 75% overlap, absolute -70 LUFS
gate and -10 LU relative gate. The K-weighting filters here are RBJ-designed
approximations of the published curves, re-derived per sample rate; treat
measurements as production-consistent rather than certified-meter-exact.
Pure DSP — fully deterministic.
"""
from __future__ import annotations

import numpy as np
from scipy.signal import lfilter


def _rbj_highshelf(fc: float, gain_db: float, sr: int, s: float = 1.0):
    A = 10.0 ** (gain_db / 40.0)
    w0 = 2.0 * np.pi * fc / sr
    cosw, sinw = np.cos(w0), np.sin(w0)
    alpha = sinw / 2.0 * np.sqrt((A + 1.0 / A) * (1.0 / s - 1.0) + 2.0)
    two_sqrtA_alpha = 2.0 * np.sqrt(A) * alpha
    b0 = A * ((A + 1) + (A - 1) * cosw + two_sqrtA_alpha)
    b1 = -2 * A * ((A - 1) + (A + 1) * cosw)
    b2 = A * ((A + 1) + (A - 1) * cosw - two_sqrtA_alpha)
    a0 = (A + 1) - (A - 1) * cosw + two_sqrtA_alpha
    a1 = 2 * ((A - 1) - (A + 1) * cosw)
    a2 = (A + 1) - (A - 1) * cosw - two_sqrtA_alpha
    return np.array([b0, b1, b2]) / a0, np.array([1.0, a1 / a0, a2 / a0])


def _rbj_highpass(fc: float, sr: int, q: float = 0.5):
    w0 = 2.0 * np.pi * fc / sr
    cosw, sinw = np.cos(w0), np.sin(w0)
    alpha = sinw / (2.0 * q)
    b0 = (1 + cosw) / 2; b1 = -(1 + cosw); b2 = (1 + cosw) / 2
    a0 = 1 + alpha
    return (np.array([b0, b1, b2]) / a0,
            np.array([1.0, -2 * cosw / a0, (1 - alpha) / a0]))


def k_weight(x: np.ndarray, sr: int) -> np.ndarray:
    """Stage 1: +4 dB high shelf ~1681 Hz; stage 2: high-pass ~38 Hz."""
    b, a = _rbj_highshelf(1681.0, 4.0, sr)
    x = lfilter(b, a, x)
    b, a = _rbj_highpass(38.0, sr)
    return lfilter(b, a, x)


def integrated_lufs(stereo: np.ndarray, sr: int) -> float:
    """stereo: [n, 2] float in -1..1. Returns gated integrated loudness."""
    n = stereo.shape[0]
    kw = np.stack([k_weight(stereo[:, c], sr) for c in range(2)], axis=1)
    block = int(0.400 * sr)
    hop = int(0.100 * sr)
    if n < block:  # very short assets: single block
        block, hop = n, n
    powers = []
    for start in range(0, n - block + 1, hop):
        seg = kw[start:start + block]
        powers.append(np.mean(seg[:, 0] ** 2) + np.mean(seg[:, 1] ** 2))
    powers = np.array(powers)
    lk = -0.691 + 10.0 * np.log10(np.maximum(powers, 1e-12))
    mask = lk > -70.0                                  # absolute gate
    if not np.any(mask):
        return -70.0
    rel = -0.691 + 10.0 * np.log10(np.mean(powers[mask])) - 10.0
    mask &= lk > rel                                   # relative gate
    if not np.any(mask):
        return -70.0
    return float(-0.691 + 10.0 * np.log10(np.mean(powers[mask])))


def normalize_lufs(stereo: np.ndarray, sr: int, target_lufs: float,
                   true_peak_ceiling_dbfs: float = -1.0) -> tuple[np.ndarray, dict]:
    """Gain to hit target integrated loudness, then limit so the (4x
    oversampled, approximate true-)peak never exceeds the ceiling."""
    measured = integrated_lufs(stereo, sr)
    gain_db = target_lufs - measured
    out = stereo * (10.0 ** (gain_db / 20.0))
    # approximate true peak via 4x linear-phase-ish FFT oversampling
    n = out.shape[0]
    up = np.fft.irfft(np.fft.rfft(out, axis=0), 4 * n, axis=0) * 4.0
    tp = np.max(np.abs(up))
    ceiling = 10.0 ** (true_peak_ceiling_dbfs / 20.0)
    limited = False
    if tp > ceiling:
        out *= ceiling / tp
        limited = True
    return out, {"measured_lufs": round(measured, 2),
                 "applied_gain_db": round(gain_db, 2),
                 "peak_limited": limited,
                 "final_lufs": round(integrated_lufs(out, sr), 2)}
