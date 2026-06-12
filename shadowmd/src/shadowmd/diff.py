"""On-demand unified diffs (§5.3).

Deltas are derived data, not primary storage. Blobs alone fully determine every
version, so a persisted diff would be redundant data with its own corruption
mode. ``difflib.unified_diff`` is sufficient, dependency-free, and the right
display format for line-oriented Markdown. (Persisted deltas return only as a
gc-time compaction strategy — §16.4 — never on the hot write path.)
"""

from __future__ import annotations

import difflib


def _lines(content: bytes) -> list[str]:
    return content.decode("utf-8", errors="replace").splitlines(keepends=True)


def unified(
    old: bytes,
    new: bytes,
    *,
    old_label: str = "a",
    new_label: str = "b",
) -> str:
    diff = difflib.unified_diff(
        _lines(old),
        _lines(new),
        fromfile=old_label,
        tofile=new_label,
        lineterm="\n",
    )
    return "".join(diff)
