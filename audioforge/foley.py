"""Procedural foley models: rain, wind, fire, surf.

Each model is a deterministic texture generator competing directly with
ambience packs: seeded event clouds and gust/wave envelopes over shaped
noise, fully vectorized, every random draw from the layer's RNG paths in
fixed order. `intensity` (0..1) is the one knob that means the same thing
everywhere: how much weather.
"""
from __future__ import annotations

import numpy as np

from . import synth
from .fx import filter_fx


def _smooth_walk(n: int, sr: int, rng, rate_hz: float) -> np.ndarray:
    """Slow seeded control curve in 0..1: steps at ~rate_hz, one-pole
    smoothed (lfilter — no Python loop)."""
    from scipy.signal import lfilter
    n_steps = max(2, int(n / sr * rate_hz) + 2)
    steps = rng.random(n_steps)
    coarse = np.repeat(steps, int(np.ceil(n / n_steps)))[:n]
    a = np.exp(-2.0 * np.pi * rate_hz * 0.5 / sr)
    return lfilter([1.0 - a], [1.0, -a], coarse)


def rain(n: int, sr: int, rng, intensity: float = 0.5,
         brightness: float = 0.5) -> np.ndarray:
    """Wash of distant rain + individual droplet transients. Intensity
    drives both the wash level and the droplet density (40..1200/s)."""
    wash = synth.noise("pink", n, rng)
    wash = filter_fx(wash, sr, "highpass", 800.0)
    wash = filter_fx(wash, sr, "lowpass", 3000.0 + 7000.0 * brightness)
    wash *= 0.25 + 0.55 * intensity

    density = 40.0 + 1160.0 * intensity ** 1.5
    n_drops = max(1, int(density * n / sr))
    t0 = np.sort(rng.uniform(0, n - 600, n_drops)).astype(np.int64)
    amps = rng.random(n_drops) ** 2.5 * 0.8
    freqs = 1800.0 + rng.random(n_drops) * 6500.0 * (0.4 + 0.6 * brightness)
    out = wash.copy()
    dn = 480                                       # 10 ms droplet
    t = np.arange(dn) / sr
    decay = np.exp(-t * 900.0)
    for k in range(n_drops):                        # tiny adds, fixed order
        out[t0[k]:t0[k] + dn] += amps[k] * decay \
            * np.sin(2.0 * np.pi * freqs[k] * t)
    peak = np.max(np.abs(out))
    return out / peak if peak > 1.0 else out


def wind(n: int, sr: int, rng, intensity: float = 0.5,
         brightness: float = 0.4) -> np.ndarray:
    """Gusting broadband wind: brown-noise bed whose level and spectral
    tilt follow a slow seeded gust curve."""
    gust = _smooth_walk(n, sr, rng, 0.35)
    gust = 0.25 + (0.2 + 0.55 * intensity) * gust
    bed = synth.noise("brown", n, rng)
    bed = filter_fx(bed, sr, "highpass", 60.0)
    lo = filter_fx(bed, sr, "lowpass", 400.0)
    hi = filter_fx(bed, sr, "lowpass", 1500.0 + 3500.0 * brightness)
    out = (lo * (1.0 - gust) + hi * gust) * gust
    peak = np.max(np.abs(out))
    return out / peak if peak > 1e-9 else out


def fire(n: int, sr: int, rng, intensity: float = 0.5,
         brightness: float = 0.5) -> np.ndarray:
    """Crackling fire: low rumble bed + hiss + sparse seeded pops with
    randomized pitch and decay. Intensity drives pop density and rumble."""
    rumble = filter_fx(synth.noise("brown", n, rng), sr, "lowpass", 300.0)
    rumble *= 0.3 + 0.4 * intensity
    hiss = filter_fx(synth.noise("white", n, rng), sr, "highpass", 3500.0)
    hiss *= 0.04 + 0.06 * intensity

    density = 4.0 + 36.0 * intensity
    n_pops = max(1, int(density * n / sr))
    t0 = np.sort(rng.uniform(0, n - 2400, n_pops)).astype(np.int64)
    amps = 0.2 + rng.random(n_pops) ** 3 * 0.8
    cuts = 600.0 + rng.random(n_pops) * 5000.0 * (0.4 + 0.6 * brightness)
    lens = (0.004 + rng.random(n_pops) * 0.04)
    out = rumble + hiss
    for k in range(n_pops):
        pn = int(lens[k] * sr)
        t = np.arange(pn) / sr
        pop = (rng.random(pn) * 2.0 - 1.0) * np.exp(-t / (lens[k] * 0.3))
        pop = filter_fx(pop, sr, "lowpass", cuts[k])
        out[t0[k]:t0[k] + pn] += amps[k] * pop
    peak = np.max(np.abs(out))
    return out / peak if peak > 1.0 else out


def surf(n: int, sr: int, rng, intensity: float = 0.5,
         brightness: float = 0.4) -> np.ndarray:
    """Ocean waves: asymmetric swells (faster rise, long wash-out) every
    6..14 s, the noise opening from dark to bright over each swell."""
    period = 14.0 - 6.0 * intensity
    env = np.zeros(n)
    t = 0.0
    while t * sr < n:
        p = period * (0.8 + 0.4 * rng.random())
        rise = 0.25 * p
        fall = 0.75 * p
        a = int(t * sr)
        rn, fn = int(rise * sr), int(fall * sr)
        seg_r = 0.5 - 0.5 * np.cos(np.pi * np.arange(rn) / max(rn, 1))
        seg_f = (0.5 + 0.5 * np.cos(np.pi * np.arange(fn) / max(fn, 1))) ** 1.4
        amp = 0.5 + 0.5 * rng.random()
        for seg, off in ((seg_r, 0), (seg_f, rn)):
            b = a + off
            m = min(seg.size, n - b)
            if m > 0:
                env[b:b + m] = np.maximum(env[b:b + m], amp * seg[:m])
        t += p
    bed = synth.noise("pink", n, rng)
    dark = filter_fx(bed, sr, "lowpass", 700.0)
    brt = filter_fx(bed, sr, "lowpass", 2500.0 + 5000.0 * brightness)
    out = (dark * (1.0 - env) + brt * env) * (0.15 + (0.3 + 0.55 * intensity) * env)
    peak = np.max(np.abs(out))
    return out / peak if peak > 1e-9 else out


FOLEY_MODELS = {"rain": rain, "wind": wind, "fire": fire, "surf": surf}
