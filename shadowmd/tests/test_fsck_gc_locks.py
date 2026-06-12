from __future__ import annotations

import json

import pytest

from shadowmd import fsck as fsckmod
from shadowmd import gc as gcmod
from shadowmd.errors import LockError
from shadowmd.hashing import hash_bytes
from shadowmd.locks import LockManager
from shadowmd.projection import write_projection_atomically


def test_fsck_clean_repo(injected):
    report = fsckmod.check(injected)
    assert report.ok


def test_fsck_detects_drift(injected, workdir):
    target = workdir / "article.md"
    target.chmod(0o644)
    target.write_text("tampered\n")
    report = fsckmod.check(injected)
    assert "article.md" in report.drift
    assert not report.ok


def test_fsck_rolls_forward_interrupted_op(injected, workdir):
    # Simulate a crash AFTER the projection was written but BEFORE the index
    # update + commit (intent present, no commit, projection == new_hash).
    mf = injected.index.get("article.md")
    old_hash = mf.content_hash
    new_content = b"rolled forward content\n"
    new_hash = injected.store.store(new_content)
    injected.journal.intent(
        operation="mutate", path="article.md",
        old_hash=old_hash, new_hash=new_hash, message="interrupted",
    )
    write_projection_atomically(injected.layout, "article.md", new_content)

    report = fsckmod.check(injected)
    assert report.rolled_forward
    # index now reflects the new hash and a commit was appended
    assert injected.index.get("article.md").content_hash == new_hash
    assert any(e.get("phase") == "commit" for e in injected.journal.read_all())


def test_fsck_rolls_back_interrupted_op(injected):
    # Intent present but projection still == old_hash (crash before projection
    # write) -> roll back.
    mf = injected.index.get("article.md")
    new_hash = hash_bytes(b"never written\n")
    injected.store.store(b"never written\n")
    injected.journal.intent(
        operation="mutate", path="article.md",
        old_hash=mf.content_hash, new_hash=new_hash, message="interrupted",
    )
    report = fsckmod.check(injected)
    assert report.rolled_back


def test_gc_removes_orphan_blob(injected):
    orphan = injected.store.store(b"orphaned content never snapshotted\n")
    assert injected.store.has(orphan)
    result = gcmod.collect(injected)
    assert orphan in result.removed
    assert not injected.store.has(orphan)


def test_gc_keeps_reachable(injected):
    reachable = injected.index.get("article.md").content_hash
    gcmod.collect(injected)
    assert injected.store.has(reachable)


def test_gc_dry_run_keeps_blob(injected):
    orphan = injected.store.store(b"orphan\n")
    result = gcmod.collect(injected, dry_run=True)
    assert orphan in result.removed
    assert injected.store.has(orphan)  # dry run did not delete


def test_lock_contention(repo):
    lm = LockManager(repo.layout)
    with lm.repo_lock(), pytest.raises(LockError), LockManager(repo.layout).repo_lock():
        pass


def test_stale_lock_cleared(repo):
    lm = LockManager(repo.layout, staleness_seconds=0)
    lock = repo.layout.locks / "repo.lock"
    lock.write_text(json.dumps({"pid": 2_000_000, "host": lm._host, "ts": "x"}))
    stale = [info for info in lm.list_locks() if info["stale"]]
    assert stale
    cleared = lm.clear_stale()
    assert "repo.lock" in cleared
    assert not lock.exists()
