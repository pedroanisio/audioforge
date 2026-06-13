"""Atomic, durable file writes — the discipline every mutable artifact obeys.

This implements the write recipe from §9.3 of the design and is reused for
projected files, the index, blobs, refs and HEAD. There is exactly one place
in the codebase that calls ``os.replace`` for a managed write.

Recipe:

    1. write content to a temp file in `tmp_dir` (same filesystem as target)
    2. fsync the temp file
    3. chmod the temp file to the final mode (target is never made writable
       on POSIX, not even briefly)
    4. [Windows only] clear FILE_ATTRIBUTE_READONLY on the existing target,
       because os.replace() onto a read-only file fails on Windows
    5. os.replace(temp, target)            # atomic same-filesystem rename
    6. fsync the parent directory          # make the rename itself durable

`tmp_dir` MUST be on the same filesystem as `target`, or step 5 raises EXDEV
and atomicity is lost. Callers guarantee this by using `.shadowmd/tmp/`.
"""

from __future__ import annotations

import os
import stat
from pathlib import Path

# 0444 / 0644 expressed once so projection.py and protection.py agree.
READONLY_MODE = stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH  # 0o444
OWNER_RW_MODE = READONLY_MODE | stat.S_IWUSR  # 0o644

_IS_WINDOWS = os.name == "nt"


def _fsync_dir(directory: Path) -> None:
    """fsync a directory so a rename into it survives a crash.

    Not all platforms permit opening a directory for fsync (notably Windows);
    failure to fsync the directory weakens durability but never correctness, so
    it is swallowed rather than propagated.
    """
    try:
        fd = os.open(directory, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)


def _clear_windows_readonly(target: Path) -> None:
    if _IS_WINDOWS and target.exists():
        try:
            target.chmod(stat.S_IWUSR | stat.S_IRUSR)
        except OSError:
            pass


def atomic_write_bytes(
    target: Path,
    data: bytes,
    *,
    tmp_dir: Path,
    mode: int = OWNER_RW_MODE,
) -> None:
    """Atomically write ``data`` to ``target`` with final permission ``mode``."""
    target = Path(target)
    tmp_dir = Path(tmp_dir)
    tmp_dir.mkdir(parents=True, exist_ok=True)
    target.parent.mkdir(parents=True, exist_ok=True)

    # A per-write unique temp name; urandom keeps concurrent writers disjoint.
    tmp = tmp_dir / f".{target.name}.{os.urandom(8).hex()}.tmp"
    try:
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            os.write(fd, data)
            os.fsync(fd)
        finally:
            os.close(fd)

        os.chmod(tmp, mode)
        _clear_windows_readonly(target)
        os.replace(tmp, target)  # atomic on same-filesystem POSIX rename
        _fsync_dir(target.parent)
    finally:
        # If os.replace succeeded the temp no longer exists; this only fires on
        # an error path between open and replace.
        try:
            tmp.unlink()
        except OSError:
            pass
