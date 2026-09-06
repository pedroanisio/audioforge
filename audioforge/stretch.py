"""Tempo-preserving time stretch for sample layers (`stretch:`), a phase vocoder.

Hann-windowed STFT at an analysis hop of ``hop / ratio`` samples, phase advance
re-derived per bin from the measured phase increment (the classic Flanagan &
Golden 1966 / Dolson 1986 vocoder; see Zölzer, *DAFX* 2nd ed., §7.3.3), then
overlap-add at the synthesis hop. Pitch is unchanged, duration scales by
``ratio``. Pure numpy, no randomness: byte-reproducible for a given input.
"""
from __future__ import annotations

import numpy as np


def time_stretch(x: np.ndarray, ratio: float, win: int = 2048, hop: int = 512) -> np.ndarray:
    """Return ``x`` stretched to ``round(len(x) · ratio)`` samples at the same pitch.

    ``ratio`` > 1 lengthens, < 1 shortens. Stereo input (n, 2) is processed per
    channel. Inputs shorter than one window are resampled linearly (no pitch
    preservation is possible without a full window; documented limitation).
    """
    ratio = float(ratio)
    if ratio <= 0:
        raise ValueError("stretch ratio must be positive")
    if abs(ratio - 1.0) < 1e-12:
        return np.asarray(x, dtype=np.float64).copy()
    x = np.asarray(x, dtype=np.float64)
    if x.ndim == 2:
        return np.stack([time_stretch(x[:, c], ratio, win, hop) for c in range(x.shape[1])], axis=1)
    n_out = max(1, int(round(x.size * ratio)))
    if x.size < win:
        src = np.arange(x.size)
        return np.interp(np.linspace(0, x.size - 1, n_out), src, x)
    ha = hop / ratio                                   # analysis hop (fractional)
    n_frames = int(np.floor((x.size - win) / ha)) + 1
    positions = np.round(np.arange(n_frames) * ha).astype(int)
    window = np.hanning(win + 1)[:-1]
    frames = np.stack([x[p:p + win] * window for p in positions])
    spec = np.fft.rfft(frames, axis=1)
    mag, phase = np.abs(spec), np.angle(spec)
    bins = np.arange(win // 2 + 1)
    out_phase = np.empty_like(phase)
    out_phase[0] = phase[0]
    for k in range(1, n_frames):
        delta_pos = positions[k] - positions[k - 1]
        omega = 2.0 * np.pi * bins * delta_pos / win           # expected advance
        dev = phase[k] - phase[k - 1] - omega
        dev = dev - 2.0 * np.pi * np.round(dev / (2.0 * np.pi))  # principal value
        inst = omega + dev                                      # true advance
        out_phase[k] = out_phase[k - 1] + inst * (hop / delta_pos)
    y_frames = np.fft.irfft(mag * np.exp(1j * out_phase), n=win, axis=1) * window
    out = np.zeros((n_frames - 1) * hop + win)
    norm = np.zeros_like(out)
    w2 = window ** 2
    for k in range(n_frames):
        s = k * hop
        out[s:s + win] += y_frames[k]
        norm[s:s + win] += w2
    out /= np.maximum(norm, 1e-8)
    if out.size >= n_out:
        return out[:n_out]
    return np.concatenate([out, np.zeros(n_out - out.size)])
