#!/usr/bin/env python3
"""Compare two audio renderings wave-vs-wave: a reference recording and an
AudioForge recreation of the same score.

A sampled/synth recreation is never sample-identical to a human recording
(timbre, rubato, room differ), so equality is the wrong question. This tool
measures *musical* agreement that is robust to those differences:

  * chroma (12 pitch-class) agreement, DTW-aligned so rubato doesn't penalise;
  * global pitch-class histogram correlation (tempo/timbre invariant);
  * spectral-centroid / duration summary.

It writes a JSON report and a PNG (waveforms + chromagrams + aligned
similarity). No librosa — chroma/DTW are implemented on numpy/scipy.

    python3 scripts/compare_waves.py REF RENDER [-o compare/report]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from scipy.signal import resample_poly, stft

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from audioforge.library import _decode_wav_bytes  # noqa: E402

SR = 22050
_A4 = 440.0


def load_mono(path: Path) -> np.ndarray:
    # reuse the engine's own decoder: handles 16/24/32-bit WAV and, via
    # libsndfile, FLAC/Ogg/MP3 — and returns mono float.
    x, sr = _decode_wav_bytes(path.read_bytes(), path.suffix.lower().lstrip("."))
    if sr != SR:
        x = resample_poly(x, SR, sr)
    m = np.abs(x).max()
    return x / m if m > 0 else x


def trim_lead(x: np.ndarray, thresh=0.02, preroll_s=0.05) -> np.ndarray:
    """Drop leading silence: start a hair before the first sample whose local
    RMS clears `thresh` of peak. Aligns a recording's silent pre-roll/soft
    entrance against a render that starts on the first note."""
    hop = 256
    n = len(x) // hop
    env = np.array([np.sqrt(np.mean(x[i*hop:(i+1)*hop]**2)) for i in range(n)])
    env /= env.max() + 1e-9
    hits = np.where(env > thresh)[0]
    if not len(hits):
        return x
    start = max(0, hits[0] * hop - int(preroll_s * SR))
    return x[start:]


def chromagram(x: np.ndarray, n=4096, hop=1024) -> tuple[np.ndarray, np.ndarray]:
    f, t, Z = stft(x, fs=SR, nperseg=n, noverlap=n - hop, boundary=None)
    mag = np.abs(Z)
    keep = (f > 55) & (f < 5000)
    f, mag = f[keep], mag[keep]
    pc = np.mod(np.round(12 * np.log2(f / _A4) + 69).astype(int), 12)
    chroma = np.zeros((12, mag.shape[1]))
    for k in range(12):
        chroma[k] = mag[pc == k].sum(axis=0)
    chroma /= (chroma.sum(axis=0, keepdims=True) + 1e-9)
    return chroma, t


def dtw_cosine(A: np.ndarray, B: np.ndarray):
    """DTW on cosine distance between chroma columns. Returns (path, mean
    cosine similarity along path)."""
    An = A / (np.linalg.norm(A, axis=0, keepdims=True) + 1e-9)
    Bn = B / (np.linalg.norm(B, axis=0, keepdims=True) + 1e-9)
    S = An.T @ Bn                         # cosine similarity matrix
    D = 1.0 - S
    n, m = D.shape
    acc = np.full((n + 1, m + 1), np.inf)
    acc[0, 0] = 0.0
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            acc[i, j] = D[i - 1, j - 1] + min(
                acc[i - 1, j], acc[i, j - 1], acc[i - 1, j - 1])
    # backtrack
    i, j, path = n, m, []
    while i > 0 and j > 0:
        path.append((i - 1, j - 1))
        step = min(acc[i - 1, j], acc[i, j - 1], acc[i - 1, j - 1])
        if step == acc[i - 1, j - 1]:
            i, j = i - 1, j - 1
        elif step == acc[i - 1, j]:
            i -= 1
        else:
            j -= 1
    path.reverse()
    sims = [S[a, b] for a, b in path]
    return path, float(np.mean(sims))


def spectral_centroid(x: np.ndarray) -> float:
    f, _, Z = stft(x, fs=SR, nperseg=4096, noverlap=3072, boundary=None)
    mag = np.abs(Z).mean(axis=1)
    return float((f * mag).sum() / (mag.sum() + 1e-9))


def rhythm_metrics(x: np.ndarray) -> dict:
    """Quantify how *mechanical* the playing is. A metronomic, uniform-velocity
    render has very even note spacing (low onset-interval variation) and a
    strongly periodic amplitude envelope; a human performance (rubato +
    dynamics + pedal) is less even and less periodic."""
    hop = 256
    n = len(x) // hop
    env = np.array([np.sqrt(np.mean(x[i*hop:(i+1)*hop]**2)) for i in range(n)])
    env /= env.max() + 1e-9
    fr = SR / hop                                   # envelope frame rate
    # onset detection: peaks in the positive envelope difference
    d = np.diff(env, prepend=env[0]).clip(min=0)
    thr = d.mean() + d.std()
    onsets = [i for i in range(1, len(d) - 1)
              if d[i] > thr and d[i] >= d[i-1] and d[i] > d[i+1]]
    iois = np.diff(onsets) / fr if len(onsets) > 2 else np.array([])
    ioi_cov = float(iois.std() / (iois.mean() + 1e-9)) if iois.size else 0.0
    dyn_cov = (float(env[onsets].std() / (env[onsets].mean() + 1e-9))
               if onsets else 0.0)
    # pulse periodicity: strongest autocorrelation peak in 0.12..1.0 s lag
    e = env - env.mean()
    ac = np.correlate(e, e, "full")[len(e)-1:]
    ac /= ac[0] + 1e-9
    lo, hi = int(0.12 * fr), int(1.0 * fr)
    periodicity = float(ac[lo:hi].max()) if hi < len(ac) else 0.0
    return {"onsets": len(onsets),
            "onset_interval_cov": round(ioi_cov, 3),
            "dynamic_cov": round(dyn_cov, 3),
            "pulse_periodicity": round(periodicity, 3)}


def compare(ref_path: Path, rend_path: Path, out_stem: Path) -> dict:
    ref, rend = load_mono(ref_path), load_mono(rend_path)
    # align on the first real onset so the reference's silent pre-roll / soft
    # entrance doesn't sit against the render's immediate first note
    ref, rend = trim_lead(ref), trim_lead(rend)
    # the recreation is the score length; trim the (longer) reference to match
    span = min(len(ref), len(rend))
    ref_t = ref[:span] if len(ref) > len(rend) else ref
    rend_t = rend[:len(ref)] if len(rend) > len(ref) else rend
    cref, tref = chromagram(ref_t)
    crend, trend = chromagram(rend_t)
    path, dtw_sim = dtw_cosine(cref, crend)
    # global pitch-class histograms (whole compared spans)
    href = cref.mean(axis=1)
    hrend = crend.mean(axis=1)
    hist_corr = float(np.corrcoef(href, hrend)[0, 1])
    report = {
        "reference": str(ref_path),
        "recreation": str(rend_path),
        "reference_duration_s": round(len(ref) / SR, 2),
        "recreation_duration_s": round(len(rend) / SR, 2),
        "compared_span_s": round(span / SR, 2),
        "chroma_dtw_cosine_similarity": round(dtw_sim, 4),
        "pitch_class_histogram_correlation": round(hist_corr, 4),
        "reference_spectral_centroid_hz": round(spectral_centroid(ref_t), 1),
        "recreation_spectral_centroid_hz": round(spectral_centroid(rend_t), 1),
        "rhythm_reference": rhythm_metrics(ref_t),
        "rhythm_recreation": rhythm_metrics(rend_t),
        "pitch_class_profile": {
            "reference": [round(v, 3) for v in href],
            "recreation": [round(v, 3) for v in hrend]},
    }
    _plot(ref_t, rend_t, cref, crend, report, out_stem.with_suffix(".png"))
    out_stem.with_suffix(".json").write_text(json.dumps(report, indent=2) + "\n")
    return report


def _plot(ref, rend, cref, crend, rep, png: Path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
    fig, ax = plt.subplots(3, 2, figsize=(13, 9))
    for col, (sig, ch, title) in enumerate(
            [(ref, cref, "Reference (Ishizaka, CC0)"),
             (rend, crend, "AudioForge recreation")]):
        tt = np.arange(len(sig)) / SR
        ax[0, col].plot(tt, sig, lw=0.4)
        ax[0, col].set_title(f"{title}\nwaveform")
        ax[0, col].set_xlim(0, len(sig) / SR)
        ax[1, col].imshow(ch, aspect="auto", origin="lower", cmap="magma",
                          extent=[0, ch.shape[1], 0, 12])
        ax[1, col].set_yticks(np.arange(12) + 0.5)
        ax[1, col].set_yticklabels(names, fontsize=7)
        ax[1, col].set_title("chromagram")
    x = np.arange(12)
    ax[2, 0].bar(x - 0.2, rep["pitch_class_profile"]["reference"], 0.4,
                 label="reference")
    ax[2, 0].bar(x + 0.2, rep["pitch_class_profile"]["recreation"], 0.4,
                 label="recreation")
    ax[2, 0].set_xticks(x)
    ax[2, 0].set_xticklabels(names, fontsize=7)
    ax[2, 0].set_title("pitch-class profile")
    ax[2, 0].legend(fontsize=8)
    ax[2, 1].axis("off")
    rr, rc = rep["rhythm_reference"], rep["rhythm_recreation"]
    ax[2, 1].text(0.02, 0.98,
                  "wave-vs-wave agreement\n\n"
                  f"chroma DTW cosine sim : {rep['chroma_dtw_cosine_similarity']}\n"
                  f"pitch-class hist corr : {rep['pitch_class_histogram_correlation']}\n\n"
                  f"centroid ref / recr.  : {rep['reference_spectral_centroid_hz']:.0f}"
                  f" / {rep['recreation_spectral_centroid_hz']:.0f} Hz\n\n"
                  "mechanical-ness        ref   recr.\n"
                  f"onset-interval CoV   {rr['onset_interval_cov']:6.2f}"
                  f"  {rc['onset_interval_cov']:6.2f}\n"
                  f"dynamic CoV          {rr['dynamic_cov']:6.2f}"
                  f"  {rc['dynamic_cov']:6.2f}\n"
                  f"pulse periodicity    {rr['pulse_periodicity']:6.2f}"
                  f"  {rc['pulse_periodicity']:6.2f}\n\n"
                  "(human = higher CoV, lower periodicity)",
                  va="top", family="monospace", fontsize=9)
    fig.tight_layout()
    fig.savefig(png, dpi=110)
    plt.close(fig)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("reference")
    ap.add_argument("recreation")
    ap.add_argument("-o", "--out", default="compare/report")
    a = ap.parse_args(argv)
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    rep = compare(Path(a.reference), Path(a.recreation), out)
    print(json.dumps(rep, indent=2))
    print(f"\nwrote {out.with_suffix('.json')} and {out.with_suffix('.png')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
