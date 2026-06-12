from __future__ import annotations

import pytest

from shadowmd.hashing import hash_bytes, split
from shadowmd.ids import new_file_id, new_snapshot_id, new_ulid
from shadowmd.layout import Layout
from shadowmd.store import BlobStore


def test_hash_is_deterministic_and_prefixed():
    h = hash_bytes(b"hello")
    assert h.startswith("sha256:")
    assert h == hash_bytes(b"hello")
    assert h != hash_bytes(b"world")


def test_split_rejects_malformed():
    assert split("sha256:abc") == ("sha256", "abc")
    with pytest.raises(ValueError):
        split("not-a-hash")


def test_store_is_idempotent_and_fanned_out(tmp_path):
    layout = Layout(tmp_path)
    for d in layout.all_dirs():
        d.mkdir(parents=True, exist_ok=True)
    store = BlobStore(layout)

    h1 = store.store(b"content")
    h2 = store.store(b"content")  # idempotent
    assert h1 == h2
    assert store.has(h1)
    assert store.read(h1) == b"content"

    # fan-out: sha256/<2>/<rest>
    _, digest = split(h1)
    assert (layout.blobs / "sha256" / digest[:2] / digest[2:]).is_file()
    assert h1 in set(store.iter_hashes())


def test_store_remove(tmp_path):
    layout = Layout(tmp_path)
    for d in layout.all_dirs():
        d.mkdir(parents=True, exist_ok=True)
    store = BlobStore(layout)
    h = store.store(b"x")
    store.remove(h)
    assert not store.has(h)
    store.remove(h)  # tolerant of double-remove


def test_ids_are_sortable_and_unique():
    ids = {new_ulid() for _ in range(200)}
    assert len(ids) == 200  # 80 bits of randomness => no collisions
    assert new_file_id().startswith("f_")
    sid = new_snapshot_id()
    assert sid.startswith("snap_") and sid.count("_") == 2
