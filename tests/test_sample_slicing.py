"""Sample-layer editing in the IR: offset, length, reverse, stretch, slices."""
import io
import wave

import numpy as np
import pytest

from audioforge import AudioForge, samples
from audioforge.dsl import compile_dsl
from audioforge.decompile import spec_to_dsl
from audioforge.render import _shape_sample, _slice_bank
from audioforge.stretch import time_stretch

SR = 48000


def _wav(mono: np.ndarray, sr: int = SR) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((np.clip(mono, -1, 1) * 32767).astype("<i2").tobytes())
    return buf.getvalue()


def _four_tone_loop() -> np.ndarray:
    t = np.arange(SR // 2) / SR
    return np.concatenate([0.5 * np.sin(2 * np.pi * f * t) for f in (220, 330, 440, 550)])


def _peak_hz(x: np.ndarray, sr: int = SR) -> float:
    spec = np.abs(np.fft.rfft(x * np.hanning(x.size)))
    return float(np.fft.rfftfreq(x.size, 1 / sr)[np.argmax(spec)])


def test_offset_length_reverse_are_exact_sample_edits():
    hit = np.arange(1000, dtype=float)
    out = _shape_sample(hit, 1000, {"offset_s": 0.25, "length_s": 0.5})
    assert np.array_equal(out, np.arange(250, 750, dtype=float))
    rev = _shape_sample(hit, 1000, {"offset_s": 0.25, "length_s": 0.5, "reverse": True})
    assert np.array_equal(rev, np.arange(749, 249, -1, dtype=float))
    stereo = np.stack([hit, -hit], axis=1)
    assert np.array_equal(_shape_sample(stereo, 1000, {"reverse": True})[:, 1], -hit[::-1])


def test_stretch_changes_duration_and_keeps_pitch():
    t = np.arange(SR) / SR
    x = np.sin(2 * np.pi * 440 * t)
    for ratio in (1.5, 0.75):
        y = time_stretch(x, ratio)
        assert abs(y.size - round(x.size * ratio)) <= 1
        assert abs(_peak_hz(y[2048:-2048]) - 440.0) < 4.4        # within 1 %
        assert np.array_equal(y, time_stretch(x, ratio))            # deterministic
    assert np.array_equal(time_stretch(x, 1.0), x)
    with pytest.raises(ValueError):
        time_stretch(x, 0.0)


def test_slice_bank_splits_evenly_and_pattern_digits_pick_slices():
    loop = _four_tone_loop()
    bank = _slice_bank(loop, {"slices": 4})
    assert len(bank) == 4 and all(b.size == SR // 2 for b in bank)
    assert abs(_peak_hz(bank[2]) - 440.0) < 5
    sha = samples.register_sample("four_tones.wav", _wav(loop))
    src = f"""asset chop {{ kind: cue
  duration: 2s
  tempo: 120bpm
  layer chop : sample {{ file: "four_tones.wav"
    sha256: "{sha}"
    slices: 4
    pattern: 3...2...1...0... }}
}}"""
    res = AudioForge().compile(src)
    assert res.ok, res.diagnostics
    audio, sr, _ = res.assets[0].render()
    mono = audio.mean(axis=1)
    # at 120 bpm a 16th is 0.125 s and a slice lasts 0.5 s = 4 steps, so the hits at
    # steps 0,4,8,12 do not overlap: slices 3,2,1,0 -> 550, 440, 330, 220 Hz
    for step, hz in ((0, 550.0), (4, 440.0), (8, 330.0), (12, 220.0)):
        start = int(step * 0.125 * sr)
        seg = mono[start:start + int(0.1 * sr)]
        assert abs(_peak_hz(seg, sr) - hz) < 12, (step, _peak_hz(seg, sr))


def test_sample_props_round_trip_through_the_decompiler_and_validate():
    sha = samples.register_sample("rt.wav", _wav(_four_tone_loop()))
    src = f"""asset rt {{ kind: cue
  duration: 2s
  tempo: 100bpm
  layer a : sample {{ file: "rt.wav"
    sha256: "{sha}"
    pitch: -2st
    offset: 0.5s
    length: 1s
    reverse: on
    stretch: 1.25
    slices: 2
    pattern: 0.1. }}
  layer b : sample {{ file: "rt.wav"
    sha256: "{sha}"
    start: 0.5s
    stretch: 0.5 }}
}}"""
    spec = compile_dsl(src)[0][0]
    a = spec["layers"][0]
    assert (a["offset_s"], a["length_s"], a["reverse"], a["stretch"], a["slices"], a["pitch_st"]) == (0.5, 1.0, True, 1.25, 2, -2.0)
    again = compile_dsl(spec_to_dsl(spec))[0][0]
    assert again["layers"] == spec["layers"]
    res = AudioForge().compile(src)
    assert res.ok, res.diagnostics
    audio, _, _ = res.assets[0].render()
    assert np.isfinite(audio).all() and np.max(np.abs(audio)) > 0.01
    bad = compile_dsl(src.replace("\n    pattern: 0.1. }", " }"))[0][0]   # slices without a pattern
    assert "pattern" not in bad["layers"][0] and bad["layers"][0]["slices"] == 2
    from audioforge.schema import SpecError, validate_spec
    with pytest.raises(SpecError, match="slices"):
        validate_spec(bad)
