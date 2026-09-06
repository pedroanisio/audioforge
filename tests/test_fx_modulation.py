"""Modulation and lo-fi effects: phaser, flanger (native kernels), chorus, bitcrush.

Each test asserts a property of the *physics* the effect claims, not a golden
buffer: notch positions, comb spacing, spectral spreading, quantization levels;
plus bypass identity and determinism, which every AudioForge effect owes."""
import numpy as np
import pytest

from audioforge import fx
from audioforge._native import flanger_native, native_available, phaser_native

SR = 48000
pytestmark = pytest.mark.skipif(not native_available(), reason="native kernels need a C compiler")


def _impulse_response(process, n=SR // 2):
    x = np.zeros(n)
    x[0] = 1.0
    return process(x)


def _mag_db(y):
    return 20.0 * np.log10(np.abs(np.fft.rfft(y)) + 1e-12)


def test_phaser_static_lfo_carves_stages_over_two_notches():
    # rate 0 freezes the LFO at sin(0)=0: fc == center, so the wet+dry sum has
    # exactly stages/2 notches below Nyquist (phase turns of the allpass chain).
    n = SR // 2
    wet = _impulse_response(lambda x: phaser_native(x, SR, 0.0, 1.0, 4, 0.0, 1000.0, 2.0), n)
    mixed = 0.5 * np.eye(1, n)[0] + 0.5 * wet
    mag = _mag_db(mixed)
    freqs = np.fft.rfftfreq(n, 1 / SR)
    band = (freqs > 100) & (freqs < 20000)
    dips = np.flatnonzero((mag[band][1:-1] < mag[band][:-2]) & (mag[band][1:-1] < mag[band][2:]) & (mag[band][1:-1] < -20))
    assert len(dips) == 2, len(dips)
    assert np.max(mag[band]) < 0.5                         # never louder than the dry signal


def test_phaser_sweeps_and_feedback_deepens_bypass_and_determinism():
    t = np.arange(SR) / SR
    x = np.sin(2 * np.pi * 220 * t) + 0.5 * np.sin(2 * np.pi * 1760 * t)
    a = fx.apply_fx_chain(x, SR, [{"type": "phaser", "rate_hz": 0.5, "depth": 0.8, "mix": 0.5}], lambda n: None)
    b = fx.apply_fx_chain(x, SR, [{"type": "phaser", "rate_hz": 0.5, "depth": 0.8, "mix": 0.5}], lambda n: None)
    assert np.array_equal(a, b) and not np.allclose(a, x)
    dry = fx.apply_fx_chain(x, SR, [{"type": "phaser", "mix": 0.0}], lambda n: None)
    assert np.array_equal(dry, x)
    # a moving LFO makes the first and second half of the output differ spectrally
    h = SR // 2
    assert not np.allclose(np.abs(np.fft.rfft(a[:h])), np.abs(np.fft.rfft(a[h:])), rtol=0.05, atol=1e-3)
    # feedback turns the flat-between-notches response into resonant peaks (+9.5 dB measured at 0.8)
    n = SR // 2
    imp = np.zeros(n)
    imp[0] = 1.0
    peaks = {}
    for feedback in (0.0, 0.8):
        wet = phaser_native(imp, SR, 0.0, 1.0, 4, feedback, 1000.0, 2.0)
        mag = _mag_db(0.5 * imp + 0.5 * wet)
        freqs = np.fft.rfftfreq(n, 1 / SR)
        peaks[feedback] = float(mag[(freqs > 100) & (freqs < 20000)].max())
    assert peaks[0.0] < 0.5 and peaks[0.8] > 6.0, peaks


def test_flanger_static_delay_is_a_comb_with_notches_at_odd_half_harmonics():
    # depth 0 -> fixed delay D = 2 ms: dry + wet = comb, notches at (2k+1)/(2D) = 250, 750, 1250 Hz …
    n = SR
    wet = _impulse_response(lambda x: flanger_native(x, SR, 0.0, 0.0, 2.0, 0.0), n)
    mixed = 0.5 * np.eye(1, n)[0] + 0.5 * wet
    mag = _mag_db(mixed)
    freqs = np.fft.rfftfreq(n, 1 / SR)
    for f in (250.0, 750.0, 1250.0):
        k = int(round(f * n / SR))
        assert mag[k] < -25, (f, mag[k])
    peak_k = int(round(500.0 * n / SR))
    assert mag[peak_k] > -1.0
    assert np.array_equal(flanger_native(wet, SR, 0.3, 3.0, 2.0, 0.5), flanger_native(wet, SR, 0.3, 3.0, 2.0, 0.5))


def test_chorus_spreads_a_pure_tone_and_bypasses_cleanly():
    t = np.arange(2 * SR) / SR
    x = np.sin(2 * np.pi * 440 * t)
    y = fx.chorus_fx(x, SR, rate_hz=1.5, depth_ms=8.0, delay_ms=20.0, voices=3, mix=1.0)
    spec_x = np.abs(np.fft.rfft(x * np.hanning(x.size)))
    spec_y = np.abs(np.fft.rfft(y * np.hanning(y.size)))
    freqs = np.fft.rfftfreq(x.size, 1 / SR)
    band = (freqs > 400) & (freqs < 480)
    width = lambda s: np.sum(s[band] > 0.01 * s[band].max())
    assert width(spec_y) > 3 * width(spec_x)                # pitch modulation widens the line
    assert abs(np.sqrt(np.mean(y[SR // 2:] ** 2)) - np.sqrt(np.mean(x ** 2))) < 0.25
    assert np.array_equal(fx.chorus_fx(x, SR, mix=0.0), x)
    assert np.array_equal(fx.apply_fx_chain(x, SR, [{"type": "chorus"}], lambda n: None),
                          fx.apply_fx_chain(x, SR, [{"type": "chorus"}], lambda n: None))


def test_bitcrush_quantizes_levels_and_holds_samples():
    x = np.linspace(-1, 1, 4001)
    y = fx.bitcrush_fx(x, bits=4, downsample=1, mix=1.0)
    assert len(np.unique(np.round(y, 9))) <= 2 ** 4 + 1
    quiet = 0.03 * np.sin(np.linspace(0, 40, 6000))          # a -30 dBFS bus crushes just as hard
    assert len(np.unique(np.round(fx.bitcrush_fx(quiet, bits=4), 9))) <= 2 ** 4 + 1
    assert not np.allclose(fx.bitcrush_fx(quiet, bits=4), quiet)
    assert np.array_equal(fx.bitcrush_fx(np.zeros(100), bits=4), np.zeros(100))
    held = fx.bitcrush_fx(np.sin(np.linspace(0, 50, 5000)), bits=24, downsample=5, mix=1.0)
    blocks = held[:5000 - 5000 % 5].reshape(-1, 5)
    assert np.all(blocks == blocks[:, :1])                 # every 5-sample block is flat
    assert np.array_equal(fx.bitcrush_fx(x, bits=3, mix=0.0), x)
    chained = fx.apply_fx_chain(x, SR, [{"type": "bitcrush", "bits": 6, "downsample": 2, "mix": 1.0}], lambda n: None)
    assert len(np.unique(np.round(chained, 9))) <= 2 ** 6 + 1


def test_new_effects_are_registered_everywhere():
    from audioforge.capabilities import capability_manifest
    from audioforge.schema import FX_TYPES, NATIVE_FX_TYPES
    from audioforge.dsl import compile_dsl
    from audioforge.decompile import spec_to_dsl
    assert {"phaser", "flanger", "chorus", "bitcrush"} <= FX_TYPES
    assert {"phaser", "flanger"} <= NATIVE_FX_TYPES
    assert {"phaser", "flanger", "chorus", "bitcrush"} <= set(capability_manifest()["fx"])
    src = """asset t { kind: cue
  duration: 1s
  tempo: 120bpm
  bus wash { fx: chorus(rate=0.6, depth=4, delay=15, voices=4, mix=0.4), bitcrush(bits=10) }
  layer m : notes { osc: saw
    bus: wash
    notes: A3 @ 0b for 2b
    fx: phaser(rate=0.3, depth=0.6, stages=6, feedback=0.3, center=700hz, spread=1.5, mix=0.5), flanger(rate=0.2, depth=2, delay=1.5, feedback=0.3, mix=0.5) }
}"""
    spec = compile_dsl(src)[0][0]
    again = compile_dsl(spec_to_dsl(spec))[0][0]
    assert again["layers"][0]["fx"] == spec["layers"][0]["fx"] and again["buses"] == spec["buses"]
    from audioforge import AudioForge
    res = AudioForge().compile(src)
    assert res.ok, res.diagnostics
    audio, _, _ = res.assets[0].render()
    assert np.isfinite(audio).all() and np.max(np.abs(audio)) > 0.01


def test_stereo_parameter_decorrelates_channels_only_on_bus_and_master_chains():
    t = np.arange(SR) / SR
    x = 0.3 * np.sin(2 * np.pi * 220 * t) + 0.2 * np.sin(2 * np.pi * 1320 * t)
    for kind in ("chorus", "phaser", "flanger"):
        mono = {"type": kind, "mix": 0.6, "stereo": 0.0}
        wide = {"type": kind, "mix": 0.6, "stereo": 1.0}
        l0, r0 = fx.apply_master_chain(x.copy(), x.copy(), SR, [mono], lambda *a: None)
        assert np.array_equal(l0, r0), kind                       # stereo=0: both channels identical
        l1, r1 = fx.apply_master_chain(x.copy(), x.copy(), SR, [wide], lambda *a: None)
        assert np.array_equal(l1, l0), kind                       # the left channel is untouched by `stereo`
        corr = float(np.corrcoef(l1, r1)[0, 1])
        assert corr < 0.995 and not np.array_equal(l1, r1), (kind, corr)
        # a layer chain is mono: `stereo` is inert there, and the default keeps goldens byte-identical
        assert np.array_equal(fx.apply_fx_chain(x, SR, [wide], lambda n: None), fx.apply_fx_chain(x, SR, [mono], lambda n: None))
    from audioforge.dsl import compile_dsl
    from audioforge.decompile import spec_to_dsl
    spec = compile_dsl("""asset s { kind: cue
  duration: 1s
  tempo: 120bpm
  bus w { fx: chorus(rate=0.5, mix=0.4, stereo=1), phaser(stereo=0.5), flanger(stereo=0.25) }
  layer m : notes { osc: saw
    bus: w
    notes: A3 @ 0b for 2b }
}""")[0][0]
    assert [f["stereo"] for f in spec["buses"][0]["fx"]] == [1.0, 0.5, 0.25]
    assert compile_dsl(spec_to_dsl(spec))[0][0]["buses"] == spec["buses"]
