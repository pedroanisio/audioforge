"""Master-bus dynamics: lookahead true-peak limiting.

Design (standard transparent-limiter recipe, fully vectorized and
deterministic): 4x-oversampled stereo-linked peak detection -> required-gain
curve -> lookahead erosion (moving minimum) -> smoothing window -> hard floor
at the required gain so the ceiling is never exceeded at sample positions ->
final oversampled safety check for residual inter-sample overs.
"""
from __future__ import annotations

import numpy as np

from ._native import running_min_fwd
from .convolution import convolve_same


def _true_peak_per_sample(stereo: np.ndarray) -> np.ndarray:
    """Stereo-linked, 4x-oversampled |peak| aligned per base sample.

    Equal to max over the four phases of |resample_poly(stereo, 4, 1)|, but
    computed by a fused native kernel: no 4n oversampled buffers (the old
    cancoes_III OOM path) and no separate abs/max passes."""
    from ._native import true_peak4
    return true_peak4(stereo)


def true_peak_limit(stereo: np.ndarray, sr: int, ceiling_dbfs: float = -1.0,
                    lookahead_ms: float = 5.0) -> tuple[np.ndarray, dict]:
    out, info, _ = _limit(stereo, sr, ceiling_dbfs, lookahead_ms)
    return out, info


def _limit(stereo: np.ndarray, sr: int, ceiling_dbfs: float,
           lookahead_ms: float = 5.0, tp: np.ndarray | None = None):
    """true_peak_limit that also takes/returns the per-sample true peak, so
    master_loudness can carry it across gain steps instead of re-measuring:
    true peak is linear in a scalar gain, tp(s*x) = s*tp(x)."""
    c = 10.0 ** (ceiling_dbfs / 20.0)
    if tp is None:
        tp = _true_peak_per_sample(stereo)
    required = np.minimum(1.0, c / np.maximum(tp, 1e-12))
    if np.all(required >= 1.0 - 1e-9):
        return stereo, {"gain_reduction_db_max": 0.0, "limited": False}, tp

    del tp
    L = max(8, int(lookahead_ms / 1000.0 * sr))
    eroded = running_min_fwd(required, L)          # lookahead erosion
    win = np.hanning(L)
    win /= win.sum()
    padded = np.pad(eroded, L, mode="edge")              # no edge droop
    del eroded
    smooth = convolve_same(padded, win)[L:-L]
    del padded
    gain = np.minimum(smooth, required)                  # never break ceiling
    del smooth, required

    stereo *= gain[:, None]                              # in place: caller
    out = stereo                                         # owns + reassigns
    tp = _true_peak_per_sample(out)                      # inter-sample overs
    resid = tp.max()
    if resid > c:
        out *= c / resid
        tp *= c / resid
    return out, {
        "gain_reduction_db_max": round(-20.0 * np.log10(max(gain.min(), 1e-6)), 2),
        "limited": True,
    }, tp


def master_loudness(stereo: np.ndarray, sr: int, target_lufs: float,
                    ceiling_dbfs: float = -1.0,
                    max_iters: int = 3) -> tuple[np.ndarray, dict]:
    """Gain to the LUFS target, then true-peak limit at the ceiling.
    Because limiting transients removes some loudness, the gain->limit pass
    iterates (with the shortfall as makeup gain) until the measurement
    converges on the target or the iteration budget runs out."""
    from .loudness import integrated_lufs
    measured = integrated_lufs(stereo, sr)
    out = stereo
    total_gain_db = 0.0
    lim: dict = {"gain_reduction_db_max": 0.0, "limited": False}
    final = measured
    tp = None
    for _ in range(max_iters):
        shortfall = target_lufs - final
        if abs(shortfall) >= 0.2:
            total_gain_db += shortfall
            s = 10.0 ** (shortfall / 20.0)
            out *= s
            if tp is not None:
                tp *= s
        out, lim_i, tp = _limit(out, sr, ceiling_dbfs, tp=tp)
        if lim_i["limited"]:
            lim = {"gain_reduction_db_max": max(
                       lim["gain_reduction_db_max"],
                       lim_i["gain_reduction_db_max"]),
                   "limited": True}
        final = integrated_lufs(out, sr)
        if abs(target_lufs - final) < 0.2:
            break
    return out, {
        "measured_lufs": round(measured, 2),
        "applied_gain_db": round(total_gain_db, 2),
        "limiter": lim,
        "final_lufs": round(final, 2),
    }


# ----------------------------------------------------- Tier-3 dynamics
def _static_curve_db(level_db: np.ndarray, threshold: float, ratio: float,
                     knee: float) -> np.ndarray:
    """Soft-knee downward compression curve. Returns gain in dB (<= 0)."""
    over = level_db - threshold
    inv = 1.0 / max(ratio, 1.0) - 1.0
    hard = over * inv
    soft = inv * (over + knee / 2.0) ** 2 / (2.0 * max(knee, 1e-6))
    return np.where(over <= -knee / 2.0, 0.0,
                    np.where(over >= knee / 2.0, hard, soft))


def _comp_gain(detector: np.ndarray, sr: int, threshold: float, ratio: float,
               attack_s: float, release_s: float, knee: float) -> np.ndarray:
    """Lookahead RMS compressor gain curve, fully vectorized:
    windowed-RMS detector (window = attack time, centered => inherent
    lookahead) -> soft-knee static curve -> release-length smoothing.
    A deterministic offline 'glue' design, not an analog feedback model."""
    aw = max(16, int(attack_s * sr))
    win = np.hanning(aw)
    win /= win.sum()
    rms = np.sqrt(np.maximum(
        convolve_same(detector * detector, win), 1e-20))
    level_db = 20.0 * np.log10(rms)
    g_db = _static_curve_db(level_db, threshold, ratio, knee)
    rw = max(16, int(release_s * sr))
    rwin = np.hanning(rw)
    rwin /= rwin.sum()
    padded = np.pad(g_db, rw, mode="edge")
    return convolve_same(padded, rwin)[rw:-rw]


def compressor_stereo(left: np.ndarray, right: np.ndarray, sr: int,
                      fx: dict) -> tuple[np.ndarray, np.ndarray]:
    """Stereo-linked glue compressor (mono-sum detector, equal gain both
    channels preserves the image)."""
    g_db = _comp_gain(0.5 * (left + right), sr,
                      float(fx.get("threshold", -18.0)),
                      float(fx.get("ratio", 2.5)),
                      float(fx.get("attack", 0.03)),
                      float(fx.get("release", 0.15)),
                      float(fx.get("knee", 6.0)))
    g = 10.0 ** ((g_db + float(fx.get("makeup", 0.0))) / 20.0)
    return left * g, right * g


def compressor_mono(x: np.ndarray, sr: int, fx: dict) -> np.ndarray:
    g_db = _comp_gain(x, sr, float(fx.get("threshold", -18.0)),
                      float(fx.get("ratio", 2.5)),
                      float(fx.get("attack", 0.03)),
                      float(fx.get("release", 0.15)),
                      float(fx.get("knee", 6.0)))
    return x * 10.0 ** ((g_db + float(fx.get("makeup", 0.0))) / 20.0)


def _lr4_split(x: np.ndarray, sr: int, fc: float):
    """Linkwitz-Riley 4th-order split (squared Butterworth-2): low + high
    sum back to (allpass-)flat magnitude."""
    from scipy.signal import butter, sosfilt
    sos_l = butter(2, fc / (sr / 2.0), "low", output="sos")
    sos_h = butter(2, fc / (sr / 2.0), "high", output="sos")
    low = sosfilt(sos_l, sosfilt(sos_l, x))
    high = sosfilt(sos_h, sosfilt(sos_h, x))
    return low, high


def _mb_bands(x: np.ndarray, sr: int, f_lo: float, f_hi: float):
    low, rest = _lr4_split(x, sr, f_lo)
    mid, high = _lr4_split(rest, sr, f_hi)
    return low, mid, high


def multiband_stereo(left: np.ndarray, right: np.ndarray, sr: int,
                     fx: dict) -> tuple[np.ndarray, np.ndarray]:
    """3-band glue: LR4 crossovers, per-band stereo-linked compression.
    Controls bass bloom and harsh highs independently — the standard
    mastering move our single-band stage can't make."""
    f_lo = float(fx.get("low", 180.0))
    f_hi = float(fx.get("high", 2800.0))
    params = dict(fx)
    outL = np.zeros_like(left)
    outR = np.zeros_like(right)
    bandsL = _mb_bands(left, sr, f_lo, f_hi)
    bandsR = _mb_bands(right, sr, f_lo, f_hi)
    for bL, bR in zip(bandsL, bandsR):
        cL, cR = compressor_stereo(bL, bR, sr, params)
        outL += cL
        outR += cR
    return outL, outR


def multiband_mono(x: np.ndarray, sr: int, fx: dict) -> np.ndarray:
    f_lo = float(fx.get("low", 180.0))
    f_hi = float(fx.get("high", 2800.0))
    return sum(compressor_mono(b, sr, dict(fx))
               for b in _mb_bands(x, sr, f_lo, f_hi))


def dc_block_lr(left: np.ndarray, right: np.ndarray, sr: int):
    """dc_block on separate channel arrays (same filter, same bits)."""
    from ._native import iir_multi
    R = 1.0 - 2.0 * np.pi * 8.0 / sr
    left, right = iir_multi([left, right], [([1.0, -1.0], [1.0, -R])])
    return left, right


def dc_block(stereo: np.ndarray, sr: int) -> np.ndarray:
    """One-pole DC blocker (~8 Hz) before quantization: synthesis DC offset
    silently eats headroom and biases the limiter; this removes it."""
    from ._native import iir_multi
    R = 1.0 - 2.0 * np.pi * 8.0 / sr
    chans = iir_multi([stereo[:, c] for c in range(stereo.shape[1])],
                      [([1.0, -1.0], [1.0, -R])])
    return np.stack(chans, axis=1)
