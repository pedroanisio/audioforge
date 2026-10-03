"""Regressions for safe delivery replacement, alpha covers and exact tags."""
from pathlib import Path
import wave

from PIL import Image
import pytest

from audioforge import distribute as D


def _delivery(tmp_path):
    wav = tmp_path / 'tone.wav'
    with wave.open(str(wav), 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(8000)
        w.writeframes(b'\0\0' * 8000)
    out = tmp_path / 'tone.mp3'
    out.write_bytes(b'previous good delivery')
    args = D.build_parser().parse_args([str(wav), '-o', str(out)])
    return args, out


@pytest.mark.parametrize('failure', ['encode', 'verify'])
def test_failed_delivery_preserves_existing_file(tmp_path, monkeypatch, failure):
    args, out = _delivery(tmp_path)
    before = set(tmp_path.iterdir())

    def encode(wav, target, tags, **kwargs):
        Path(target).write_bytes(b'partial delivery')
        if failure == 'encode':
            raise D.DistributeError('encoder interrupted')

    def verify(*args, **kwargs):
        raise D.DistributeError('verification failed')

    monkeypatch.setattr(D, 'encode_mp3', encode)
    monkeypatch.setattr(D, 'verify', verify)
    with pytest.raises(D.DistributeError):
        D.pack(args)
    assert out.read_bytes() == b'previous good delivery'
    assert set(tmp_path.iterdir()) == before


def test_successful_delivery_replaces_only_after_verification(tmp_path, monkeypatch):
    args, out = _delivery(tmp_path)
    before = set(tmp_path.iterdir())

    def encode(wav, target, tags, **kwargs):
        target = Path(target)
        assert target != out and target.parent == out.parent
        assert target.suffix == '.mp3'
        target.write_bytes(b'new delivery')

    def verify(target, tags, **kwargs):
        assert out.read_bytes() == b'previous good delivery'
        assert Path(target).read_bytes() == b'new delivery'
        return {'verified': True}

    monkeypatch.setattr(D, 'encode_mp3', encode)
    monkeypatch.setattr(D, 'verify', verify)
    assert D.pack(args) == {'verified': True, 'output': str(out)}
    assert out.read_bytes() == b'new delivery'
    assert set(tmp_path.iterdir()) == before


@pytest.mark.parametrize('fit', ['contain', 'cover'])
@pytest.mark.parametrize('alpha,expected', [(0, (255, 255, 255)), (128, (255, 127, 127))])
def test_cover_composites_alpha_over_selected_background(tmp_path, fit, alpha, expected):
    src = tmp_path / 'cover.png'
    out = tmp_path / 'cover.jpg'
    Image.new('RGBA', (64, 64), (255, 0, 0, alpha)).save(src)
    D.prepare_cover(src, out, size=64, fit=fit, bg='#ffffff')
    pixel = Image.open(out).getpixel((32, 32))
    assert all(abs(actual - wanted) <= 3 for actual, wanted in zip(pixel, expected))


@pytest.mark.parametrize('got', ['Wrong Tone Edition', 'Tone Extended'])
def test_metadata_verification_rejects_substring_title(tmp_path, monkeypatch, got):
    out = tmp_path / 'tone.mp3'
    out.write_bytes(b'encoded audio')
    info = {'streams': [{'codec_type': 'audio', 'codec_name': 'mp3'}],
            'format': {'duration': '1', 'bit_rate': '128000', 'tags': {'title': got}}}
    monkeypatch.setattr(D, 'ffprobe', lambda path: info)
    with pytest.raises(D.DistributeError, match="tag 'title'"):
        D.verify(out, {'title': 'Tone'}, want_cover=False, src_duration_s=1)
