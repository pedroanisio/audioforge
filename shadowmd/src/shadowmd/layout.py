"""The on-disk layout of a ``.shadowmd`` control directory (§4).

A single object that resolves every path inside the store. Every other module
asks ``Layout`` for paths instead of hard-coding strings, so the directory
schema has exactly one definition.
"""

from __future__ import annotations

from pathlib import Path

CONTROL_DIRNAME = ".shadowmd"


class Layout:
    def __init__(self, root: Path) -> None:
        #: project root — the directory that *contains* ``.shadowmd``
        self.root = Path(root)
        #: the control directory itself
        self.control = self.root / CONTROL_DIRNAME

    # --- top-level files -------------------------------------------------
    @property
    def config(self) -> Path:
        return self.control / "config.json"

    @property
    def index(self) -> Path:
        return self.control / "index.json"

    @property
    def head(self) -> Path:
        return self.control / "HEAD"

    @property
    def txn(self) -> Path:
        # Transaction marker for begin/commit/abort (§10.1). Present iff a
        # group is open; persists across CLI processes.
        return self.control / "TXN.json"

    # --- directories -----------------------------------------------------
    @property
    def refs(self) -> Path:
        return self.control / "refs"

    @property
    def snapshots(self) -> Path:
        return self.control / "snapshots"

    @property
    def blobs(self) -> Path:
        return self.control / "blobs"

    @property
    def locks(self) -> Path:
        return self.control / "locks"

    @property
    def journal(self) -> Path:
        return self.control / "journal"

    @property
    def tmp(self) -> Path:
        return self.control / "tmp"

    # --- derived paths ---------------------------------------------------
    def ref(self, name: str) -> Path:
        return self.refs / name

    def snapshot_file(self, snapshot_id: str) -> Path:
        return self.snapshots / f"{snapshot_id}.json"

    def journal_log(self) -> Path:
        return self.journal / "log.ndjson"

    def all_dirs(self) -> list[Path]:
        return [
            self.control,
            self.refs,
            self.snapshots,
            self.blobs,
            self.locks,
            self.journal,
            self.tmp,
        ]
