"""The working projection index (§4.2).

The index is the *current* mapping path -> ManagedFile. It is mutable state and
is rewritten atomically (write to tmp, fsync, os.replace) exactly like a
projected file — a torn index is as dangerous as a torn projection.

There is one expected hash per file (``content_hash``). The v1 ``projection_hash``
field was redundant (always equal, verified against the same physical file) and
is intentionally absent.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from .atomicio import OWNER_RW_MODE, atomic_write_bytes
from .errors import FileAlreadyTracked, FileNotTracked
from .jsonio import dumps, load_file
from .layout import Layout
from .models import ManagedFile

INDEX_VERSION = 1


class Index:
    def __init__(self, files: dict[str, ManagedFile] | None = None) -> None:
        self._files: dict[str, ManagedFile] = dict(files or {})

    # --- persistence -----------------------------------------------------
    @classmethod
    def load(cls, layout: Layout) -> Index:
        if not layout.index.exists():
            return cls()
        data = load_file(layout.index)
        files = {p: ManagedFile.from_dict(v) for p, v in data.get("files", {}).items()}
        return cls(files)

    def write_atomically(self, layout: Layout) -> None:
        payload: dict[str, Any] = {
            "version": INDEX_VERSION,
            "files": {p: mf.to_dict() for p, mf in sorted(self._files.items())},
        }
        atomic_write_bytes(
            layout.index, dumps(payload), tmp_dir=layout.tmp, mode=OWNER_RW_MODE
        )

    # --- queries ---------------------------------------------------------
    def __contains__(self, path: str) -> bool:
        return path in self._files

    def __iter__(self) -> Iterator[ManagedFile]:
        return iter(self._files.values())

    def __len__(self) -> int:
        return len(self._files)

    def paths(self) -> list[str]:
        return sorted(self._files)

    def get(self, path: str) -> ManagedFile:
        try:
            return self._files[path]
        except KeyError:
            raise FileNotTracked(f"{path} is not tracked by ShadowMD") from None

    def find_by_id(self, file_id: str) -> ManagedFile | None:
        for mf in self._files.values():
            if mf.file_id == file_id:
                return mf
        return None

    def managed_files(self) -> dict[str, ManagedFile]:
        return dict(self._files)

    # --- mutations (in-memory; caller persists via write_atomically) -----
    def add(self, mf: ManagedFile) -> None:
        if mf.path in self._files:
            raise FileAlreadyTracked(f"{mf.path} is already tracked")
        self._files[mf.path] = mf

    def replace(self, mf: ManagedFile) -> None:
        self._files[mf.path] = mf

    def remove(self, path: str) -> ManagedFile:
        try:
            return self._files.pop(path)
        except KeyError:
            raise FileNotTracked(f"{path} is not tracked by ShadowMD") from None

    def update_content(
        self, path: str, content_hash: str, size: int, last_snapshot: str | None = None
    ) -> ManagedFile:
        mf = self.get(path)
        updated = ManagedFile(
            file_id=mf.file_id,
            path=mf.path,
            content_hash=content_hash,
            size=size,
            readonly=mf.readonly,
            last_snapshot=last_snapshot if last_snapshot is not None else mf.last_snapshot,
            previous_paths=mf.previous_paths,
            original_mode=mf.original_mode,
        )
        self._files[path] = updated
        return updated

    def rename(self, old_path: str, new_path: str) -> ManagedFile:
        if new_path in self._files:
            raise FileAlreadyTracked(f"{new_path} is already tracked")
        mf = self.remove(old_path)
        moved = ManagedFile(
            file_id=mf.file_id,
            path=new_path,
            content_hash=mf.content_hash,
            size=mf.size,
            readonly=mf.readonly,
            last_snapshot=mf.last_snapshot,
            previous_paths=(*mf.previous_paths, old_path),
            original_mode=mf.original_mode,
        )
        self._files[new_path] = moved
        return moved

    def set_last_snapshot(self, snapshot_id: str) -> None:
        for path, mf in list(self._files.items()):
            self._files[path] = ManagedFile(
                file_id=mf.file_id,
                path=mf.path,
                content_hash=mf.content_hash,
                size=mf.size,
                readonly=mf.readonly,
                last_snapshot=snapshot_id,
                previous_paths=mf.previous_paths,
                original_mode=mf.original_mode,
            )
