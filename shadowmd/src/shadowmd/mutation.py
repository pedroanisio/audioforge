"""The single mutation primitive (§9.4).

Every write command — edit, append, prepend, replace, apply, absorb, the
per-file step of restore — is sugar over this one function. No command has its
own write path. The ordering here is the load-bearing part of the design:

    1. verify projection (abort on external drift)
    2. store the new blob (durable BEFORE the journal — write-ahead invariant)
    3. journal "intent"
    4. write the projection atomically (§9.3)
    5. rewrite the index atomically
    6. journal "commit"
    7. auto-snapshot (outside the file lock, honoring repo-before-file order)

A no-op write (content unchanged) records nothing at all.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .projection import verify_projection, write_projection_atomically

if TYPE_CHECKING:  # avoid an import cycle with repo.py
    from .repo import ShadowRepository


def mutate_file(
    repo: ShadowRepository,
    path: str,
    new_content: bytes,
    message: str,
    *,
    operation: str = "mutate",
) -> bool:
    """Apply ``new_content`` to ``path``. Returns True if anything changed."""
    changed = False
    with repo.locks.file_lock(path):
        mf = repo.index.get(path)                 # FileNotTracked if absent
        verify_projection(repo.layout, mf)        # ProjectionViolation on drift

        old_hash = mf.content_hash
        new_hash = repo.store.store(new_content)   # durable before journal

        if old_hash == new_hash:
            return False                           # no-op; nothing recorded

        # In a transaction, remember the pre-image so `abort` can roll back.
        if repo.in_transaction:
            repo.txn_record_touch(path, old_hash)

        entry = repo.journal.intent(
            operation=operation,
            path=path,
            old_hash=old_hash,
            new_hash=new_hash,
            message=message,
        )

        write_projection_atomically(repo.layout, path, new_content)  # §9.3

        repo.index.update_content(path, content_hash=new_hash, size=len(new_content))
        repo.index.write_atomically(repo.layout)

        repo.journal.commit(entry)
        changed = True

    # Snapshot outside the file lock so we never hold file-then-repo (the lock
    # hierarchy is repo-before-file; §9.1).
    if changed and repo.config.auto_snapshot and not repo.in_transaction:
        repo.snapshot(message)

    return changed
