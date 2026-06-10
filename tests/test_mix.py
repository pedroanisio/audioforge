"""Mix & production tests (v2.6): parametric EQ, buses with shared FX,
sidechain ducking, transient shaping, glue saturation — verified in audio."""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from audioforge import AudioForge  # noqa: E402
from audioforge import fx as F  # noqa: E402

SR = 48000
AF = AudioForge()


def _mono(src):
    res = AF.compile(src)
    assert res.ok, [d.message for d in res.diagnostics]
    s, sr, _ = res.assets[0].render()
    return s.mean(axis=1), sr


def _band_db(x, sr, lo, hi):
    s = np.abs(np.fft.rfft(x * np.hanning(x.size)))
    f = np.fft.rfftfreq(x.size, 1 / sr)
    return 20 * np.log10(s[(f > lo) & (f < hi)].mean() + 1e-12)


def test_eq_peak_and_shelf():
    rng = np.random.default_rng(11)
    x = rng.standard_normal(SR * 2) * 0.1
    boosted = F.eq_fx(x, SR, "peak", 1000.0, 6.0, 1.0)
    rise = _band_db(boosted, SR, 900, 1100) - _band_db(x, SR, 900, 1100)
    far = _band_db(boosted, SR, 6000, 8000) - _band_db(x, SR, 6000, 8000)
    assert 4.5 < rise < 7.0, rise
    assert abs(far) < 0.5, far
    shelved = F.eq_fx(x, SR, "lowshelf", 150.0, -6.0)
    cut = _band_db(shelved, SR, 40, 120) - _band_db(x, SR, 40, 120)
    assert -7.5 < cut < -4.5, cut
    print(f"PASS  EQ: peak +6 dB measures {rise:+.1f} dB at 1 kHz "
          f"(distant band {far:+.2f}); lowshelf -6 measures {cut:+.1f}")


BUS_AB = """
asset b_{tag} {{
  kind: cue
  duration: 4s
  tempo: 120bpm
  {bus_decl}
  layer a : notes {{
    osc: sine
    gain: -8db
    {route}
    env: a=0.01s d=0.1s s=0.8 r=0.1s
    notes: A4 @ 0b for 2b
  }}
  layer b : notes {{
    osc: sine
    gain: -10db
    {route}
    env: a=0.01s d=0.1s s=0.8 r=0.1s
    notes: E5 @ 0b for 2b
  }}
  master {{ peak: -1db
           fadeout: 0.05s }}
}}
"""


def test_bus_shared_fx_tail():
    dry, sr = _mono(BUS_AB.format(tag="dry", bus_decl="", route=""))
    bused, _ = _mono(BUS_AB.format(
        tag="bus",
        bus_decl="bus verb { fx: hall(rt60=2.5s, damp=0.4, mix=0.5) }",
        route="bus: verb"))
    # notes end at 1.0 s; a shared bus hall leaves a tail where dry has none
    tail = slice(int(1.6 * sr), int(3.2 * sr))
    rms = lambda x: np.sqrt(np.mean(x ** 2)) + 1e-12  # noqa: E731
    assert rms(bused[tail]) > 8 * rms(dry[tail]), \
        (rms(dry[tail]), rms(bused[tail]))
    print(f"PASS  bus: shared hall leaves a {20*np.log10(rms(bused[tail])/rms(dry[tail])):.0f} dB "
          f"louder tail than unbused layers")


DUCK = """
asset d_{tag} {{
  kind: cue
  duration: 4s
  tempo: 120bpm
  {bus_decl}
  layer pad : tone {{
    osc: sine
    note: A3
    duration: 4s
    gain: -10db
    bus: pads
    env: a=0.05s d=0.1s s=1 r=0.1s
  }}
  layer kick : drums {{
    voice: kick
    pattern: X.......X.......
    gain: -4db
  }}
  master {{ peak: -1db
           fadeout: 0.05s }}
}}
"""


def test_sidechain_duck_depth_and_recovery():
    no_duck, sr = _mono(DUCK.format(
        tag="n", bus_decl="bus pads { }"))
    ducked, _ = _mono(DUCK.format(
        tag="y", bus_decl="bus pads { duck: source=kick amount=9db "
                          "attack=0.005s release=0.12s threshold=-40db }"))

    def pad_env(x, t0, t1):
        seg = x[int(t0 * sr):int(t1 * sr)]
        s = np.abs(np.fft.rfft(seg))
        f = np.fft.rfftfreq(seg.size, 1 / sr)
        return s[(f > 200) & (f < 240)].max()    # A3 fundamental, kick-free
    # SELF-REFERENCED: cross-render comparison is polluted by the master
    # LUFS stage (the ducked mix is quieter overall, so it gets more makeup
    # gain). Measure duck depth and recovery within the ducked render only.
    # Kick hits every 1.0 s (16 sixteenths @ 120 bpm, X at steps 0 and 8).
    at_hit = pad_env(ducked, 2.02, 2.10)
    gap_a = pad_env(ducked, 1.70, 1.85)
    gap_b = pad_env(ducked, 2.70, 2.85)
    depth_db = 20 * np.log10(gap_a / at_hit)
    assert depth_db > 5.0, depth_db              # duck bites near full amount
    steady = abs(20 * np.log10(gap_a / gap_b))
    assert steady < 0.5, steady                  # recovery is stable per gap
    # sanity: the un-ducked render is gap-to-gap stable too (the hit window
    # itself is polluted by kick spectral overlap, so we don't compare to it)
    no_steady = abs(20 * np.log10(pad_env(no_duck, 1.70, 1.85)
                                  / pad_env(no_duck, 2.70, 2.85)))
    assert no_steady < 0.5, no_steady
    print(f"PASS  sidechain: pad ducks {depth_db:.1f} dB at the kick "
          f"(self-referenced), gap-to-gap stable within {steady:.2f} dB")


def test_transient_shaper_crest():
    rng = np.random.default_rng(5)
    hit = np.sin(2 * np.pi * 80 * np.arange(SR // 2) / SR) \
        * np.exp(-np.arange(SR // 2) / SR * 18)
    x = np.tile(np.concatenate([hit, np.zeros(SR // 2)]), 2)
    crest = lambda v: np.max(np.abs(v)) / (np.sqrt(np.mean(v ** 2)) + 1e-12)  # noqa: E731
    sharp = F.transient_fx(x, SR, attack_db=8.0, sustain_db=-4.0)
    soft = F.transient_fx(x, SR, attack_db=-6.0, sustain_db=4.0)
    assert crest(sharp) > 1.15 * crest(x), (crest(x), crest(sharp))
    assert crest(soft) < 0.92 * crest(x), (crest(x), crest(soft))
    print(f"PASS  transient: crest {crest(x):.1f} -> {crest(sharp):.1f} "
          f"(attack+) / {crest(soft):.1f} (sustain+)")


def test_saturate_harmonics_and_bypass():
    t = np.arange(SR) / SR
    x = 0.7 * np.sin(2 * np.pi * 220 * t)
    sat = F.saturate_fx(x, amount=0.5, mix=1.0, warmth=0.5)
    s = np.abs(np.fft.rfft(sat * np.hanning(SR)))
    f = np.fft.rfftfreq(SR, 1 / SR)
    h2 = s[(f > 430) & (f < 450)].max()
    h3 = s[(f > 650) & (f < 670)].max()
    h1 = s[(f > 210) & (f < 230)].max()
    assert h2 > h1 * 0.01 and h3 > h1 * 0.01, (h2 / h1, h3 / h1)
    assert np.array_equal(F.saturate_fx(x, amount=0.5, mix=0.0), x)
    print(f"PASS  saturate: H2 {20*np.log10(h2/h1):.0f} dBc, "
          f"H3 {20*np.log10(h3/h1):.0f} dBc; mix=0 is bit-exact bypass")


def test_bus_chain_deterministic():
    src = DUCK.format(tag="det",
                      bus_decl="bus pads { duck: source=kick amount=6db } ")
    a, _ = _mono(src)
    b, _ = _mono(src)
    assert np.array_equal(a, b)
    print("PASS  bus + duck chain renders byte-identically")


if __name__ == "__main__":
    test_eq_peak_and_shelf()
    test_bus_shared_fx_tail()
    test_sidechain_duck_depth_and_recovery()
    test_transient_shaper_crest()
    test_saturate_harmonics_and_bypass()
    test_bus_chain_deterministic()
    print("\nAll mix & production tests passed.")
