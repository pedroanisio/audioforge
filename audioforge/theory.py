"""Compile-time music theory for the DSL: chord parsing and voicings,
Euclidean rhythm generation, motif transforms, diatonic transposition.

Everything here expands into explicit note events or pattern strings at
compile time — the JSON IR stays the complete ground truth.
"""
from __future__ import annotations

import re

PC_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
PC_OF = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}

# quality -> semitone intervals from root (longest names first for parsing)
CHORD_QUALITIES = {
    "min7b5": (0, 3, 6, 10), "m7b5": (0, 3, 6, 10),
    "dim7": (0, 3, 6, 9),
    "maj9": (0, 4, 7, 11, 14), "min9": (0, 3, 7, 10, 14),
    "maj7": (0, 4, 7, 11), "min7": (0, 3, 7, 10), "m9": (0, 3, 7, 10, 14),
    "add9": (0, 4, 7, 14), "sus2": (0, 2, 7), "sus4": (0, 5, 7),
    "maj": (0, 4, 7), "min": (0, 3, 7), "dim": (0, 3, 6), "aug": (0, 4, 8),
    "m7": (0, 3, 7, 10), "m6": (0, 3, 7, 9),
    "m": (0, 3, 7), "7": (0, 4, 7, 10), "6": (0, 4, 7, 9), "9": (0, 4, 7, 10, 14),
    # merged from the _tmp/audioforge subset (scripts/diff_engines.py); `s11`
    # spells #11 without the DSL comment char. Aliases let subset-authored
    # specs parse here too.
    "7sus4": (0, 5, 7, 10), "dom7sus4": (0, 5, 7, 10),
    "maj7#11": (0, 4, 7, 11, 18), "maj7s11": (0, 4, 7, 11, 18),
}
# Canonical pitch spelling: letter, optional accidental, optional sign, exactly
# one octave digit. Single source of truth for both the DSL note grammar and the
# IR validator's tone-pitch check (audit finding F13) so they cannot diverge.
NOTE_RE = re.compile(r"^[A-Ga-g][#b]?-?\d$")

_QUALITY_ALT = sorted(CHORD_QUALITIES, key=len, reverse=True)
CHORD_RE = re.compile(
    r"^([A-Ga-g][#b]?-?\d)(" + "|".join(re.escape(q) for q in _QUALITY_ALT) + r")$")

VOICINGS = ("close", "drop2", "drop3", "spread", "open", "wide",
            "inv1", "inv2")


def note_to_semis(note: str) -> int:
    m = re.match(r"^([A-Ga-g])([#b]?)(-?\d)$", note)
    if not m:
        raise ValueError(f"bad note name {note!r}")
    pc = PC_OF[m.group(1).upper()]
    pc += {"#": 1, "b": -1, "": 0}[m.group(2)]
    return int(m.group(3)) * 12 + pc


def semis_to_note(s: int) -> str:
    return f"{PC_NAMES[s % 12]}{s // 12}"


def parse_chord(text: str) -> tuple[str, str] | None:
    """'C3min7' -> ('C3', 'min7'); None when not a chord symbol."""
    m = CHORD_RE.match(text)
    return (m.group(1), m.group(2)) if m else None


def chord_semis(root_note: str, quality: str, voicing: str = "close") -> list[int]:
    """Absolute semitone stack for a chord, voiced. Deterministic mappings:
    close = as stacked; drop2/drop3 = classic drops; spread = drop2 with the
    root doubled an octave down; open = root down an octave; wide = alternate
    tones lifted an octave; inv1/inv2 = inversions (bass tones up)."""
    root = note_to_semis(root_note)
    stack = [root + i for i in CHORD_QUALITIES[quality]]
    if voicing == "close":
        return stack
    if voicing == "drop2" and len(stack) >= 3:
        s = sorted(stack)
        s[-2] -= 12
        return sorted(s)
    if voicing == "drop3" and len(stack) >= 4:
        s = sorted(stack)
        s[-3] -= 12
        return sorted(s)
    if voicing == "spread":
        s = sorted(stack)
        if len(s) >= 3:
            s[-2] -= 12
        return sorted([s[0] - 12] + s)
    if voicing == "open":
        s = sorted(stack)
        return sorted([s[0] - 12] + s[1:])
    if voicing == "wide":
        s = sorted(stack)
        return sorted(v + (12 if i % 2 else 0) for i, v in enumerate(s))
    if voicing in ("inv1", "inv2"):
        n = 1 if voicing == "inv1" else 2
        s = sorted(stack)
        for k in range(min(n, len(s) - 1)):
            s[k] += 12
        return sorted(s)
    return stack


def bjorklund(k: int, n: int, rotate: int = 0) -> str:
    """Euclidean rhythm E(k, n) as an 'x'/'.' pattern string (Bjorklund)."""
    if k <= 0:
        return "." * n
    if k >= n:
        return "x" * n
    a, b = [["x"]] * k, [["."]] * (n - k)
    while len(b) > 1:
        pairs = min(len(a), len(b))
        a, b = ([a[i] + b[i] for i in range(pairs)],
                a[pairs:] if len(a) > pairs else b[pairs:])
    pat = "".join("".join(g) for g in a + b)
    rotate %= n
    return pat[rotate:] + pat[:rotate]


# ----------------------------------------------------------- transforms
def retrograde(events: list[dict]) -> list[dict]:
    if not events:
        return events
    span = max(e["start_beat"] + e["dur_beats"] for e in events)
    out = []
    for e in events:
        e2 = dict(e)
        e2["start_beat"] = round(span - (e["start_beat"] + e["dur_beats"]), 6)
        out.append(e2)
    return sorted(out, key=lambda e: e["start_beat"])


def invert(events: list[dict]) -> list[dict]:
    """Chromatic mirror around the first (earliest, then lowest) pitch."""
    pitched = [e for e in events if "note" in e or "chord_root" in e]
    if not pitched:
        return events
    first = min(pitched, key=lambda e: (e["start_beat"],
                note_to_semis(e.get("note") or e["chord_root"])))
    axis = note_to_semis(first.get("note") or first["chord_root"])
    out = []
    for e in events:
        e2 = dict(e)
        key = "note" if "note" in e2 else ("chord_root" if "chord_root" in e2
                                           else None)
        if key:
            e2[key] = semis_to_note(2 * axis - note_to_semis(e2[key]))
        out.append(e2)
    return out


def stretch(events: list[dict], factor: float) -> list[dict]:
    out = []
    for e in events:
        e2 = dict(e)
        e2["start_beat"] = round(e["start_beat"] * factor, 6)
        e2["dur_beats"] = round(e["dur_beats"] * factor, 6)
        out.append(e2)
    return out


def diatonic_transpose(note: str, degrees: int, root_pc: int,
                       intervals: list[int]) -> str:
    """Move a note by scale degrees within a 7-note scale (root pitch class
    + ascending interval list, e.g. major [0,2,4,5,7,9,11]). Out-of-scale
    tones keep their chromatic offset from the nearest lower scale tone.
    Built on a root-relative semitone ladder, so motion is monotonic by
    construction for every key."""
    s = note_to_semis(note)
    rel = s - root_pc
    octv, within = divmod(rel, 12)
    idx = max(i for i, iv in enumerate(intervals) if iv <= within)
    delta = within - intervals[idx]
    oct_shift, deg = divmod(idx + degrees, 7)
    return semis_to_note(root_pc + 12 * (octv + oct_shift)
                         + intervals[deg] + delta)
