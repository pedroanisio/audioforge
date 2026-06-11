import hashlib
import io
import wave

import numpy as np
import pytest

from audioforge import samples
from audioforge.schema import SpecError


def _wav_bytes(values, *, channels=1, sample_width=2, sample_rate=48000):
    arr = np.asarray(values)
    if sample_width == 2:
        raw = np.clip(arr, -32768, 32767).astype("<i2").tobytes()
    elif sample_width == 3:
        ints = np.clip(arr, -(1 << 23), (1 << 23) - 1).astype(np.int32)
        raw = b"".join(int(v).to_bytes(3, "little", signed=True) for v in ints)
    elif sample_width == 4:
        raw = np.clip(arr, -(1 << 31), (1 << 31) - 1).astype("<i4").tobytes()
    else:
        raw = np.clip(arr, 0, 255).astype("u1").tobytes()

    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav:
        wav.setnchannels(channels)
        wav.setsampwidth(sample_width)
        wav.setframerate(sample_rate)
        wav.writeframes(raw)
    return buf.getvalue()


def test_sample_lookup_reports_search_paths(monkeypatch, tmp_path):
    monkeypatch.setattr(samples, "_REGISTRY", {})
    monkeypatch.setattr(samples, "SAMPLE_PATHS", [tmp_path / "missing"])

    with pytest.raises(SpecError, match="searched registry"):
        samples.load_sample("absent.wav", "0" * 64, 48000)


def test_wav_decode_supports_24_bit_32_bit_and_stereo_mix():
    stereo_24 = _wav_bytes(
        [-(1 << 22), 1 << 22, 0, 1 << 22],
        channels=2,
        sample_width=3,
    )
    mixed, sr = samples._decode_wav(stereo_24)
    assert sr == 48000
    assert mixed.shape == (2,)
    assert np.all(np.isfinite(mixed))

    mono_32 = _wav_bytes([-(1 << 30), 1 << 30], sample_width=4)
    decoded, sr = samples._decode_wav(mono_32)
    assert sr == 48000
    assert decoded[0] < 0 < decoded[1]


def test_sample_loading_resamples_and_preserves_multichannel_cache(monkeypatch):
    monkeypatch.setattr(samples, "_CACHE", {})
    data = _wav_bytes([0, 12000, -12000, 0], sample_rate=24000)
    sha = samples.register_sample("resample.wav", data)

    mono = samples.load_sample("resample.wav", sha, 48000)
    assert mono.size > 4

    stereo = _wav_bytes([0, 12000, 12000, 0], channels=2)
    stereo_sha = samples.register_sample("stereo.wav", stereo)
    kept = samples.load_sample_multi("stereo.wav", stereo_sha, 48000)
    assert kept.shape == (2, 2)
    assert samples.load_sample_multi("stereo.wav", stereo_sha, 48000) is kept


def test_ingest_reports_undecodable_wavs(tmp_path):
    bad = tmp_path / "bad.wav"
    bad.write_bytes(b"not a wav")

    catalog = samples.ingest(tmp_path)

    assert catalog[0]["file"] == "bad.wav"
    assert catalog[0]["sha256"] == hashlib.sha256(b"not a wav").hexdigest()
    assert catalog[0]["error"].startswith("undecodable:")
