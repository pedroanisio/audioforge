"""Write-ahead operation journal (§4.7, §5.4, §9.2).

Append-only NDJSON. Every logical mutation writes an ``intent`` entry *before*
the working tree is touched (and after the new blob is durable) and a ``commit``
entry after the index update. ``fsck`` uses unpaired ``intent`` entries to roll
interrupted operations forward or back (§9.2).

Ordering matters: v1 journaled *after* the projection write, so a crash in the
gap lost the history entry. Here the journal is genuinely write-ahead.
"""

from __future__ import annotations

import json
import os
from typing import Any

from .ids import iso_now
from .layout import Layout


class Journal:
    def __init__(self, layout: Layout) -> None:
        self._layout = layout
        self._path = layout.journal_log()

    # --- low-level append ------------------------------------------------
    def _append(self, entry: dict[str, Any]) -> dict[str, Any]:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        line = (json.dumps(entry, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")
        # O_APPEND makes the write atomic w.r.t. concurrent appenders; fsync
        # makes it durable before we return (write-ahead guarantee).
        fd = os.open(self._path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
        try:
            os.write(fd, line)
            os.fsync(fd)
        finally:
            os.close(fd)
        return entry

    def next_seq(self) -> int:
        last = 0
        for entry in self.read_all():
            seq = entry.get("seq", 0)
            if isinstance(seq, int) and seq > last:
                last = seq
        return last + 1

    # --- entry kinds -----------------------------------------------------
    def intent(
        self,
        *,
        operation: str,
        path: str | None,
        old_hash: str | None,
        new_hash: str | None,
        message: str,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        entry = {
            "seq": self.next_seq(),
            "ts": iso_now(),
            "phase": "intent",
            "operation": operation,
            "path": path,
            "old_hash": old_hash,
            "new_hash": new_hash,
            "message": message,
        }
        if extra:
            entry.update(extra)
        return self._append(entry)

    def commit(self, intent_entry: dict[str, Any]) -> dict[str, Any]:
        entry = dict(intent_entry)
        entry["phase"] = "commit"
        entry["ts"] = iso_now()
        return self._append(entry)

    def marker(self, operation: str, message: str = "") -> dict[str, Any]:
        """A standalone event (transaction begin/commit/abort, etc.)."""
        return self._append(
            {
                "seq": self.next_seq(),
                "ts": iso_now(),
                "phase": "marker",
                "operation": operation,
                "path": None,
                "old_hash": None,
                "new_hash": None,
                "message": message,
            }
        )

    # --- reading ---------------------------------------------------------
    def read_all(self) -> list[dict[str, Any]]:
        if not self._path.exists():
            return []
        entries: list[dict[str, Any]] = []
        with open(self._path, encoding="utf-8") as fh:
            for raw in fh:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    entries.append(json.loads(raw))
                except json.JSONDecodeError:
                    # A torn final line (crash mid-append) is ignored on read;
                    # fsck reports it. Never crash the whole tool on one bad line.
                    continue
        return entries

    def unpaired_intents(self) -> list[dict[str, Any]]:
        """Intent entries with no matching commit, by (seq) — for fsck."""
        committed = {
            e["seq"] for e in self.read_all() if e.get("phase") == "commit"
        }
        return [
            e
            for e in self.read_all()
            if e.get("phase") == "intent" and e.get("seq") not in committed
        ]
