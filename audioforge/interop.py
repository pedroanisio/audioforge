"""MIDI/MusicXML interop for the explicit note-event IR."""
from __future__ import annotations

import struct
import xml.etree.ElementTree as ET

from . import theory

TPQ = 480


def _vlq(n: int) -> bytes:
    out = [n & 0x7F]
    n >>= 7
    while n:
        out.append(0x80 | (n & 0x7F))
        n >>= 7
    return bytes(reversed(out))


def _read_vlq(data: bytes, i: int) -> tuple[int, int]:
    n = 0
    while True:
        b = data[i]
        i += 1
        n = (n << 7) | (b & 0x7F)
        if not b & 0x80:
            return n, i


def _midi_note(note: str) -> int:
    return theory.note_to_semis(note) + 12


def _note_name(midi: int) -> str:
    return theory.semis_to_note(midi - 12)


def _notes(spec: dict) -> list[dict]:
    out = []
    for layer in spec.get("layers", []):
        for ev in layer.get("notes", []):
            if "note" in ev:
                out.append(ev)
    return sorted(out, key=lambda e: (e["start_beat"], e["note"]))


def export_midi_bytes(spec: dict) -> bytes:
    bpm = float(spec.get("bpm", 120.0))
    tempo_us = int(round(60_000_000 / bpm))
    events = [(0, b"\xff\x51\x03" + tempo_us.to_bytes(3, "big"))]
    for ev in _notes(spec):
        start = int(round(ev["start_beat"] * TPQ))
        end = int(round((ev["start_beat"] + ev["dur_beats"]) * TPQ))
        note = max(0, min(127, _midi_note(ev["note"])))
        vel = max(1, min(127, int(round(96 * float(ev.get("vel", 0.8))))))
        events.append((start, bytes([0x90, note, vel])))
        events.append((end, bytes([0x80, note, 0])))
    events.sort(key=lambda x: (x[0], x[1][0] == 0x90))
    track = bytearray()
    last = 0
    for tick, payload in events:
        track.extend(_vlq(max(0, tick - last)))
        track.extend(payload)
        last = tick
    track.extend(_vlq(0))
    track.extend(b"\xff\x2f\x00")
    return (b"MThd" + struct.pack(">IHHH", 6, 0, 1, TPQ)
            + b"MTrk" + struct.pack(">I", len(track)) + bytes(track))


def import_midi_bytes(data: bytes, asset_id: str = "imported_midi") -> dict:
    if not data.startswith(b"MThd"):
        raise ValueError("not a MIDI file")
    _hlen, _fmt, _ntrks, division = struct.unpack(">IHHH", data[4:14])
    pos = data.index(b"MTrk", 14)
    length = struct.unpack(">I", data[pos + 4:pos + 8])[0]
    track = data[pos + 8:pos + 8 + length]
    i = tick = 0
    bpm = 120.0
    active: dict[int, tuple[int, int]] = {}
    notes = []
    while i < len(track):
        delta, i = _read_vlq(track, i)
        tick += delta
        status = track[i]
        i += 1
        if status == 0xFF:
            meta = track[i]; i += 1
            ln, i = _read_vlq(track, i)
            payload = track[i:i + ln]; i += ln
            if meta == 0x51 and ln == 3:
                bpm = 60_000_000 / int.from_bytes(payload, "big")
            if meta == 0x2F:
                break
        elif status in (0x90, 0x80):
            note, vel = track[i], track[i + 1]
            i += 2
            if status == 0x90 and vel:
                active[note] = (tick, vel)
            elif note in active:
                st, v = active.pop(note)
                notes.append({
                    "note": _note_name(note),
                    "start_beat": round(st / division, 6),
                    "dur_beats": round((tick - st) / division, 6),
                    "vel": round(v / 127.0, 4),
                })
        else:
            raise ValueError(f"unsupported MIDI event 0x{status:02x}")
    dur_beats = max((n["start_beat"] + n["dur_beats"] for n in notes),
                    default=1.0)
    return {
        "id": asset_id, "kind": "cue", "duration_s": round(dur_beats * 60 / bpm, 3),
        "bpm": round(bpm, 6),
        "layers": [{"name": "midi", "type": "notes", "osc": "sine",
                    "env": {"attack": 0.01, "decay": 0.1,
                            "sustain": 0.8, "release": 0.1},
                    "notes": notes}],
        "master": {"target_peak_dbfs": -1.0},
    }


def export_musicxml(spec: dict) -> str:
    bpm = float(spec.get("bpm", 120.0))
    root = ET.Element("score-partwise", version="3.1")
    plist = ET.SubElement(root, "part-list")
    score_part = ET.SubElement(plist, "score-part", id="P1")
    ET.SubElement(score_part, "part-name").text = spec.get("id", "AudioForge")
    part = ET.SubElement(root, "part", id="P1")
    measure = ET.SubElement(part, "measure", number="1")
    attrs = ET.SubElement(measure, "attributes")
    ET.SubElement(attrs, "divisions").text = str(TPQ)
    if "score" in spec and "meter" in spec["score"]:
        time = ET.SubElement(attrs, "time")
        ET.SubElement(time, "beats").text = str(spec["score"]["meter"]["beats"])
        ET.SubElement(time, "beat-type").text = str(spec["score"]["meter"]["unit"])
    sound = ET.SubElement(measure, "sound")
    sound.set("tempo", str(round(bpm, 3)))
    cursor = 0
    for ev in _notes(spec):
        start = int(round(ev["start_beat"] * TPQ))
        if start > cursor:
            rest = ET.SubElement(measure, "note")
            ET.SubElement(rest, "rest")
            ET.SubElement(rest, "duration").text = str(start - cursor)
            cursor = start
        note = ET.SubElement(measure, "note")
        pitch = ET.SubElement(note, "pitch")
        name = ev["note"]
        step = name[0].upper()
        idx = 1
        ET.SubElement(pitch, "step").text = step
        if idx < len(name) and name[idx] in "#b":
            ET.SubElement(pitch, "alter").text = "1" if name[idx] == "#" else "-1"
            idx += 1
        ET.SubElement(pitch, "octave").text = name[idx:]
        dur = int(round(ev["dur_beats"] * TPQ))
        ET.SubElement(note, "duration").text = str(dur)
        cursor = start + dur
    return ET.tostring(root, encoding="unicode")


# --------------------------------------------------------- notated score ----
# A *formal* MusicXML projection: one staff per layer, durations quantized to a
# grid so they map to standard figures, gaps filled with rests, real measures /
# key / time signature, cross-barline ties. Lossy by construction (the IR's
# non-metric timing is snapped) — the "as notated" view, distinct from the
# exact-tick interchange `export_musicxml` above. Open in MuseScore/LilyPond.
_MAJ_FIFTHS = {"C": 0, "G": 1, "D": 2, "A": 3, "E": 4, "B": 5, "F#": 6, "C#": 7,
               "F": -1, "Bb": -2, "Eb": -3, "Ab": -4, "Db": -5, "Gb": -6, "Cb": -7}
_MIN_FIFTHS = {"A": 0, "E": 1, "B": 2, "F#": 3, "C#": 4, "G#": 5, "D#": 6,
               "D": -1, "G": -2, "C": -3, "F": -4, "Bb": -5, "Eb": -6, "Ab": -7}
# (quarter-fraction, MusicXML type, dots) — largest first, for greedy split
_FIG = [(4.0, "whole", 0), (3.0, "half", 1), (2.0, "half", 0),
        (1.5, "quarter", 1), (1.0, "quarter", 0), (0.75, "eighth", 1),
        (0.5, "eighth", 0), (0.375, "16th", 1), (0.25, "16th", 0),
        (0.125, "32nd", 0)]


def _key_fifths(key: str) -> int:
    p = (key or "C major").split()
    mode = p[1].lower() if len(p) > 1 else "major"
    return (_MIN_FIFTHS if mode == "minor" else _MAJ_FIFTHS).get(p[0], 0)


def _decompose(ticks: int, tpq: int):
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


def _xml_pitch(parent, name: str):
    pit = ET.SubElement(parent, "pitch")
    ET.SubElement(pit, "step").text = name[0].upper()
    i = 1
    if i < len(name) and name[i] in "#b":
        ET.SubElement(pit, "alter").text = "1" if name[i] == "#" else "-1"
        i += 1
    ET.SubElement(pit, "octave").text = name[i:]


def _emit_rest(measure, ticks: int, tpq: int):
    for ft, typ, dots in _decompose(ticks, tpq):
        n = ET.SubElement(measure, "note")
        ET.SubElement(n, "rest")
        ET.SubElement(n, "duration").text = str(ft)
        ET.SubElement(n, "type").text = typ
        for _ in range(dots):
            ET.SubElement(n, "dot")


def _emit_seg(measure, seg, tpq: int):
    figs = _decompose(seg["dur"], tpq)
    for fi, (ft, typ, dots) in enumerate(figs):
        tie_back = (fi > 0) or seg["tie_stop"]
        tie_fwd = (fi < len(figs) - 1) or seg["tie_start"]
        for pi, name in enumerate(seg["pitches"]):
            n = ET.SubElement(measure, "note")
            if pi > 0:
                ET.SubElement(n, "chord")
            _xml_pitch(n, name)
            ET.SubElement(n, "duration").text = str(ft)
            if tie_back:
                ET.SubElement(n, "tie", type="stop")
            if tie_fwd:
                ET.SubElement(n, "tie", type="start")
            ET.SubElement(n, "type").text = typ
            for _ in range(dots):
                ET.SubElement(n, "dot")
            if tie_back or tie_fwd:
                nots = ET.SubElement(n, "notations")
                if tie_back:
                    ET.SubElement(nots, "tied", type="stop")
                if tie_fwd:
                    ET.SubElement(nots, "tied", type="start")


def export_notated_musicxml(spec: dict, *, beats_per_bar: int = 4,
                            grid: float = 0.25) -> str:
    """Formal, engraver-ready MusicXML (quantized; open in MuseScore)."""
    tpq, mt = TPQ, beats_per_bar * TPQ
    fifths = _key_fifths(spec.get("key", "C major"))
    bpm = float(spec.get("bpm", 120.0))

    parts = []
    for layer in spec.get("layers", []):
        raw = [e for e in (layer.get("notes") or []) if "note" in e]
        if not raw:
            continue
        groups = {}
        for e in raw:
            on = round(round(e["start_beat"] / grid) * grid, 4)
            du = max(grid, round(e["dur_beats"] / grid) * grid)
            g = groups.setdefault(on, {"p": set(), "dur": 0.0})
            g["p"].add(e["note"])
            g["dur"] = max(g["dur"], du)
        onsets = sorted(groups)
        events = []
        for i, on in enumerate(onsets):
            nxt = onsets[i + 1] if i + 1 < len(onsets) else on + groups[on]["dur"]
            dur = min(groups[on]["dur"], round(nxt - on, 4))
            if dur > 0:
                events.append((int(round(on * tpq)), int(round(dur * tpq)),
                               sorted(groups[on]["p"], key=_midi_note)))
        if events:
            mids = sorted(_midi_note(p) for _, _, ps in events for p in ps)
            parts.append({"id": f"P{len(parts) + 1}",
                          "name": layer.get("name", "part"),
                          "clef": "G" if mids[len(mids) // 2] >= 60 else "F",
                          "events": events})
    if not parts:
        raise ValueError("no pitched layers to notate")

    total = max(ev[0] + ev[1] for p in parts for ev in p["events"])
    measures = max(1, (total + mt - 1) // mt)

    root = ET.Element("score-partwise", version="3.1")
    ET.SubElement(ET.SubElement(root, "work"), "work-title").text = \
        spec.get("id", "AudioForge")
    plist = ET.SubElement(root, "part-list")
    for p in parts:
        ET.SubElement(ET.SubElement(plist, "score-part", id=p["id"]),
                      "part-name").text = p["name"]
    for pi, p in enumerate(parts):
        part = ET.SubElement(root, "part", id=p["id"])
        by_m = {}
        for on, dur, pitches in p["events"]:        # split at barlines, tie
            t, end = on, on + dur
            while t < end:
                m = t // mt
                seg_end = min(end, (m + 1) * mt)
                by_m.setdefault(int(m), []).append(
                    {"start": t - m * mt, "dur": seg_end - t, "pitches": pitches,
                     "tie_stop": t > on, "tie_start": seg_end < end})
                t = seg_end
        for m in range(measures):
            measure = ET.SubElement(part, "measure", number=str(m + 1))
            if m == 0:
                at = ET.SubElement(measure, "attributes")
                ET.SubElement(at, "divisions").text = str(tpq)
                ET.SubElement(ET.SubElement(at, "key"), "fifths").text = str(fifths)
                tm = ET.SubElement(at, "time")
                ET.SubElement(tm, "beats").text = str(beats_per_bar)
                ET.SubElement(tm, "beat-type").text = "4"
                cl = ET.SubElement(at, "clef")
                ET.SubElement(cl, "sign").text = p["clef"]
                ET.SubElement(cl, "line").text = "2" if p["clef"] == "G" else "4"
                if pi == 0:
                    ET.SubElement(measure, "sound").set("tempo", str(round(bpm, 3)))
            pos = 0
            for s in sorted(by_m.get(m, []), key=lambda s: s["start"]):
                if s["start"] > pos:
                    _emit_rest(measure, s["start"] - pos, tpq)
                _emit_seg(measure, s, tpq)
                pos = s["start"] + s["dur"]
            if pos < mt:
                _emit_rest(measure, mt - pos, tpq)
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + \
        ET.tostring(root, encoding="unicode")


def import_musicxml(text: str, asset_id: str = "imported_musicxml") -> dict:
    root = ET.fromstring(text)
    divisions = int(root.findtext(".//divisions", default=str(TPQ)))
    sound = root.find(".//sound")
    bpm = float(sound.get("tempo", 120.0)) if sound is not None else 120.0
    tick = 0
    notes = []
    for n in root.findall(".//part/measure/note"):
        dur = int(n.findtext("duration", default="0"))
        if n.find("rest") is not None:
            tick += dur
            continue
        pitch = n.find("pitch")
        step = pitch.findtext("step")
        alter = int(pitch.findtext("alter", default="0"))
        octave = pitch.findtext("octave")
        acc = "#" if alter > 0 else "b" if alter < 0 else ""
        notes.append({"note": f"{step}{acc}{octave}",
                      "start_beat": round(tick / divisions, 6),
                      "dur_beats": round(dur / divisions, 6)})
        tick += dur
    dur_beats = max((n["start_beat"] + n["dur_beats"] for n in notes),
                    default=1.0)
    return {
        "id": asset_id, "kind": "cue", "duration_s": round(dur_beats * 60 / bpm, 3),
        "bpm": bpm,
        "layers": [{"name": "musicxml", "type": "notes", "osc": "sine",
                    "env": {"attack": 0.01, "decay": 0.1,
                            "sustain": 0.8, "release": 0.1},
                    "notes": notes}],
        "master": {"target_peak_dbfs": -1.0},
    }
