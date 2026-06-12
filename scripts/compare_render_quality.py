#!/usr/bin/env python3
"""Render-quality A/B: AudioForge vs a professional sample-based renderer.

Renders the *same note events* two ways and measures the engineering quality of
each finished render (true-peak, noise floor, dynamic spread, bandwidth, band
balance, stereo geometry — see `audioforge.quality`):

  A) AudioForge — `audioforge render <spec>` (native synthesis + master chain).
  B) Professional reference — the spec's MIDI (`audioforge export-midi`) played
     through FluidSynth with a real General-MIDI SoundFont (FluidR3_GM by
     default: Frank Wen, MIT-licensed — the de-facto open GM bank shipped by
     MuseScore and most Linux distros, and a legitimate professional renderer).

Honest scope: `export-midi` is program-agnostic (one flattened channel), so the
professional reference is GM program 0 — a grand piano. This is an
apples-to-apples comparison of *render-pipeline fidelity and overall character*
on identical notes, NOT a claim about instrument realism. Keep the source
material pianistic (see static/samples/reference_piano.af) for the reference to
be musically apt.

    python3 scripts/compare_render_quality.py SPEC.af [-o compare/quality] \
        [--soundfont PATH.sf2] [--gain 0.6]

Writes <out>.json (full metrics + comparison) and <out>.png (spectra + table).
Requires `fluidsynth` on PATH and a GM SoundFont; fails loudly if either is
absent.
"""
from __future__ import annotations

import argparse
import io
import json
import shutil
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from audioforge.quality import (  # noqa: E402
    _db, _true_peak_dbtp, compare_quality, render_quality,
)

_SF_CANDIDATES = [
    "/usr/share/sounds/sf2/FluidR3_GM.sf2",
    "/usr/share/sounds/sf2/default-GM.sf2",
    "/usr/share/sounds/sf3/default-GM.sf3",
]


def load_stereo_wav(path: Path) -> tuple[np.ndarray, int]:
    """Decode a 16/24/32-bit PCM WAV to (float64 [frames, 2], sample_rate),
    preserving stereo so correlation/width are real, not assumed."""
    with wave.open(io.BytesIO(path.read_bytes())) as w:
        sr, ch, sw, n = (w.getframerate(), w.getnchannels(),
                         w.getsampwidth(), w.getnframes())
        raw = w.readframes(n)
    if sw == 2:
        x = np.frombuffer(raw, dtype="<i2").astype(np.float64) / 32768.0
    elif sw == 3:
        b = np.frombuffer(raw, dtype=np.uint8).reshape(-1, 3)
        v = (b[:, 0].astype(np.int32) | (b[:, 1].astype(np.int32) << 8)
             | (b[:, 2].astype(np.int32) << 16))
        x = (v - ((v >> 23) & 1) * (1 << 24)) / float(1 << 23)
    elif sw == 4:
        x = np.frombuffer(raw, dtype="<i4").astype(np.float64) / (2.0 ** 31)
    else:
        raise ValueError(f"unsupported WAV sample width {sw * 8}-bit")
    x = x.reshape(-1, ch)
    if ch == 1:
        x = np.column_stack([x[:, 0], x[:, 0]])
    elif ch > 2:
        x = x[:, :2]
    return x, sr


def find_soundfont(explicit: str | None) -> Path:
    if explicit:
        p = Path(explicit)
        if not p.exists():
            raise SystemExit(f"error: soundfont not found: {p}")
        return p
    for cand in _SF_CANDIDATES:
        if Path(cand).exists():
            return Path(cand)
    raise SystemExit(
        "error: no GM SoundFont found. Install one (e.g. `apt-get install "
        "fluid-soundfont-gm`) or pass --soundfont PATH.sf2")


def af_render(spec: Path, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [sys.executable, "-m", "audioforge.cli", "render", str(spec),
         "-o", str(out_dir)],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    wav = out_dir / f"{spec.stem}.wav"
    if not wav.exists():                     # spec id may differ from filename
        wavs = sorted(out_dir.glob("*.wav"))
        if not wavs:
            raise SystemExit(f"error: AudioForge produced no WAV in {out_dir}")
        wav = wavs[-1]
    return wav


def fluidsynth_render(spec: Path, out_dir: Path, soundfont: Path, sr: int,
                      gain: float) -> Path:
    if shutil.which("fluidsynth") is None:
        raise SystemExit(
            "error: fluidsynth not found on PATH. Install it (e.g. `apt-get "
            "install fluidsynth`) to render the professional reference.")
    midi = out_dir / f"{spec.stem}.mid"
    subprocess.run(
        [sys.executable, "-m", "audioforge.cli", "export-midi", str(spec),
         "-o", str(midi)],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    out_wav = out_dir / f"{spec.stem}_fluidr3.wav"
    subprocess.run(
        ["fluidsynth", "-ni", "-F", str(out_wav), "-r", str(sr),
         "-O", "s24", "-g", str(gain), str(soundfont), str(midi)],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if not out_wav.exists():
        raise SystemExit("error: fluidsynth produced no output WAV")
    return out_wav


def delivery_levels(buf: np.ndarray) -> dict:
    """Raw, as-rendered level story — measured before any normalisation, so it
    reflects what each pipeline actually delivers (mastered vs raw instrument)."""
    peak = float(np.max(np.abs(buf)))
    rms = float(np.sqrt(np.mean(buf * buf)))
    return {
        "peak_dbfs": round(_db(peak), 3),
        "true_peak_dbtp": _true_peak_dbtp(buf),
        "rms_dbfs": round(_db(rms), 3),
    }


def rms_normalize(buf: np.ndarray, target_dbfs: float = -20.0) -> np.ndarray:
    """Loudness-align to a common RMS so level-dependent metrics (noise floor,
    dynamic range, crest) compare fairly — the equal-loudness A/B a mastering
    engineer performs before judging two renders. Spectral and stereo metrics
    are already level-invariant; this only neutralises the arbitrary output
    gain of each renderer."""
    rms = float(np.sqrt(np.mean(buf * buf)))
    if rms <= 1e-12:
        return buf
    return buf * (10.0 ** (target_dbfs / 20.0) / rms)


def run(spec: Path, out_stem: Path, soundfont: Path, gain: float) -> dict:
    out_dir = out_stem.parent
    af_wav = af_render(spec, out_dir)
    af_buf, af_sr = load_stereo_wav(af_wav)
    pro_wav = fluidsynth_render(spec, out_dir, soundfont, af_sr, gain)
    pro_buf, pro_sr = load_stereo_wav(pro_wav)

    af_delivery = delivery_levels(af_buf)
    pro_delivery = delivery_levels(pro_buf)

    # level-align before the comparative metrics (see rms_normalize docstring)
    af_n = rms_normalize(af_buf)
    pro_n = rms_normalize(pro_buf)
    q_af = render_quality(af_n, af_sr)
    q_pro = render_quality(pro_n, pro_sr)
    cmp = compare_quality(q_af, q_pro, label_a="audioforge",
                          label_b="fluidr3_pro")
    report = {
        "spec": str(spec),
        "method": (
            "Same MIDI rendered two ways. Delivery levels are raw; all other "
            "metrics are measured after RMS-normalising both renders to "
            "-20 dBFS for a fair equal-loudness comparison."
        ),
        "renders": {
            "audioforge": {"wav": str(af_wav), "renderer": "AudioForge native synthesis",
                           "delivery": af_delivery},
            "fluidr3_pro": {"wav": str(pro_wav),
                            "renderer": f"FluidSynth + {soundfont.name} (GM grand piano)",
                            "delivery": pro_delivery},
        },
        "audioforge": q_af,
        "fluidr3_pro": q_pro,
        "comparison": cmp,
    }
    out_stem.with_suffix(".json").write_text(json.dumps(report, indent=2) + "\n")
    _plot(af_n, af_sr, pro_n, pro_sr, report, out_stem.with_suffix(".png"))
    return report


def _plot(af, af_sr, pro, pro_sr, rep, png: Path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from audioforge.quality import _avg_spectrum, _frame_rms

    fig, ax = plt.subplots(2, 2, figsize=(13, 8.5))

    # averaged spectra (log-log), the headline visual difference
    for buf, sr, name, c in [(af, af_sr, "AudioForge", "#1f77b4"),
                             (pro, pro_sr, "FluidR3 (pro)", "#d62728")]:
        f, s = _avg_spectrum(buf.mean(axis=1), sr)
        s = s / (s.max() + 1e-12)
        ax[0, 0].semilogx(f[1:], 20 * np.log10(s[1:] + 1e-9), lw=0.8, label=name, color=c)
    ax[0, 0].set_title("Averaged magnitude spectrum (normalised)")
    ax[0, 0].set_xlabel("Hz"); ax[0, 0].set_ylabel("dB")
    ax[0, 0].set_xlim(20, max(af_sr, pro_sr) / 2); ax[0, 0].set_ylim(-90, 3)
    ax[0, 0].grid(True, which="both", alpha=0.3); ax[0, 0].legend(fontsize=9)

    # frame-RMS envelope: dynamic spread & noise floor over time
    for buf, sr, name, c in [(af, af_sr, "AudioForge", "#1f77b4"),
                             (pro, pro_sr, "FluidR3 (pro)", "#d62728")]:
        m = buf.mean(axis=1)
        frame = max(256, int(0.043 * sr)); hop = frame // 2
        fr = _frame_rms(m, frame, hop)
        t = np.arange(len(fr)) * hop / sr
        ax[0, 1].plot(t, 20 * np.log10(fr + 1e-9), lw=0.8, label=name, color=c)
    ax[0, 1].set_title("Frame-RMS envelope (43 ms)")
    ax[0, 1].set_xlabel("s"); ax[0, 1].set_ylabel("dBFS")
    ax[0, 1].set_ylim(-100, 0); ax[0, 1].grid(True, alpha=0.3); ax[0, 1].legend(fontsize=9)

    # band-balance bars
    bands = rep["comparison"]["bands"]
    keys = list(bands["audioforge"].keys())
    x = np.arange(len(keys))
    ax[1, 0].bar(x - 0.2, [bands["audioforge"][k] for k in keys], 0.4,
                 label="AudioForge", color="#1f77b4")
    ax[1, 0].bar(x + 0.2, [bands["fluidr3_pro"][k] for k in keys], 0.4,
                 label="FluidR3 (pro)", color="#d62728")
    ax[1, 0].set_xticks(x)
    ax[1, 0].set_xticklabels([k.split("_")[0] for k in keys], fontsize=8, rotation=30)
    ax[1, 0].set_title("Spectral energy by band (fraction)")
    ax[1, 0].legend(fontsize=9)

    # metric table
    ax[1, 1].axis("off")
    m = rep["comparison"]["metrics"]
    rows = ["true_peak_dbtp", "rms_dbfs", "crest_db", "noise_floor_dbfs",
            "dynamic_range_db", "dc_offset_dbfs", "spectral_centroid_hz",
            "spectral_rolloff99_hz", "ultrasonic_share_db", "stereo_width"]
    lines = [f"{'metric':22} {'AudioForge':>11} {'FluidR3':>11}  favours", ""]
    for k in rows:
        if k not in m:
            continue
        e = m[k]
        fav = e["favours"] or "-"
        lines.append(f"{k:22} {e['audioforge']:>11.2f} {e['fluidr3_pro']:>11.2f}  {fav}")
    wins = rep["comparison"]["scored_metric_wins"]
    lines += ["", f"scored-metric tally  AudioForge {wins.get('audioforge', 0)}"
              f"  ·  FluidR3 {wins.get('fluidr3_pro', 0)}",
              "(scored = cleaner/more-dynamic metrics only;",
              " timbre & band balance are descriptive, not scored)"]
    ax[1, 1].text(0.0, 1.0, "\n".join(lines), va="top", family="monospace",
                  fontsize=8.5)

    fig.suptitle("Render-quality A/B — same notes, two renderers", fontsize=13)
    fig.tight_layout(rect=[0, 0, 1, 0.97])
    fig.savefig(png, dpi=110)
    plt.close(fig)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("spec")
    ap.add_argument("-o", "--out", default="compare/quality")
    ap.add_argument("--soundfont", default=None)
    ap.add_argument("--gain", type=float, default=0.6)
    a = ap.parse_args(argv)
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    sf = find_soundfont(a.soundfont)
    rep = run(Path(a.spec), out, sf, a.gain)
    cmp = rep["comparison"]
    print(json.dumps({
        "spec": rep["spec"],
        "scored_metric_wins": cmp["scored_metric_wins"],
        "delivery_true_peak_dbtp": {
            "audioforge": rep["renders"]["audioforge"]["delivery"]["true_peak_dbtp"],
            "fluidr3_pro": rep["renders"]["fluidr3_pro"]["delivery"]["true_peak_dbtp"]},
        "noise_floor_dbfs_at_-20rms": {
            "audioforge": rep["audioforge"]["noise_floor_dbfs"],
            "fluidr3_pro": rep["fluidr3_pro"]["noise_floor_dbfs"]},
        "dynamic_range_db_at_-20rms": {
            "audioforge": rep["audioforge"]["dynamic_range_db"],
            "fluidr3_pro": rep["fluidr3_pro"]["dynamic_range_db"]}},
        indent=2))
    print(f"\nwrote {out.with_suffix('.json')} and {out.with_suffix('.png')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
