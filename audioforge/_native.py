"""On-demand compilation + ctypes loading of the native kernel.

The kernel is required only for plate modulation (`plate(..., mod>0)`),
which is not expressible as an LTI impulse response. Policy: if no C
compiler is available the feature raises a clear error — never a silent
fallback that would make the same spec render differently across machines.
Compiled artifacts are cached, keyed by a hash of the source.
"""
from __future__ import annotations

import ctypes
import hashlib
import shutil
import subprocess
from pathlib import Path

import numpy as np

_LIBS: dict = {}
_NATIVE_DIR = Path(__file__).parent / "native"


_AVAILABLE: bool | None = None


def native_available() -> bool:
    """True when a C compiler (or a prebuilt kernel) is usable. Cached."""
    global _AVAILABLE
    if _AVAILABLE is None:
        import shutil
        _AVAILABLE = any(shutil.which(cc) for cc in ("cc", "gcc", "clang"))
    return _AVAILABLE


class NativeUnavailable(RuntimeError):
    pass


def _build(stem: str, feature: str) -> Path:
    src_path = _NATIVE_DIR / f"{stem}.c"
    tag = hashlib.sha256(src_path.read_bytes()).hexdigest()[:16]
    out = Path.home() / ".cache" / "audioforge" / f"{stem}_{tag}.so"
    if out.exists():
        return out
    cc = shutil.which("cc") or shutil.which("gcc") or shutil.which("clang")
    if not cc:
        raise NativeUnavailable(
            f"{feature} needs a C compiler (cc/gcc/clang) to build the "
            f"native kernel; none found. Deterministic rendering fails "
            f"loudly rather than silently substituting different audio.")
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".tmp.so")
    subprocess.run([cc, "-O2", "-fPIC", "-shared", str(src_path), "-o",
                    str(tmp), "-lm"], check=True, capture_output=True)
    tmp.replace(out)
    return out


def _lib(stem: str, feature: str):
    if stem not in _LIBS:
        _LIBS[stem] = ctypes.CDLL(str(_build(stem, feature)))
    return _LIBS[stem]


def plate_mod_native(mono: np.ndarray, sr: int, decay: float, damp: float,
                     mod_depth: float, mod_rate: float):
    lib = _lib("plate_mod", "plate modulation (mod > 0)")
    if not getattr(lib, "_sig_done", False):
        lib.plate_mod.restype = ctypes.c_int
        lib.plate_mod.argtypes = [
            ctypes.POINTER(ctypes.c_double), ctypes.c_long, ctypes.c_int,
            ctypes.c_double, ctypes.c_double, ctypes.c_double,
            ctypes.c_double, ctypes.POINTER(ctypes.c_double),
            ctypes.POINTER(ctypes.c_double)]
        lib._sig_done = True
    x = np.ascontiguousarray(mono, dtype=np.float64)
    wetL = np.zeros(x.size)
    wetR = np.zeros(x.size)
    p = lambda a: a.ctypes.data_as(ctypes.POINTER(ctypes.c_double))  # noqa
    rc = lib.plate_mod(p(x), x.size, sr, float(decay), float(damp),
                        float(mod_depth), float(mod_rate), p(wetL), p(wetR))
    if rc != 0:
        raise RuntimeError("native plate kernel failed")
    return wetL, wetR


def bowed_native(freq: float, n: int, sr: int, pressure: float,
                 position: float, brightness: float) -> np.ndarray:
    lib = _lib("bowed", "the bowed-string voice (osc: bowed)")
    if not getattr(lib, "_bowed_sig", False):
        lib.bowed_string.restype = ctypes.c_int
        lib.bowed_string.argtypes = [
            ctypes.c_double, ctypes.c_long, ctypes.c_int, ctypes.c_double,
            ctypes.c_double, ctypes.c_double,
            ctypes.POINTER(ctypes.c_double)]
        lib._bowed_sig = True
    out = np.zeros(n)
    rc = lib.bowed_string(float(freq), n, sr, float(pressure),
                          float(position), float(brightness),
                          out.ctypes.data_as(ctypes.POINTER(ctypes.c_double)))
    if rc != 0:
        raise RuntimeError("bowed kernel failed")
    peak = np.max(np.abs(out))
    return out / peak if peak > 1e-9 else out


def blown_native(freq: float, n: int, sr: int, pressure: float,
                 brightness: float, noise) -> np.ndarray:
    lib = _lib("blown", "the blown-pipe voice (osc: blown)")
    if not getattr(lib, "_blown_sig", False):
        lib.blown_pipe.restype = ctypes.c_int
        lib.blown_pipe.argtypes = [
            ctypes.c_double, ctypes.c_long, ctypes.c_int, ctypes.c_double,
            ctypes.c_double, ctypes.POINTER(ctypes.c_double),
            ctypes.POINTER(ctypes.c_double)]
        lib._blown_sig = True
    nz = np.ascontiguousarray(noise, dtype=np.float64)
    out = np.zeros(n)
    p = lambda a: a.ctypes.data_as(ctypes.POINTER(ctypes.c_double))  # noqa
    rc = lib.blown_pipe(float(freq), n, sr, float(pressure),
                        float(brightness), p(nz), p(out))
    if rc != 0:
        raise RuntimeError("blown kernel failed")
    peak = np.max(np.abs(out))
    return out / peak if peak > 1e-9 else out
