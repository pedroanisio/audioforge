"""Instrument-class tests (v2.5): custom modal tables, wavetable morphing,
granular, content-addressed samples, bowed waveguide — each verified
acoustically and for determinism."""
import io
import sys
import wave
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from audioforge import AudioForge  # noqa: E402
from audioforge import samples as smod  # noqa: E402
from audioforge import synth  # noqa: E402
from audioforge.determinism import rng_for  # noqa: E402

SR = 48000
F = AudioForge()


def _mono(src):
    res = F.compile(src)
    assert res.ok, [d.message for d in res.diagnostics]
    s, sr, _ = res.assets[0].render()
    return s.mean(axis=1), sr


def _spec(x, sr):
    s = np.abs(np.fft.rfft(x * np.hanning(x.size)))
    return s, np.fft.rfftfreq(x.size, 1 / sr)


def test_custom_modes_place_partials():
    """Declared mode ratios must appear as spectral peaks."""
    ratios = [1.0, 2.31, 3.92]
    x, sr = _mono("""
asset m {
  kind: cue
  duration: 2s
  tempo: 60bpm
  layer t : notes {
    osc: modal
    modes: 1.0 1.0 1.0, 2.31 0.6 0.5, 3.92 0.4 0.35
    modedecay: 1.5s
    gain: -6db
    env: a=0.005s d=0.5s s=0.3 r=0.5s
    notes: A3 @ 0b for 2b
  }
  master { peak: -1db
           fadeout: 0.05s }
}
""")
    s, f = _spec(x[:sr], sr)
    f0 = 220.0
    floor = s.mean()
    for r in ratios:
        band = (f > f0 * r * 0.97) & (f < f0 * r * 1.03)
        assert s[band].max() > 12 * floor, f"mode {r} missing"
    # and a ratio NOT declared is absent
    band = (f > f0 * 3.0 * 0.98) & (f < f0 * 3.0 * 1.02)
    assert s[band].max() < 6 * floor
    print("PASS  custom modes: partials at declared ratios only")


def test_morph_scan_changes_spectrum():
    base = """
asset w {{
  kind: cue
  duration: 2s
  tempo: 60bpm
  layer t : tone {{
    osc: morph
    note: A2
    scan: {scan}
    duration: 2s
    gain: -8db
    env: a=0.02s d=0.2s s=0.9 r=0.1s
  }}
  master {{ peak: -1db
           fadeout: 0.05s }}
}}
"""
    sine_end, sr = _mono(base.format(scan=0.0))
    saw_zone, _ = _mono(base.format(scan=0.75))

    def harm_energy(x):
        s, f = _spec(x, sr)
        return s[(f > 250) & (f < 4000)].sum() / s[(f > 80) & (f < 250)].sum()
    e0, e1 = harm_energy(sine_end), harm_energy(saw_zone)
    assert e1 > 8 * e0, (e0, e1)
    print(f"PASS  morph: harmonic content x{e1 / e0:.0f} from scan 0 -> 0.75")


def test_morph_scan_automation():
    x, sr = _mono("""
asset wa {
  kind: cue
  duration: 4s
  tempo: 60bpm
  layer t : tone {
    osc: morph
    note: A2
    duration: 4s
    gain: -8db
    env: a=0.02s d=0.2s s=0.9 r=0.1s
    auto scan: 0s=0, 4s=1
  }
  master { peak: -1db
           fadeout: 0.05s }
}
""")
    def centroid(seg):
        s, f = _spec(seg, sr)
        return (s * f).sum() / s.sum()
    early = centroid(x[int(0.2 * sr):int(1.0 * sr)])
    late = centroid(x[int(3.0 * sr):int(3.8 * sr)])
    assert late > 2.0 * early, (early, late)
    print(f"PASS  morph automation: centroid rides {early:.0f} -> "
          f"{late:.0f} Hz across the scan")


def test_granular_deterministic_and_spread():
    g1 = synth.granular(np.sin(np.arange(SR) / SR * 2 * np.pi * 440), SR, SR,
                        rng_for("h", "g", "grains"), pitch_spread_cents=80.0)
    g2 = synth.granular(np.sin(np.arange(SR) / SR * 2 * np.pi * 440), SR, SR,
                        rng_for("h", "g", "grains"), pitch_spread_cents=80.0)
    assert np.array_equal(g1, g2)
    g0 = synth.granular(np.sin(np.arange(SR) / SR * 2 * np.pi * 440), SR, SR,
                        rng_for("h", "g", "grains"), pitch_spread_cents=0.0)

    def width(x):
        s, f = _spec(x, SR)
        band = (f > 340) & (f < 560)
        p = s[band] / s[band].sum()
        mu = (p * f[band]).sum()
        return np.sqrt((p * (f[band] - mu) ** 2).sum())
    assert width(g1) > 1.5 * width(g0), (width(g0), width(g1))
    print(f"PASS  granular: deterministic; pitch spread widens line "
          f"{width(g0):.0f} -> {width(g1):.0f} Hz")


def _make_sample():
    sr = SR
    t = np.arange(int(0.2 * sr)) / sr
    x = np.sin(2 * np.pi * 200 * t) * np.exp(-t * 30)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((x * 32000).astype("<i2").tobytes())
    return buf.getvalue()


def test_sample_layer_hash_and_pattern():
    data = _make_sample()
    sha = smod.register_sample("t_hit.wav", data)
    src = f"""
asset sp {{
  kind: loop
  duration: 2s
  tempo: 120bpm
  layer s : sample {{
    file: "t_hit.wav"
    sha256: "{sha}"
    pattern: X...X...X...X...
    gain: -6db
  }}
  master {{ peak: -1db
           fadeout: 0.02s }}
}}
"""
    a, sr = _mono(src)
    b, _ = _mono(src)
    assert np.array_equal(a, b)
    # hits land on the grid: energy at beat positions
    step = int(60 / 120 * sr)
    on = sum(np.abs(a[i * step:i * step + 2000]).max() for i in range(4))
    off = sum(np.abs(a[i * step + step // 2:i * step + step // 2 + 2000]).max()
              for i in range(3))
    assert on > 5 * off, (on, off)
    # mismatch refuses
    # a repeated-char pin is placeholder-shaped: the distinct diagnostic
    res = F.compile(src.replace(sha, "f" * 64))
    try:
        res.assets[0].render()
        raise AssertionError("placeholder pin not refused")
    except Exception as e:
        assert "unbound placeholder" in str(e)
    # a realistic wrong pin: the genuine mismatch path, both hashes cited
    res = F.compile(src.replace(sha, ("fe" * 32)))
    try:
        res.assets[0].render()
        raise AssertionError("hash mismatch not refused")
    except Exception as e:
        assert "hash mismatch" in str(e)
    print("PASS  sample layer: byte-deterministic, pattern-triggered, "
          "wrong hash refused")


def test_bowed_voice_pitch():
    x, sr = _mono("""
asset bw {
  kind: cue
  duration: 2.5s
  tempo: 60bpm
  layer c : notes {
    osc: bowed
    pressure: 0.6
    bowpos: 0.13
    gain: -8db
    env: a=0.1s d=0.2s s=0.9 r=0.3s
    notes: A2 @ 0b for 2.5b
  }
  master { peak: -1db
           fadeout: 0.05s }
}
""")
    seg = x[sr:2 * sr]
    s, f = _spec(seg, sr)
    band = (f > 90) & (f < 130)
    peak = f[band][np.argmax(s[band])]
    assert abs(peak - 110.0) < 4.0, peak
    assert np.sqrt(np.mean(seg ** 2)) > 0.01      # sustains, not a pluck
    print(f"PASS  bowed: sustained self-oscillation at {peak:.1f} Hz "
          f"(A2 = 110)")


if __name__ == "__main__":
    test_custom_modes_place_partials()
    test_morph_scan_changes_spectrum()
    test_morph_scan_automation()
    test_granular_deterministic_and_spread()
    test_sample_layer_hash_and_pattern()
    test_bowed_voice_pitch()
    print("\nAll instrument-class tests passed.")
