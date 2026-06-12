"""Garbage collection (§13.1).

Reclaims blobs that are unreachable from any snapshot manifest or the current
index. Snapshots themselves are treated as roots in the MVP — gc never deletes
history, only orphaned content objects (e.g. blobs left by an ``absorb`` that
was later superseded and never snapshotted, or intermediate edits in manual
mode that were never captured).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .repo import ShadowRepository


@dataclass
class GCResult:
    reachable: int
    removed: list[str]
    kept: int

    @property
    def removed_count(self) -> int:
        return len(self.removed)


def reachable_hashes(repo: ShadowRepository) -> set[str]:
    reachable: set[str] = {mf.content_hash for mf in repo.index}
    for snap in repo.snapshots.list():
        for mf in snap.root.values():
            reachable.add(mf.content_hash)
    return reachable


def collect(repo: ShadowRepository, *, dry_run: bool = False) -> GCResult:
    with repo.repo_locked():
        reachable = reachable_hashes(repo)
        present = set(repo.store.iter_hashes())
        orphans = sorted(present - reachable)
        if not dry_run:
            for h in orphans:
                repo.store.remove(h)
            repo.journal.marker("gc", message=f"removed {len(orphans)} orphan blob(s)")
        return GCResult(
            reachable=len(reachable),
            removed=orphans,
            kept=len(present) - len(orphans),
        )
