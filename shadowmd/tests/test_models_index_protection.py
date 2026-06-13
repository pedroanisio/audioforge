from __future__ import annotations

import pytest

from shadowmd import protection
from shadowmd.errors import FileAlreadyTracked, FileNotTracked
from shadowmd.index import Index
from shadowmd.models import BlobRef, ManagedFile, Snapshot


def test_blobref_roundtrip():
    ref = BlobRef.parse("sha256:abcdef")
    assert ref.algorithm == "sha256"
    assert ref.digest == "abcdef"
    assert ref.uri == "sha256:abcdef"


def test_managed_file_roundtrip_full():
    mf = ManagedFile(
        file_id="f_1",
        path="a.md",
        content_hash="sha256:1",
        size=10,
        readonly=True,
        last_snapshot="snap_x",
        previous_paths=("old.md",),
        original_mode=0o644,
    )
    assert ManagedFile.from_dict(mf.to_dict()) == mf


def test_snapshot_roundtrip():
    mf = ManagedFile(file_id="f_1", path="a.md", content_hash="sha256:1", size=1)
    snap = Snapshot(id="snap_1", created_at="t", parent=None, message="m", root={"a.md": mf})
    assert Snapshot.from_dict(snap.to_dict()) == snap


def test_index_operations_and_errors():
    idx = Index()
    mf = ManagedFile(file_id="f_1", path="a.md", content_hash="sha256:1", size=1)
    idx.add(mf)
    assert "a.md" in idx
    assert idx.find_by_id("f_1") is mf
    assert idx.find_by_id("missing") is None
    assert len(idx) == 1
    assert idx.paths() == ["a.md"]

    with pytest.raises(FileAlreadyTracked):
        idx.add(mf)
    with pytest.raises(FileNotTracked):
        idx.get("nope.md")
    with pytest.raises(FileNotTracked):
        idx.remove("nope.md")

    idx.update_content("a.md", "sha256:2", 5, last_snapshot="snap_y")
    assert idx.get("a.md").content_hash == "sha256:2"
    assert idx.get("a.md").last_snapshot == "snap_y"

    moved = idx.rename("a.md", "b.md")
    assert moved.path == "b.md"
    assert "a.md" in moved.previous_paths
    with pytest.raises(FileNotTracked):
        idx.update_content("a.md", "sha256:3", 1)

    idx.add(ManagedFile(file_id="f_2", path="c.md", content_hash="sha256:9", size=1))
    with pytest.raises(FileAlreadyTracked):
        idx.rename("b.md", "c.md")

    idx.set_last_snapshot("snap_z")
    assert all(m.last_snapshot == "snap_z" for m in idx)

    idx.replace(ManagedFile(file_id="f_2", path="c.md", content_hash="sha256:replaced", size=2))
    assert idx.get("c.md").content_hash == "sha256:replaced"


def test_protection_permission_helpers(tmp_path):
    f = tmp_path / "x.md"
    f.write_text("hi")
    protection.make_readonly(f)
    assert protection.is_readonly(f)
    assert protection.current_mode(f) == 0o444

    protection.make_writable_by_owner(f)
    assert not protection.is_readonly(f)
    assert protection.current_mode(f) == 0o644


def test_strict_protection_errors_when_unsupported(tmp_path, monkeypatch):
    f = tmp_path / "x.md"
    f.write_text("hi")
    monkeypatch.setattr(protection.shutil, "which", lambda _name: None)
    assert protection.strict_supported() is False
    with pytest.raises(protection.StrictProtectionError):
        protection.set_immutable(f)
    with pytest.raises(protection.StrictProtectionError):
        protection.clear_immutable(f)
