"""Content-addressed blob store (§4.3, §5.1).

Blobs are immutable full-content objects addressed by ``sha256:<hex>`` and laid
out with Git/Nix-style fan-out::

    .shadowmd/blobs/sha256/ab/cdef...

Writing a blob is atomic and idempotent: if the target already exists the
content is identical by construction (content addressing), so the write is
skipped. Blobs are stored 0444 — immutability is the contract (invariant 3).
"""

from __future__ import annotations

from pathlib import Path

from .atomicio import READONLY_MODE, atomic_write_bytes
from .errors import ShadowError
from .hashing import hash_bytes, split
from .layout import Layout


class BlobStore:
    def __init__(self, layout: Layout) -> None:
        self._layout = layout

    def _path_for(self, content_hash: str) -> Path:
        algo, digest = split(content_hash)
        return self._layout.blobs / algo / digest[:2] / digest[2:]

    def has(self, content_hash: str) -> bool:
        return self._path_for(content_hash).exists()

    def store(self, content: bytes) -> str:
        """Store ``content``, returning its ``sha256:<hex>`` address."""
        content_hash = hash_bytes(content)
        target = self._path_for(content_hash)
        if target.exists():
            return content_hash  # idempotent: identical content by construction
        atomic_write_bytes(
            target, content, tmp_dir=self._layout.tmp, mode=READONLY_MODE
        )
        return content_hash

    def read(self, content_hash: str) -> bytes:
        target = self._path_for(content_hash)
        if not target.exists():
            raise ShadowError(f"blob not found: {content_hash}")
        return target.read_bytes()

    def iter_hashes(self) -> list[str]:
        """All blob addresses currently present (used by gc/fsck)."""
        out: list[str] = []
        root = self._layout.blobs
        if not root.exists():
            return out
        for algo_dir in root.iterdir():
            if not algo_dir.is_dir():
                continue
            algo = algo_dir.name
            for prefix_dir in algo_dir.iterdir():
                if not prefix_dir.is_dir():
                    continue
                for obj in prefix_dir.iterdir():
                    if obj.is_file():
                        out.append(f"{algo}:{prefix_dir.name}{obj.name}")
        return out

    def remove(self, content_hash: str) -> None:
        """Delete a blob (gc only). Tolerates already-absent blobs."""
        target = self._path_for(content_hash)
        try:
            target.chmod(0o644)  # readonly blobs need a writable bit to unlink on some FS
        except OSError:
            pass
        try:
            target.unlink()
        except FileNotFoundError:
            pass
