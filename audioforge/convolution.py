"""FFT convolution helpers (overlap-add), without importing scipy.signal.

``convolve_head`` -- long-IR reverbs: y = (x * ir)[:len(x)] for one or more
IRs. The input is cut into blocks of up to 2^20 samples, all transformed in
one batched FFT call (cache-friendly, where a single signal-length FFT of tens
of millions of points is not: measured 2.5x faster on a 300 s feed with a
2.8 s IR); the input spectrum is shared by every IR (stereo reverbs convolve
one mono feed with an L and an R response); transforms of >= 2^17 points run
in float32 (max error ~ -126 dB re the output peak, far below the 24-bit
floor for a reverb return), smaller ones in float64.

``convolve_same`` -- smoothing windows (limiter, compressor): scipy's
``mode="same"`` output, all float64 (these drive gain curves).

Deterministic: fixed block and FFT sizes, no threads.
"""
from __future__ import annotations

import numpy as np

_BLOCK = 1 << 20
_F32_MIN = 1 << 17


def _ola(x: np.ndarray, irs, start: int, count: int, allow_f32: bool):
    """(x * ir)[start:start+count] per ir, by batched overlap-add."""
    import scipy.fft as sfft               # lazy: ~0.1 s import, often unused
    x = np.asarray(x, dtype=np.float64)
    n = x.size
    irs = [np.asarray(ir, dtype=np.float64) for ir in irs]
    if n == 0 or count <= 0:
        return [np.zeros(max(count, 0)) for _ in irs]
    m = max(ir.size for ir in irs)
    B = min(_BLOCK, n) if allow_f32 else min(max(8 * m, 1 << 14), n)
    L = sfft.next_fast_len(B + m - 1, real=True)
    dt = np.float32 if allow_f32 and L >= _F32_MIN else np.float64
    nb = -(-n // B)
    xb = np.zeros((nb, B), dtype=dt)
    xb.reshape(-1)[:n] = x
    live = np.flatnonzero(np.any(xb, axis=1))    # silent blocks add exactly 0
    X = sfft.rfft(xb[live], L, axis=1)
    del xb
    outs = []
    for ir in irs:
        Y = sfft.irfft(X * sfft.rfft(ir.astype(dt), L), L, axis=1)
        out = np.zeros(nb * B + L)
        for row, k in enumerate(live.tolist()):  # overlap-add the tails
            out[k * B:k * B + L] += Y[row]
        outs.append(out[start:start + count].copy())
    return outs


def convolve_head(x: np.ndarray, *irs: np.ndarray) -> list[np.ndarray]:
    """[(x * ir)[:x.size] for ir in irs] as float64 arrays."""
    return _ola(x, irs, 0, np.asarray(x).size, allow_f32=True)


def convolve_same(x: np.ndarray, h: np.ndarray) -> np.ndarray:
    """scipy.signal.convolve(x, h, mode="same") for len(x) >= len(h), float64."""
    h = np.asarray(h, dtype=np.float64)
    n = np.asarray(x).size
    return _ola(x, [h], (h.size - 1) // 2, n, allow_f32=False)[0]
