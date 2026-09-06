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
import os
import shutil
import subprocess
import tempfile
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


def _native_cache_dir() -> Path:
    override = os.environ.get("AUDIOFORGE_NATIVE_CACHE")
    if override:
        return Path(override)
    xdg_cache = os.environ.get("XDG_CACHE_HOME")
    if xdg_cache:
        return Path(xdg_cache) / "audioforge"
    return Path.home() / ".cache" / "audioforge"


def _build_output_path(stem: str) -> Path:
    src_path = _NATIVE_DIR / f"{stem}.c"
    tag = hashlib.sha256(src_path.read_bytes()).hexdigest()[:16]
    return _native_cache_dir() / f"{stem}_{tag}.so"


def _ensure_cache_dir(path: Path) -> Path:
    try:
        path.mkdir(parents=True, exist_ok=True)
        return path
    except OSError:
        if os.environ.get("AUDIOFORGE_NATIVE_CACHE"):
            raise
        fallback = Path(tempfile.gettempdir()) / "audioforge-native-cache"
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback


def _build(stem: str, feature: str) -> Path:
    src_path = _NATIVE_DIR / f"{stem}.c"
    out = _build_output_path(stem)
    if out.exists():
        return out
    cc = shutil.which("cc") or shutil.which("gcc") or shutil.which("clang")
    if not cc:
        raise NativeUnavailable(
            f"{feature} needs a C compiler (cc/gcc/clang) to build the "
            f"native kernel; none found. Deterministic rendering fails "
            f"loudly rather than silently substituting different audio.")
    cache_dir = _ensure_cache_dir(out.parent)
    if cache_dir != out.parent:
        out = cache_dir / out.name
        if out.exists():
            return out
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


def ladder_native(x: np.ndarray, sr: int, cutoff_hz: float,
                  resonance: float, drive: float) -> np.ndarray:
    lib = _lib("ladder", "the nonlinear ladder filter (fx: ladder)")
    if not getattr(lib, "_ladder_sig", False):
        lib.ladder.restype = ctypes.c_int
        lib.ladder.argtypes = [
            ctypes.POINTER(ctypes.c_double), ctypes.c_long, ctypes.c_int,
            ctypes.c_double, ctypes.c_double, ctypes.c_double,
            ctypes.POINTER(ctypes.c_double)]
        lib._ladder_sig = True
    xin = np.ascontiguousarray(x, dtype=np.float64)
    out = np.zeros(xin.size)
    p = lambda a: a.ctypes.data_as(ctypes.POINTER(ctypes.c_double))  # noqa
    rc = lib.ladder(p(xin), xin.size, sr, float(cutoff_hz),
                    float(resonance), float(drive), p(out))
    if rc != 0:
        raise RuntimeError("native ladder kernel failed")
    return out


def sympathetic_native(exc, n: int, sr: int, freq: float, coupling: float,
                       buzz: float, damping: float,
                       brightness: float) -> np.ndarray:
    lib = _lib("sympathetic", "the sympathetic-string voice (osc: sympathetic)")
    if not getattr(lib, "_symp_sig", False):
        lib.sympathetic.restype = ctypes.c_int
        lib.sympathetic.argtypes = [
            ctypes.POINTER(ctypes.c_double), ctypes.c_long, ctypes.c_int,
            ctypes.c_double, ctypes.c_double, ctypes.c_double, ctypes.c_double,
            ctypes.c_double, ctypes.POINTER(ctypes.c_double)]
        lib._symp_sig = True
    ex = np.ascontiguousarray(exc, dtype=np.float64)
    out = np.zeros(n)
    p = lambda a: a.ctypes.data_as(ctypes.POINTER(ctypes.c_double))  # noqa
    rc = lib.sympathetic(p(ex), n, sr, float(freq), float(coupling),
                         float(buzz), float(damping), float(brightness), p(out))
    if rc != 0:
        raise RuntimeError("native sympathetic kernel failed")
    peak = np.max(np.abs(out))
    return out / peak if peak > 1e-9 else out


def struck_native(exc, n: int, sr: int, freq: float, damping: float,
                  brightness: float, tension: float) -> np.ndarray:
    lib = _lib("struck", "the struck-string voice (osc: struck)")
    if not getattr(lib, "_struck_sig", False):
        lib.struck.restype = ctypes.c_int
        lib.struck.argtypes = [
            ctypes.POINTER(ctypes.c_double), ctypes.c_long, ctypes.c_int,
            ctypes.c_double, ctypes.c_double, ctypes.c_double, ctypes.c_double,
            ctypes.POINTER(ctypes.c_double)]
        lib._struck_sig = True
    ex = np.ascontiguousarray(exc, dtype=np.float64)
    out = np.zeros(n)
    p = lambda a: a.ctypes.data_as(ctypes.POINTER(ctypes.c_double))  # noqa
    rc = lib.struck(p(ex), n, sr, float(freq), float(damping),
                    float(brightness), float(tension), p(out))
    if rc != 0:
        raise RuntimeError("native struck kernel failed")
    peak = np.max(np.abs(out))
    return out / peak if peak > 1e-9 else out


def tape_native(x: np.ndarray, sr: int, drive: float, flutter: float,
                tone: float) -> np.ndarray:
    lib = _lib("tape", "the analog tape effect (fx: tape)")
    if not getattr(lib, "_tape_sig", False):
        lib.tape.restype = ctypes.c_int
        lib.tape.argtypes = [
            ctypes.POINTER(ctypes.c_double), ctypes.c_long, ctypes.c_int,
            ctypes.c_double, ctypes.c_double, ctypes.c_double,
            ctypes.POINTER(ctypes.c_double)]
        lib._tape_sig = True
    xin = np.ascontiguousarray(x, dtype=np.float64)
    out = np.zeros(xin.size)
    p = lambda a: a.ctypes.data_as(ctypes.POINTER(ctypes.c_double))  # noqa
    rc = lib.tape(p(xin), xin.size, sr, float(drive), float(flutter),
                  float(tone), p(out))
    if rc != 0:
        raise RuntimeError("native tape kernel failed")
    return out


def brass_native(freq: float, n: int, sr: int, pressure: float,
                 brightness: float, lip: float, noise) -> np.ndarray:
    lib = _lib("brass", "the brass lip-reed voice (osc: brass)")
    if not getattr(lib, "_brass_sig", False):
        lib.brass_lip.restype = ctypes.c_int
        lib.brass_lip.argtypes = [
            ctypes.c_double, ctypes.c_long, ctypes.c_int, ctypes.c_double,
            ctypes.c_double, ctypes.c_double,
            ctypes.POINTER(ctypes.c_double), ctypes.POINTER(ctypes.c_double)]
        lib._brass_sig = True
    nz = np.ascontiguousarray(noise, dtype=np.float64)
    out = np.zeros(n)
    p = lambda a: a.ctypes.data_as(ctypes.POINTER(ctypes.c_double))  # noqa
    rc = lib.brass_lip(float(freq), n, sr, float(pressure),
                       float(brightness), float(lip), p(nz), p(out))
    if rc != 0:
        raise RuntimeError("brass kernel failed")
    peak = np.max(np.abs(out))
    return out / peak if peak > 1e-9 else out


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


def phaser_native(x: np.ndarray, sr: int, rate_hz: float, depth: float, stages: int,
                  feedback: float, center_hz: float, spread: float, phase: float = 0.0) -> np.ndarray:
    lib = _lib("phaser", "the swept allpass phaser (fx: phaser)")
    if not getattr(lib, "_phaser_sig", False):
        lib.phaser.restype = ctypes.c_int
        lib.phaser.argtypes = [
            ctypes.POINTER(ctypes.c_double), ctypes.c_long, ctypes.c_int,
            ctypes.c_double, ctypes.c_double, ctypes.c_int, ctypes.c_double,
            ctypes.c_double, ctypes.c_double, ctypes.c_double, ctypes.POINTER(ctypes.c_double)]
        lib._phaser_sig = True
    xin = np.ascontiguousarray(x, dtype=np.float64)
    out = np.zeros(xin.size)
    p = lambda a: a.ctypes.data_as(ctypes.POINTER(ctypes.c_double))  # noqa
    rc = lib.phaser(p(xin), xin.size, sr, float(rate_hz), float(depth), int(stages),
                    float(feedback), float(center_hz), float(spread), float(phase), p(out))
    if rc != 0:
        raise RuntimeError("native phaser kernel failed")
    return out


def flanger_native(x: np.ndarray, sr: int, rate_hz: float, depth_ms: float,
                   delay_ms: float, feedback: float, phase: float = 0.0) -> np.ndarray:
    lib = _lib("flanger", "the swept fractional-delay flanger (fx: flanger)")
    if not getattr(lib, "_flanger_sig", False):
        lib.flanger.restype = ctypes.c_int
        lib.flanger.argtypes = [
            ctypes.POINTER(ctypes.c_double), ctypes.c_long, ctypes.c_int,
            ctypes.c_double, ctypes.c_double, ctypes.c_double, ctypes.c_double,
            ctypes.c_double, ctypes.POINTER(ctypes.c_double)]
        lib._flanger_sig = True
    xin = np.ascontiguousarray(x, dtype=np.float64)
    out = np.zeros(xin.size)
    p = lambda a: a.ctypes.data_as(ctypes.POINTER(ctypes.c_double))  # noqa
    rc = lib.flanger(p(xin), xin.size, sr, float(rate_hz), float(depth_ms),
                     float(delay_ms), float(feedback), float(phase), p(out))
    if rc != 0:
        raise RuntimeError("native flanger kernel failed")
    return out
