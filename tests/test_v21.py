"""V2.1 tests: PADsynth, Karplus-Strong, modal, unison, limiter, hall."""
import sys
import tempfile
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from audioforge import AudioForge  # noqa: E402
from audioforge.determinism import rng_for  # noqa: E402
from audioforge.dynamics import master_loudness  # noqa: E402
from audioforge.fx import hall_fx  # noqa: E402
from audioforge.loudness import integrated_lufs  # noqa: E402
from audioforge.synth import modal, padsynth, pluck, unison  # noqa: E402

SR = 48000


def _peak_freq(x, sr):
    spec = np.abs(np.fft.rfft(x * np.hanning(x.size)))
    return np.argmax(spec) * sr / x.size


def test_new_voices_deterministic():
    for name, fn in (("pad", lambda r: padsynth(220.0, SR, SR, r)),
                     ("pluck", lambda r: pluck(220.0, SR, SR, r)),
                     ("modal", lambda r: modal(220.0, SR, SR, r))):
        a = fn(rng_for("root", name))
        b = fn(rng_for("root", name))
        c = fn(rng_for("other", name))
        assert np.array_equal(a, b), name
        assert not np.array_equal(a, c), name  # seed actually matters
    print("PASS  pad/pluck/modal are seed-deterministic")


def test_pluck_pitch():
    f = _peak_freq(pluck(220.0, SR, SR, rng_for("r", "p"))[SR // 10:], SR)
    assert abs(f - 220.0) < 6.0, f
    print(f"PASS  pluck fundamental within tuning tolerance ({f:.1f} Hz)")


def test_modal_partials():
    x = modal(440.0, SR * 2, SR, rng_for("r", "m"), material="glass",
              strike=0.0)
    spec = np.abs(np.fft.rfft(x * np.hanning(x.size)))
    freqs = np.fft.rfftfreq(x.size, 1 / SR)
    for ratio in (1.0, 2.32, 4.25):
        band = spec[(freqs > 440 * ratio * 0.97) & (freqs < 440 * ratio * 1.03)]
        floor = np.median(spec)
        assert band.max() > 50 * floor, ratio
    print("PASS  modal partials sit at the material's mode ratios")


def test_padsynth_loops_and_is_rich():
    x = padsynth(110.0, 1 << 18, SR, rng_for("r", "pad"),
                 bandwidth_cents=50.0)
    # built from one IFFT table -> wraps perfectly at table length
    y = padsynth(110.0, (1 << 18) + 1000, SR, rng_for("r", "pad"),
                 bandwidth_cents=50.0)
    assert np.array_equal(y[:1000], y[1 << 18:])
    print("PASS  padsynth tables loop perfectly")


def test_unison_widens_spectrum():
    mono = unison("saw", 110.0, SR, SR, 1, 0.0)
    wide = unison("saw", 110.0, SR, SR, 7, 25.0)
    s_m = np.abs(np.fft.rfft(mono))
    s_w = np.abs(np.fft.rfft(wide))
    freqs = np.fft.rfftfreq(SR, 1 / SR)
    band = (freqs > 100) & (freqs < 121)
    # energy concentrated in one bin for mono, spread across the band for 7v
    spread_m = (s_m[band] > s_m[band].max() * 0.1).sum()
    spread_w = (s_w[band] > s_w[band].max() * 0.1).sum()
    assert spread_w > spread_m * 2, (spread_m, spread_w)
    print("PASS  unison spreads spectral energy as expected")


def test_limiter_reaches_target_and_holds_ceiling():
    rng = np.random.default_rng(3)
    t = np.arange(SR * 5) / SR
    x = 0.5 * np.sin(2 * np.pi * 80 * t)
    for p in range(12):
        i = int((0.2 + p * 0.38) * SR)
        x[i:i + 32] += 1.5 * np.hanning(32)
    st = np.stack([x, np.roll(x, 11)], axis=1)
    out, rep = master_loudness(st, SR, target_lufs=-14.0, ceiling_dbfs=-1.0)
    up = np.abs(np.fft.irfft(np.fft.rfft(out, axis=0), 4 * out.shape[0],
                             axis=0) * 4.0).max()
    assert 20 * np.log10(up) <= -0.99
    assert abs(integrated_lufs(out, SR) - (-14.0)) < 0.5
    assert rep["limiter"]["limited"]
    print("PASS  limiter: LUFS target reached, true peak held at ceiling")


def test_hall_decay_tracks_rt60():
    imp = np.zeros(SR * 4)
    imp[0] = 1.0
    short = hall_fx(imp, SR, rt60=0.8, mix=1.0)
    long = hall_fx(imp, SR, rt60=3.0, mix=1.0)
    e = lambda x, a, b: np.sum(x[int(a * SR):int(b * SR)] ** 2)  # noqa: E731
    r_short = e(short, 1.0, 1.5) / max(e(short, 0.0, 0.5), 1e-12)
    r_long = e(long, 1.0, 1.5) / max(e(long, 0.0, 0.5), 1e-12)
    assert r_long > r_short * 10, (r_short, r_long)
    assert np.array_equal(short, hall_fx(imp, SR, rt60=0.8, mix=1.0))
    print("PASS  hall tail length tracks rt60; deterministic")


def test_16bit_dither_reproducible():
    src = """
asset d16 {
  kind: sfx
  duration: 1s
  bitdepth: 16
  layer t : tone {
    osc: sine
    note: A4
    gain: -20db
    env: a=0.01s d=0.2s s=0.5 r=0.2s
  }
  master { peak: -3db }
}
"""
    f = AudioForge()
    with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
        m1 = f.compile(src).assets[0].export(a)
        m2 = f.compile(src).assets[0].export(b)
        assert m1["output_sha256"] == m2["output_sha256"]
    print("PASS  high-pass TPDF 16-bit dither stays byte-reproducible")


if __name__ == "__main__":
    test_new_voices_deterministic()
    test_pluck_pitch()
    test_modal_partials()
    test_padsynth_loops_and_is_rich()
    test_unison_widens_spectrum()
    test_limiter_reaches_target_and_holds_ceiling()
    test_hall_decay_tracks_rt60()
    test_16bit_dither_reproducible()
    print("\nAll v2.1 tests passed.")
