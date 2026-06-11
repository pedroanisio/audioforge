"""Effects. Each effect is a pure function (mono in, mono out) except the
stereo stage, which happens at mixdown. Ordering follows the spec's fx list.
"""
from __future__ import annotations

import numpy as np
from scipy.signal import fftconvolve, lfilter, resample_poly

_FV_COMBS = (1116, 1188, 1277, 1356, 1422, 1491, 1557, 1617)   # @44.1k
_FV_ALLPASS = (556, 441, 341, 225)


def _lbcf(x, L, g, d):
    """Lowpass-feedback comb (Freeverb building block), block recurrence:
    y[n] = x[n] + g * f[n];  f[n] = (1-d) * y[n-L] + d * f[n-1]."""
    n = x.size
    y = np.zeros(n)
    zi = np.zeros(1)
    for s in range(0, n, L):
        e = min(s + L, n)
        ydel = y[s - L:e - L] if s >= L else np.zeros(e - s)
        fblk, zi = lfilter([1.0 - d], [1.0, -d], ydel, zi=zi)
        y[s:e] = x[s:e] + g * fblk
    return y


def _fv_allpass(x, L, g=0.5):
    """Schroeder allpass y[n] = -g x[n] + x[n-L] + g y[n-L], blockwise."""
    n = x.size
    y = np.zeros(n)
    for s in range(0, n, L):
        e = min(s + L, n)
        xdel = x[s - L:e - L] if s >= L else np.zeros(e - s)
        ydel = y[s - L:e - L] if s >= L else np.zeros(e - s)
        y[s:e] = -g * x[s:e] + xdel + g * ydel
    return y


def hall_fx(x: np.ndarray, sr: int, rt60: float = 2.5, damp: float = 0.4,
            mix: float = 0.3) -> np.ndarray:
    """Freeverb-lineage hall (Schroeder/Moorer family): parallel lowpass-
    feedback combs + series allpasses. Per-comb feedback derived from the
    requested RT60, in-loop damping rolls highs off faster — natural,
    frequency-dependent decay without metallic ringing. Deterministic."""
    scale = sr / 44100.0
    wet = np.zeros_like(x)
    for L0 in _FV_COMBS:
        L = max(8, int(round(L0 * scale)))
        g = 10.0 ** (-3.0 * L / (max(rt60, 0.05) * sr))
        wet += _lbcf(x, L, g, float(np.clip(damp, 0.0, 0.95)))
    wet /= len(_FV_COMBS)
    for L0 in _FV_ALLPASS:
        wet = _fv_allpass(wet, max(4, int(round(L0 * scale))))
    return (1.0 - mix) * x + mix * wet


def _biquad(kind: str, fc: float, sr: int, q: float = 0.7071):
    """RBJ cookbook biquad coefficients."""
    fc = min(max(fc, 10.0), sr / 2.0 - 1.0)
    w0 = 2.0 * np.pi * fc / sr
    cosw, sinw = np.cos(w0), np.sin(w0)
    alpha = sinw / (2.0 * q)
    if kind == "lowpass":
        b0 = (1 - cosw) / 2; b1 = 1 - cosw; b2 = (1 - cosw) / 2
    elif kind == "highpass":
        b0 = (1 + cosw) / 2; b1 = -(1 + cosw); b2 = (1 + cosw) / 2
    elif kind == "bandpass":
        b0 = alpha; b1 = 0.0; b2 = -alpha
    else:
        raise ValueError(kind)
    a0 = 1 + alpha; a1 = -2 * cosw; a2 = 1 - alpha
    return np.array([b0, b1, b2]) / a0, np.array([1.0, a1 / a0, a2 / a0])


def filter_fx(x: np.ndarray, sr: int, kind: str, cutoff_hz: float,
              q: float = 0.7071) -> np.ndarray:
    b, a = _biquad(kind, cutoff_hz, sr, q)
    return lfilter(b, a, x)


def delay_fx(x: np.ndarray, sr: int, time_s: float, feedback: float,
             mix: float) -> np.ndarray:
    d = max(1, int(time_s * sr))
    out = np.copy(x)
    buf = np.zeros(x.size + d)
    buf[:x.size] += x
    wet = np.zeros_like(buf)
    fb = min(max(feedback, 0.0), 0.95)
    src = buf
    gain = 1.0
    # bounded number of echo taps -> fully deterministic, no recursion drift
    for tap in range(1, 24):
        gain *= fb
        if gain < 1e-4:
            break
        start = tap * d
        if start >= wet.size:
            break
        seg = min(x.size, wet.size - start)
        wet[start:start + seg] += gain * x[:seg]
    wet = wet[:x.size]
    return (1.0 - mix) * out + mix * (out + wet)


def reverb_fx(x: np.ndarray, sr: int, decay_s: float, mix: float,
              rng: np.random.Generator) -> np.ndarray:
    """Convolution reverb with a deterministic synthetic IR
    (exponentially decaying seeded noise, lightly low-passed)."""
    n_ir = max(16, int(decay_s * sr))
    t = np.arange(n_ir) / sr
    ir = rng.standard_normal(n_ir) * np.exp(-6.0 * t / max(decay_s, 1e-3))
    ir = lfilter(*_biquad("lowpass", 6000.0, sr), ir)
    ir /= (np.sqrt(np.sum(ir**2)) or 1.0)
    wet = fftconvolve(x, ir, mode="full")[:x.size]
    return (1.0 - mix) * x + mix * wet


def drive_fx(x: np.ndarray, amount: float) -> np.ndarray:
    """tanh soft saturation; amount 0..1."""
    g = 1.0 + 9.0 * min(max(amount, 0.0), 1.0)
    return np.tanh(g * x) / np.tanh(g)


def tremolo_fx(x: np.ndarray, sr: int, rate_hz: float, depth: float) -> np.ndarray:
    t = np.arange(x.size) / sr
    mod = 1.0 - depth * 0.5 * (1.0 + np.sin(2.0 * np.pi * rate_hz * t))
    return x * mod


def gain_fx(x: np.ndarray, db: float) -> np.ndarray:
    return x * (10.0 ** (db / 20.0))


def filter_auto_fx(x: np.ndarray, sr: int, kind: str,
                   cutoff_env: np.ndarray, q: float = 0.7071,
                   block: int = 512) -> np.ndarray:
    """Time-varying biquad: cutoff follows a per-sample envelope, with the
    filter state carried across fixed-size blocks (deterministic, no zipper
    noise at these block sizes for musical sweeps)."""
    out = np.empty_like(x)
    zi = np.zeros(2)
    for start in range(0, x.size, block):
        seg = x[start:start + block]
        fc = float(cutoff_env[min(start + seg.size // 2, cutoff_env.size - 1)])
        b, a = _biquad(kind, fc, sr, q)
        out[start:start + seg.size], zi = lfilter(b, a, seg, zi=zi)
    return out


def apply_fx_chain(x: np.ndarray, sr: int, chain: list[dict],
                   rng_factory, automation_envs: dict | None = None) -> np.ndarray:
    """rng_factory(name) -> seeded Generator unique per fx slot.
    automation_envs: {fx_index: cutoff_env ndarray} for automated filters."""
    automation_envs = automation_envs or {}
    for i, fx in enumerate(chain):
        kind = fx["type"]
        if kind == "filter":
            if i in automation_envs:
                x = filter_auto_fx(x, sr, fx["mode"], automation_envs[i],
                                   fx.get("q", 0.7071))
            else:
                x = filter_fx(x, sr, fx["mode"], fx["cutoff_hz"],
                              fx.get("q", 0.7071))
        elif kind == "delay":
            x = delay_fx(x, sr, fx["time_s"], fx.get("feedback", 0.3),
                         fx.get("mix", 0.3))
        elif kind == "reverb":
            x = reverb_fx(x, sr, fx.get("decay_s", 1.2), fx.get("mix", 0.25),
                          rng_factory(f"fx{i}:reverb"))
        elif kind == "drive":
            x = drive_fx(x, fx.get("amount", 0.3))
        elif kind == "tremolo":
            x = tremolo_fx(x, sr, fx.get("rate_hz", 5.0), fx.get("depth", 0.5))
        elif kind == "hall":
            x = hall_fx(x, sr, fx.get("rt60", 2.5), fx.get("damp", 0.4),
                        fx.get("mix", 0.3))
        elif kind in ("plate", "fdn"):
            from .spaces import MONO_FX
            x = MONO_FX[kind](x, sr, fx)
        elif kind == "comp":
            from .dynamics import compressor_mono
            x = compressor_mono(x, sr, fx)
        elif kind == "mbcomp":
            from .dynamics import multiband_mono
            x = multiband_mono(x, sr, fx)
        elif kind == "gain":
            x = gain_fx(x, fx.get("db", 0.0))
        elif kind in ("peak", "lowshelf", "highshelf"):
            x = eq_fx(x, sr, kind, fx["freq_hz"], fx.get("gain_db", 0.0),
                      fx.get("q", 0.7071))
        elif kind == "transient":
            x = transient_fx(x, sr, fx.get("attack_db", 0.0),
                             fx.get("sustain_db", 0.0))
        elif kind == "convolve":
            x = convolve_fx(x, sr, fx["file"], fx["sha256"],
                            fx.get("mix", 0.3), fx.get("gain_db", 0.0))
        elif kind == "saturate":
            x = saturate_fx(x, fx.get("amount", 0.3), fx.get("mix", 1.0),
                            fx.get("warmth", 0.3))
        elif kind == "ladder":
            from ._native import ladder_native
            wet = ladder_native(x, sr, fx["cutoff_hz"],
                                fx.get("resonance", 0.5), fx.get("drive", 0.0))
            mix = float(fx.get("mix", 1.0))
            x = wet if mix >= 1.0 else (1.0 - mix) * x + mix * wet
        elif kind == "tape":
            from ._native import tape_native
            wet = tape_native(x, sr, fx.get("drive", 0.4),
                              fx.get("flutter", 0.3), fx.get("tone", 0.5))
            mix = float(fx.get("mix", 1.0))
            x = wet if mix >= 1.0 else (1.0 - mix) * x + mix * wet
        else:
            from .plugins import FX as FX_PLUGINS
            if kind in FX_PLUGINS:
                x = FX_PLUGINS[kind](x, sr, fx, rng_factory(f"fx{i}:{kind}"))
            else:
                raise ValueError(f"unknown fx type: {kind!r}")
    return x


def apply_master_chain(left: np.ndarray, right: np.ndarray, sr: int,
                       chain: list[dict], rng_factory,
                       automation_envs: dict | None = None):
    """Master-bus chain. Mono fx run per channel (channel-distinct seeded
    paths, as before); plate/fdn are true-stereo: mono-summed network input,
    decorrelated left/right tap outputs."""
    from .dynamics import compressor_stereo, multiband_stereo
    from .spaces import STEREO_FX
    stereo_fx = dict(STEREO_FX)
    stereo_fx["comp"] = compressor_stereo
    stereo_fx["mbcomp"] = multiband_stereo
    automation_envs = automation_envs or {}
    for i, fx in enumerate(chain):
        kind = fx["type"]
        if kind in stereo_fx:
            left, right = stereo_fx[kind](left, right, sr, fx)
        else:
            env = {0: automation_envs[i]} if i in automation_envs else None
            left = apply_fx_chain(left, sr, [fx],
                                  lambda s: rng_factory("L", f"{i}:{s}"),
                                  automation_envs=env)
            right = apply_fx_chain(right, sr, [fx],
                                   lambda s: rng_factory("R", f"{i}:{s}"),
                                   automation_envs=env)
    return left, right


# ------------------------------------------------ v2.6 mix & production
def _rbj_coeffs(kind: str, sr: int, freq: float, gain_db: float,
                q: float) -> tuple:
    """RBJ Audio-EQ-Cookbook biquads: peak, lowshelf, highshelf."""
    A = 10.0 ** (gain_db / 40.0)
    w0 = 2.0 * np.pi * min(freq, sr * 0.49) / sr
    cw, sw = np.cos(w0), np.sin(w0)
    alpha = sw / (2.0 * q)
    if kind == "peak":
        b0, b1, b2 = 1 + alpha * A, -2 * cw, 1 - alpha * A
        a0, a1, a2 = 1 + alpha / A, -2 * cw, 1 - alpha / A
    elif kind == "lowshelf":
        beta = 2.0 * np.sqrt(A) * alpha
        b0 = A * ((A + 1) - (A - 1) * cw + beta)
        b1 = 2 * A * ((A - 1) - (A + 1) * cw)
        b2 = A * ((A + 1) - (A - 1) * cw - beta)
        a0 = (A + 1) + (A - 1) * cw + beta
        a1 = -2 * ((A - 1) + (A + 1) * cw)
        a2 = (A + 1) + (A - 1) * cw - beta
    else:                                   # highshelf
        beta = 2.0 * np.sqrt(A) * alpha
        b0 = A * ((A + 1) + (A - 1) * cw + beta)
        b1 = -2 * A * ((A - 1) + (A + 1) * cw)
        b2 = A * ((A + 1) + (A - 1) * cw - beta)
        a0 = (A + 1) - (A - 1) * cw + beta
        a1 = 2 * ((A - 1) - (A + 1) * cw)
        a2 = (A + 1) - (A - 1) * cw - beta
    return (np.array([b0, b1, b2]) / a0, np.array([1.0, a1 / a0, a2 / a0]))


def eq_fx(x: np.ndarray, sr: int, kind: str, freq: float, gain_db: float,
          q: float = 0.7071) -> np.ndarray:
    from scipy.signal import lfilter
    b, a = _rbj_coeffs(kind, sr, freq, gain_db, q)
    return lfilter(b, a, x)


def _onepole(x: np.ndarray, sr: int, tau_s: float) -> np.ndarray:
    from scipy.signal import lfilter
    a = np.exp(-1.0 / max(tau_s * sr, 1.0))
    return lfilter([1.0 - a], [1.0, -a], x)


def transient_fx(x: np.ndarray, sr: int, attack_db: float = 0.0,
                 sustain_db: float = 0.0) -> np.ndarray:
    """Transient shaper: fast/slow envelope-follower difference steers gain.
    attack_db boosts/cuts onsets; sustain_db boosts/cuts the body."""
    mag = np.abs(x) + 1e-9
    fast = _onepole(mag, sr, 0.0012)
    slow = _onepole(mag, sr, 0.055)
    ratio_db = 20.0 * np.log10(fast / (slow + 1e-12))
    t = np.clip(ratio_db / 9.0, 0.0, 1.0)       # how onset-like
    s = np.clip(-ratio_db / 9.0, 0.0, 1.0)      # how body-like
    g_db = attack_db * t + sustain_db * s
    return x * 10.0 ** (g_db / 20.0)


def saturate_fx(x: np.ndarray, amount: float = 0.3, mix: float = 1.0,
                warmth: float = 0.3) -> np.ndarray:
    """Glue saturation: 4x-oversampled tanh with an even-harmonic warmth
    term, dry/wet mix. Gentler than drive; meant for buses and masters."""
    if amount <= 0.0 or mix <= 0.0:
        return x
    from scipy.signal import resample_poly
    d = 1.0 + amount * 5.0
    bias = warmth * 0.12                        # curve bias -> even harmonics
    up = resample_poly(x, 4, 1)
    up = (np.tanh((up + bias) * d) - np.tanh(bias * d)) / np.tanh(d)
    wet = resample_poly(up, 1, 4)[:x.size]
    return x * (1.0 - mix) + wet * mix


def duck_envelope(src: np.ndarray, sr: int, amount_db: float = 6.0,
                  threshold_db: float = -35.0, attack_s: float = 0.012,
                  release_s: float = 0.18) -> np.ndarray:
    """Sidechain ducking gain curve from a source signal (mono). Gate the
    source against the threshold (1 ms blocks), then approach full/zero
    reduction with attack/release one-poles computed exactly per constant
    segment — vectorized, deterministic, no per-sample Python loop."""
    blk = max(8, sr // 1000)
    nb = src.size // blk
    env = np.abs(src[:nb * blk]).reshape(nb, blk).max(axis=1)
    env_db = 20.0 * np.log10(env + 1e-9)
    target = np.where(env_db > threshold_db, amount_db, 0.0)
    # piecewise-exponential approach over constant-target segments
    edges = np.flatnonzero(np.diff(target)) + 1
    starts = np.concatenate(([0], edges))
    ends = np.concatenate((edges, [nb]))
    a_att = np.exp(-blk / max(attack_s * sr, 1.0))
    a_rel = np.exp(-blk / max(release_s * sr, 1.0))
    gr = np.empty(nb)
    y = 0.0
    for s0, e0 in zip(starts, ends):
        tgt = target[s0]
        a = a_att if tgt > y else a_rel
        seglen = e0 - s0
        k = a ** np.arange(1, seglen + 1)
        gr[s0:e0] = tgt + (y - tgt) * k
        y = gr[e0 - 1]
    gain = 10.0 ** (-gr / 20.0)
    full = np.repeat(gain, blk)
    if full.size < src.size:
        full = np.concatenate([full, np.full(src.size - full.size, full[-1])])
    return full


def convolve_fx(x: np.ndarray, sr: int, file: str, sha256: str,
                mix: float = 0.3, gain_db: float = 0.0) -> np.ndarray:
    """Convolution with a hash-pinned impulse response: real spaces under
    the same content-addressing discipline as samples. The IR is located,
    byte-verified, mono-mixed and resampled by the sample loader; a wrong
    file refuses with both hashes named."""
    from scipy.signal import fftconvolve
    from .samples import load_sample
    ir = load_sample(file, sha256, sr)
    ir = ir / max(np.sqrt(np.sum(ir ** 2)), 1e-9)      # energy-normalized
    wet = fftconvolve(x, ir)[:x.size] * 10.0 ** (gain_db / 20.0)
    return x * (1.0 - mix) + wet * mix
