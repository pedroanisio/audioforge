"""Permission enforcement (§3, §14.2).

Layer 1 of the enforcement model: ``chmod 0444`` is *accident protection*, not a
security boundary. The authoritative guarantee is projection-hash verification
(``projection.py`` + §11). This module deliberately does not pretend otherwise.

Layer 3 (strict mode) shells out to ``chattr +i`` on Linux and must verify both
privilege and filesystem support before claiming success — a failed strict
protect that reports success would be a lie about durability.
"""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
from pathlib import Path

from .atomicio import OWNER_RW_MODE, READONLY_MODE


def make_readonly(path: Path) -> None:
    path.chmod(READONLY_MODE)


def make_writable_by_owner(path: Path, mode: int | None = None) -> None:
    path.chmod(mode if mode is not None else OWNER_RW_MODE)


def is_readonly(path: Path) -> bool:
    return not bool(path.stat().st_mode & stat.S_IWUSR)


def current_mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


# --- Layer 3: strict immutability (opt-in, Linux only) -------------------

class StrictProtectionError(RuntimeError):
    """Strict protection could not be applied/removed and did NOT silently pass."""


def strict_supported() -> bool:
    return os.name == "posix" and shutil.which("chattr") is not None


def _run_chattr(flag: str, path: Path) -> None:
    if not strict_supported():
        raise StrictProtectionError(
            "strict mode requires `chattr` (Linux ext4/xfs/btrfs); not available here"
        )
    try:
        subprocess.run(
            ["chattr", flag, str(path)],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        raise StrictProtectionError(
            f"chattr {flag} {path} failed (needs CAP_LINUX_IMMUTABLE / root and a "
            f"supporting filesystem): {exc.stderr.strip() or exc}"
        ) from exc


def set_immutable(path: Path) -> None:
    _run_chattr("+i", path)


def clear_immutable(path: Path) -> None:
    _run_chattr("-i", path)
