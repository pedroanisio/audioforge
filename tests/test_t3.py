"""Tier-3 tests: glue/multiband compression, DC blocker, modulated plate."""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from audioforge import AudioForge  # noqa: E402
from audioforge.dynamics import (compressor_stereo, dc_block,  # noqa: E402
                                 multiband_stereo)

SR = 48000


def _crest(x):
    return np.abs(x).max() / np.sqrt(np.mean(x ** 2))


def test_comp_reduces_crest_and_is_deterministic():
    rng = np.random.default_rng(11)
    t = np.arange(SR * 4) / SR
    x = 0.2 * np.sin(2 * np.pi * 220 * t)
    for p in range(8):
        i = int((0.3 + p * 0.45) * SR)
        x[i:i + 2000] *= 4.0
    st = np.stack([x, x], axis=1)
    fx = {"threshold": -18.0, "ratio": 4.0, "attack": 0.02, "release": 0.12}
    aL, aR = compressor_stereo(st[:, 0], st[:, 1], SR, fx)
    bL, _ = compressor_stereo(st[:, 0], st[:, 1], SR, fx)
    assert np.array_equal(aL, bL)
    assert _crest(aL) < _crest(x) * 0.8, (_crest(x), _crest(aL))
    assert np.array_equal(aL, aR)  # linked: identical gain both channels
    print(f"PASS  glue comp: crest {_crest(x):.1f} -> {_crest(aL):.1f}, "
          f"deterministic, stereo-linked")


def test_multiband_acts_per_band():
    t = np.arange(SR * 3) / SR
    low = 0.6 * np.sin(2 * np.pi * 80 * t)          # loud lows
    high = 0.05 * np.sin(2 * np.pi * 6000 * t)      # quiet highs
    x = low + high
    fx = {"threshold": -14.0, "ratio": 4.0, "low": 200.0, "high": 2500.0}
    yL, _ = multiband_stereo(x, x.copy(), SR, fx)
    spec_in = np.abs(np.fft.rfft(x))
    spec_out = np.abs(np.fft.rfft(yL))
    freqs = np.fft.rfftfreq(x.size, 1 / SR)
    lo_red = (spec_out[(freqs > 70) & (freqs < 90)].max()
              / spec_in[(freqs > 70) & (freqs < 90)].max())
    hi_red = (spec_out[(freqs > 5900) & (freqs < 6100)].max()
              / spec_in[(freqs > 5900) & (freqs < 6100)].max())
    # loud low band compressed hard; quiet high band nearly untouched
    assert lo_red < 0.7 and hi_red > 0.85, (lo_red, hi_red)
    print(f"PASS  multiband: low band gain {lo_red:.2f}, high band {hi_red:.2f}")


def test_dc_blocker():
    t = np.arange(SR * 2) / SR
    x = 0.3 * np.sin(2 * np.pi * 200 * t) + 0.25      # heavy DC offset
    st = np.stack([x, x], axis=1)
    y = dc_block(st, SR)
    assert abs(np.mean(y[SR:, 0])) < 0.005
    # tone essentially preserved
    tone_in = np.abs(np.fft.rfft(x))[400]
    tone_out = np.abs(np.fft.rfft(y[:, 0]))[400]
    assert tone_out > tone_in * 0.95
    print("PASS  DC blocker removes offset, preserves the tone")


def test_modulated_plate_via_dsl():
    src = """
asset t3p {{
  kind: cue
  duration: 4s
  tempo: 60bpm
  layer b : notes {{
    osc: modal
    material: glass
    gain: -8db
    env: a=0.001s d=2s s=0.2 r=0.5s
    notes: A4 @ 0b for 3b
  }}
  master {{ peak: -1db
           fadeout: 0.5s
           fx: plate(decay=0.8, mod={mod}, modrate=0.9, mix=0.45) }}
}}
"""
    f = AudioForge()
    s_mod, sr, _ = f.compile(src.format(mod=0.7)).assets[0].render()
    s_mod2, _, _ = f.compile(src.format(mod=0.7)).assets[0].render()
    s_static, _, _ = f.compile(src.format(mod=0.0)).assets[0].render()
    assert np.array_equal(s_mod, s_mod2)              # deterministic
    diff = np.sqrt(np.mean((s_mod - s_static) ** 2))
    assert diff > 1e-4                                # shimmer is real
    print(f"PASS  modulated plate: deterministic, audibly distinct "
          f"(rms diff {diff:.4f})")


def test_full_master_chain_t3():
    src = """
asset t3m {
  kind: cue
  duration: 5s
  tempo: 120bpm
  layer k : drums {
    voice: kick
    pattern: X.x.X.x.X.x.X.xx
    gain: -1db
  }
  layer bass : notes {
    osc: saw
    unison: 3
    spread: 8c
    gain: -8db
    loop: 4b
    env: a=0.003s d=0.2s s=0.6 r=0.05s
    notes: E2 @ 0b for 1.5b, G2 @ 2b for 1.5b
    fx: lowpass(800hz), drive(0.3)
  }
  master {
    width: 0.6
    lufs: -13
    peak: -1db
    fadeout: 0.2s
    fx: highpass(30hz), mbcomp(threshold=-20, ratio=2, low=160, high=3000),
        comp(threshold=-14, ratio=2, attack=0.03, release=0.2)
  }
}
"""
    f = AudioForge()
    s1, sr, m1 = f.compile(src).assets[0].render()
    s2, _, _ = f.compile(src).assets[0].render()
    assert np.array_equal(s1, s2)
    assert abs(m1["loudness"]["final_lufs"] - (-13.0)) < 0.5
    print(f"PASS  full T3 master chain renders deterministically at "
          f"{m1['loudness']['final_lufs']} LUFS")


if __name__ == "__main__":
    test_comp_reduces_crest_and_is_deterministic()
    test_multiband_acts_per_band()
    test_dc_blocker()
    test_modulated_plate_via_dsl()
    test_full_master_chain_t3()
    print("\nAll T3 tests passed.")
