from __future__ import annotations

import pytest

from shadowmd.errors import TransactionError


def test_transaction_groups_into_one_snapshot(injected, write_file):
    write_file("b.md", "b\n")
    injected.inject("b.md")
    before = len(injected.snapshots.list())

    injected.begin("restructure")
    injected.append("article.md", "x")
    injected.append("b.md", "y")
    assert injected.in_transaction
    snap = injected.commit()

    assert len(injected.snapshots.list()) == before + 1
    assert snap.id == injected.snapshots.head_snapshot_id()
    assert not injected.in_transaction


def test_abort_rolls_back_touched_files(injected, workdir):
    original = (workdir / "article.md").read_text()
    injected.begin("risky")
    injected.append("article.md", "DANGER")
    assert "DANGER" in (workdir / "article.md").read_text()
    injected.abort()
    assert (workdir / "article.md").read_text() == original
    assert not injected.in_transaction


def test_double_begin_rejected(injected):
    injected.begin("one")
    with pytest.raises(TransactionError):
        injected.begin("two")
    injected.abort()


def test_commit_without_begin(injected):
    with pytest.raises(TransactionError):
        injected.commit()
