from __future__ import annotations

from collections import defaultdict
from typing import Any

_ARTICULATION_TAGS = {
    "sustain", "sus", "staccato", "stac", "pizzicato", "pizz", "spiccato",
    "spic", "tremolo", "trem", "mute", "muted", "harmonic", "legato",
}
_VELOCITY_NAMES = {
    "soft": (1, 63),
    "quiet": (1, 63),
    "p": (1, 63),
    "pp": (1, 45),
    "medium": (40, 95),
    "mf": (40, 95),
    "loud": (64, 127),
    "hard": (64, 127),
    "f": (64, 127),
    "ff": (84, 127),
}


def accepted_pitched_samples(analyses: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        [a for a in analyses
         if a.get("status") == "accepted" and a.get("midi_note") is not None],
        key=lambda a: (
            int(a["midi_note"]),
            articulation(a),
            velocity_range(a),
            a.get("round_robin_group") or "",
            a.get("path", ""),
        ),
    )


def articulation(sample: dict[str, Any]) -> str:
    value = sample.get("articulation") or sample.get("descriptors", {}).get("articulation")
    if value:
        return str(value).strip().lower().replace(" ", "_")
    tags = [str(t).strip().lower() for t in sample.get("tags", [])]
    for tag in tags:
        if tag in _ARTICULATION_TAGS:
            return {"sus": "sustain", "stac": "staccato",
                    "pizz": "pizzicato", "spic": "spiccato",
                    "trem": "tremolo", "muted": "mute"}.get(tag, tag)
    return "sustain"


def velocity_range(sample: dict[str, Any]) -> tuple[int, int]:
    if "velocity_range" in sample:
        lo, hi = sample["velocity_range"]
        return max(1, int(lo)), min(127, int(hi))
    if "lovel" in sample or "hivel" in sample:
        return max(1, int(sample.get("lovel", 1))), min(127, int(sample.get("hivel", 127)))
    value = sample.get("velocity_layer") or sample.get("descriptors", {}).get("velocity")
    if value:
        key = str(value).strip().lower()
        if key in _VELOCITY_NAMES:
            return _VELOCITY_NAMES[key]
    return (1, 127)


def round_robin_key(sample: dict[str, Any]) -> str | None:
    value = sample.get("round_robin_group") or sample.get("descriptors", {}).get("round_robin_group")
    if value:
        return str(value)
    return None


def _provenance_value(sample: dict[str, Any], key: str) -> Any:
    value = sample.get(key)
    if value:
        return value
    descriptors = sample.get("descriptors", {})
    if isinstance(descriptors, dict) and descriptors.get(key):
        return descriptors[key]
    raw = sample.get("source_raw_metadata", {})
    if isinstance(raw, dict) and raw.get(key):
        return raw[key]
    return None


def compatible_round_robin_key(sample: dict[str, Any]) -> str | None:
    explicit = round_robin_key(sample)
    if explicit:
        return f"explicit:{explicit}"
    for key in ("session", "session_id", "pack", "institution"):
        value = _provenance_value(sample, key)
        if value:
            return f"{key}:{value}"
    return None


def assign_key_ranges(samples: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ordered = accepted_pitched_samples(samples)
    out = []
    by_art_vel: dict[tuple[str, tuple[int, int]], list[dict[str, Any]]] = defaultdict(list)
    for sample in ordered:
        by_art_vel[(articulation(sample), velocity_range(sample))].append(sample)
    for group in by_art_vel.values():
        group.sort(key=lambda s: (int(s["midi_note"]), s.get("path", "")))
        notes = sorted({int(s["midi_note"]) for s in group})
        ranges = {}
        for i, note in enumerate(notes):
            prev_note = notes[i - 1] if i else note
            next_note = notes[i + 1] if i + 1 < len(notes) else note
            lo = note if i == 0 else int((prev_note + note) // 2 + 1)
            hi = note if i + 1 == len(notes) else int((note + next_note) // 2)
            ranges[note] = (max(0, lo), min(127, hi))
        for sample in group:
            note = int(sample["midi_note"])
            row = dict(sample)
            row["lokey"], row["hikey"] = ranges[note]
            row["articulation"] = articulation(sample)
            row["lovel"], row["hivel"] = velocity_range(sample)
            out.append(row)
    return _assign_round_robin(out)


def _assign_round_robin(samples: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for sample in samples:
        note = int(sample["midi_note"])
        rr = compatible_round_robin_key(sample)
        key = (
            rr,
            sample["articulation"],
            note,
            sample["lovel"],
            sample["hivel"],
            sample["lokey"],
            sample["hikey"],
        )
        buckets[key].append(sample)
    out = []
    for rows in buckets.values():
        rows.sort(key=lambda s: s.get("path", ""))
        rr = compatible_round_robin_key(rows[0])
        if rr and len(rows) > 1:
            total = len(rows)
            for idx, row in enumerate(rows, 1):
                row = dict(row)
                row["seq_length"] = total
                row["seq_position"] = idx
                out.append(row)
        else:
            out.extend(rows)
    return sorted(out, key=lambda r: (
        int(r["midi_note"]), r["lovel"], r["articulation"],
        r.get("seq_position", 0), r.get("path", "")))
