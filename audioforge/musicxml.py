"""MusicXML 3.1 interchange for the note-event IR (ADR-0009).

* ``export_musicxml`` — exact-tick interchange. One part per pitched layer, one
  measure per part, ``<chord/>`` for simultaneous onsets, ``<backup>`` and
  ``<forward>`` for exact cursor moves. Nothing is quantized.
* ``export_notated_musicxml`` — the formal score. Durations snap to a grid and
  become standard figures; measures come from the spec meter (per-part
  polymeter); an anacrusis is an implicit first measure; ``key_map`` changes
  land on the first barline at or after the change beat; ``tempo_map`` points
  thin to the grid (see ``tempo_marks``) and become metronome directions; notes
  tie across barlines.
* ``import_musicxml`` — part-aware, cursor-exact reader: chords, backup and
  forward, voices, per-measure divisions/time/key/tempo, merged ties.

XSD validity of the exports, structural parity with music21, and the import's
onset fidelity are asserted by tests/test_notation_oracles.py.

⚠ ARCHITECTURAL CONTRACT (PALS's LAW): ``import_musicxml`` returns the parser's
*claim* about a foreign document; callers validate it (``ir_schema`` /
``AudioForge.load_spec``) before trusting it.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET

from . import theory

TPQ = 480             # divisions per quarter note in every export
NOTATED_GRID = 0.25   # default quantization grid of the notated view (quarter beats)
TEMPO_MARK_MIN_DELTA_BPM = 0.1   # consecutive marks closer than this are one mark

_MAJ_FIFTHS = {"C": 0, "G": 1, "D": 2, "A": 3, "E": 4, "B": 5, "F#": 6, "C#": 7,
               "F": -1, "Bb": -2, "Eb": -3, "Ab": -4, "Db": -5, "Gb": -6, "Cb": -7}
_MIN_FIFTHS = {"A": 0, "E": 1, "B": 2, "F#": 3, "C#": 4, "G#": 5, "D#": 6,
               "D": -1, "G": -2, "C": -3, "F": -4, "Bb": -5, "Eb": -6, "Ab": -7}
# (quarter-fraction, MusicXML type, dots) — largest first, for greedy split
_FIG = [(4.0, "whole", 0), (3.0, "half", 1), (2.0, "half", 0),
        (1.5, "quarter", 1), (1.0, "quarter", 0), (0.75, "eighth", 1),
        (0.5, "eighth", 0), (0.375, "16th", 1), (0.25, "16th", 0),
        (0.125, "32nd", 0)]
FORTE_VELOCITY = 90   # MusicXML: a note's `dynamics` attribute is a percentage of MIDI velocity 90
VEL_SCALE = 96        # the MIDI export maps vel 1.0 to velocity 96; both exporters share it

# IR articulation -> MusicXML notation (group, element). `sustain` is the default and
# writes nothing; `legato` becomes a slur over the run; `pizzicato` becomes a "pizz."
# direction with <sound pizzicato="yes"> (and "arco" when the run ends).
ARTICULATION_XML = {
    "staccato": ("articulations", "staccato"),
    "spiccato": ("articulations", "spiccato"),
    "marcato": ("articulations", "strong-accent"),
    "tremolo": ("ornaments", "tremolo"),
}
_XML_ARTICULATION = {v: k for k, v in ARTICULATION_XML.items()}
_LEGATO_SLUR_BASE = 1000   # synthetic slur ids for `art legato` runs (authored ids are small)


def _dynamic_marks() -> dict[str, float]:
    from .dsl import DYNAMIC_MARKS   # the DSL owns the vocabulary; dsl is heavy, import lazily
    return DYNAMIC_MARKS


def _mark_for(value: float) -> str:
    marks = _dynamic_marks()
    return min(marks, key=lambda m: abs(marks[m] - value))


def _vel_attr(vel: float) -> str:
    return _num(max(0.0, float(vel)) * VEL_SCALE / FORTE_VELOCITY * 100.0)


def _vel_from_attr(text: str) -> float:
    return round(float(text) / 100.0 * FORTE_VELOCITY / VEL_SCALE, 4)


def _midi_note(note: str) -> int:
    return theory.note_to_semis(note) + 12


def _note_name(midi: int) -> str:
    return theory.semis_to_note(midi - 12)


def layer_ident(text: str, fallback: str, used: set[str]) -> str:
    """Coerce a foreign part/track name into a unique DSL IDENT.

    The grammar's IDENT is ``letter , { letter | digit | "_" | "#" }`` — no
    hyphens, spaces, or leading digits — and layer names must be unique so the
    decompiled ``.af`` round-trips. Invalid runs collapse to ``_``; a numeric
    suffix disambiguates collisions.
    """
    cleaned = re.sub(r"[^A-Za-z0-9_#]+", "_", (text or "").strip()).strip("_")
    if not cleaned or not cleaned[0].isalpha():
        cleaned = fallback if (fallback and fallback[0].isalpha()) else f"L_{cleaned}"
    candidate = cleaned
    n = 2
    while candidate in used:
        candidate = f"{cleaned}_{n}"
        n += 1
    return candidate


# ------------------------------------------------------------------ keys ----
def _split_key(key: str | None) -> tuple[str, str]:
    p = (key or "C major").split()
    return p[0], (p[1].lower() if len(p) > 1 else "major")


def _tonic_fifths(tonic: str, mode: str) -> int:
    return (_MIN_FIFTHS if mode == "minor" else _MAJ_FIFTHS).get(tonic, 0)


def _key_fifths(key: str) -> int:
    return _tonic_fifths(*_split_key(key))


def _fifths_key(fifths: int, mode: str) -> str:
    mode = "minor" if mode == "minor" else "major"
    table = _MIN_FIFTHS if mode == "minor" else _MAJ_FIFTHS
    inverse = {v: k for k, v in table.items()}
    return f"{inverse.get(fifths, 'A' if mode == 'minor' else 'C')} {mode}"


def _key_points(spec: dict) -> list[tuple[int, int, str]]:
    """``(tick, fifths, mode)`` for the initial key and every ``key_map`` change,
    sorted, starting at tick 0, consecutive duplicates removed."""
    tonic, mode = _split_key(spec.get("key"))
    pts = [(0, _tonic_fifths(tonic, mode), mode)]
    for beat, tonic, mode in spec.get("key_map") or []:
        mode = str(mode).lower()
        pts.append((int(round(float(beat) * TPQ)), _tonic_fifths(tonic, mode), mode))
    pts.sort(key=lambda p: p[0])
    out: list[tuple[int, int, str]] = []
    for p in pts:
        if out and out[-1][0] == p[0]:
            out[-1] = p                      # a key_map entry at 0 overrides `key`
        elif not out or (p[1], p[2]) != (out[-1][1], out[-1][2]):
            out.append(p)
    return out


def _key_at(points: list[tuple[int, int, str]], tick: int) -> tuple[int, int, str]:
    cur = points[0]
    for p in points:
        if p[0] <= tick:
            cur = p
        else:
            break
    return cur


# ----------------------------------------------------------------- tempo ----
def tempo_points(spec: dict) -> list[tuple[float, float]]:
    """Raw ``(beat, bpm)`` points: ``tempo_map`` or the single ``bpm``, sorted,
    with the first tempo extended back to beat 0 (as the renderer's TempoMap does)."""
    pts = sorted((float(b), float(v)) for b, v in (spec.get("tempo_map") or []))
    if not pts:
        pts = [(0.0, float(spec.get("bpm", 120.0)))]
    if pts[0][0] != 0.0:
        pts.insert(0, (0.0, pts[0][1]))
    return pts


def tempo_marks(spec: dict, grid: float = NOTATED_GRID) -> list[tuple[float, float]]:
    """The tempo marks the notated export writes: ``tempo_points`` snapped to
    ``grid`` (one mark per slot, last point wins) with consecutive marks that
    differ by less than ``TEMPO_MARK_MIN_DELTA_BPM`` collapsed. A dense rubato
    map therefore thins to its audible steps; the resolution is the grid.

    A MusicXML metronome mark holds until the next one, so the IR's linear
    ramps between points are stepped at their points on export."""
    slots: dict[float, float] = {}
    for beat, bpm in tempo_points(spec):
        slots[round(round(beat / grid) * grid, 6)] = bpm
    out: list[tuple[float, float]] = []
    for beat in sorted(slots):
        if not out or abs(slots[beat] - out[-1][1]) >= TEMPO_MARK_MIN_DELTA_BPM:
            out.append((beat, slots[beat]))
    return out


def stepped_tempo_map(marks: list[tuple[float, float]]) -> list[list[float]]:
    """IR ``tempo_map`` with the *step* semantics of notation tempo marks: the
    IR interpolates linearly between points, so each change is written as
    ``[beat, previous_bpm], [beat, new_bpm]`` (equal beats are allowed by the
    validator and integrate to a step)."""
    out: list[list[float]] = []
    for beat, bpm in marks:
        if out and out[-1][1] != bpm:
            out.append([beat, out[-1][1]])
        out.append([beat, bpm])
    return out


# -------------------------------------------------------------- measures ----
def _bar_ticks(spec: dict, layer_name: str | None = None,
               beats_override: int | None = None) -> tuple[int, int, int]:
    """``(beats, unit, bar_ticks)`` for a part: the layer's polymeter entry, else
    the score meter, else 4/4. ``beats_override`` keeps the legacy CLI flag."""
    score = spec.get("score") or {}
    meter = ((score.get("polymeter") or {}).get(layer_name) if layer_name else None) \
        or score.get("meter") or {}
    beats = int(beats_override or meter.get("beats", 4))
    unit = int(meter.get("unit", 4))
    return beats, unit, int(round(beats * 4 * TPQ / unit))


def _pickup_ticks(spec: dict) -> int:
    return int(round(float((spec.get("score") or {}).get("pickup_beats", 0.0)) * TPQ))


def _spans(total: int, bar: int, pickup: int) -> list[tuple[int, int]]:
    """Measure ``[start, end)`` tick spans covering ``total`` ticks: an implicit
    anacrusis of ``pickup`` ticks first, then full bars (at least one)."""
    spans = [(0, pickup)] if pickup > 0 else []
    t = pickup
    while t < total or not spans:
        spans.append((t, t + bar))
        t += bar
    return spans


def _span_of(tick: int, bar: int, pickup: int) -> int:
    if pickup > 0 and tick < pickup:
        return 0
    return (1 if pickup > 0 else 0) + (tick - pickup) // bar


def _is_barline(tick: int, bar: int, pickup: int) -> bool:
    if tick == 0 or tick == pickup:
        return True
    return tick > pickup and (tick - pickup) % bar == 0


def _sections(spec: dict) -> list[dict]:
    return [s for s in (spec.get("score") or {}).get("sections") or [] if "start_beat" in s]


def _repeat_spans(spec: dict) -> list[tuple[int, int, int]]:
    """``(start_tick, end_tick, times)`` for every `score.repeats` entry whose section exists."""
    out = []
    by_name = {s["name"]: s for s in _sections(spec)}
    for r in (spec.get("score") or {}).get("repeats") or []:
        sec = by_name.get(r.get("section"))
        if sec:
            end = sec.get("end_beat", float(sec["start_beat"]) + float(sec.get("dur_beats", 0)))
            out.append((_tick(sec["start_beat"]), _tick(end), max(1, int(r.get("count", 2)))))
    return out


def repeats_align_with_barlines(spec: dict, beats_per_bar: int | None = None) -> bool:
    """True when every repeated section starts and ends on a barline of every pitched
    part (the notated export can then write repeat barlines instead of a lossy code)."""
    pickup = _pickup_ticks(spec)
    for layer in _pitched_layers(spec):
        _, _, bar = _bar_ticks(spec, layer.get("name"), beats_per_bar)
        for start, end, _ in _repeat_spans(spec):
            if not (_is_barline(start, bar, pickup) and _is_barline(end, bar, pickup)):
                return False
    return True


def performed(spec: dict) -> dict:
    """The spec as performed: score repeats expanded into the explicit timeline (what
    the renderer plays). The notated export keeps repeat signs instead."""
    if (spec.get("score") or {}).get("repeats"):
        from .arrangement import compile_repeats
        return compile_repeats(spec)
    return spec


# ------------------------------------------------------------ XML pieces ----
def _num(x: float) -> str:
    return f"{float(x):.3f}".rstrip("0").rstrip(".")


def _score_root(spec: dict, parts: list[dict]) -> ET.Element:
    root = ET.Element("score-partwise", version="3.1")
    ET.SubElement(ET.SubElement(root, "work"), "work-title").text = \
        str(spec.get("id", "AudioForge"))
    plist = ET.SubElement(root, "part-list")
    for p in parts:
        ET.SubElement(ET.SubElement(plist, "score-part", id=p["id"]),
                      "part-name").text = p["name"]
    return root


def _attributes(measure, *, divisions=None, key=None, time=None, clef=None):
    at = ET.SubElement(measure, "attributes")
    if divisions is not None:
        ET.SubElement(at, "divisions").text = str(divisions)
    if key is not None:
        k = ET.SubElement(at, "key")
        ET.SubElement(k, "fifths").text = str(key[1])
        ET.SubElement(k, "mode").text = key[2]
    if time is not None:
        tm = ET.SubElement(at, "time")
        ET.SubElement(tm, "beats").text = str(time[0])
        ET.SubElement(tm, "beat-type").text = str(time[1])
    if clef is not None:
        cl = ET.SubElement(at, "clef")
        ET.SubElement(cl, "sign").text = clef
        ET.SubElement(cl, "line").text = "2" if clef == "G" else "4"


def _direction(measure, offset_ticks: int, kind: str, value, placement: str = "above"):
    """One <direction> ``offset_ticks`` from the current position (negative offsets
    place a mark inside the preceding note). ``kind`` selects the payload:
    metronome (bpm), dynamics (mark), wedge (crescendo|diminuendo|stop),
    rehearsal (text), words (text, with <sound pizzicato> when value is a tuple)."""
    d = ET.SubElement(measure, "direction", placement=placement)
    dt = ET.SubElement(d, "direction-type")
    sound = None
    if kind == "metronome":
        m = ET.SubElement(dt, "metronome")
        ET.SubElement(m, "beat-unit").text = "quarter"
        ET.SubElement(m, "per-minute").text = _num(value)
        sound = {"tempo": _num(value)}
    elif kind == "dynamics":
        ET.SubElement(ET.SubElement(dt, "dynamics"), value)
    elif kind == "wedge":
        ET.SubElement(dt, "wedge", type=value)
    elif kind == "rehearsal":
        ET.SubElement(dt, "rehearsal").text = str(value)
    elif kind == "words":
        text, pizz = value
        ET.SubElement(dt, "words").text = text
        sound = {"pizzicato": "yes" if pizz else "no"}
    if offset_ticks:
        ET.SubElement(d, "offset", sound="yes").text = str(int(offset_ticks))
    if sound:
        ET.SubElement(d, "sound", **sound)


def _barline(measure, location: str, times: int | None = None):
    bl = ET.SubElement(measure, "barline", location=location)
    if location == "left":
        ET.SubElement(bl, "bar-style").text = "heavy-light"
        ET.SubElement(bl, "repeat", direction="forward")
    else:
        ET.SubElement(bl, "bar-style").text = "light-heavy"
        ET.SubElement(bl, "repeat", direction="backward", times=str(times or 2))


# direction ordering at one tick: wedge stops first, then marks, then wedge starts
_DIR_RANK = {"wedge_stop": 0, "metronome": 1, "rehearsal": 1, "dynamics": 2, "wedge": 3}


def _dynamic_directions(layer: dict) -> list[tuple[int, str, object]]:
    """Dynamic marks (and hairpins between differing marks) for a layer's `dynamic` points."""
    pts = [(float(b), float(v)) for b, v in (layer.get("dynamic") or [])]
    out: list[tuple[int, str, object]] = []
    for i, (beat, value) in enumerate(pts):
        out.append((_tick(beat), "dynamics", _mark_for(value)))
        if i + 1 < len(pts) and pts[i + 1][1] != value:
            out.append((_tick(beat), "wedge", "crescendo" if pts[i + 1][1] > value else "diminuendo"))
            out.append((_tick(pts[i + 1][0]), "wedge_stop", "stop"))
    return out


def _move(measure, kind: str, ticks: int):
    if ticks > 0:
        ET.SubElement(ET.SubElement(measure, kind), "duration").text = str(ticks)


def _xml_pitch(parent, name: str):
    pit = ET.SubElement(parent, "pitch")
    ET.SubElement(pit, "step").text = name[0].upper()
    i = 1
    if i < len(name) and name[i] in "#b":
        ET.SubElement(pit, "alter").text = "1" if name[i] == "#" else "-1"
        i += 1
    ET.SubElement(pit, "octave").text = name[i:]


def _decompose(ticks: int, tpq: int = TPQ):
    figs = [(int(round(q * tpq)), t, d) for q, t, d in _FIG]
    out, rem, guard = [], ticks, 0
    while rem > 0 and guard < 128:
        for ft, t, d in figs:
            if ft <= rem:
                out.append((ft, t, d))
                rem -= ft
                break
        else:
            break
        guard += 1
    return out or [(ticks, "quarter", 0)]


def _emit_rest(measure, ticks: int, fermata: bool = False):
    for fi, (ft, typ, dots) in enumerate(_decompose(ticks)):
        n = ET.SubElement(measure, "note")
        ET.SubElement(n, "rest")
        ET.SubElement(n, "duration").text = str(ft)
        ET.SubElement(n, "type").text = typ
        for _ in range(dots):
            ET.SubElement(n, "dot")
        if fermata and fi == 0:
            ET.SubElement(ET.SubElement(n, "notations"), "fermata")


def _emit_seg(measure, seg: dict, fermata: bool = False):
    """Write one segment (a note or chord between two boundaries) as standard figures.
    `written` ticks drive the figure types, `dur` the sounding <duration> (they differ
    inside tuplets); marks sit on the first figure of the first pitch."""
    tm = seg.get("time_mod")
    figs = _decompose(seg.get("written") or seg["dur"])
    scale = (tm[1] / tm[0]) if tm else 1.0
    assigned = 0
    for fi, (ft, typ, dots) in enumerate(figs):
        act = int(round(ft * scale)) if fi < len(figs) - 1 else seg["dur"] - assigned
        assigned += act
        tie_back = (fi > 0) or seg.get("tie_stop", False)
        tie_fwd = (fi < len(figs) - 1) or seg.get("tie_start", False)
        for pi, name in enumerate(seg["pitches"]):
            n = ET.SubElement(measure, "note")
            if seg.get("vel") is not None:
                n.set("dynamics", _vel_attr(seg["vel"]))
            if pi > 0:
                ET.SubElement(n, "chord")
            _xml_pitch(n, name)
            ET.SubElement(n, "duration").text = str(max(1, act))
            if tie_back:
                ET.SubElement(n, "tie", type="stop")
            if tie_fwd:
                ET.SubElement(n, "tie", type="start")
            ET.SubElement(n, "type").text = typ
            for _ in range(dots):
                ET.SubElement(n, "dot")
            if tm:
                t = ET.SubElement(n, "time-modification")
                ET.SubElement(t, "actual-notes").text = str(tm[0])
                ET.SubElement(t, "normal-notes").text = str(tm[1])
            nots = ET.Element("notations")
            if tie_back:
                ET.SubElement(nots, "tied", type="stop")
            if tie_fwd:
                ET.SubElement(nots, "tied", type="start")
            if fi == 0 and pi == 0:
                if seg.get("slur_start"):
                    ET.SubElement(nots, "slur", type="start", number=str(seg["slur_start"]))
                if seg.get("slur_stop"):
                    ET.SubElement(nots, "slur", type="stop", number=str(seg["slur_stop"]))
                if seg.get("tuplet_start"):
                    ET.SubElement(nots, "tuplet", type="start")
                if seg.get("tuplet_stop"):
                    ET.SubElement(nots, "tuplet", type="stop")
                art = ARTICULATION_XML.get(seg.get("art") or "")
                if art:
                    group = ET.SubElement(nots, art[0])
                    el = ET.SubElement(group, art[1])
                    if art[1] == "tremolo":
                        el.set("type", "single")
                        el.text = "3"
                if fermata:
                    ET.SubElement(nots, "fermata")
            if len(nots):
                n.append(nots)
            if fi == 0 and pi == 0 and seg.get("lyric"):
                ly = ET.SubElement(n, "lyric", number="1")
                ET.SubElement(ly, "syllabic").text = "single"
                ET.SubElement(ly, "text").text = seg["lyric"]


def _pitched_layers(spec: dict) -> list[dict]:
    return [layer for layer in spec.get("layers", [])
            if any("note" in e for e in (layer.get("notes") or []))]


def _tick(beats: float) -> int:
    return int(round(float(beats) * TPQ))


# ------------------------------------------------------ exact-tick export ----
def export_musicxml(spec: dict) -> str:
    """Exact-tick MusicXML: one part per pitched layer, one measure each, no
    quantization. Simultaneous onsets become ``<chord/>`` groups (one group per
    distinct duration, joined with ``<backup>``); overlaps and gaps move the
    cursor with ``<backup>`` / rests. Tempo points become directions in part 1."""
    spec = performed(spec)
    layers = _pitched_layers(spec)
    parts = [{"id": f"P{i + 1}",
              "name": layer.get("name") or str(spec.get("id", "AudioForge")),
              "notes": sorted((e for e in layer["notes"] if "note" in e),
                              key=lambda e: (_tick(e["start_beat"]), _midi_note(e["note"])))}
             for i, layer in enumerate(layers)] or \
            [{"id": "P1", "name": str(spec.get("id", "AudioForge")), "notes": []}]
    root = _score_root(spec, parts)
    meter = (spec.get("score") or {}).get("meter")
    key = _key_points(spec)[0]
    for pi, p in enumerate(parts):
        measure = ET.SubElement(ET.SubElement(root, "part", id=p["id"]), "measure", number="1")
        _attributes(measure, divisions=TPQ, key=key,
                    time=(meter["beats"], meter["unit"]) if meter else None)
        if pi == 0:
            for beat, bpm in tempo_points(spec):
                _direction(measure, _tick(beat), "metronome", bpm)
            for sec in _sections(spec):
                _direction(measure, _tick(sec["start_beat"]), "rehearsal", sec["name"])
        cursor, i, notes = 0, 0, p["notes"]
        while i < len(notes):
            start = _tick(notes[i]["start_beat"])
            group = []
            while i < len(notes) and _tick(notes[i]["start_beat"]) == start:
                group.append(notes[i])
                i += 1
            if start > cursor:
                n = ET.SubElement(measure, "note")
                ET.SubElement(n, "rest")
                ET.SubElement(n, "duration").text = str(start - cursor)
            elif start < cursor:
                _move(measure, "backup", cursor - start)
            by_dur: dict[int, list[dict]] = {}
            for ev in group:
                by_dur.setdefault(max(1, _tick(ev["dur_beats"])), []).append(ev)
            prev = None
            for dur, evs in by_dur.items():
                if prev is not None:
                    _move(measure, "backup", prev)
                for j, ev in enumerate(evs):
                    n = ET.SubElement(measure, "note")
                    if ev.get("vel") is not None:
                        n.set("dynamics", _vel_attr(ev["vel"]))
                    if j > 0:
                        ET.SubElement(n, "chord")
                    _xml_pitch(n, ev["note"])
                    ET.SubElement(n, "duration").text = str(dur)
                prev = dur
            cursor = start + (prev or 0)
    return ET.tostring(root, encoding="unicode")


# --------------------------------------------------------- notated export ----
def _q(x: float, grid: float) -> float:
    return round(round(x / grid) * grid, 6)


def _tuplet_spans(spec: dict, layer_name: str | None) -> list[tuple[float, float, int, int]]:
    return [(float(t["start_beat"]), float(t["dur_beats"]), int(t["ratio"][0]), int(t["ratio"][1]))
            for t in (spec.get("notation") or {}).get("tuplets") or []
            if t.get("layer") == layer_name and len(t.get("ratio") or []) == 2]


def _tuplet_at(spans, beat: float):
    for t0, d, a, n in spans:
        if t0 - 1e-9 <= beat < t0 + d - 1e-9:
            return t0, a, n
    return None


def _notated_events(spec: dict, layer: dict, grid: float) -> list[dict]:
    """Quantized onset groups for one layer. Same-onset notes form one chord with the
    longest duration, truncated at the next onset. Inside a tuplet span the *written*
    value is quantized (a triplet quarter stays a quarter) and the sounding duration
    follows from the ratio. Articulation, slur, lyric and velocity ride on the group."""
    spans = _tuplet_spans(spec, layer.get("name"))
    groups: dict[int, dict] = {}
    for e in layer["notes"]:
        if "note" not in e:
            continue
        start, dur = float(e["start_beat"]), float(e["dur_beats"])
        tup = _tuplet_at(spans, start)
        if tup:
            t0, a, n = tup
            w_on = _q((start - t0) * a / n, grid)
            w_dur = max(grid, _q(dur * a / n, grid))
            on, dur_t = _tick(t0 + w_on * n / a), int(round(w_dur * n / a * TPQ))
        else:
            on, dur_t = _tick(_q(start, grid)), _tick(max(grid, _q(dur, grid)))
        g = groups.setdefault(on, {"on": on, "pitches": set(), "dur": 0, "art": None, "slur": None,
                                   "tuplet": (tup[1], tup[2], _tick(tup[0])) if tup else None,
                                   "vel": None})
        g["pitches"].add(e["note"])
        g["dur"] = max(g["dur"], dur_t)
        if e.get("art") not in (None, "sustain") and g["art"] is None:
            g["art"] = e["art"]
        if e.get("slur") is not None and g["slur"] is None:
            g["slur"] = int(e["slur"])
        if e.get("vel") is not None:
            g["vel"] = max(g["vel"] or 0.0, float(e["vel"]))
    events = [groups[k] for k in sorted(groups)]
    for i, g in enumerate(events):
        if i + 1 < len(events):
            g["dur"] = min(g["dur"], events[i + 1]["on"] - g["on"])
        a_n = g["tuplet"]
        g["written"] = int(round(g["dur"] * a_n[0] / a_n[1])) if a_n else g["dur"]
        g["pitches"] = sorted(g["pitches"], key=_midi_note)
    events = [g for g in events if g["dur"] > 0]
    # `art legato` runs become slurs (synthetic ids) unless the notes already carry one
    gid, run = _LEGATO_SLUR_BASE, False
    for g in events:
        if g["art"] == "legato" and g["slur"] is None:
            if not run:
                gid += 1
                run = True
            g["slur"] = gid
        else:
            run = False
    for key in ("slur", "tuplet"):
        first: dict = {}
        last: dict = {}
        for g in events:
            if g[key] is not None:
                first.setdefault(g[key], g)
                last[g[key]] = g
        for k, g in first.items():
            g[f"{key}_start"] = ((k - 1) % 6) + 1 if key == "slur" else True
        for k, g in last.items():
            g[f"{key}_stop"] = ((k - 1) % 6) + 1 if key == "slur" else True
    for entry in (spec.get("notation") or {}).get("lyrics") or []:
        if entry.get("layer") != layer.get("name"):
            continue
        syllables = str(entry.get("text", "")).split()
        start = _tick(entry.get("start_beat", 0.0))
        for g in events:
            if not syllables:
                break
            if g["on"] >= start and not g.get("lyric"):
                g["lyric"] = syllables.pop(0)
    return events


def _notated_parts(spec: dict, grid: float) -> list[dict]:
    parts = []
    for layer in _pitched_layers(spec):
        events = _notated_events(spec, layer, grid)
        if events:
            mids = sorted(_midi_note(p) for g in events for p in g["pitches"])
            parts.append({"id": f"P{len(parts) + 1}", "name": layer.get("name", "part"),
                          "clef": "G" if mids[len(mids) // 2] >= 60 else "F",
                          "events": events, "layer": layer})
    return parts


def _segments(events: list[dict], spans: list[tuple[int, int]], bar: int, pickup: int) -> dict[int, list[dict]]:
    """Split events at barlines into per-measure segments, tying the pieces; marks that
    belong to the whole event sit on its first (start marks) or last (stop marks) piece."""
    by_m: dict[int, list[dict]] = {}
    for g in events:
        t, end = g["on"], g["on"] + g["dur"]
        a_n = g["tuplet"]
        pieces = []
        while t < end:
            mi = _span_of(t, bar, pickup)
            s0, s1 = spans[mi]
            seg_end = min(end, s1)
            seg = {"start": t - s0, "dur": seg_end - t, "pitches": g["pitches"],
                   "tie_stop": t > g["on"], "tie_start": seg_end < end, "vel": g["vel"]}
            if a_n:
                seg["time_mod"] = (a_n[0], a_n[1])
                seg["written"] = int(round(seg["dur"] * a_n[0] / a_n[1]))
            by_m.setdefault(mi, []).append(seg)
            pieces.append(seg)
            t = seg_end
        if pieces:
            pieces[0].update({k: g[k] for k in ("art", "slur_start", "tuplet_start", "lyric") if g.get(k)})
            pieces[-1].update({k: g[k] for k in ("slur_stop", "tuplet_stop") if g.get(k)})
    return by_m


def _holds_in(hold_ticks: list[int], a: int, b: int) -> bool:
    return any(a < h <= b for h in hold_ticks)


def export_notated_musicxml(spec: dict, *, beats_per_bar: int | None = None,
                            grid: float = NOTATED_GRID) -> str:
    """Formal MusicXML (quantized to ``grid``; measures, keys, tempi, dynamics,
    articulations, slurs, tuplets, lyrics, fermatas, rehearsal marks, repeat barlines
    and the anacrusis from the spec). ``beats_per_bar`` overrides the meter's beat
    count for the legacy ``--bars`` flag; leave it ``None`` to trust the spec."""
    parts = _notated_parts(spec, grid)
    if not parts:
        raise ValueError("no pitched layers to notate")
    pickup = _pickup_ticks(spec)
    keys = _key_points(spec)
    score_dirs: list[tuple[int, str, object]] = \
        [(_tick(b), "metronome", bpm) for b, bpm in tempo_marks(spec, grid)] + \
        [(_tick(sec["start_beat"]), "rehearsal", sec["name"]) for sec in _sections(spec)]
    hold_ticks = [_tick(h["beat"]) for h in spec.get("holds") or [] if "beat" in h]
    repeats = _repeat_spans(spec) if repeats_align_with_barlines(spec, beats_per_bar) else []
    root = _score_root(spec, parts)
    for pi, p in enumerate(parts):
        beats, unit, bar = _bar_ticks(spec, p["name"], beats_per_bar)
        total = max(g["on"] + g["dur"] for g in p["events"])
        spans = _spans(total, bar, pickup)
        by_m = _segments(p["events"], spans, bar, pickup)
        dirs = (score_dirs if pi == 0 else []) + _dynamic_directions(p["layer"])
        part = ET.SubElement(root, "part", id=p["id"])
        key_prev = None
        pizz = False
        for mi, (s0, s1) in enumerate(spans):
            measure = ET.SubElement(part, "measure", number=str(mi if pickup > 0 else mi + 1))
            if pickup > 0 and mi == 0:
                measure.set("implicit", "yes")
            if any(start == s0 for start, _, _ in repeats):
                _barline(measure, "left")
            key = _key_at(keys, s0)
            if mi == 0:
                _attributes(measure, divisions=TPQ, key=key, time=(beats, unit), clef=p["clef"])
            elif key != key_prev:
                _attributes(measure, key=key)
            key_prev = key
            pending = sorted(((t - s0, _DIR_RANK.get(kind, 2), kind, value)
                              for t, kind, value in dirs if s0 <= t < s1), key=lambda x: (x[0], x[1]))

            def flush(boundary: int):
                while pending and pending[0][0] <= boundary:
                    tick, _, kind, value = pending.pop(0)
                    _direction(measure, tick - boundary, "wedge" if kind == "wedge_stop" else kind,
                               value, placement="below" if kind in ("dynamics", "wedge", "wedge_stop") else "above")

            pos = 0
            for seg in sorted(by_m.get(mi, []), key=lambda x: x["start"]):
                if seg["start"] > pos:
                    flush(pos)
                    _emit_rest(measure, seg["start"] - pos, fermata=_holds_in(hold_ticks, s0 + pos, s0 + seg["start"]))
                    pos = seg["start"]
                flush(pos)
                if not seg["tie_stop"]:
                    if seg.get("art") == "pizzicato" and not pizz:
                        _direction(measure, 0, "words", ("pizz.", True))
                        pizz = True
                    elif pizz and seg.get("art") != "pizzicato":
                        _direction(measure, 0, "words", ("arco", False))
                        pizz = False
                _emit_seg(measure, seg, fermata=_holds_in(hold_ticks, s0 + seg["start"], s0 + seg["start"] + seg["dur"]))
                pos = seg["start"] + seg["dur"]
            if pos < s1 - s0:
                flush(pos)
                _emit_rest(measure, s1 - s0 - pos, fermata=_holds_in(hold_ticks, s0 + pos, s1))
                pos = s1 - s0
            flush(pos)
            for _, end, times in repeats:
                if end == s1:
                    _barline(measure, "right", times=times)
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding="unicode")


# ---------------------------------------------------------------- import ----
def _pitch_name(pitch, dropped: list[dict], where: dict) -> str:
    step = pitch.findtext("step", default="C").upper()
    alter = float(pitch.findtext("alter", default="0"))
    octave = pitch.findtext("octave", default="4")
    if alter != int(alter):
        dropped.append({"construct": "microtonal_alter", "alter": alter, **where})
        alter = round(alter)
    alter = int(alter)
    if alter in (-1, 0, 1):
        return f"{step}{'#' if alter > 0 else 'b' if alter < 0 else ''}{octave}"
    return _note_name(_midi_note(f"{step}{octave}") + alter)


def _dur_beats(el, divisions: int) -> float:
    return int(float(el.findtext("duration", default="0"))) / divisions


def _art_from_notations(nots) -> str | None:
    for group, tag in _XML_ARTICULATION:
        if nots.find(f"{group}/{tag}") is not None:
            return _XML_ARTICULATION[(group, tag)]
    return None


def import_musicxml(text: str, asset_id: str = "imported_musicxml") -> dict:
    """Read a ``score-partwise`` document into an IR spec: one ``notes`` layer per
    ``<part>`` (named from ``part-name``), exact onsets from the MusicXML cursor
    (``<chord/>``, ``<backup>``, ``<forward>``, voices), per-measure
    ``divisions`` / ``<time>`` / ``<key>`` / tempo, tied notes merged into one
    event, and the notation marks the IR can hold: dynamics (marks -> layer
    `dynamic` points), articulations, slurs, tuplets, lyrics, rehearsal marks
    (-> `score.sections`), repeat barlines (-> `score.repeats`), fermatas (-> a
    hold of the note's own length; the sign carries no duration) and the note
    `dynamics` attribute (-> `vel`). Metronome marks import as tempo steps.
    Constructs the IR cannot hold (unpitched or grace notes, mid-piece time
    signature changes, microtonal alters, unknown marks, empty parts) are listed
    under ``_meta.import.dropped`` instead of vanishing.
    """
    root = ET.fromstring(text)
    if root.tag != "score-partwise":
        raise ValueError(f"unsupported MusicXML root <{root.tag}>; "
                         "only score-partwise documents are supported")
    marks = _dynamic_marks()
    part_names = {sp.get("id"): (sp.findtext("part-name") or "").strip()
                  for sp in root.iter("score-part")}
    tempo: dict[float, float] = {}
    keysig: dict[float, tuple[int, str]] = {}
    meters: list[tuple[float, int, int]] = []
    rehearsal: dict[float, str] = {}
    repeats_found: list[tuple[float, float, int]] = []
    holds: dict[float, float] = {}
    tuplets: list[dict] = []
    lyrics: list[dict] = []
    dropped: list[dict] = []
    pickup: float | None = None
    layers: list[dict] = []
    used: set[str] = set()
    slur_ids = 0
    for pi, part in enumerate(root.findall("part")):
        pid = part.get("id") or f"P{pi + 1}"
        divisions = TPQ
        measure_start = 0.0
        cur_meter: tuple[int, int] | None = None
        notes: list[dict] = []
        dyn_points: dict[float, float] = {}
        pending: dict[tuple[str, str], dict] = {}
        open_slurs: dict[str, int] = {}
        open_repeat: float | None = None
        pizz = False
        tup: dict | None = None
        lyr: dict | None = None
        layer_name = layer_ident(part_names.get(pid, ""), f"part{pi + 1}", used)
        for mi, measure in enumerate(part.findall("measure")):
            cursor = extent = last_start = 0.0
            for el in measure:
                tag = el.tag
                here = {"part": pid, "measure": measure.get("number")}
                if tag == "attributes":
                    d = el.findtext("divisions")
                    if d:
                        divisions = max(1, int(float(d)))
                    for tm in el.findall("time"):
                        b, u = tm.findtext("beats"), tm.findtext("beat-type")
                        if b and u:
                            ts = (sum(int(x) for x in b.split("+")), int(u))
                            if ts != cur_meter:
                                meters.append((round(measure_start + cursor, 6), *ts))
                                cur_meter = ts
                    for k in el.findall("key"):
                        f = k.findtext("fifths")
                        if f is not None:
                            keysig.setdefault(round(measure_start + cursor, 6),
                                              (int(f), (k.findtext("mode") or "major").lower()))
                elif tag == "direction":
                    off = el.findtext("offset")
                    beat = round(measure_start + cursor + (float(off) / divisions if off else 0.0), 6)
                    snd = el.find("sound")
                    val = (snd.get("tempo") if snd is not None else None) \
                        or el.findtext(".//metronome/per-minute")
                    if val:
                        try:
                            tempo.setdefault(beat, float(val))
                        except ValueError:
                            dropped.append({"construct": "tempo_text", "value": val, **here})
                    dyn = el.find("direction-type/dynamics")
                    if dyn is not None and len(dyn):
                        if dyn[0].tag in marks:
                            dyn_points.setdefault(beat, marks[dyn[0].tag])
                        else:
                            dropped.append({"construct": "dynamic_mark", "value": dyn[0].tag, **here})
                    reh = el.findtext("direction-type/rehearsal")
                    if reh:
                        rehearsal.setdefault(beat, reh.strip())
                    words = (el.findtext("direction-type/words") or "").strip().lower()
                    if snd is not None and snd.get("pizzicato") in ("yes", "no"):
                        pizz = snd.get("pizzicato") == "yes"
                    elif words.startswith("pizz"):
                        pizz = True
                    elif words == "arco":
                        pizz = False
                elif tag == "sound" and el.get("tempo"):
                    tempo.setdefault(round(measure_start + cursor, 6), float(el.get("tempo")))
                elif tag == "barline":
                    rep = el.find("repeat")
                    if rep is not None:
                        if rep.get("direction") == "forward":
                            open_repeat = round(measure_start, 6)
                        elif pi == 0:
                            repeats_found.append((open_repeat or 0.0, round(measure_start + extent, 6),
                                                  int(rep.get("times") or 2)))
                            open_repeat = None
                elif tag == "backup":
                    cursor -= _dur_beats(el, divisions)
                elif tag == "forward":
                    cursor += _dur_beats(el, divisions)
                    extent = max(extent, cursor)
                elif tag == "note":
                    if el.find("grace") is not None or el.find("duration") is None:
                        if el.find("rest") is None:
                            dropped.append({"construct": "grace_note", **here})
                        continue
                    dur = _dur_beats(el, divisions)
                    if el.find("chord") is not None:
                        start = last_start
                    else:
                        start = cursor
                        cursor = start + dur
                        last_start = start
                    extent = max(extent, start + dur)
                    is_rest = el.find("rest") is not None
                    if is_rest or dur <= 0:
                        if el.find("lyric") is None:
                            lyr = None
                        if el.find("time-modification") is None:
                            tup = None
                        continue
                    pitch = el.find("pitch")
                    if pitch is None:
                        dropped.append({"construct": "unpitched", **here})
                        continue
                    name = _pitch_name(pitch, dropped, here)
                    abs_start = round(measure_start + start, 6)
                    nots = el.find("notations")
                    if nots is not None and nots.find("fermata") is not None:
                        holds.setdefault(round(abs_start + dur, 6), abs_start)   # end -> start
                    tie_key = (el.findtext("voice") or "1", name)
                    ties = {t.get("type") for t in el.findall("tie")} \
                        or ({t.get("type") for t in nots.findall("tied")} if nots is not None else set())
                    if "stop" in ties and tie_key in pending:
                        ev = pending.pop(tie_key)
                        ev["dur_beats"] = round(abs_start + dur - ev["start_beat"], 6)
                        if "start" in ties:
                            pending[tie_key] = ev
                        continue
                    ev = {"note": name, "start_beat": abs_start, "dur_beats": round(dur, 6)}
                    if el.get("dynamics"):
                        ev["vel"] = _vel_from_attr(el.get("dynamics"))
                    bend_alter = el.findtext(".//bend/bend-alter")
                    if bend_alter is not None:
                        ev["curves"] = [{
                            "target": "pitch_cents", "time_basis": "note_beats",
                            "points": [[0.0, 0.0],
                                       [ev["dur_beats"], round(float(bend_alter) * 100.0, 6)]],
                        }]
                    art = _art_from_notations(nots) if nots is not None else None
                    if art is None and pizz:
                        art = "pizzicato"
                    if art:
                        ev["art"] = art
                    if nots is not None:
                        for sl in nots.findall("slur"):
                            num = sl.get("number") or "1"
                            if sl.get("type") == "start":
                                slur_ids += 1
                                open_slurs[num] = slur_ids
                            elif sl.get("type") == "stop" and num in open_slurs:
                                ev["slur"] = open_slurs.pop(num)
                        for group in ("articulations", "ornaments", "technical"):
                            g = nots.find(group)
                            for child in (g if g is not None else []):
                                if (group, child.tag) not in _XML_ARTICULATION:
                                    dropped.append({"construct": "articulation", "value": child.tag, **here})
                    if "slur" not in ev and open_slurs:
                        ev["slur"] = min(open_slurs.values())
                    if el.find("chord") is None:
                        tm = el.find("time-modification")
                        if tm is not None:
                            ratio = [int(tm.findtext("actual-notes")), int(tm.findtext("normal-notes"))]
                            if tup and tup["ratio"] == ratio and abs(tup["end"] - abs_start) < 1e-4:
                                tup["end"] = round(abs_start + dur, 6)
                            else:
                                tup = {"layer": layer_name, "start_beat": abs_start, "end": round(abs_start + dur, 6), "ratio": ratio}
                                tuplets.append(tup)
                        else:
                            tup = None
                        ly = el.find("lyric")
                        if ly is not None and ly.findtext("text"):
                            word = ly.findtext("text").strip()
                            if lyr is not None and abs(lyr["_next"] - abs_start) < 1e-4:
                                lyr["_words"].append(word)
                            else:
                                lyr = {"layer": layer_name, "start_beat": abs_start, "_words": [word]}
                                lyrics.append(lyr)
                            lyr["_next"] = round(abs_start + dur, 6)
                        else:
                            lyr = None
                    notes.append(ev)
                    if "start" in ties:
                        pending[tie_key] = ev
            nominal = cur_meter[0] * 4.0 / cur_meter[1] if cur_meter else None
            if (pi == 0 and mi == 0 and nominal and extent > 0
                    and (measure.get("implicit") == "yes" or extent < nominal - 1e-6)):
                pickup = round(extent, 6)
            measure_start += extent if extent > 0 else (nominal or 0.0)
        if notes:
            used.add(layer_name)
            layer: dict = {"name": layer_name, "type": "notes", "osc": "sine",
                           "env": {"attack": 0.01, "decay": 0.1, "sustain": 0.8, "release": 0.1},
                           "notes": sorted(notes, key=lambda n: (n["start_beat"], _midi_note(n["note"])))}
            if dyn_points:
                pts = [[b, v] for b, v in sorted(dyn_points.items())]
                layer["dynamic"] = pts
                layer["automation"] = [{"target": "dynamic", "time_basis": "layer_beats", "points": pts}]
            layers.append(layer)
        else:
            dropped.append({"construct": "empty_part", "part": pid})

    tempo_marks_found = sorted(tempo.items()) or [(0.0, 120.0)]
    if tempo_marks_found[0][0] != 0.0:
        tempo_marks_found.insert(0, (0.0, tempo_marks_found[0][1]))
    tempo_marks_found = [p for i, p in enumerate(tempo_marks_found)
                         if i == 0 or p[1] != tempo_marks_found[i - 1][1]]
    tempo_pts = stepped_tempo_map(tempo_marks_found)
    bpm = tempo_pts[0][1]
    key_pts = sorted(keysig.items())
    key_names = [(beat, *_fifths_key(f, m).split()) for beat, (f, m) in key_pts]
    key_names = [k for i, k in enumerate(key_names) if i == 0 or k[1:] != key_names[i - 1][1:]]
    total_beats = max((n["start_beat"] + n["dur_beats"] for layer in layers for n in layer["notes"]),
                      default=1.0)
    from .sequencer import TempoMap   # sequencer is heavy; only the importer needs it
    tmap = TempoMap(tempo_pts)
    spec: dict = {
        "id": asset_id, "kind": "cue",
        "duration_s": round(tmap.sec(total_beats) + sum(
            tmap.sec(end) - tmap.sec(start) for end, start in holds.items()), 3),
        "bpm": round(bpm, 6),
        "layers": layers or [{"name": "musicxml", "type": "notes", "osc": "sine",
                              "env": {"attack": 0.01, "decay": 0.1, "sustain": 0.8, "release": 0.1},
                              "notes": []}],
        "master": {"target_peak_dbfs": -1.0},
    }
    if len(tempo_pts) > 1:
        spec["tempo_map"] = [[b, v] for b, v in tempo_pts]
    if key_names:
        spec["key"] = f"{key_names[0][1]} {key_names[0][2]}"
        if len(key_names) > 1:
            spec["key_map"] = [[b, t, m] for b, t, m in key_names]
    if holds:   # a fermata holds for the note's own length at the tempo in force
        spec["holds"] = [{"beat": end, "duration_s": round(tmap.sec(end) - tmap.sec(start), 6)}
                         for end, start in sorted(holds.items())]
    score: dict = {}
    if meters:
        score["meter"] = {"beats": meters[0][1], "unit": meters[0][2]}
        for beat, b, u in meters[1:]:
            dropped.append({"construct": "time_signature_change", "beat": beat, "meter": [b, u]})
    if pickup:
        score["pickup_beats"] = pickup
    sections: list[dict] = []
    if rehearsal:
        starts = sorted(rehearsal)
        for i, b in enumerate(starts):
            end = starts[i + 1] if i + 1 < len(starts) else round(total_beats, 6)
            sections.append({"name": layer_ident(rehearsal[b], f"section{i + 1}", {s["name"] for s in sections}),
                             "start_beat": b, "dur_beats": round(end - b, 6), "end_beat": end})
    if repeats_found:
        score["repeats"] = []
        for start, end, times in repeats_found:
            match = next((s for s in sections if abs(s["start_beat"] - start) < 1e-6
                          and abs(s["end_beat"] - end) < 1e-6), None)
            if match is None:
                match = {"name": f"repeat{len(score['repeats']) + 1}", "start_beat": start,
                         "dur_beats": round(end - start, 6), "end_beat": end}
                sections.append(match)
            score["repeats"].append({"section": match["name"], "count": times})
    if sections:
        score["sections"] = sorted(sections, key=lambda s: s["start_beat"])
    if score:
        spec["score"] = score
    notation: dict = {}
    if tuplets:
        notation["tuplets"] = [{"layer": t["layer"], "start_beat": t["start_beat"],
                                "dur_beats": round(t["end"] - t["start_beat"], 6), "ratio": t["ratio"]}
                               for t in tuplets]
    if lyrics:
        notation["lyrics"] = [{"layer": l["layer"], "start_beat": l["start_beat"], "text": " ".join(l["_words"])}
                              for l in lyrics]
    if notation:
        spec["notation"] = notation
    if dropped:
        spec["_meta"] = {"import": {"format": "musicxml", "dropped": dropped}}
    return spec
