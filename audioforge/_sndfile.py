"""Minimal, deterministic libsndfile binding for compressed sample formats.

AudioForge decodes WAV in pure Python (the `wave` module). For FLAC / Ogg /
AIFF samples — which several CC0 libraries ship (VSUpright1, Virtuosity Drums,
parts of VCSL) — we lean on the system libsndfile via ctypes, matching the
project's existing ctypes-native style (see `_native.py`). libsndfile's PCM
decode is bit-exact and reproducible, so determinism holds.

If libsndfile is absent, `available()` is False and `decode()` raises a clear
error naming the format and the install hint — WAV samples are unaffected.
"""
from __future__ import annotations

import ctypes
import ctypes.util
import os
import tempfile

import numpy as np

_SFM_READ = 0x10


class _SF_INFO(ctypes.Structure):
    _fields_ = [
        ("frames", ctypes.c_int64),
        ("samplerate", ctypes.c_int),
        ("channels", ctypes.c_int),
        ("format", ctypes.c_int),
        ("sections", ctypes.c_int),
        ("seekable", ctypes.c_int),
    ]


def _load():
    names = [ctypes.util.find_library("sndfile"), "libsndfile.so.1",
             "libsndfile.so", "libsndfile.1.dylib", "libsndfile.dylib",
             "sndfile", "libsndfile-1.dll"]
    for n in filter(None, names):
        try:
            lib = ctypes.CDLL(n)
        except OSError:
            continue
        lib.sf_open.argtypes = [ctypes.c_char_p, ctypes.c_int,
                                ctypes.POINTER(_SF_INFO)]
        lib.sf_open.restype = ctypes.c_void_p
        lib.sf_readf_double.argtypes = [ctypes.c_void_p,
                                        ctypes.POINTER(ctypes.c_double),
                                        ctypes.c_int64]
        lib.sf_readf_double.restype = ctypes.c_int64
        lib.sf_close.argtypes = [ctypes.c_void_p]
        lib.sf_close.restype = ctypes.c_int
        lib.sf_strerror.argtypes = [ctypes.c_void_p]
        lib.sf_strerror.restype = ctypes.c_char_p
        return lib
    return None


_UNSET = object()
_LIB = _UNSET          # the library handle, or None when absent; lazy


def _lib():
    """libsndfile, located on first use (find_library spawns ldconfig, so an
    eager lookup cost every process ~0.1 s even when no sample is decoded)."""
    global _LIB
    if _LIB is _UNSET:
        _LIB = _load()
    return _LIB


def available() -> bool:
    return _lib() is not None


def decode(data: bytes, ext: str = "") -> tuple[np.ndarray, int]:
    """Decode compressed audio bytes -> (float64 array [frames, channels], sr).

    libsndfile reads from a path, so the verified bytes are staged in a temp
    file (suffixed by `ext` to help format sniffing) and removed afterwards.
    """
    if _lib() is None:
        raise RuntimeError(
            f"cannot decode '{ext or 'compressed'}' sample: libsndfile not "
            f"found. Install it (apt: libsndfile1, brew: libsndfile) — WAV "
            f"samples do not need it.")
    suffix = ("." + ext.lstrip(".")) if ext else ""
    fd, path = tempfile.mkstemp(suffix=suffix)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        info = _SF_INFO()
        handle = _lib().sf_open(path.encode(), _SFM_READ, ctypes.byref(info))
        if not handle:
            msg = _lib().sf_strerror(None)
            raise ValueError(f"libsndfile could not open {ext or 'audio'}: "
                             f"{(msg or b'').decode(errors='replace')}")
        try:
            n = int(info.frames) * int(info.channels)
            buf = (ctypes.c_double * n)()
            got = _lib().sf_readf_double(handle, buf, info.frames)
            x = np.ctypeslib.as_array(buf).astype(np.float64).copy()
        finally:
            _lib().sf_close(handle)
        ch = int(info.channels)
        if ch > 1:
            x = x[: int(got) * ch].reshape(-1, ch)
        else:
            x = x[: int(got)].reshape(-1, 1)
        return x, int(info.samplerate)
    finally:
        os.unlink(path)
