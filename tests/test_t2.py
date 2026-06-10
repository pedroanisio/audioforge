"""Tier-2 tests: Dattorro plate + per-band FDN, stereo master chain."""
import sys
from pathlib import Path

import numpy as np
from scipy.signal import lfilter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from audioforge import AudioForge  # noqa: E402
from audioforge.spaces import _fdn_irs, _plate_irs  # noqa: E402

SR = 48000


def _rms(x, a, b):
    return np.sqrt(np.mean(x[int(a * SR):int(b * SR)] ** 2) + 1e-30)


def test_plate_stable_decaying_decorrelated():
    irL, irR = _plate_irs(SR, 0.78, 0.3, SR * 12)
    assert _rms(irL, 0.0, 0.5) > _rms(irL, 2.0, 2.5) > _rms(irL, 4.0, 4.5)
    assert abs(np.corrcoef(irL, irR)[0, 1]) < 0.1   # true stereo taps
    a = _plate_irs(SR, 0.78, 0.3, SR * 12)
    assert np.array_equal(a[0], irL)                # deterministic + cached
    print("PASS  plate: stable exponential decay, decorrelated L/R, deterministic")


def test_plate_decay_parameter():
    s, _ = _plate_irs(SR, 0.5, 0.3, SR * 12)
    l, _ = _plate_irs(SR, 0.9, 0.3, SR * 12)
    r_s = _rms(s, 1.5, 2.0) / _rms(s, 0.2, 0.7)
    r_l = _rms(l, 1.5, 2.0) / _rms(l, 0.2, 0.7)
    assert r_l > r_s * 5, (r_s, r_l)
    print("PASS  plate: decay parameter controls tail length")


def test_fdn_per_band_rt60():
    irL, _ = _fdn_irs(SR, 6.0, 1.2, 2500.0, 1.0, SR * 12)
    lo = lfilter(*_butter_low(800.0), irL)
    hi = irL - lfilter(*_butter_low(5000.0), irL)
    decay_lo = _rms(lo, 2.5, 3.0) / _rms(lo, 0.4, 0.9)
    decay_hi = _rms(hi, 2.5, 3.0) / _rms(hi, 0.4, 0.9)
    # high band (rt60 1.2 s) must be far more decayed by 2.5 s than the
    # low band (rt60 6 s): the signature of per-band decay
    assert decay_hi < decay_lo * 0.2, (decay_lo, decay_hi)
    print(f"PASS  fdn: per-band decay (low ratio {decay_lo:.3f} vs "
          f"high {decay_hi:.4f})")


def _butter_low(fc):
    from scipy.signal import butter
    return butter(2, fc / (SR / 2))


def test_fdn_rt60_scaling():
    a, _ = _fdn_irs(SR, 1.5, 0.6, 2500.0, 1.0, SR * 12)
    b, _ = _fdn_irs(SR, 6.0, 2.4, 2500.0, 1.0, SR * 12)
    ra = _rms(a, 1.4, 1.9) / _rms(a, 0.4, 0.9)
    rb = _rms(b, 1.4, 1.9) / _rms(b, 0.4, 0.9)
    assert rb > ra * 4, (ra, rb)
    print("PASS  fdn: rt60 scales the tail")


def test_stereo_master_chain_renders_deterministically():
    src = """
asset t2m {
  kind: cue
  duration: 4s
  tempo: 60bpm
  layer b : notes {
    osc: modal
    material: glass
    gain: -8db
    env: a=0.001s d=2s s=0.2 r=0.5s
    notes: A4 @ 0b for 3b
    fx: plate(decay=0.7, mix=0.35)
  }
  master { peak: -1db
           fadeout: 0.5s
           fx: fdn(rt60=3.5, rt60_high=1.4, mix=0.3) }
}
"""
    f = AudioForge()
    s1, sr, _ = f.compile(src).assets[0].render()
    s2, _, _ = f.compile(src).assets[0].render()
    assert np.array_equal(s1, s2)
    # FDN wet must inject stereo difference even from a centered source
    mid_tail = s1[2 * sr:3 * sr]
    side = mid_tail[:, 0] - mid_tail[:, 1]
    assert np.sqrt(np.mean(side ** 2)) > 1e-4
    print("PASS  stereo master chain: deterministic, decorrelated width from "
          "a centered source")


if __name__ == "__main__":
    test_plate_stable_decaying_decorrelated()
    test_plate_decay_parameter()
    test_fdn_per_band_rt60()
    test_fdn_rt60_scaling()
    test_stereo_master_chain_renders_deterministically()
    print("\nAll T2 tests passed.")
