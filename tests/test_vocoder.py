"""Bus vocoder (cross-synthesis): the named source's spectral envelope shapes the bus.

The engine transfers an envelope it was given; it generates no voice (ADR-0002)."""
import numpy as np

from audioforge import AudioForge, fx
from audioforge.dsl import compile_dsl
from audioforge.decompile import spec_to_dsl

SR = 48000


def _saw(f, n):
    t = np.arange(n) / SR
    return 2.0 * ((t * f) % 1.0) - 1.0


def test_modulator_gates_the_carrier_envelope_and_bypass_is_exact():
    n = 2 * SR
    carrier = np.stack([_saw(110, n), _saw(110.5, n)], axis=1) * 0.5
    gate = (np.arange(n) // (SR // 4)) % 2 == 0            # 250 ms on / 250 ms off
    rng = np.random.default_rng(7)
    modulator = rng.standard_normal(n) * gate
    out = fx.vocoder_bus(carrier, modulator, SR, bands=16, smooth_s=0.005)
    rms = lambda seg: float(np.sqrt(np.mean(seg ** 2)))
    on = rms(out[SR // 8: SR // 8 + SR // 16])                # middle of the first "on" window
    off = rms(out[SR // 4 + SR // 8: SR // 4 + SR // 8 + SR // 16])
    assert on > 8 * off, (on, off)
    assert abs(rms(out) - rms(carrier)) / rms(carrier) < 0.05    # level-matched to the carrier
    assert np.array_equal(fx.vocoder_bus(carrier, modulator, SR, mix=0.0), carrier)
    assert np.array_equal(fx.vocoder_bus(carrier, np.zeros(n), SR), np.zeros_like(carrier))  # silence in, silence out
    assert np.array_equal(out, fx.vocoder_bus(carrier, modulator, SR, bands=16, smooth_s=0.005))


def test_modulator_spectrum_is_imprinted_on_the_carrier():
    n = 2 * SR
    carrier = _saw(100, n)
    t = np.arange(n) / SR
    modulator = np.sin(2 * np.pi * 1500 * t)                  # energy only around 1.5 kHz
    out = fx.vocoder_bus(carrier, modulator, SR, bands=24, low_hz=80, high_hz=8000)
    spec = np.abs(np.fft.rfft(out * np.hanning(n)))
    freqs = np.fft.rfftfreq(n, 1 / SR)
    near = spec[(freqs > 1200) & (freqs < 1900)].sum()
    far = spec[(freqs > 200) & (freqs < 600)].sum()
    assert near > 5 * far


def test_dsl_bus_vocoder_compiles_validates_renders_and_round_trips():
    src = """asset robot { kind: cue
  duration: 2s
  tempo: 120bpm
  bus voice {
    vocoder: source=mod bands=20 low=90hz high=7000hz smooth=0.006s depth=1.2 mix=0.9
  }
  layer mod : drums { voice: snare
    pattern: x...x...x...x...
    gain: -80db }
  layer carrier : notes { osc: saw
    bus: voice
    notes: A2 @ 0b for 4b, E3 @ 0b for 4b }
}"""
    spec = compile_dsl(src)[0][0]
    assert spec["buses"][0]["vocoder"] == {"source": "mod", "bands": 20, "low_hz": 90.0, "high_hz": 7000.0,
                                           "smooth_s": 0.006, "depth": 1.2, "mix": 0.9}
    assert compile_dsl(spec_to_dsl(spec))[0][0]["buses"] == spec["buses"]
    res = AudioForge().compile(src)
    assert res.ok, res.diagnostics
    audio, sr, _ = res.assets[0].render()
    mono = audio.mean(axis=1)
    hit = float(np.sqrt(np.mean(mono[int(0.02 * sr): int(0.08 * sr)] ** 2)))
    gap = float(np.sqrt(np.mean(mono[int(0.35 * sr): int(0.45 * sr)] ** 2)))
    assert hit > 3 * gap                                      # the snare's envelope shapes the saw
    from audioforge.schema import SpecError, validate_spec
    import copy
    bad = copy.deepcopy(spec)
    bad["buses"][0]["vocoder"]["source"] = "nope"
    try:
        validate_spec(bad)
    except SpecError as e:
        assert "vocoder.source" in str(e)
    else:
        raise AssertionError("unknown vocoder source must be refused")
