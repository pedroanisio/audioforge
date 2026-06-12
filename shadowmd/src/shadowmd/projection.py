"""Atomic read-only file projection + integrity verification (§9.3, §11).

The projected file in the working tree is a read-only view of canonical state.
Two responsibilities live here:

* ``write_projection_atomically`` — replace the visible file's content via the
  atomic recipe, leaving it 0444. On POSIX the target is *never* made writable,
  not even briefly (§9.3 correction to v1).
* ``verify_projection`` — assert ``sha256(visible file) == index hash`` before
  any mutation. This is the authoritative guarantee (§3.2): an external write
  cannot be silently absorbed into history.
"""

from __future__ import annotations

from pathlib import Path

from .atomicio import READONLY_MODE, atomic_write_bytes
from .errors import ProjectionViolation
from .hashing import hash_file
from .layout import Layout
from .models import ManagedFile


def write_projection_atomically(layout: Layout, relpath: str, content: bytes) -> None:
    target = layout.root / relpath
    atomic_write_bytes(target, content, tmp_dir=layout.tmp, mode=READONLY_MODE)


def projection_hash(layout: Layout, relpath: str) -> str:
    return hash_file(layout.root / relpath)


def verify_projection(layout: Layout, mf: ManagedFile) -> None:
    """Raise :class:`ProjectionViolation` if the visible file drifted."""
    target: Path = layout.root / mf.path
    if not target.exists():
        raise ProjectionViolation(mf.path, mf.content_hash, "sha256:<missing file>")
    actual = hash_file(target)
    if actual != mf.content_hash:
        raise ProjectionViolation(mf.path, mf.content_hash, actual)
