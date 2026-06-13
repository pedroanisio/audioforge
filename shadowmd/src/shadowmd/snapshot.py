"""Snapshot creation, refs and HEAD (§4.4, §4.5, §5.2, §10).

Snapshots are immutable full manifests of all managed files (content is
deduplicated through blobs, so a full manifest costs only metadata). Restore is
therefore a single materialization — no chain replay. Invariant 4: a snapshot is
never modified after creation; restores only ever create new snapshots.

Refs are mutable named pointers to immutable snapshots:

    refs/main -> snap_...           (a snapshot id)
    HEAD      -> ref: refs/main     (a symbolic ref)
"""

from __future__ import annotations

from .atomicio import OWNER_RW_MODE, atomic_write_bytes
from .errors import SnapshotNotFound
from .ids import iso_now, new_snapshot_id
from .index import Index
from .jsonio import dumps, load_file
from .layout import Layout
from .models import ManagedFile, Snapshot

DEFAULT_BRANCH = "main"
_HEAD_PREFIX = "ref: "


class SnapshotManager:
    def __init__(self, layout: Layout) -> None:
        self._layout = layout

    # --- HEAD / refs -----------------------------------------------------
    def _read_head_ref(self) -> str:
        head = self._layout.head
        if not head.exists():
            return f"refs/{DEFAULT_BRANCH}"
        text = head.read_text(encoding="utf-8").strip()
        if text.startswith(_HEAD_PREFIX):
            return text[len(_HEAD_PREFIX):].strip()
        return text  # tolerate a bare ref path

    def _write_head_ref(self, ref: str) -> None:
        atomic_write_bytes(
            self._layout.head,
            f"{_HEAD_PREFIX}{ref}\n".encode(),
            tmp_dir=self._layout.tmp,
            mode=OWNER_RW_MODE,
        )

    def current_branch(self) -> str:
        ref = self._read_head_ref()
        return ref.split("/", 1)[1] if ref.startswith("refs/") else ref

    def head_snapshot_id(self) -> str | None:
        ref_path = self._layout.control / self._read_head_ref()
        if not ref_path.exists():
            return None
        sid = ref_path.read_text(encoding="utf-8").strip()
        return sid or None

    def _advance_head(self, snapshot_id: str) -> None:
        ref = self._read_head_ref()
        ref_path = self._layout.control / ref
        atomic_write_bytes(
            ref_path,
            f"{snapshot_id}\n".encode(),
            tmp_dir=self._layout.tmp,
            mode=OWNER_RW_MODE,
        )
        # Ensure HEAD is materialized (first snapshot in a fresh repo).
        if not self._layout.head.exists():
            self._write_head_ref(ref)

    # --- create ----------------------------------------------------------
    def create(self, index: Index, message: str) -> Snapshot:
        parent = self.head_snapshot_id()
        snapshot_id = new_snapshot_id()
        root: dict[str, ManagedFile] = {
            mf.path: ManagedFile(
                file_id=mf.file_id,
                path=mf.path,
                content_hash=mf.content_hash,
                size=mf.size,
                readonly=mf.readonly,
                previous_paths=mf.previous_paths,
            )
            for mf in index
        }
        snap = Snapshot(
            id=snapshot_id,
            created_at=iso_now(),
            parent=parent,
            message=message,
            root=root,
        )
        # Immutable object: write 0444, then point the branch at it last so a
        # crash never leaves HEAD referencing a half-written manifest.
        atomic_write_bytes(
            self._layout.snapshot_file(snapshot_id),
            dumps(snap.to_dict()),
            tmp_dir=self._layout.tmp,
            mode=0o444,
        )
        self._advance_head(snapshot_id)
        index.set_last_snapshot(snapshot_id)
        return snap

    # --- read ------------------------------------------------------------
    def load(self, snapshot_id: str) -> Snapshot:
        path = self._layout.snapshot_file(snapshot_id)
        if not path.exists():
            raise SnapshotNotFound(f"snapshot not found: {snapshot_id}")
        return Snapshot.from_dict(load_file(path))

    def list(self) -> list[Snapshot]:
        snaps_dir = self._layout.snapshots
        if not snaps_dir.exists():
            return []
        snaps = [
            Snapshot.from_dict(load_file(p))
            for p in snaps_dir.glob("*.json")
        ]
        # Compact-timestamp ids sort chronologically by prefix; created_at
        # breaks ties deterministically.
        snaps.sort(key=lambda s: (s.created_at, s.id))
        return snaps

    def resolve(self, selector: str) -> str:
        """Resolve an exact id, ``HEAD``, or a unique id prefix to a full id."""
        if selector == "HEAD":
            sid = self.head_snapshot_id()
            if sid is None:
                raise SnapshotNotFound("HEAD does not point at any snapshot yet")
            return sid
        if self._layout.snapshot_file(selector).exists():
            return selector
        matches = [s.id for s in self.list() if s.id.startswith(selector)]
        if len(matches) == 1:
            return matches[0]
        if not matches:
            raise SnapshotNotFound(f"no snapshot matches {selector!r}")
        raise SnapshotNotFound(
            f"ambiguous snapshot selector {selector!r}: {', '.join(sorted(matches))}"
        )
