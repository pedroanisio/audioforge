"""Repository configuration (§4.1).

``tracked_extensions`` is the only Markdown-specific knob in the whole system.
Default it to ``[".md"]`` and ShadowMD is a Markdown tool; widen it and the
exact same machinery manages any text files — this is the seam that lets
ShadowMD become a general overlay tool without a rewrite.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from . import ids
from .atomicio import OWNER_RW_MODE, atomic_write_bytes
from .jsonio import dumps, load_file
from .layout import Layout

CONFIG_VERSION = 1


@dataclass
class Config:
    version: int = CONFIG_VERSION
    tracked_extensions: list[str] = field(default_factory=lambda: [".md"])
    readonly_projection: bool = True
    mutation_mode: str = "cli-only"
    auto_snapshot: bool = True
    created_at: str = field(default_factory=ids.iso_now)
    # Locks older than this (seconds) are reported stale by `status` (§9.1).
    lock_staleness_seconds: int = 3600

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "tracked_extensions": list(self.tracked_extensions),
            "readonly_projection": self.readonly_projection,
            "mutation_mode": self.mutation_mode,
            "auto_snapshot": self.auto_snapshot,
            "created_at": self.created_at,
            "lock_staleness_seconds": self.lock_staleness_seconds,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Config:
        return cls(
            version=int(d.get("version", CONFIG_VERSION)),
            tracked_extensions=list(d.get("tracked_extensions", [".md"])),
            readonly_projection=bool(d.get("readonly_projection", True)),
            mutation_mode=d.get("mutation_mode", "cli-only"),
            auto_snapshot=bool(d.get("auto_snapshot", True)),
            created_at=d.get("created_at", ids.iso_now()),
            lock_staleness_seconds=int(d.get("lock_staleness_seconds", 3600)),
        )

    @classmethod
    def load(cls, layout: Layout) -> Config:
        return cls.from_dict(load_file(layout.config))

    def save(self, layout: Layout) -> None:
        atomic_write_bytes(
            layout.config, dumps(self.to_dict()), tmp_dir=layout.tmp, mode=OWNER_RW_MODE
        )

    def tracks(self, relpath: str) -> bool:
        return any(relpath.endswith(ext) for ext in self.tracked_extensions)
