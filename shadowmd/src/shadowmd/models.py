"""Immutable value objects (§14.1).

These mirror the on-disk JSON but are the typed currency the library passes
around. Persistence (index/snapshot modules) converts between these and dicts;
nothing else constructs the raw dicts by hand.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .hashing import split


@dataclass(frozen=True)
class BlobRef:
    algorithm: str
    digest: str

    @property
    def uri(self) -> str:
        return f"{self.algorithm}:{self.digest}"

    @classmethod
    def parse(cls, content_hash: str) -> BlobRef:
        algo, digest = split(content_hash)
        return cls(algorithm=algo, digest=digest)


@dataclass(frozen=True)
class ManagedFile:
    """One tracked file as it appears in the index or a snapshot manifest."""

    file_id: str
    path: str
    content_hash: str
    size: int
    readonly: bool = True
    last_snapshot: str | None = None
    previous_paths: tuple[str, ...] = ()
    # Permission mode the file had before injection, restored on eject (§7.1).
    original_mode: int | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "file_id": self.file_id,
            "path": self.path,
            "content_hash": self.content_hash,
            "size": self.size,
            "readonly": self.readonly,
        }
        if self.last_snapshot is not None:
            d["last_snapshot"] = self.last_snapshot
        if self.previous_paths:
            d["previous_paths"] = list(self.previous_paths)
        if self.original_mode is not None:
            d["original_mode"] = self.original_mode
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ManagedFile:
        return cls(
            file_id=d["file_id"],
            path=d["path"],
            content_hash=d["content_hash"],
            size=int(d.get("size", 0)),
            readonly=bool(d.get("readonly", True)),
            last_snapshot=d.get("last_snapshot"),
            previous_paths=tuple(d.get("previous_paths", ())),
            original_mode=d.get("original_mode"),
        )


@dataclass(frozen=True)
class Snapshot:
    id: str
    created_at: str
    parent: str | None
    message: str
    root: dict[str, ManagedFile] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "created_at": self.created_at,
            "parent": self.parent,
            "message": self.message,
            "root": {path: mf.to_dict() for path, mf in sorted(self.root.items())},
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Snapshot:
        return cls(
            id=d["id"],
            created_at=d["created_at"],
            parent=d.get("parent"),
            message=d.get("message", ""),
            root={p: ManagedFile.from_dict(v) for p, v in d.get("root", {}).items()},
        )
