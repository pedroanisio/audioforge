import os

import numpy as np
import pytest

from audioforge import _sndfile


def test_sndfile_unavailable_error_is_actionable(monkeypatch):
    monkeypatch.setattr(_sndfile, "_LIB", None)

    assert _sndfile.available() is False
    with pytest.raises(RuntimeError, match="libsndfile not found"):
        _sndfile.decode(b"data", "flac")


class _FakeSndfile:
    def __init__(self, *, open_ok=True):
        self.open_ok = open_ok
        self.closed = []

    def sf_open(self, path, mode, info_ptr):
        if not self.open_ok:
            return None
        info = info_ptr._obj
        info.frames = 2
        info.samplerate = 44100
        info.channels = 2
        return 123

    def sf_readf_double(self, handle, buf, frames):
        for i, value in enumerate((0.1, 0.2, 0.3, 0.4)):
            buf[i] = value
        return frames

    def sf_close(self, handle):
        self.closed.append(handle)
        return 0

    def sf_strerror(self, handle):
        return b"bad format"


def test_sndfile_decode_success_and_open_failure_cleanup(monkeypatch):
    fake = _FakeSndfile()
    monkeypatch.setattr(_sndfile, "_LIB", fake)

    decoded, sr = _sndfile.decode(b"fake-bytes", ".aiff")

    assert sr == 44100
    assert decoded.shape == (2, 2)
    assert np.allclose(decoded, [[0.1, 0.2], [0.3, 0.4]])
    assert fake.closed == [123]

    opened_paths = []
    real_unlink = os.unlink

    def tracking_unlink(path):
        opened_paths.append(path)
        real_unlink(path)

    monkeypatch.setattr(os, "unlink", tracking_unlink)
    monkeypatch.setattr(_sndfile, "_LIB", _FakeSndfile(open_ok=False))
    with pytest.raises(ValueError, match="bad format"):
        _sndfile.decode(b"bad", "ogg")
    assert opened_paths
