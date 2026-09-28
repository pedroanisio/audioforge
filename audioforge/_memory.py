"""Heap policy for the duration of a render (glibc only).

A render allocates and frees dozens of full-length float64 buffers (hundreds
of MB each for long assets). glibc serves every block above its mmap
threshold (capped at 32 MB) with a fresh mmap and returns it with munmap on
free, so each new buffer is page-faulted and zero-filled by the kernel again:
measured at ~15% of render CPU (clear_page_erms) and a third of system time.

Inside ``render_heap()`` large blocks come from the heap and freed ones are
kept for reuse; on exit the defaults are restored and ``malloc_trim(0)``
returns the memory to the OS. Audio is unaffected (allocation policy only).
Nested/concurrent renders share one refcounted window. Set
``AUDIOFORGE_MALLOC_TUNE=0`` to disable, e.g. when embedding in a host that
tunes malloc itself.
"""
from __future__ import annotations

import contextlib
import ctypes
import ctypes.util
import os
import threading

_M_TRIM_THRESHOLD = -1
_M_MMAP_THRESHOLD = -3
_M_MMAP_MAX = -4
_DEFAULT_TRIM = 128 * 1024
_DEFAULT_MMAP_MAX = 65536

_lock = threading.Lock()
_depth = 0
_libc = None


def _glibc():
    global _libc
    if _libc is None:
        _libc = False
        try:
            import platform
            if platform.libc_ver()[0] == "glibc":
                lib = ctypes.CDLL(ctypes.util.find_library("c") or "libc.so.6")
                lib.mallopt.argtypes = [ctypes.c_int, ctypes.c_int]
                lib.malloc_trim.argtypes = [ctypes.c_size_t]
                _libc = lib
        except OSError:
            _libc = False
    return _libc


@contextlib.contextmanager
def render_heap():
    global _depth
    lib = _glibc() if os.environ.get("AUDIOFORGE_MALLOC_TUNE", "1") != "0" else False
    if not lib:
        yield
        return
    with _lock:
        _depth += 1
        if _depth == 1:
            lib.mallopt(_M_MMAP_MAX, 0)               # large blocks: heap
            lib.mallopt(_M_TRIM_THRESHOLD, 2**31 - 1)  # keep freed for reuse
    try:
        yield
    finally:
        with _lock:
            _depth -= 1
            if _depth == 0:
                lib.mallopt(_M_MMAP_MAX, _DEFAULT_MMAP_MAX)
                lib.mallopt(_M_TRIM_THRESHOLD, _DEFAULT_TRIM)
                lib.malloc_trim(0)
