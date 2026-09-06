"""On-demand compilation + ctypes loading of the native C kernels.

Every render goes through native kernels (ADR-0012): the engine-wide streaming
DSP in native/dsp.c and native/upfirdn.c (registered in ENGINE_KERNELS), plus
the dedicated physical-model voices, ladder/tape effects and modulated plate.
Policy (ADR-0004): if no C compiler is available rendering fails loudly -- never
a silent fallback that would make the same spec render differently across
machines; the only fallback is one proven bit-identical by a test
(resample_poly -> scipy). Compiled artifacts are cached, keyed by a hash of the
source (and, for the SIMD kernels, the compiler flags and CPU identity).
"""
from __future__ import annotations

import ctypes
import hashlib
import os
import shutil
import subprocess
import tempfile
import threading
from pathlib import Path

import numpy as np

_LIBS: dict = {}
_LIB_LOCK = threading.RLock()
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


# Engine-infrastructure kernels (not DSL oscillators or effects): source stem
# -> the wrappers built on it. scripts/drift_inspect.py checks both directions.
ENGINE_KERNELS = {
    "dsp": ("true_peak4", "freeverb", "biquad_tv", "biquad", "iir_multi",
            "biquad_batch", "curve_seconds",
            "delay_taps", "wavetable_acc", "fdn_ir", "saturate4",
            "running_min_fwd", "sparse_feedback"),
    "upfirdn": ("resample_poly",),
}

# Streaming kernels are built for the host CPU's full vector width. They are
# safe to vectorize across ISAs: every loop is lane-parallel over independent
# outputs (no reassociated reductions), and FMA contraction and fast-math are
# off, so AVX2, AVX-512 and scalar builds produce identical bits (verified).
_SIMD_STEMS = frozenset({"dsp", "upfirdn"})
_SIMD_FLAGS = ["-O3", "-march=native", "-ffp-contract=off", "-fno-fast-math"]


def _cpu_identity() -> str:
    """Host CPU identity for the cache key: a -march=native binary must never
    be loaded on a different CPU (e.g. a home directory shared over NFS)."""
    import platform
    ident = platform.machine()
    try:
        with open("/proc/cpuinfo") as fh:
            for line in fh:
                if line.startswith(("model name", "flags", "Features")):
                    ident += line
                    if line.startswith(("flags", "Features")):
                        break
    except OSError:
        ident += platform.processor()
    return ident


def _compile_flags(stem: str) -> list[str]:
    return _SIMD_FLAGS if stem in _SIMD_STEMS else ["-O2"]


def _build_output_path(stem: str) -> Path:
    src_path = _NATIVE_DIR / f"{stem}.c"
    h = hashlib.sha256(src_path.read_bytes())
    if stem in _SIMD_STEMS:
        h.update(" ".join(_compile_flags(stem)).encode())
        h.update(_cpu_identity().encode())
    tag = h.hexdigest()[:16]
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
    # Separate compiler outputs also make publication safe across processes.
    fd, filename = tempfile.mkstemp(prefix=out.stem + "_", suffix=".tmp.so",
                                    dir=out.parent)
    os.close(fd)
    tmp = Path(filename)
    try:
        subprocess.run([cc, *_compile_flags(stem), "-fPIC", "-shared",
                        str(src_path), "-o", str(tmp), "-lm"],
                       check=True, capture_output=True)
        tmp.replace(out)
    finally:
        tmp.unlink(missing_ok=True)
    return out


def _lib(stem: str, feature: str):
    with _LIB_LOCK:
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


_RESAMPLE_FILTERS: dict = {}   # (up, down) -> (h, n_pre_pad, n_pre_remove)

# scipy.signal.firwin(81, 0.25, window=("kaiser", 5.0)) as exact float64 bit
# patterns: the 4x oversampling filter of the limiter and saturator. Frozen so
# the render path never imports scipy.signal (~0.4 s CPU per process) and the
# taps cannot drift with scipy versions; tests/test_native_resample.py checks
# them against firwin.
_KAISER5_LP81 = np.array([float.fromhex(v) for v in (
    '-0x1.a6a4300ba71c9p-62', '-0x1.28611e8298483p-12', '-0x1.13aa9a5e3f476p-11',
    '-0x1.f282c65a55606p-12', '0x1.11adce2da5a3fp-60', '0x1.7f9584c74ee84p-11',
    '0x1.48e4fa30b5f02p-10', '0x1.16ae13530551dp-10', '-0x1.01da64d2040fbp-59',
    '-0x1.84c350aacf6cfp-10', '-0x1.40d377da7a8dep-9', '-0x1.0700052f53411p-9',
    '0x1.9dbb79621dc70p-59', '0x1.5b81f186879cap-9', '0x1.186a29c763147p-8',
    '0x1.c2b092330eb1cp-9', '-0x1.2a8a8de600f95p-58', '-0x1.20045cf60f943p-8',
    '-0x1.ca7a5ee634d16p-8', '-0x1.6c0cf475626edp-8', '0x1.8dcd0890bcf53p-58',
    '0x1.c8925199e37c1p-8', '0x1.68dea87191e7ep-7', '0x1.1d0af026ae67bp-7',
    '-0x1.f0a230de2f0b9p-58', '-0x1.63b8d00520e29p-7', '-0x1.19592635fa7bfp-6',
    '-0x1.bdda8706b1727p-7', '0x1.250dd5b98ba71p-57', '0x1.1a82bd3777fc7p-6',
    '0x1.c4f9bc9efca6ep-6', '0x1.6db460605c314p-6', '-0x1.48c390d2693adp-57',
    '-0x1.ec11ff10a3ce3p-6', '-0x1.9d75948cc65dep-5', '-0x1.644e71625b76fp-5',
    '0x1.5fceed6b34bb8p-57', '0x1.2fa8ebc041f71p-4', '0x1.4456fa47e4ebcp-3',
    '0x1.cc9ca3edcf7c1p-3', '0x1.0029b7ca3d50ap-2', '0x1.cc9ca3edcf7c1p-3',
    '0x1.4456fa47e4ebcp-3', '0x1.2fa8ebc041f71p-4', '0x1.5fceed6b34bb8p-57',
    '-0x1.644e71625b76fp-5', '-0x1.9d75948cc65dep-5', '-0x1.ec11ff10a3ce3p-6',
    '-0x1.48c390d2693adp-57', '0x1.6db460605c314p-6', '0x1.c4f9bc9efca6ep-6',
    '0x1.1a82bd3777fc7p-6', '0x1.250dd5b98ba71p-57', '-0x1.bdda8706b1727p-7',
    '-0x1.19592635fa7bfp-6', '-0x1.63b8d00520e29p-7', '-0x1.f0a230de2f0b9p-58',
    '0x1.1d0af026ae67bp-7', '0x1.68dea87191e7ep-7', '0x1.c8925199e37c1p-8',
    '0x1.8dcd0890bcf53p-58', '-0x1.6c0cf475626edp-8', '-0x1.ca7a5ee634d16p-8',
    '-0x1.20045cf60f943p-8', '-0x1.2a8a8de600f95p-58', '0x1.c2b092330eb1cp-9',
    '0x1.186a29c763147p-8', '0x1.5b81f186879cap-9', '0x1.9dbb79621dc70p-59',
    '-0x1.0700052f53411p-9', '-0x1.40d377da7a8dep-9', '-0x1.84c350aacf6cfp-10',
    '-0x1.01da64d2040fbp-59', '0x1.16ae13530551dp-10', '0x1.48e4fa30b5f02p-10',
    '0x1.7f9584c74ee84p-11', '0x1.11adce2da5a3fp-60', '-0x1.f282c65a55606p-12',
    '-0x1.13aa9a5e3f476p-11', '-0x1.28611e8298483p-12', '-0x1.a6a4300ba71c9p-62',
)])


def _upfirdn_output_len(len_h: int, in_len: int, up: int, down: int) -> int:
    """scipy.signal._upfirdn._output_len: ceil(((in_len-1)*up + len_h)/down)."""
    return (((in_len - 1) * up + len_h) - 1) // down + 1


def _pad_h(h: np.ndarray, up: int) -> np.ndarray:
    """scipy.signal._upfirdn._pad_h: coefficients in upfirdn's transposed,
    per-phase flipped layout."""
    h_full = np.zeros(h.size + (-h.size % up), h.dtype)
    h_full[:h.size] = h
    return h_full.reshape(-1, up).T[:, ::-1].ravel()


def _resample_filter(up: int, down: int, n_in: int):
    """scipy.signal.resample_poly's default filter (window=('kaiser', 5.0)),
    padded and stored in upfirdn's transposed/flipped layout."""
    key = (up, down)
    if key not in _RESAMPLE_FILTERS:
        max_rate = max(up, down)
        half_len = 10 * max_rate
        if max_rate == 4:
            h = _KAISER5_LP81.copy()
        else:
            from scipy.signal import firwin
            h = np.asarray(firwin(2 * half_len + 1, 1.0 / max_rate,
                                  window=("kaiser", 5.0)), dtype=np.float64)
        h *= up
        n_pre_pad = down - half_len % down
        n_pre_remove = (half_len + n_pre_pad) // down
        _RESAMPLE_FILTERS[key] = (h, n_pre_pad, n_pre_remove)
    h, n_pre_pad, n_pre_remove = _RESAMPLE_FILTERS[key]
    n_out = n_in * up
    n_out = n_out // down + bool(n_out % down)
    n_post_pad = 0            # scipy's loop; depends on n_in, rarely > 0
    while _upfirdn_output_len(h.shape[0] + n_pre_pad + n_post_pad, n_in,
                              up, down) < n_out + n_pre_remove:
        n_post_pad += 1
    hp = np.concatenate((np.zeros(n_pre_pad), h, np.zeros(n_post_pad)))
    hf = np.ascontiguousarray(_pad_h(hp, up))
    return hf, hf.size // up, n_pre_remove, n_out


def resample_poly(x: np.ndarray, up: int, down: int, axis: int = 0) -> np.ndarray:
    """Bit-identical drop-in for ``scipy.signal.resample_poly(x, up, down,
    axis=axis)`` with the default window and constant zero padding, for
    float64 input along axis 0 of a 1-D or 2-D array.

    The native kernel evaluates only the kept output window, vectorized
    across outputs with scipy's per-output summation order, so every sample
    matches scipy exactly (tests/test_native_resample.py). Anything outside
    that envelope, or a missing C compiler, uses scipy itself — the same
    bytes either way, so there is no cross-machine divergence."""
    import math
    from scipy.signal import resample_poly as _scipy_resample_poly
    x = np.asarray(x)
    if (x.dtype != np.float64 or x.ndim not in (1, 2) or axis not in (0, -x.ndim)
            or not native_available()):
        return _scipy_resample_poly(x, up, down, axis=axis)
    g = math.gcd(int(up), int(down))
    up, down = int(up) // g, int(down) // g
    if up == down == 1:
        return x.copy()
    n_in = x.shape[0]
    hf, hpp, n_pre_remove, n_out = _resample_filter(up, down, n_in)
    lib = _lib("upfirdn", "polyphase resampling")
    if not getattr(lib, "_upfirdn_sig", False):
        lib.upfirdn_range.restype = ctypes.c_int
        lib.upfirdn_range.argtypes = [
            ctypes.POINTER(ctypes.c_double), ctypes.POINTER(ctypes.c_double),
            ctypes.c_long, ctypes.c_long, ctypes.c_long, ctypes.c_long,
            ctypes.c_long, ctypes.POINTER(ctypes.c_double)]
        lib._upfirdn_sig = True
    p = lambda a: a.ctypes.data_as(ctypes.POINTER(ctypes.c_double))  # noqa
    cols = [x] if x.ndim == 1 else [x[:, c] for c in range(x.shape[1])]
    outs = []
    xp = np.zeros(n_in + 2 * (hpp - 1))
    for col in cols:
        xp[hpp - 1:hpp - 1 + n_in] = col
        out = np.empty(n_out)
        rc = lib.upfirdn_range(p(xp), p(hf), hpp, up, down, n_pre_remove,
                               n_out, p(out))
        if rc != 0:
            raise RuntimeError("native upfirdn kernel failed")
        outs.append(out)
    return outs[0] if x.ndim == 1 else np.stack(outs, axis=1)


_P = ctypes.POINTER(ctypes.c_double)
_L = ctypes.c_long


def _ptr(a: np.ndarray):
    return a.ctypes.data_as(_P)


def _dsp():
    lib = _lib("dsp", "the streaming DSP kernels (limiter, hall, filters, delay)")
    if not getattr(lib, "_dsp_sig", False):
        LP = ctypes.POINTER(ctypes.c_long)
        lib.true_peak4.restype = ctypes.c_int
        lib.true_peak4.argtypes = [_P, _P, _L, _P, _L, _L, _P]
        lib.freeverb.restype = ctypes.c_int
        lib.freeverb.argtypes = [_P, _L, LP, _P, _L, ctypes.c_double, LP, _L,
                                 ctypes.c_double, _P]
        lib.biquad_tv.restype = ctypes.c_int
        lib.biquad_tv.argtypes = [_P, _L, _P, _L, _P]
        lib.delay_taps.restype = ctypes.c_int
        lib.delay_taps.argtypes = [_P, _L, _L, _P, _L, _P]
        lib.fdn_ir.restype = ctypes.c_int
        lib.fdn_ir.argtypes = [_L, LP, _P, _P, ctypes.c_double, LP, _P,
                               ctypes.c_double, ctypes.c_double, _P, _P]
        lib.saturate4.restype = ctypes.c_int
        lib.saturate4.argtypes = [_P, _L, _P, _L, _L, _P, _L, _L,
                                  ctypes.c_double, ctypes.c_double,
                                  ctypes.c_double, ctypes.c_double, _P]
        PP = ctypes.POINTER(_P)
        lib.iir_multi.restype = ctypes.c_int
        lib.iir_multi.argtypes = [PP, _L, _L, _P, _L, PP]
        lib.running_min_fwd.restype = ctypes.c_int
        lib.running_min_fwd.argtypes = [_P, _L, _L, _P]
        lib.sparse_feedback.restype = ctypes.c_int
        lib.sparse_feedback.argtypes = [_P, _L, LP, _P, _L, _P]
        lib.iir_ragged.restype = ctypes.c_int
        lib.iir_ragged.argtypes = [PP, LP, _L, _P, PP]
        lib.curve_seconds.restype = ctypes.c_int
        lib.curve_seconds.argtypes = [_L, ctypes.c_double, ctypes.c_double,
                                      _P, _P, LP, _P, _L, _L, ctypes.c_double, _P]
        lib.wavetable_acc.restype = ctypes.c_int
        lib.wavetable_acc.argtypes = [_P, _L, ctypes.c_double, ctypes.c_double,
                                      ctypes.c_double, _L, ctypes.c_double, _P]
        lib._dsp_sig = True
    return lib


def true_peak4(stereo: np.ndarray) -> np.ndarray:
    """Stereo-linked 4x-oversampled |peak| per base sample, equal to
    max over phases of |resample_poly(stereo, 4, 1, axis=0)| (fused kernel)."""
    n = stereo.shape[0]
    hf, hpp, n_pre_remove, _ = _resample_filter(4, 1, n)
    pads = []
    for c in range(2):
        xp = np.zeros(n + 2 * (hpp - 1) + 8)
        xp[hpp - 1:hpp - 1 + n] = stereo[:, c]
        pads.append(xp)
    out = np.empty(n)
    if _dsp().true_peak4(_ptr(pads[0]), _ptr(pads[1]), n, _ptr(hf), hpp,
                         n_pre_remove, _ptr(out)) != 0:
        raise RuntimeError("native true-peak kernel failed")
    return out


def freeverb(x: np.ndarray, comb_lengths, comb_gains, damp: float,
             allpass_lengths, allpass_gain: float = 0.5) -> np.ndarray:
    xin = np.ascontiguousarray(x, dtype=np.float64)
    cl = np.ascontiguousarray(comb_lengths, dtype=np.int64)
    cg = np.ascontiguousarray(comb_gains, dtype=np.float64)
    al = np.ascontiguousarray(allpass_lengths, dtype=np.int64)
    LP = ctypes.POINTER(ctypes.c_long)
    wet = np.empty(xin.size)
    if _dsp().freeverb(_ptr(xin), xin.size, cl.ctypes.data_as(LP), _ptr(cg),
                       cl.size, float(damp), al.ctypes.data_as(LP), al.size,
                       float(allpass_gain), _ptr(wet)) != 0:
        raise RuntimeError("native freeverb kernel failed")
    return wet


def biquad_tv(x: np.ndarray, coef: np.ndarray, block: int) -> np.ndarray:
    """coef: [n_blocks, 5] rows of (b0, b1, b2, a1, a2), a0 == 1."""
    xin = np.ascontiguousarray(x, dtype=np.float64)
    c = np.ascontiguousarray(coef, dtype=np.float64)
    if c.shape != (-(-xin.size // block), 5):
        raise ValueError("biquad_tv: one coefficient row per block required")
    out = np.empty(xin.size)
    if _dsp().biquad_tv(_ptr(xin), xin.size, _ptr(c), int(block), _ptr(out)) != 0:
        raise RuntimeError("native biquad kernel failed")
    return out


def delay_taps(x: np.ndarray, d: int, gains) -> np.ndarray:
    xin = np.ascontiguousarray(x, dtype=np.float64)
    g = np.ascontiguousarray(gains, dtype=np.float64)
    wet = np.empty(xin.size)
    if _dsp().delay_taps(_ptr(xin), xin.size, int(d), _ptr(g), g.size,
                         _ptr(wet)) != 0:
        raise RuntimeError("native delay kernel failed")
    return wet


def wavetable_acc(table: np.ndarray, w: float, phase0: float, sr: int, n: int,
                  amp: float, out: np.ndarray) -> np.ndarray:
    """out += amp * wavetable(table) at angular rate w (= 2*pi*f); in place."""
    if out.dtype != np.float64 or not out.flags.c_contiguous or out.size < n:
        raise ValueError("wavetable_acc: out must be contiguous float64 of size >= n")
    tb = np.ascontiguousarray(table, dtype=np.float64)
    if _dsp().wavetable_acc(_ptr(tb), tb.size, float(w), float(phase0),
                            float(sr), int(n), float(amp), _ptr(out)) != 0:
        raise RuntimeError("native wavetable kernel failed")
    return out


def biquad(x: np.ndarray, b, a) -> np.ndarray:
    """Static biquad (or first-order) filter: lfilter(b, a, x) in one native
    pass, bit-identical to lfilter, subnormal-safe. a[0] must be 1."""
    return iir_multi([x], [(b, a)])[0]


def fdn_ir(ir_len: int, lengths, b0, b1, p: float, ap_lengths, ap_gains,
           inj: float, two_over_n: float):
    """Raw stereo impulse response of the 8-line FDN (see spaces._fdn_irs)."""
    LP = ctypes.POINTER(ctypes.c_long)
    ls = np.ascontiguousarray(lengths, dtype=np.int64)
    al = np.ascontiguousarray(ap_lengths, dtype=np.int64)
    arrs = [np.ascontiguousarray(v, dtype=np.float64) for v in (b0, b1, ap_gains)]
    if ls.size != 8 or al.size != 2:
        raise ValueError("fdn_ir: 8 lines and 2 input allpasses required")
    irL = np.empty(ir_len)
    irR = np.empty(ir_len)
    if _dsp().fdn_ir(int(ir_len), ls.ctypes.data_as(LP), _ptr(arrs[0]),
                     _ptr(arrs[1]), float(p), al.ctypes.data_as(LP),
                     _ptr(arrs[2]), float(inj), float(two_over_n),
                     _ptr(irL), _ptr(irR)) != 0:
        raise RuntimeError("native FDN kernel failed")
    return irL, irR


def saturate4(x: np.ndarray, bias: float, d: float) -> np.ndarray:
    """(tanh((up + bias) * d) - tanh(bias * d)) / tanh(d) at 4x oversampling,
    decimated back: the wet path of fx.saturate_fx in one fused native pass."""
    xin = np.ascontiguousarray(x, dtype=np.float64)
    n = xin.size
    if n == 0:
        return np.zeros(0)
    hu, hpu, y0u, _ = _resample_filter(4, 1, n)
    hd, hpd, y0d, _ = _resample_filter(1, 4, 4 * n)
    margin = hpu + hpd + 16                  # kernel reads stay in bounds
    buf = np.zeros(n + 2 * (hpu - 1) + 2 * margin)
    buf[margin + hpu - 1:margin + hpu - 1 + n] = xin
    xp = buf[margin:]
    out = np.empty(n)
    c0 = float(np.tanh(bias * d))
    inv = 1.0 / float(np.tanh(d))
    if _dsp().saturate4(_ptr(xp), n, _ptr(hu), hpu, y0u, _ptr(hd), hpd, y0d,
                        float(bias), float(d), c0, inv, _ptr(out)) != 0:
        raise RuntimeError("native saturation kernel failed")
    return out


def iir_multi(channels, sections) -> list[np.ndarray]:
    """Filter each channel through the cascade ``sections`` = [(b, a), ...]
    (each order <= 2, a[0] == 1) in one native pass; lfilter update order
    per section, so results match cascaded lfilter calls."""
    rows = [np.ascontiguousarray(c, dtype=np.float64) for c in channels]
    n = rows[0].size
    if any(r.size != n for r in rows):
        raise ValueError("iir_multi: channels must have equal length")
    coef = []
    for b, a in sections:
        b = [float(v) for v in b] + [0.0] * (3 - len(b))
        a = [float(v) for v in a] + [0.0] * (3 - len(a))
        if len(b) != 3 or len(a) != 3 or a[0] != 1.0:
            raise ValueError("iir_multi: sections of order <= 2 with a[0] == 1")
        coef += [b[0], b[1], b[2], a[1], a[2]]
    coef = np.array(coef)
    outs = [np.empty(n) for _ in rows]
    PA = _P * len(rows)
    xin = PA(*[_ptr(r) for r in rows])
    xout = PA(*[_ptr(o) for o in outs])
    if _dsp().iir_multi(xin, len(rows), n, _ptr(coef), len(sections), xout) != 0:
        raise RuntimeError("native IIR kernel failed")
    return outs


def running_min_fwd(x: np.ndarray, L: int) -> np.ndarray:
    """out[i] = min(x[i:i+L]) == scipy.ndimage.minimum_filter1d(x, L,
    mode="nearest", origin=-(L // 2)), in O(n)."""
    xin = np.ascontiguousarray(x, dtype=np.float64)
    out = np.empty(xin.size)
    if _dsp().running_min_fwd(_ptr(xin), xin.size, int(L), _ptr(out)) != 0:
        raise RuntimeError("native running-min kernel failed")
    return out


def sparse_feedback(x: np.ndarray, taps: dict) -> np.ndarray:
    """y[n] = x[n] + sum(c * y[n - lag] for lag, c in taps.items())."""
    xin = np.ascontiguousarray(x, dtype=np.float64)
    lags = np.array(list(taps.keys()), dtype=np.int64)
    cs = np.array([float(v) for v in taps.values()])
    y = np.empty(xin.size)
    LP = ctypes.POINTER(ctypes.c_long)
    if _dsp().sparse_feedback(_ptr(xin), xin.size, lags.ctypes.data_as(LP),
                              _ptr(cs), lags.size, _ptr(y)) != 0:
        raise RuntimeError("native feedback kernel failed")
    return y


def biquad_batch(items) -> list[np.ndarray]:
    """[lfilter(b, a, x) for x, b, a in items] (order <= 2, a[0] == 1), run
    8 at a time so independent short filters overlap; same bits as biquad."""
    outs: list[np.ndarray] = []
    LP = ctypes.POINTER(ctypes.c_long)
    for g in range(0, len(items), 8):
        grp = items[g:g + 8]
        rows = [np.ascontiguousarray(x, dtype=np.float64) for x, _, _ in grp]
        coef = []
        for _, b, a in grp:
            b = [float(v) for v in b] + [0.0] * (3 - len(b))
            a = [float(v) for v in a] + [0.0] * (3 - len(a))
            if len(b) != 3 or len(a) != 3 or a[0] != 1.0:
                raise ValueError("biquad_batch: order <= 2 with a[0] == 1")
            coef += [b[0], b[1], b[2], a[1], a[2]]
        coef = np.array(coef)
        lens = np.array([r.size for r in rows], dtype=np.int64)
        res = [np.empty(r.size) for r in rows]
        PA = _P * len(rows)
        if _dsp().iir_ragged(PA(*[_ptr(r) for r in rows]), lens.ctypes.data_as(LP),
                             len(rows), _ptr(coef), PA(*[_ptr(o) for o in res])) != 0:
            raise RuntimeError("native IIR kernel failed")
        outs += res
    return outs



def curve_seconds(curve: dict, n: int, sr: int, mode: int = 0,
                  scale: float = 0.0) -> np.ndarray | None:
    """curves.evaluate_curve(curve, arange(n) / sr) in one native pass, with
    mode 1 = exp(value * scale) and mode 2 = clip to [0, 1] fused in. None
    when the curve needs the general path (time_map)."""
    from .curves import _normalized_points, _pow_exponent, _shape_kind
    if curve.get("time_map"):
        return None
    pts = _normalized_points(curve)
    t = np.array([p[0] for p in pts], dtype=np.float64)
    v = np.array([p[1] for p in pts], dtype=np.float64)
    kinds, exps = [], []
    for _, _, shape in pts:
        kd = _shape_kind(shape)
        kinds.append({"linear": 0, "hold": 1}.get(kd, 2))
        exps.append(_pow_exponent(shape) if kd not in ("linear", "hold") else 1.0)
    kind = np.array(kinds, dtype=np.int64)
    ex = np.array(exps, dtype=np.float64)
    out = np.empty(n)
    LP = ctypes.POINTER(ctypes.c_long)
    if _dsp().curve_seconds(int(n), float(sr), float(curve.get("time_offset", 0)),
                            _ptr(t), _ptr(v), kind.ctypes.data_as(LP), _ptr(ex),
                            t.size, int(mode), float(scale), _ptr(out)) != 0:
        raise RuntimeError("native curve kernel failed")
    return out


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
