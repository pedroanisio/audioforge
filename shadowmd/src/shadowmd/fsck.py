"""Integrity verification + write-ahead journal recovery (§9.2, §11).

``fsck`` answers two questions:

1. Is the visible tree consistent with the index, and is every referenced blob
   present? (integrity)
2. Was an operation interrupted between its ``intent`` and ``commit`` journal
   entries, and if so, can it be resolved? (recovery)

Recovery uses the rule from §9.2. The new blob is durable before the intent
entry, so both branches always have the content they need:

* intent without commit, projection hash == old hash  -> roll back (abort entry)
* intent without commit, projection hash == new hash  -> roll forward (redo
  index update, append commit)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from .hashing import hash_file

if TYPE_CHECKING:
    from .repo import ShadowRepository


@dataclass
class FsckReport:
    drift: list[str] = field(default_factory=list)          # files modified outside CLI
    missing_files: list[str] = field(default_factory=list)  # tracked but absent
    missing_blobs: list[str] = field(default_factory=list)  # referenced but absent
    rolled_forward: list[int] = field(default_factory=list)  # journal seqs
    rolled_back: list[int] = field(default_factory=list)
    unresolved: list[int] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not (
            self.drift
            or self.missing_files
            or self.missing_blobs
            or self.unresolved
        )


def check(repo: ShadowRepository, *, repair_journal: bool = True) -> FsckReport:
    report = FsckReport()
    with repo.repo_locked():
        _check_integrity(repo, report)
        _recover_journal(repo, report, repair_journal)
    return report


def _check_integrity(repo: ShadowRepository, report: FsckReport) -> None:
    for mf in repo.index:
        target = repo.layout.root / mf.path
        if not target.exists():
            report.missing_files.append(mf.path)
        elif hash_file(target) != mf.content_hash:
            report.drift.append(mf.path)
        if not repo.store.has(mf.content_hash):
            report.missing_blobs.append(mf.content_hash)


def _recover_journal(repo: ShadowRepository, report: FsckReport, repair: bool) -> None:
    for entry in repo.journal.unpaired_intents():
        seq = int(entry.get("seq", -1))
        path = entry.get("path")
        old_hash = entry.get("old_hash")
        new_hash = entry.get("new_hash")
        target = repo.layout.root / path if path else None

        # Operations without a content target (markers/structural) cannot be
        # auto-resolved by hash; report them as unresolved for human review.
        if path is None or target is None or not target.exists():
            report.unresolved.append(seq)
            continue

        actual = hash_file(target)
        if actual == new_hash:
            # Roll forward: the projection already advanced; finish the record.
            if repair:
                if path in repo.index and new_hash is not None:
                    size = target.stat().st_size
                    repo.index.update_content(path, content_hash=new_hash, size=size)
                    repo.index.write_atomically(repo.layout)
                repo.journal.commit(entry)
            report.rolled_forward.append(seq)
        elif actual == old_hash:
            # Roll back: nothing happened visibly; mark the intent aborted.
            if repair:
                repo.journal.marker("fsck-rollback", message=f"aborted seq {seq} on {path}")
            report.rolled_back.append(seq)
        else:
            report.unresolved.append(seq)
