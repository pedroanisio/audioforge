"""Canonical JSON serialization helpers.

All on-disk JSON is written sorted and indented so diffs are stable and blobs
that content-address a manifest are reproducible. Mutable JSON (index, refs)
is written through ``atomic_write_bytes``; immutable JSON (snapshots, blobs)
through the store/snapshot modules, which also go via ``atomic_write_bytes``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def dumps(obj: Any) -> bytes:
    return (json.dumps(obj, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def loads(data: bytes) -> Any:
    return json.loads(data.decode("utf-8"))


def load_file(path: Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))
