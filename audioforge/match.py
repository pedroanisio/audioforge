"""Audio -> editable AudioForge patch, by offline analysis-by-synthesis.

Given a target sample, infer a *playable, inspectable* `.af` patch whose render
approximates the target's timbre and amplitude shape. The engine is its own
forward model: candidate specs are rendered and scored against the target, the
best is returned as IR (and DSL), and — crucially — re-rendered and re-measured
so the reported quality is *verified*, not asserted.

⚠ ARCHITECTURAL CONTRACT (PALS's LAW, applied to inference)
An inferred patch is an approximation, not ground truth. This module never
returns a match it has not re-rendered and re-scored: `verified_distance` and
`confidence` come from an independent render of the emitted spec, so a caller
can gate on measured fidelity rather than trusting the optimiser. The output is
explicit IR/DSL — diffable, hash-trackable, and byte-reproducible — so a human
or agent can read and edit exactly what will render.

Scope (first slice): pitched, single-voice *timbre* matching — oscillator
choice, brightness, FM colour, and an ADSR fitted from the target's envelope.
It does not yet model drums/noise one-shots, evolving/morphing timbres,
polyphony, or microtonal pitch (pitch is quantised to the nearest semitone, the
only pitch the tone DSL surface exposes). These are honest limits, reported in
the result, not silent failures.
"""
from __future__ import annotations

import math

import numpy as np

from . import theory
from .analysis import analyze_audio
from .decompile import spec_to_dsl
from .quality import _avg_spectrum
from .render import render as _render_audio

# Deterministic search grid. Fixed order; ties resolved by first-seen — so the
# same target bytes always yield the same patch.
_OSCILLATORS = ("sine", "triangle", "saw", "square", "fm",
                "organ", "pad", "pluck", "struck", "modal")
_CUTOFFS_HZ = (None, 700.0, 1400.0, 2800.0, 5600.0, 11000.0)
_FM_RATIOS = (1.0, 2.0, 3.0, 3.5)
_FM_INDICES = (1.0, 3.0, 6.0)

_LOG_BINS = 48          # log-frequency spectral-envelope resolution
_LO_HZ = 50.0
_ENV_POINTS = 64        # amplitude-envelope comparison resolution
_W_SPECTRAL = 0.8       # timbre dominates the objective; envelope shapes it
_W_ENVELOPE = 0.2


def _mono(stereo: np.ndarray) -> np.ndarray:
    arr = np.asarray(stereo, dtype=np.float64)
    if arr.ndim == 2:
        arr = arr.mean(axis=1)
    if arr.size == 0:
        raise ValueError("cannot match empty audio")
    return arr


def _frame_rms_env(mono: np.ndarray, sr: int, hop: int = 256) -> np.ndarray:
    n = max(1, len(mono) // hop)
    frame = max(hop, 2 * hop)
    out = np.empty(n)
    for i in range(n):
        seg = mono[i * hop:i * hop + frame]
        out[i] = math.sqrt(float(np.mean(seg * seg)) + 1e-24) if seg.size else 0.0
    return out


def _log_spectral_envelope(mono: np.ndarray, sr: int) -> np.ndarray:
    """Averaged magnitude spectrum resampled onto log-spaced bins and L1-
    normalised: a loudness- and (coarsely) pitch-robust timbre descriptor."""
    freqs, spec = _avg_spectrum(mono, sr)
    hi = sr / 2.0
    edges = np.geomspace(_LO_HZ, hi, _LOG_BINS + 1)
    env = np.zeros(_LOG_BINS)
    idx = np.clip(np.searchsorted(edges, freqs) - 1, 0, _LOG_BINS - 1)
    for b in range(_LOG_BINS):
        sel = spec[idx == b]
        env[b] = float(sel.sum())
    total = env.sum()
    return env / total if total > 0 else env


def _estimate_f0(mono: np.ndarray, sr: int) -> tuple[float, float]:
    """Autocorrelation f0 over a post-attack window. Returns (f0_hz,
    harmonicity 0..1); harmonicity gates whether the target is pitched."""
    n = len(mono)
    a = mono[int(0.1 * n):int(0.6 * n)] if n > 20 else mono
    a = a - a.mean()
    if a.size < 64 or np.max(np.abs(a)) < 1e-9:
        return 0.0, 0.0
    ac = np.correlate(a, a, "full")[a.size - 1:]
    ac0 = ac[0] if ac[0] != 0 else 1.0
    lo = max(1, int(sr / 2000.0))
    hi = min(len(ac) - 1, int(sr / 50.0))
    if hi <= lo:
        return 0.0, 0.0
    seg = ac[lo:hi]
    peak = float(seg.max())
    # Pick the SHORTEST-lag strong peak, not the global max: a periodic signal
    # autocorrelates at T, 2T, 3T… with similar height, and the global argmax is
    # often a sub-octave (the classic octave-halving error). The first peak
    # clearing 0.8·max is the true fundamental.
    thr = 0.8 * peak
    k = lo + int(np.argmax(seg))
    for i in range(1, len(seg) - 1):
        if seg[i] >= thr and seg[i] >= seg[i - 1] and seg[i] >= seg[i + 1]:
            k = lo + i
            break
    return sr / float(k), float(max(0.0, min(1.0, ac[k] / ac0)))


def _freq_to_note(f0: float) -> str:
    midi = 69 + 12.0 * math.log2(max(f0, 1e-6) / 440.0)
    return theory.semis_to_note(int(round(midi)) - 12)


def _estimate_adsr(mono: np.ndarray, sr: int, dur: float) -> dict:
    """Heuristic ADSR from the RMS envelope: attack = time-to-peak, decay =
    time to 1/e of peak, sustain = late-window level, release ~ decay."""
    env = _frame_rms_env(mono, sr)
    hop = 256
    if env.size < 3 or env.max() <= 1e-9:
        return {"attack": 0.01, "decay": 0.2, "sustain": 0.6, "release": 0.2}
    p = int(np.argmax(env))
    peak = float(env[p])
    attack = max(0.002, p * hop / sr)
    thr = peak / math.e
    after = np.where(env[p:] < thr)[0]
    decay = max(0.02, (after[0] * hop / sr) if after.size else dur * 0.4)
    late = env[int(0.8 * env.size):]
    sustain = float(np.clip((late.mean() / peak) if late.size else 0.4, 0.0, 1.0))
    release = float(np.clip(decay, 0.05, 1.5))
    return {"attack": round(attack, 4), "decay": round(decay, 4),
            "sustain": round(sustain, 4), "release": round(release, 4)}


def _candidate_spec(osc: str, note: str, adsr: dict, dur: float,
                    cutoff: float | None, fm_ratio: float | None,
                    fm_index: float | None) -> dict:
    layer: dict = {"name": "matched", "type": "tone", "osc": osc,
                   "note": note, "gain_db": -6.0, "env": dict(adsr)}
    if osc == "fm" and fm_ratio is not None:
        layer["fm_ratio"] = fm_ratio
        layer["fm_index"] = fm_index
    if cutoff is not None:
        layer["fx"] = [{"type": "filter", "mode": "lowpass",
                        "cutoff_hz": float(cutoff)}]
    return {"id": "matched", "kind": "cue", "duration_s": round(dur, 4),
            "bpm": 120, "key": "C major", "layers": [layer],
            "master": {"target_peak_dbfs": -1.0}}


def _envelope_distance(a_mono: np.ndarray, b_mono: np.ndarray, sr: int) -> float:
    ea, eb = _frame_rms_env(a_mono, sr), _frame_rms_env(b_mono, sr)
    ea = ea / (ea.max() + 1e-12)
    eb = eb / (eb.max() + 1e-12)
    xa = np.linspace(0, 1, _ENV_POINTS)
    ra = np.interp(xa, np.linspace(0, 1, len(ea)), ea)
    rb = np.interp(xa, np.linspace(0, 1, len(eb)), eb)
    return float(np.mean(np.abs(ra - rb)))


def _score(target_env: np.ndarray, target_mono: np.ndarray,
           cand_stereo: np.ndarray, sr: int) -> float:
    cm = _mono(cand_stereo)
    spec_d = float(np.sum(np.abs(target_env - _log_spectral_envelope(cm, sr))))
    env_d = _envelope_distance(target_mono, cm, sr)
    return _W_SPECTRAL * spec_d + _W_ENVELOPE * env_d


def _iter_candidates():
    for osc in _OSCILLATORS:
        if osc == "fm":
            for cutoff in _CUTOFFS_HZ:
                for r in _FM_RATIOS:
                    for ix in _FM_INDICES:
                        yield osc, cutoff, r, ix
        else:
            for cutoff in _CUTOFFS_HZ:
                yield osc, cutoff, None, None


def match_patch(target: np.ndarray, sample_rate: int, *,
                max_duration_s: float = 3.0) -> dict:
    """Infer an editable AudioForge patch approximating ``target``.

    Returns the best spec (IR), its `.af` DSL, the fitted pitch/ADSR, a ranked
    shortlist, and — independently re-rendered — ``verified_distance`` and a
    ``confidence`` in [0, 1]. Lower distance is better.
    """
    sr = int(sample_rate)
    tmono = _mono(target)
    dur = min(max(len(tmono) / sr, 0.1), max_duration_s)
    tmono_scored = tmono[:int(dur * sr)] if len(tmono) > int(dur * sr) else tmono

    f0, harmonicity = _estimate_f0(tmono_scored, sr)
    note = _freq_to_note(f0) if f0 > 0 else "A3"
    adsr = _estimate_adsr(tmono_scored, sr, dur)
    target_env = _log_spectral_envelope(tmono_scored, sr)

    ranking: list[tuple[float, dict, tuple]] = []
    for osc, cutoff, fr, ix in _iter_candidates():
        spec = _candidate_spec(osc, note, adsr, dur, cutoff, fr, ix)
        audio, _sr, _meta = _render_audio(spec)
        d = _score(target_env, tmono_scored, audio, sr)
        ranking.append((d, spec, (osc, cutoff, fr, ix)))
    ranking.sort(key=lambda t: (t[0], _OSCILLATORS.index(t[2][0]),
                                t[2][1] or 0.0))
    best_d, best_spec, _best_params = ranking[0]

    # VERIFY: re-render the chosen patch independently and re-score (PALS).
    v_audio, _vsr, _vmeta = _render_audio(best_spec)
    verified_d = _score(target_env, tmono_scored, v_audio, sr)
    # confidence folds measured fidelity with how pitched the target is.
    fid = max(0.0, 1.0 - verified_d / 1.2)
    confidence = round(float(fid * (0.4 + 0.6 * harmonicity)), 4)

    target_feat = analyze_audio(target, sr)
    matched_feat = analyze_audio(v_audio, _vsr)
    return {
        "spec": best_spec,
        "dsl": spec_to_dsl(best_spec),
        "distance": round(best_d, 6),
        "verified_distance": round(verified_d, 6),
        "confidence": confidence,
        "f0_hz": round(f0, 3),
        "note": note,
        "harmonicity": round(harmonicity, 4),
        "adsr": adsr,
        "target_features": {k: target_feat[k] for k in
                            ("spectral_centroid_hz", "spectral_rolloff85_hz",
                             "low_band_share", "crest_db")},
        "matched_features": {k: matched_feat[k] for k in
                             ("spectral_centroid_hz", "spectral_rolloff85_hz",
                              "low_band_share", "crest_db")},
        "ranking": [{"osc": p[0], "cutoff_hz": p[1], "fm_ratio": p[2],
                     "fm_index": p[3], "distance": round(d, 6)}
                    for d, _s, p in ranking[:5]],
        "limits": ("pitched single-voice timbre match; pitch quantised to the "
                   "nearest semitone; drums/noise, evolving timbres, and "
                   "polyphony are not modelled in this slice"),
    }
