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
