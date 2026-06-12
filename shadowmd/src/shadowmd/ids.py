"""Identifier and timestamp helpers.

Two id schemes, both chosen in the design (§5.2, §6):

* ``file_id`` — ``f_<ULID>``: lexicographically sortable, time-ordered, with
  80 bits of randomness so two files injected in the same millisecond do not
  collide.
* ``snapshot id`` — ``snap_<UTC compact timestamp>_<4 hex chars>``: sortable by
  prefix (auto-snapshot mode makes same-second snapshots likely, so the random
  suffix is mandatory, not decorative).

Crockford base32 (no I, L, O, U) is used for the ULID body, matching the ULID
spec so ids remain copy-pasteable without ambiguous characters.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def utc_now() -> datetime:
    """Timezone-aware UTC now. Single chokepoint so tests can monkeypatch it."""
    return datetime.now(timezone.utc)


def iso_now() -> str:
    """RFC 3339 / ISO 8601 UTC timestamp, e.g. ``2026-06-12T14:23:11Z``."""
    return utc_now().strftime("%Y-%m-%dT%H:%M:%SZ")


def compact_now() -> str:
    """Compact UTC timestamp for ids, e.g. ``20260612T142311Z``."""
    return utc_now().strftime("%Y%m%dT%H%M%SZ")


def _b32(value: int, length: int) -> str:
    out = []
    for _ in range(length):
        out.append(_CROCKFORD[value & 0x1F])
        value >>= 5
    return "".join(reversed(out))


def new_ulid() -> str:
    """A 26-char Crockford-base32 ULID: 48-bit ms timestamp + 80-bit random."""
    ms = int(utc_now().timestamp() * 1000) & ((1 << 48) - 1)
    rand = int.from_bytes(os.urandom(10), "big")  # 80 bits
    return _b32(ms, 10) + _b32(rand, 16)


def new_file_id() -> str:
    return f"f_{new_ulid()}"


def new_snapshot_id() -> str:
    suffix = os.urandom(2).hex()  # 4 hex chars
    return f"snap_{compact_now()}_{suffix}"
