from __future__ import annotations

import pytest

from shadowmd import protection
from shadowmd.errors import FileAlreadyTracked, FileNotTracked, ShadowError


def test_init_creates_layout(repo):
    for d in repo.layout.all_dirs():
        assert d.is_dir()
    assert repo.layout.config.is_file()
    assert repo.layout.index.is_file()


def test_inject_makes_readonly_and_tracks(injected, workdir):
    target = workdir / "article.md"
    assert protection.is_readonly(target)
    mf = injected.index.get("article.md")
    assert mf.file_id.startswith("f_")
    assert injected.store.has(mf.content_hash)
    # initial snapshot exists
    assert injected.snapshots.head_snapshot_id() is not None


def test_inject_twice_rejected(injected):
    with pytest.raises(FileAlreadyTracked):
        injected.inject("article.md")


def test_inject_missing_file(repo):
    with pytest.raises(ShadowError):
        repo.inject("nope.md")


def test_append_changes_content_and_snapshots(injected, workdir):
    before = len(injected.snapshots.list())
    changed = injected.append("article.md", "Another paragraph.")
    assert changed
    text = (workdir / "article.md").read_text()
    assert text.endswith("Another paragraph.\n")
    assert len(injected.snapshots.list()) == before + 1


def test_prepend(injected, workdir):
    injected.prepend("article.md", "TOP")
    assert (workdir / "article.md").read_text().startswith("TOP\n")


def test_noop_mutation_records_nothing(injected):
    before = len(injected.snapshots.list())
    same = injected.current_content("article.md")
    changed = injected.replace("article.md", same)
    assert changed is False
    assert len(injected.snapshots.list()) == before


def test_mutate_untracked_raises(repo, write_file):
    write_file("x.md", "hi")
    with pytest.raises(FileNotTracked):
        repo.append("x.md", "more")


def test_projection_stays_readonly_after_mutation(injected, workdir):
    injected.append("article.md", "x")
    assert protection.is_readonly(workdir / "article.md")


def test_eject_restores_writable_and_keeps_history(injected, workdir):
    mf = injected.index.get("article.md")
    blob = mf.content_hash
    injected.eject("article.md")
    assert "article.md" not in injected.index
    assert not protection.is_readonly(workdir / "article.md")
    assert injected.store.has(blob)  # history retained
