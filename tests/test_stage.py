"""Stage & room (P4) tests. Measured: azimuth flips channel energy and
ITD sign; distance costs level and highs; early reflections add image-
source energy in the 8-120 ms window; the shared hall tail decays like the
pinned measured space; hash discipline and seat/bus exclusivity hold."""
import io
import json
import sys
import tempfile
import wave as wavemod
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from audioforge import AudioForge  # noqa: E402
from audioforge import samples as smod  # noqa: E402
from audioforge.stage import (air_shelf_db, direct_tap, early_ir,  # noqa
                              early_tap, hall_tail, seat_pan_itd)

SR = 48000
AF = AudioForge()


def _impulse(n=SR):
    x = np.zeros(n)
    x[100:100 + 240] = np.hanning(240)
    return x


def test_azimuth_pan_and_itd():
    x = _impulse()
    left_seat = direct_tap(x, SR, -30.0, 3.0)
    right_seat = direct_tap(x, SR, +30.0, 3.0)
    el = (left_seat ** 2).sum(axis=0)
    er = (right_seat ** 2).sum(axis=0)
    assert el[0] > 2.0 * el[1] and er[1] > 2.0 * er[0], (el, er)
    # ITD: the far ear lags — cross-correlate channels
    def lag(st):
        c = np.correlate(st[:2000, 0], st[:2000, 1], "full")
        return np.argmax(c) - (2000 - 1)
    assert lag(left_seat) < 0 < lag(right_seat), \
        (lag(left_seat), lag(right_seat))
    itd_ms = abs(lag(right_seat)) / SR * 1000.0
    assert 0.15 < itd_ms < 0.6, itd_ms
    print(f"PASS  azimuth: L/R energy follows the seat; ITD "
          f"{itd_ms:.2f} ms with correct sign at ±30°")


def test_distance_level_and_air():
    rng = np.random.default_rng(5)
    x = rng.standard_normal(SR)
    near = direct_tap(x, SR, 0.0, 2.0)
    far = direct_tap(x, SR, 0.0, 12.0)
    drop = 20 * np.log10(np.sqrt((near ** 2).mean())
                         / np.sqrt((far ** 2).mean()))
    # 15.6 dB geometric + ~2 dB air-shelf loss on white noise (HF-heavy)
    assert 14.0 < drop < 19.0, drop

    def hf_share(st):
        m = st.mean(axis=1)
        s = np.abs(np.fft.rfft(m)) ** 2
        f = np.fft.rfftfreq(m.size, 1 / SR)
        return s[f > 6000].sum() / s.sum()
    # an RBJ shelf transitions gradually; -3.3 dB nominal above 6 kHz
    # lands ~0.84x on white-noise HF share — assert direction + magnitude
    assert hf_share(far) < 0.9 * hf_share(near), \
        (hf_share(near), hf_share(far))
    assert air_shelf_db(12.0) < air_shelf_db(2.0) <= 0.0
    print(f"PASS  distance: {drop:.1f} dB level drop 2->12 m; HF share "
          f"{hf_share(near):.3f} -> {hf_share(far):.3f} (air shelf)")


def test_early_reflections_image_source():
    ir = early_ir(-10.0, 5.0, [16.0, 24.0, 11.0], SR)
    assert ir.shape == (int(0.12 * SR), 2)
    e = (ir ** 2).sum(axis=1)
    assert e[:int(0.002 * SR)].sum() == 0.0      # direct path excluded
    n_refl = int(np.sum(e > 1e-6))
    assert 6 <= n_refl <= 60, n_refl             # 2nd-order image count
    assert np.array_equal(ir, early_ir(-10.0, 5.0, [16.0, 24.0, 11.0], SR))
    # a staged impulse grows a reflection tail the dry path lacks
    x = _impulse()
    tail = early_tap(x, SR, -10.0, 5.0, [16.0, 24.0, 11.0])
    win = slice(int(0.015 * SR) + 100, int(0.1 * SR) + 100)
    assert np.sqrt((tail[win] ** 2).mean()) > 1e-4
    print(f"PASS  early reflections: {n_refl} image arrivals in 8-120 ms, "
          f"direct excluded, cached and deterministic")


def _ir_wav_bytes(rt60=1.5, sr=SR):
    rng = np.random.default_rng(77)
    t = np.arange(int(rt60 * 1.5 * sr)) / sr
    ir = rng.standard_normal((t.size, 2)) * \
        (10 ** (-3 * t / rt60))[:, None]
    ir[0] = [0.9, 0.9]
    buf = io.BytesIO()
    with wavemod.open(buf, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(sr)
        inter = (np.clip(ir, -1, 1) * 30000).astype("<i2")
        w.writeframes(inter.tobytes())
    return buf.getvalue()


def test_hall_tail_decay_and_pinning():
    data = _ir_wav_bytes(rt60=1.5)
    sha = smod.register_sample("t_hall.wav", data)
    x = _impulse(4 * SR)
    wet = hall_tail(x, SR, "t_hall.wav", sha)
    assert wet.shape == (4 * SR, 2)
    assert not np.array_equal(wet[:, 0], wet[:, 1])   # decorrelated stereo
    r1 = np.sqrt((wet[int(0.5 * SR):int(0.7 * SR)] ** 2).mean())
    r2 = np.sqrt((wet[int(1.5 * SR):int(1.7 * SR)] ** 2).mean())
    db_per_s = 20 * np.log10(r1 / r2)
    assert 32.0 < db_per_s < 48.0, db_per_s    # RT60 1.5 s = 60 dB/1.5 s = 40 dB/s
    try:
        hall_tail(x, SR, "t_hall.wav", "0" * 64)
        raise AssertionError("hash mismatch not refused")
    except Exception as e:
        assert "hash mismatch" in str(e)
    print(f"PASS  hall tail: stereo decorrelated, decays "
          f"{db_per_s:.0f} dB/s (RT60 1.5 s IR), wrong pin refused")


def test_dsl_stage_and_exclusivity():
    data = _ir_wav_bytes(rt60=1.0)
    sha = smod.register_sample("t_hall2.wav", data)
    res = AF.compile(f"""
asset st {{ kind: cue
  duration: 4s
  tempo: 100bpm
  stage {{
    hall: "t_hall2.wav@{sha}"
    mics: tree=0.8, close=0.1, ambient=0.4
    size: 14m, 20m, 9m
  }}
  layer a : tone {{ osc: sine
    note: A4
    duration: 1s
    env: a=0.01s d=0.1s s=0.8 r=0.2s
    seat: -20deg @ 6m
    gain: -10db }}
  master {{ peak: -1db
           fadeout: 0.2s }}
}}""")
    assert res.ok, [d.message for d in res.diagnostics]
    spec = res.assets[0].spec
    assert spec["stage"]["mics"]["tree"] == 0.8
    assert spec["layers"][0]["seat"] == {"az_deg": -20.0, "dist_m": 6.0}
    st, sr, _ = res.assets[0].render()
    assert not np.array_equal(st[:, 0], st[:, 1])
    bad = AF.compile(f"""
asset st2 {{ kind: cue
  duration: 4s
  tempo: 100bpm
  stage {{ hall: "t_hall2.wav@{sha}" }}
  bus b {{ gain: -1db }}
  layer a : tone {{ osc: sine
    note: A4
    duration: 1s
    env: a=0.01s d=0.1s s=0.8 r=0.2s
    seat: 0deg @ 4m
    bus: b
    gain: -10db }}
  master {{ peak: -1db }}
}}""")
    assert not bad.ok and any("mutually exclusive" in d.message
                              for d in bad.diagnostics)
    print("PASS  DSL: stage/seat compile to explicit IR, render is stereo, "
          "seat+bus refused")


if __name__ == "__main__":
    test_azimuth_pan_and_itd()
    test_distance_level_and_air()
    test_early_reflections_image_source()
    test_hall_tail_decay_and_pinning()
    test_dsl_stage_and_exclusivity()
    print("\nAll stage & room (P4) tests passed.")
