from __future__ import annotations

from shadowmd import restore as restoremod


def test_restore_is_forward_recorded(injected, workdir):
    first = injected.snapshots.head_snapshot_id()
    injected.append("article.md", "v2")
    injected.append("article.md", "v3")
    assert injected.snapshots.head_snapshot_id() != first

    snap = restoremod.restore(injected, first, "article.md")
    # HEAD advanced to a NEW snapshot, the old one is untouched
    assert snap.id == injected.snapshots.head_snapshot_id()
    assert snap.id != first
    assert injected.snapshots.load(first).id == first  # old snapshot still loadable

    # content matches the restored version
    restored = injected.current_content("article.md")
    assert restored == injected.store.read(
        injected.snapshots.load(first).root["article.md"].content_hash
    )


def test_whole_tree_restore(injected, workdir, write_file):
    write_file("b.md", "second\n")
    injected.inject("b.md")
    target = injected.snapshots.head_snapshot_id()
    injected.append("article.md", "changed")
    injected.append("b.md", "changed")

    restoremod.restore(injected, target, None)
    a = (workdir / "article.md").read_text()
    b = (workdir / "b.md").read_text()
    assert "changed" not in a
    assert "changed" not in b


def test_resolve_prefix_and_head(injected):
    sid = injected.snapshots.head_snapshot_id()
    assert injected.snapshots.resolve("HEAD") == sid
    assert injected.snapshots.resolve(sid[:12]) == sid


def test_timeline_tracks_file_across_rename(injected):
    injected.append("article.md", "v2")
    injected.move("article.md", "essays/article.md")
    mf = injected.index.get("essays/article.md")
    # the same file_id appears in earlier snapshots under the old path
    seen_paths = set()
    for snap in injected.snapshots.list():
        match = next((m for m in snap.root.values() if m.file_id == mf.file_id), None)
        if match:
            seen_paths.add(match.path)
    assert {"article.md", "essays/article.md"} <= seen_paths
