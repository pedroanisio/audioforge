"""Tier R: stage & room (P4).

For staged layers (those with a `seat:`), per-layer reverb is replaced by a
physically-motivated, fully deterministic chain; the old fx path remains for
sound design. Three signal taps per source, blended by the `mics:` weights:

  close   — the spot mic: the source's stereo placement with distance
            clamped to 1.5 m (negligible air loss, little room).
  tree    — the main pair image: direct sound *at distance* (1/r gain, air
            absorption as a distance-scaled high-shelf cut, azimuth pan plus
            a sub-ms interaural delay) plus image-source early reflections
            over a parameterized shoebox fitted to the hall size.
  ambient — the shared hall tail: one stereo convolution per stage with a
            content-addressed measured (or generated) impulse response.

This deliberately refines the architecture plan's tap definition (which put
the bare direct path on `close` and only reflections on `tree`): a real
main pair captures direct + early together, and a mix model should too —
documented here, as ever.

Honesty notes: air absorption is a documented approximation of ISO 9613-1
*behavior* (a -0.3 dB/m shelf above ~6 kHz), not a certified implementation.
The ITD is integer-sample at 48 kHz (≤ ~21 µs quantization). The shoebox
image-source model runs to second order — early character, not a full room
simulation. All of it is closed-form and seedless: same seat + same hall =
the same reflections, forever.
"""
from __future__ import annotations

import numpy as np

from .fx import eq_fx

SPEED_OF_SOUND = 343.0
_early_cache: dict[tuple, np.ndarray] = {}


def seat_pan_itd(az_deg: float) -> tuple[float, int]:
    """Azimuth -> (constant-power pan position -1..1, ITD in samples@48k).
    Stage azimuths span roughly ±45°; ITD peaks ~0.65 ms at full lateral."""
    az = float(np.clip(az_deg, -60.0, 60.0))
    pan = np.sin(np.radians(az)) / np.sin(np.radians(45.0))
    itd_s = 0.00065 * np.sin(np.radians(az))
    return float(np.clip(pan, -1.0, 1.0)), int(round(abs(itd_s) * 48000))


def air_shelf_db(dist_m: float) -> float:
    """High-shelf cut above ~6 kHz approximating atmospheric absorption
    (ISO 9613-1 behavior at 20 °C / 50 % RH, documented approximation)."""
    return -0.3 * max(dist_m - 1.0, 0.0)


def direct_tap(sig: np.ndarray, sr: int, az_deg: float, dist_m: float,
               itd_sr_scale: bool = True) -> np.ndarray:
    """Mono or stereo source -> stereo direct path at the seat: 1/r gain,
    air shelf, and for mono sources constant-power pan + ITD. Stereo
    sources (sections) keep their internal image; only gain/air apply."""
    dist = max(float(dist_m), 1.0)
    g = 1.0 / dist
    shelf = air_shelf_db(dist)
    if sig.ndim == 2:
        out = sig * g
        if shelf < -0.05:
            out = np.stack([eq_fx(out[:, c], sr, "highshelf", 6000.0,
                                  shelf) for c in (0, 1)], axis=1)
        return out
    x = sig * g
    if shelf < -0.05:
        x = eq_fx(x, sr, "highshelf", 6000.0, shelf)
    pan, itd48 = seat_pan_itd(az_deg)
    itd = int(round(itd48 * sr / 48000.0)) if itd_sr_scale else itd48
    theta = (pan + 1.0) * np.pi / 4.0
    left = np.cos(theta) * x
    right = np.sin(theta) * x
    if itd > 0:                      # far ear arrives late
        if pan > 0:                  # source right -> left ear delayed
            left = np.concatenate([np.zeros(itd), left[:-itd]])
        elif pan < 0:
            right = np.concatenate([np.zeros(itd), right[:-itd]])
    return np.stack([left, right], axis=1)


def _image_positions(src, order: int):
    """1-D mirror coordinates for the image-source method."""
    out = []
    for n in range(-order, order + 1):
        out.append((n, src if n % 2 == 0 else -src))
    return out


def early_ir(az_deg: float, dist_m: float, dims, sr: int) -> np.ndarray:
    """Stereo early-reflection IR (~120 ms) for a seat in a shoebox hall
    of dims [W, L, H] m: image-source method to second order, wall
    reflection coefficient 0.82, direct path excluded (the direct tap
    carries it). Image enumeration per axis: coordinate c in a room of
    size D mirrors to k*D + (c if k even else D - c) with |k| bounces.
    Closed-form, seedless, cached per (seat, dims, sr)."""
    key = (round(az_deg, 2), round(dist_m, 2), tuple(dims), sr)
    if key in _early_cache:
        return _early_cache[key]
    W, L, H = (float(d) for d in dims)
    lis = np.array([W / 2.0, L * 0.72, 1.7])         # audience point
    az = np.radians(az_deg)
    src = lis + np.array([np.sin(az) * dist_m, -np.cos(az) * dist_m, 0.0])
    src[2] = 1.4                                      # instrument height
    refl = 0.82
    order = 2
    n_ir = int(0.12 * sr)
    ir = np.zeros((n_ir, 2))
    d_direct = max(np.linalg.norm(src - lis), 1e-6)

    def mirrors(c, D, max_k):
        return [(abs(k), k * D + (c if k % 2 == 0 else D - c))
                for k in range(-max_k, max_k + 1)]

    for ox, x in mirrors(src[0], W, order):
        for oy, y in mirrors(src[1], L, order):
            for oz, z in mirrors(src[2], H, 1):
                o = ox + oy + oz
                if o == 0 or o > order:
                    continue
                img = np.array([x, y, z])
                d = np.linalg.norm(img - lis)
                delay = int(round((d - d_direct) / SPEED_OF_SOUND * sr))
                if delay < 8 or delay >= n_ir:
                    continue
                g = (refl ** o) * (d_direct / d)
                im_az = np.degrees(np.arctan2(img[0] - lis[0],
                                              lis[1] - img[1]))
                pan, _ = seat_pan_itd(im_az)
                theta = (pan + 1.0) * np.pi / 4.0
                ir[delay, 0] += g * np.cos(theta)
                ir[delay, 1] += g * np.sin(theta)
    _early_cache[key] = ir
    return ir


def early_tap(sig_mono: np.ndarray, sr: int, az_deg: float, dist_m: float,
              dims) -> np.ndarray:
    from scipy.signal import fftconvolve
    ir = early_ir(az_deg, dist_m, dims, sr)
    n = sig_mono.size
    return np.stack([fftconvolve(sig_mono, ir[:, c])[:n] for c in (0, 1)],
                    axis=1)


def hall_tail(tail_in: np.ndarray, sr: int, file: str, sha256: str,
              gain_db: float = 0.0) -> np.ndarray:
    """Shared stereo hall: one convolution per stage with a hash-pinned IR
    (stereo IRs give a decorrelated tail; mono IRs apply per channel)."""
    from scipy.signal import fftconvolve
    from .samples import load_sample_multi
    ir = load_sample_multi(file, sha256, sr)          # (n, ch) verified
    if ir.ndim == 1:
        ir = np.stack([ir, ir], axis=1)
    e = np.sqrt((ir ** 2).sum())
    ir = ir / max(e, 1e-9)
    n = tail_in.size
    g = 10.0 ** (gain_db / 20.0)
    return np.stack([fftconvolve(tail_in, ir[:, min(c, ir.shape[1] - 1)])[:n]
                     for c in (0, 1)], axis=1) * g
