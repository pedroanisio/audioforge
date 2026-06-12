"""Content hashing — the single source of truth for what a "hash" looks like.

ShadowMD addresses content by ``sha256:<hex>``. The algorithm prefix is kept in
the string everywhere (index, snapshots, journal, blob refs) so the format is
self-describing and a future migration to another algorithm is a data question,
not a code-wide find-and-replace.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

ALGORITHM = "sha256"


def hash_bytes(data: bytes) -> str:
    """Return ``sha256:<hex>`` for ``data``."""
    return f"{ALGORITHM}:{hashlib.sha256(data).hexdigest()}"


def hash_file(path: Path) -> str:
    """Stream-hash a file so large projections do not load fully into memory."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return f"{ALGORITHM}:{h.hexdigest()}"


def split(content_hash: str) -> tuple[str, str]:
    """Split ``sha256:abcdef...`` into ``("sha256", "abcdef...")``."""
    algo, _, digest = content_hash.partition(":")
    if not digest:
        raise ValueError(f"malformed content hash: {content_hash!r}")
    return algo, digest
