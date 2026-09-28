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
    from ._native import biquad
    b, a = _rbj_highshelf(1681.0, 4.0, sr)
    x = biquad(x, b, a)
    b, a = _rbj_highpass(38.0, sr)
    return biquad(x, b, a)


def integrated_lufs(stereo: np.ndarray, sr: int) -> float:
    """stereo: [n, 2] float in -1..1. Returns gated integrated loudness."""
    n = stereo.shape[0]
    from ._native import iir_multi
    kl, kr = iir_multi([stereo[:, 0], stereo[:, 1]],
                       [_rbj_highshelf(1681.0, 4.0, sr), _rbj_highpass(38.0, sr)])
    block = int(0.400 * sr)
    hop = int(0.100 * sr)
    if n < block:  # very short assets: single block
        block, hop = n, n
    nblocks = (n - block) // hop + 1
    if block == 4 * hop:
        # 400 ms blocks at 75% overlap are exactly four 100 ms hops: sum the
        # squares once per hop, then each block's power is four hop sums
        nh = nblocks + 3
        hs = [np.einsum("ij,ij->i", h, h) for h in
              (kl[:nh * hop].reshape(nh, hop), kr[:nh * hop].reshape(nh, hop))]
        powers = sum((c[:nblocks] + c[1:nblocks + 1] + c[2:nblocks + 2]
                      + c[3:nblocks + 3]) / block for c in hs)
    else:
        powers = np.array([np.mean(kl[s0:s0 + block] ** 2)
                           + np.mean(kr[s0:s0 + block] ** 2)
                           for s0 in range(0, n - block + 1, hop)])
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
