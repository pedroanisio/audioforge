from __future__ import annotations

import pytest

from shadowmd import diff as diffmod
from shadowmd.patchtools import PatchError, apply_unified


def test_unified_diff_roundtrips_through_apply():
    old = b"line1\nline2\nline3\n"
    new = b"line1\nline2 changed\nline3\nline4\n"
    patch = diffmod.unified(old, new, old_label="a", new_label="b").encode()
    assert apply_unified(old, patch) == new


def test_apply_rejects_context_mismatch():
    old = b"a\nb\nc\n"
    new = b"a\nB\nc\n"
    patch = diffmod.unified(old, new).encode()
    with pytest.raises(PatchError):
        apply_unified(b"totally\ndifferent\nfile\n", patch)


def test_apply_requires_a_hunk():
    with pytest.raises(PatchError):
        apply_unified(b"x\n", b"no hunks here\n")


def test_apply_command_path(injected, workdir):
    old = injected.current_content("article.md")
    new = old + b"appended via patch\n"
    patch = diffmod.unified(old, new).encode()
    new_content = apply_unified(injected.current_content("article.md"), patch)
    injected.mutate_file("article.md", new_content, "patched")
    assert (workdir / "article.md").read_bytes() == new
