"""Restore — forward-recorded, never a history rewind (§10.2).

Restoring writes the restored content through the canonical write path and then
creates a **new** snapshot whose manifest equals (in whole or part) the old one,
with a provenance message. ``HEAD`` only ever advances. This preserves invariant
4 (no snapshot is modified or orphaned) and makes an accidental restore itself
undoable — Time Machine semantics, not ``git reset --hard``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .errors import ShadowError
from .models import ManagedFile, Snapshot
from .mutation import mutate_file
from .projection import write_projection_atomically

if TYPE_CHECKING:
    from .repo import ShadowRepository


def _restore_one(repo: ShadowRepository, target_path: str, mf: ManagedFile, source: str) -> None:
    content = repo.store.read(mf.content_hash)
    if target_path in repo.index:
        # Tracked: go through the primitive (verifies, journals, indexes).
        mutate_file(
            repo,
            target_path,
            content,
            f"restore {target_path} from {source}",
            operation="restore",
        )
        return
    # The file was removed/ejected since the snapshot: re-materialize it,
    # preserving its original file_id so the timeline stays continuous.
    entry = repo.journal.intent(
        operation="restore",
        path=target_path,
        old_hash=None,
        new_hash=mf.content_hash,
        message=f"restore (recreate) {target_path} from {source}",
    )
    write_projection_atomically(repo.layout, target_path, content)
    repo.index.add(
        ManagedFile(
            file_id=mf.file_id,
            path=target_path,
            content_hash=mf.content_hash,
            size=mf.size,
            readonly=True,
            previous_paths=mf.previous_paths,
            original_mode=None,  # unknown for a re-materialized file; eject falls back to 0644
        )
    )
    repo.index.write_atomically(repo.layout)
    repo.journal.commit(entry)


def restore(repo: ShadowRepository, snapshot_id: str, path: str | None = None) -> Snapshot:
    resolved = repo.snapshots.resolve(snapshot_id)
    snap = repo.snapshots.load(resolved)

    if path is not None:
        if path not in snap.root:
            raise ShadowError(f"{path} does not exist in snapshot {resolved}")
        targets = {path: snap.root[path]}
        message = f"restored {path} from {resolved}"
    else:
        targets = dict(snap.root)
        message = f"restored from {resolved}"

    with repo.repo_locked():
        with repo.suppress_autosnapshot():
            for target_path, mf in targets.items():
                _restore_one(repo, target_path, mf, resolved)
        # One provenance snapshot for the whole restore, even if every file was
        # already identical (the snapshot still records the restore event).
        return repo._snapshot_locked(message)
