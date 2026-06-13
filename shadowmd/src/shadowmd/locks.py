"""Repo/file lock hierarchy backed by kernel advisory locks (§9.1).

Two lock levels, acquired in a fixed order to prevent deadlock:

    repo lock  — held by snapshot, restore, gc, fsck
    file lock  — held per managed file by any mutation
    order      — repo lock (if needed) before file lock; never the reverse

Locking uses ``fcntl.flock`` on an open file descriptor, NOT a presence-based
``O_EXCL`` file plus PID heuristics. This is a deliberate correctness decision:

* The kernel releases an ``flock`` when the holding process dies — including
  ``kill -9`` and crashes — so there is no "stale lock" to detect or guess at.
  A presence-based lock leaks forever on crash; a PID heuristic both deadlocks
  on PID reuse (a dead lock looks alive) and, worse, can classify a *live*
  lock as stale and delete it. None of those failure modes exist here.
* flock is mutually exclusive across processes on the same host and local
  filesystem. Network-filesystem and cross-host semantics remain out of scope
  (documented limitation — this is a local-first tool).

Reentrancy within a single process is handled one level up by
``ShadowRepository.repo_locked`` (a depth counter that acquires the OS lock once
at depth 0), so each lock file is opened exactly once per held region.
"""

from __future__ import annotations

import json
import os
import socket
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from .errors import LockError
from .ids import iso_now
from .layout import Layout

try:  # POSIX
    import fcntl

    _HAVE_FLOCK = True
except ImportError:  # pragma: no cover - Windows
    _HAVE_FLOCK = False

REPO_LOCK = "repo.lock"


def _slug(name: str) -> str:
    """Map a file path to a safe single lock filename."""
    return "file__" + name.replace(os.sep, "_").replace("/", "_") + ".lock"


class _Held:
    """A held lock: the open fd whose flock the kernel will drop on death."""

    __slots__ = ("fd", "path")

    def __init__(self, fd: int, path: Path) -> None:
        self.fd = fd
        self.path = path


class LockManager:
    def __init__(self, layout: Layout, staleness_seconds: int = 3600) -> None:
        self._layout = layout
        self._host = socket.gethostname()
        # Retained only for cross-host diagnostics; flock needs no staleness.
        self._staleness = staleness_seconds

    def _lock_path(self, name: str) -> Path:
        return self._layout.locks / name

    def _open(self, name: str) -> int:
        path = self._lock_path(name)
        path.parent.mkdir(parents=True, exist_ok=True)
        return os.open(path, os.O_RDWR | os.O_CREAT, 0o644)

    def _acquire(self, name: str) -> _Held:
        path = self._lock_path(name)
        fd = self._open(name)
        if _HAVE_FLOCK:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                os.close(fd)
                raise LockError(
                    f"could not acquire lock {name!r}; held by {self._read_holder(path)}"
                ) from None
        else:  # pragma: no cover - Windows fallback (weaker, presence-based)
            try:
                fd2 = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
                os.close(fd2)
            except FileExistsError:
                os.close(fd)
                raise LockError(f"could not acquire lock {name!r}") from None
        # Record holder metadata for human-readable diagnostics only; it is
        # NEVER consulted to decide liveness (the kernel is the authority).
        os.ftruncate(fd, 0)
        os.write(
            fd,
            json.dumps({"pid": os.getpid(), "host": self._host, "ts": iso_now()}).encode(),
        )
        os.fsync(fd)
        return _Held(fd, path)

    def _read_holder(self, path: Path) -> str:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return f"pid {data.get('pid')} on {data.get('host')} since {data.get('ts')}"
        except (OSError, ValueError):
            return "another process"

    def _release(self, held: _Held) -> None:
        # Do NOT unlink: unlinking a flock'd path races a waiter that already
        # opened the same name onto a now-dead inode. The kernel drops the lock
        # on close; the (tiny, bounded, reused) lock file is left in place.
        try:
            if _HAVE_FLOCK:
                fcntl.flock(held.fd, fcntl.LOCK_UN)
        finally:
            os.close(held.fd)

    @contextmanager
    def repo_lock(self) -> Iterator[None]:
        held = self._acquire(REPO_LOCK)
        try:
            yield
        finally:
            self._release(held)

    @contextmanager
    def file_lock(self, relpath: str) -> Iterator[None]:
        held = self._acquire(_slug(relpath))
        try:
            yield
        finally:
            self._release(held)

    # --- diagnostics -----------------------------------------------------
    def _is_held(self, path: Path) -> bool:
        """Kernel-truth liveness: can we flock it? If yes, nobody holds it."""
        if not _HAVE_FLOCK:  # pragma: no cover - Windows
            return path.exists()
        fd = os.open(path, os.O_RDWR)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.flock(fd, fcntl.LOCK_UN)
            return False
        except OSError:
            return True
        finally:
            os.close(fd)

    def list_locks(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        locks_dir = self._layout.locks
        if not locks_dir.exists():
            return out
        for path in sorted(locks_dir.iterdir()):
            if not path.is_file():
                continue
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                data = {}
            held = self._is_held(path)
            out.append(
                {
                    "name": path.name,
                    "pid": data.get("pid"),
                    "host": data.get("host"),
                    "held": held,
                    # "stale" == a leftover lock FILE that no process holds.
                    # With flock this is purely cosmetic; it never indicates a
                    # lock that could be wrongly broken.
                    "stale": not held,
                    "reason": "live" if held else "leftover file (not held)",
                }
            )
        return out

    def clear_stale(self) -> list[str]:
        """Remove leftover lock *files* that no process currently holds.

        This is cosmetic: an unheld flock file is harmless (the next acquirer
        simply reopens it). It can never remove a lock a live process holds,
        because :meth:`_is_held` asks the kernel, not a PID guess.
        """
        cleared: list[str] = []
        for info in self.list_locks():
            if not info["held"]:
                try:
                    (self._layout.locks / info["name"]).unlink()
                    cleared.append(info["name"])
                except FileNotFoundError:
                    pass
        return cleared
