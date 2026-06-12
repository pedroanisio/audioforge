"""Repo/file lock hierarchy with stale-lock detection (§9.1).

Two lock levels, acquired in a fixed order to prevent deadlock:

    repo lock  — held by snapshot, restore, gc, fsck
    file lock  — held per managed file by any mutation
    order      — repo lock (if needed) before file lock; never the reverse

Locks are files created with ``O_CREAT | O_EXCL`` in ``.shadowmd/locks/``,
containing pid + hostname + timestamp. ``O_EXCL`` creation is atomic on POSIX
local filesystems; network-filesystem semantics are out of scope (documented
limitation — this is a local-first tool).
"""

from __future__ import annotations

import json
import os
import socket
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from .errors import LockError
from .ids import iso_now
from .layout import Layout

REPO_LOCK = "repo.lock"


def _slug(name: str) -> str:
    """Map a file path to a safe single lock filename."""
    return "file__" + name.replace(os.sep, "_").replace("/", "_") + ".lock"


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # exists but owned by another user
    except OSError:
        return False
    return True


class LockManager:
    def __init__(self, layout: Layout, staleness_seconds: int = 3600) -> None:
        self._layout = layout
        self._host = socket.gethostname()
        self._staleness = staleness_seconds

    def _lock_path(self, name: str) -> Path:
        return self._layout.locks / name

    def _acquire(self, name: str) -> Path:
        path = self._lock_path(name)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(
            {"pid": os.getpid(), "host": self._host, "ts": iso_now()}
        ).encode("utf-8")
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        except FileExistsError:
            holder = self._read_holder(path)
            raise LockError(
                f"could not acquire lock {name!r}; held by {holder}. "
                f"If stale, run `shadowmd unlock --stale`."
            ) from None
        try:
            os.write(fd, payload)
            os.fsync(fd)
        finally:
            os.close(fd)
        return path

    def _read_holder(self, path: Path) -> str:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return f"pid {data.get('pid')} on {data.get('host')} since {data.get('ts')}"
        except (OSError, ValueError):
            return "an unknown process"

    @staticmethod
    def _release(path: Path) -> None:
        try:
            path.unlink()
        except FileNotFoundError:
            pass

    @contextmanager
    def repo_lock(self) -> Iterator[None]:
        path = self._acquire(REPO_LOCK)
        try:
            yield
        finally:
            self._release(path)

    @contextmanager
    def file_lock(self, relpath: str) -> Iterator[None]:
        path = self._acquire(_slug(relpath))
        try:
            yield
        finally:
            self._release(path)

    # --- stale-lock inspection / clearing (status, unlock --stale) -------
    def list_locks(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        locks_dir = self._layout.locks
        if not locks_dir.exists():
            return out
        now = time.time()
        for path in sorted(locks_dir.iterdir()):
            if not path.is_file():
                continue
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                data = {}
            host = data.get("host")
            pid = data.get("pid", -1)
            age = now - path.stat().st_mtime
            same_host = host == self._host
            dead = same_host and not _pid_alive(int(pid)) if isinstance(pid, int) else False
            stale = dead or age > self._staleness
            out.append(
                {
                    "name": path.name,
                    "pid": pid,
                    "host": host,
                    "age_seconds": round(age, 1),
                    "same_host": same_host,
                    "stale": stale,
                    "reason": "dead pid" if dead else ("age" if stale else "live"),
                }
            )
        return out

    def clear_stale(self) -> list[str]:
        cleared: list[str] = []
        for info in self.list_locks():
            if info["stale"]:
                self._release(self._layout.locks / info["name"])
                cleared.append(info["name"])
        return cleared
