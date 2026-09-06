"""Native channel identity must survive the complete sampled-instrument path."""
import io
import wave

import numpy as np
import pytest

from audioforge import AudioForge, library, sampler
from audioforge.sequencer import TempoMap


def wav_bytes(x, sr=8000, width=2):
    stream = io.BytesIO()
    values = np.rint(x * (2 ** (width * 8 - 1) - 1)).astype('<i4')
    raw = values.astype('<i2').tobytes() if width == 2 else values.tobytes()
    if width == 3:
        raw = values.view(np.uint8).reshape(-1, 4)[:, :3].tobytes()
    with wave.open(stream, 'wb') as w:
        w.setparams((1 if x.ndim == 1 else x.shape[1], width, sr, len(x), 'NONE', ''))
        w.writeframes(raw)
    return stream.getvalue()


@pytest.fixture
def channels():
    t = np.arange(8000) / 8000
    return np.stack([.3 * np.sin(2*np.pi*220*t), .2 * np.sin(2*np.pi*370*t)], axis=1)


@pytest.mark.parametrize('width', [2, 3, 4])
def test_decode_retains_native_stereo(channels, width):
    decoded, sr = library._decode_wav_bytes(wav_bytes(channels, width=width))
    assert sr == 8000
    assert decoded.shape == channels.shape
    np.testing.assert_allclose(decoded, channels, atol=2 ** (1-width*8))


@pytest.mark.parametrize('loop', ['no_loop', 'loop_continuous', 'loop_sustain'])
def test_channels_have_identical_resampling_clock_and_envelopes(channels, loop):
    r = sampler.Region(loop_mode=loop, loop_start=800, loop_end=4000,
                       loop_crossfade=.013, ampeg_release=.1)
    args = dict(midi_float=65.1, dur_n=9000, sr=12000,
                pitch_cents=np.linspace(-10, 20, 10200))
    stereo = sampler.render_region(r, channels, 8000, **args)
    expected = np.column_stack([sampler.render_region(r, x, 8000, **args)
                                for x in channels.T])
    np.testing.assert_array_equal(stereo, expected)


@pytest.fixture
def pin(tmp_path, channels):
    root = tmp_path / 'stereo_probe'
    root.mkdir()
    (root / 'stereo.wav').write_bytes(wav_bytes(channels))
    (root / 'mono.wav').write_bytes(wav_bytes(channels[:, 0]))
    (root / 'violin.sfz').write_text('''<global> ampeg_release=0.04
<region> key=60 sample=stereo.wav lovel=1 hivel=127
<region> key=62 sample=stereo.wav lovel=1 hivel=64
<region> key=62 sample=mono.wav lovel=65 hivel=127
''')
    manifest = library.generate_manifest(root, name='stereo_probe')
    library.add_library_path(tmp_path)
    return manifest['manifest_sha256']


@pytest.mark.parametrize('dynamic', [False, True])
def test_track_native_channels_and_mixed_velocity_bands(pin, dynamic):
    lib = library.load_library(f'stereo_probe@{pin}')
    track = dict(name='probe', instrument='violin', notes=[
        dict(note='C4', start_beat=0, dur_beats=.5, vel=.5),
        dict(note='D4', start_beat=1, dur_beats=.5, vel=.5)])
    if dynamic:
        track['dynamic'] = [[0, .2], [2, .8]]
    out = sampler.render_instrument_track(track, 8000, 8000, TempoMap([[0, 120]]),
                                         lambda _: np.random.default_rng(42), lib)
    assert out.shape == (8000, 2)
    assert np.linalg.norm(out[:, 0] - out[:, 1]) > 1
    assert np.isfinite(out).all()


@pytest.mark.parametrize('pan', [-.7, 0, .7])
def test_stereo_survives_fx_and_layer_pan(pin, pan):
    src = f'''asset stereo {{
kind: cue
duration: 1s
tempo: 120bpm
library: "stereo_probe@{pin}"
layer v : instrument {{
instrument: violin
pan: {pan}
notes: C4 @ 0b for 1b vel 0.5 }}
master {{ peak: -1db
fadeout: 0.05s }} }}'''
    compiled = AudioForge().compile(src)
    assert compiled.ok, compiled.diagnostics
    spec = compiled.assets[0].spec
    spec['layers'][0]['fx'] = [dict(type='filter', mode='lowpass', cutoff_hz=1500)]
    from audioforge.render import _premaster
    # Test the actual layer/master path before loudness normalization.
    left, right, stems = _premaster(spec, '', 8000, spec['master'], True)
    st = np.column_stack([left, right])
    assert st.shape == (8000, 2)
    assert np.linalg.norm(st[:, 0] - st[:, 1]) > 1
    # Distinct source frequencies must stay in their original channels.
    power = np.abs(np.fft.rfft(st[:4000], axis=0)) ** 2
    assert power[110, 0] > power[185, 0] * 100
    assert power[185, 1] > power[110, 1] * 100
    ratio = np.linalg.norm(st[:, 0]) / np.linalg.norm(st[:, 1])
    if pan < 0:
        assert ratio > 2
    elif pan > 0:
        assert ratio < 1


def test_compressed_decoder_preserves_channels(monkeypatch, channels):
    from audioforge import _sndfile
    monkeypatch.setattr(_sndfile, 'decode', lambda *_: (channels, 8000))
    got, _ = library._decode_wav_bytes(b'compressed fixture', 'flac')
    np.testing.assert_array_equal(got, channels)


def test_surround_sample_requires_explicit_conversion():
    with pytest.raises(ValueError, match='mono or stereo'):
        library._decode_wav_bytes(wav_bytes(np.zeros((80, 6))))


def test_antiphase_information_survives_seated_mix_and_stem(pin, monkeypatch):
    from audioforge.render import _premaster
    import importlib
    renderer = importlib.import_module('audioforge.render')
    t = np.arange(8000)/8000
    wave = np.sin(2*np.pi*220*t)*.1
    signal = np.column_stack([wave, -wave])
    layer = dict(type='instrument', name='probe', seat=dict(az_deg=-25, dist_m=1))
    monkeypatch.setattr(renderer, '_layer_signals', lambda *args: ([layer], [signal]))
    spec = dict(duration_s=1, layers=[layer], stage=dict(mics=dict(close=1,tree=0,ambient=0)))
    lib = library.load_library(f'stereo_probe@{pin}')
    spec['stage'].update(hall_file=str(lib.root/'stereo.wav'), hall_sha256=lib._by_path['stereo.wav'])
    left, right, stems = _premaster(spec, '', 8000, {}, True)
    assert np.linalg.norm(left) > np.linalg.norm(right) > 1
    assert np.corrcoef(left, right)[0, 1] < -.99
    np.testing.assert_allclose(stems['probe'][:, 0], wave)


def test_section_renders_both_recorded_channels(pin):
    lib = library.load_library(f'stereo_probe@{pin}')
    layer = dict(name='section', instrument='violin', section=dict(size=2, spread=.4),
                 notes=[dict(note='C4', start_beat=0, dur_beats=.5, vel=.5)])
    out = sampler.render_section(layer, 8000, 8000, TempoMap([[0,120]]),
                                 lambda _: np.random.default_rng(42), lib)
    assert out.shape == (8000,2)
    assert np.isfinite(out).all()
    assert np.linalg.norm(out[:,0]-out[:,1]) > 1
