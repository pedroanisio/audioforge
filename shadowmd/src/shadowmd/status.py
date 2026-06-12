"""Repository status (§12.1).

Gathers a structured snapshot of repo health: branch/HEAD, tracked files with
per-file drift, any open transaction, and stale locks. The CLI renders it; this
module returns data so it is testable without parsing text.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from .hashing import hash_file

if TYPE_CHECKING:
    from .repo import ShadowRepository


@dataclass
class FileStatus:
    path: str
    file_id: str
    state: str  # "clean" | "drifted" | "missing"


@dataclass
class RepoStatus:
    branch: str
    head: str | None
    auto_snapshot: bool
    in_transaction: bool
    transaction_message: str | None
    files: list[FileStatus] = field(default_factory=list)
    stale_locks: list[dict[str, Any]] = field(default_factory=list)

    @property
    def drifted(self) -> list[FileStatus]:
        return [f for f in self.files if f.state != "clean"]


def gather(repo: ShadowRepository) -> RepoStatus:
    files: list[FileStatus] = []
    for mf in repo.index:
        target = repo.layout.root / mf.path
        if not target.exists():
            state = "missing"
        elif hash_file(target) != mf.content_hash:
            state = "drifted"
        else:
            state = "clean"
        files.append(FileStatus(path=mf.path, file_id=mf.file_id, state=state))

    txn_message = None
    if repo.layout.txn.exists():
        from .jsonio import load_file

        txn_message = load_file(repo.layout.txn).get("message")

    locks = [info for info in repo.locks.list_locks() if info["stale"]]

    return RepoStatus(
        branch=repo.snapshots.current_branch(),
        head=repo.snapshots.head_snapshot_id(),
        auto_snapshot=repo.config.auto_snapshot,
        in_transaction=repo.in_transaction,
        transaction_message=txn_message,
        files=sorted(files, key=lambda f: f.path),
        stale_locks=locks,
    )
