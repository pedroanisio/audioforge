"""MIDI/MusicXML interop for the explicit note-event IR."""
from __future__ import annotations

import hashlib
import json
import struct
import xml.etree.ElementTree as ET
from pathlib import Path

from . import theory
from .determinism import spec_hash

TPQ = 480


def interop_diagnostics(spec: dict, format: str) -> list[dict]:
    """Return structured lossy-conversion warnings for an export target."""
    warnings = []
    if spec.get("notation", {}).get("lyrics") and format in {"midi", "musicxml"}:
        warnings.append({
            "severity": "warning",
            "code": "lossy_lyrics",
            "message": f"{format} exporter preserves notes but not lyric metadata",
        })
    for layer_i, layer in enumerate(spec.get("layers", [])):
        for note_i, ev in enumerate(layer.get("notes", [])):
            if ev.get("art") and format == "midi":
                warnings.append({
                    "severity": "warning",
                    "code": "lossy_articulation",
                    "message": "MIDI export drops note articulation metadata",
                    "path": f"layer:{layer.get('name', layer.get('type'))}",
                })
            for curve in ev.get("curves", []) or []:
                target = curve.get("target")
                if target == "pitch_cents":
                    warnings.append({
                        "severity": "warning",
                        "code": "lossy_pitch_curve",
                        "message": (
                            f"{format} exporter does not project arbitrary "
                            "AudioForge pitch_cents note curves"
                        ),
                        "path": f"layers[{layer_i}].notes[{note_i}].curves",
                    })
                elif target == "dynamic":
                    warnings.append({
                        "severity": "warning",
                        "code": "lossy_dynamic_curve",
                        "message": (
                            f"{format} exporter preserves notes but not "
                            "AudioForge through-note dynamic curves"
                        ),
                        "path": f"layers[{layer_i}].notes[{note_i}].curves",
                    })
        for curve_i, curve in enumerate(layer.get("automation", []) or []):
            if curve.get("target") == "pitch_cents":
                warnings.append({
                    "severity": "warning",
                    "code": "lossy_pitch_curve",
                    "message": (
                        f"{format} exporter does not project arbitrary "
                        "AudioForge pitch_cents automation curves"
                    ),
                    "path": f"layers[{layer_i}].automation[{curve_i}]",
                })
            elif curve.get("target") == "dynamic":
                warnings.append({
                    "severity": "warning",
                    "code": "lossy_dynamic_curve",
                    "message": (
                        f"{format} exporter preserves notes but not "
                        "AudioForge dynamic automation curves"
                    ),
                    "path": f"layers[{layer_i}].automation[{curve_i}]",
                })
    return warnings


def export_session_bundle(spec: dict, outdir: str | Path) -> dict:
    """Write a deterministic, manifest-backed session/stems bundle skeleton."""
    from .plan import build_render_plan, dumps_plan

    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    spec_path = out / f"{spec['id']}.spec.json"
    spec_text = json.dumps(spec, indent=2, sort_keys=True) + "\n"
    spec_path.write_text(spec_text)
    midi_path = out / f"{spec['id']}.mid"
    midi_bytes = export_midi_bytes(spec)
    midi_path.write_bytes(midi_bytes)
    plan_result = None
    plan_path = None
    plan_text = None
    plan_warning = None
    try:
        plan_result = build_render_plan(spec)
        plan_path = out / f"{spec['id']}.plan.json"
        plan_text = dumps_plan(plan_result.plan)
        plan_path.write_text(plan_text)
    except Exception as exc:
        plan_warning = {
            "severity": "warning",
            "code": "render_plan_unavailable",
            "message": f"session bundle omitted render plan: {exc}",
        }
    manifest = {
        "schema": "audioforge.session-bundle/1",
        "id": spec["id"],
        "spec_hash": spec_hash(spec),
        "files": {
            "spec": str(spec_path),
            "midi": str(midi_path),
        },
        "sha256": {
            "spec": hashlib.sha256(spec_text.encode()).hexdigest(),
            "midi": hashlib.sha256(midi_bytes).hexdigest(),
        },
        "warnings": interop_diagnostics(spec, "midi"),
    }
    if plan_result is not None and plan_path is not None and plan_text is not None:
        manifest["plan_hash"] = plan_result.plan_hash
        manifest["files"]["plan"] = str(plan_path)
        manifest["sha256"]["plan"] = hashlib.sha256(
            plan_text.encode()).hexdigest()
    if plan_warning is not None:
        manifest["warnings"].append(plan_warning)
    (out / "session.manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    )
    return manifest


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


# General MIDI program-number families -> a renderable (non-native) osc shape.
# Used to voice each imported channel; native-kernel oscillators are avoided so
# an imported file always renders without extra material/kernel dependencies.
_GM_PROGRAM_OSC = [
    (8, "triangle"), (16, "pluck"), (24, "organ"), (32, "pluck"),
    (40, "saw"), (48, "pad"), (56, "pad"), (64, "saw"), (72, "triangle"),
    (80, "triangle"), (88, "saw"), (96, "pad"), (104, "pluck"),
    (112, "pluck"), (120, "pluck"), (128, "triangle"),
]
_PERCUSSIVE_OSC = {"pluck", "saw"}
# GM channel 10 (0-based index 9) is the percussion channel.
_GM_DRUM_CHANNEL = 9
# Floor for imported note duration (beats); keeps zero-length percussion hits
# above the IR's dur_beats minimum while staying rhythmically negligible.
_MIN_DUR_BEATS = 0.02


def _layer_ident(text: str, fallback: str, used: set[str]) -> str:
    """Coerce a MIDI track name into a unique DSL IDENT.

    The grammar's IDENT is ``letter , { letter | digit | "_" | "#" }`` — no
    hyphens, spaces, or leading digits — and layer names must be unique so the
    decompiled ``.af`` round-trips. Invalid runs collapse to ``_``; a numeric
    suffix disambiguates collisions.
    """
    import re

    cleaned = re.sub(r"[^A-Za-z0-9_#]+", "_", (text or "").strip()).strip("_")
    if not cleaned or not cleaned[0].isalpha():
        cleaned = fallback if (fallback and fallback[0].isalpha()) else f"L_{cleaned}"
    candidate = cleaned
    n = 2
    while candidate in used:
        candidate = f"{cleaned}_{n}"
        n += 1
    return candidate


def _osc_for_program(program: int) -> str:
    for ceiling, shape in _GM_PROGRAM_OSC:
        if program < ceiling:
            return shape
    return "triangle"


def _env_for_osc(osc: str) -> dict:
    if osc in _PERCUSSIVE_OSC:
        return {"attack": 0.002, "decay": 0.12, "sustain": 0.0, "release": 0.14}
    return {"attack": 0.01, "decay": 0.1, "sustain": 0.8, "release": 0.18}


def _split_tracks(data: bytes) -> tuple[int, int, list[bytes]]:
    """Return (format, division, [track_bytes...]) for every MTrk chunk."""
    _hlen, fmt, _ntrks, division = struct.unpack(">IHHH", data[4:14])
    tracks: list[bytes] = []
    pos = data.index(b"MTrk", 14)
    while pos + 8 <= len(data) and data[pos:pos + 4] == b"MTrk":
        length = struct.unpack(">I", data[pos + 4:pos + 8])[0]
        tracks.append(data[pos + 8:pos + 8 + length])
        pos += 8 + length
    return fmt, division, tracks


def import_midi_bytes(data: bytes, asset_id: str = "imported_midi") -> dict:
    """Import a Standard MIDI File (format 0 or 1) into an IR spec.

    Each ``(track, channel)`` that carries notes becomes its own ``notes``
    layer voiced from its GM program; the percussion channel (10) is voiced
    percussively. Running status, multi-track files, meta and SysEx events are
    handled; per-channel pitch bend (with RPN sensitivity) projects to a
    layer-scope ``pitch_cents`` automation curve.

    ⚠ ARCHITECTURAL CONTRACT (PALS's LAW) — the returned spec is the parser's
    *claim*; callers compile/validate it (``ir_schema`` / ``AudioForge``)
    before trusting it. The parser never asserts the file's musical intent.
    """
    if not data.startswith(b"MThd"):
        raise ValueError("not a MIDI file")
    _hlen, _fmt, _ntrks, division = struct.unpack(">IHHH", data[4:14])
    if division & 0x8000:
        raise ValueError("SMPTE time-division MIDI files are not supported; "
                         "only ticks-per-quarter (PPQ) division")
    _fmt, division, tracks = _split_tracks(data)

    bpm = 120.0
    bpm_set = False
    # (track_index, channel) -> accumulated state for that voice.
    voices: dict[tuple[int, int], dict] = {}

    def voice(ti: int, ch: int) -> dict:
        return voices.setdefault((ti, ch), {
            "notes": [], "active": {}, "program": 0,
            "rpn": [None, None], "bend_range_cents": 200.0,
            "pitch_points": [],
        })

    track_name: dict[int, str] = {}
    for ti, track in enumerate(tracks):
        i = tick = 0
        status = 0
        while i < len(track):
            delta, i = _read_vlq(track, i)
            tick += delta
            head = track[i]
            if head & 0x80:                       # new status byte
                status = head
                i += 1
            # else: running status — reuse previous `status`, data starts here
            if status == 0xFF:
                meta = track[i]; i += 1
                ln, i = _read_vlq(track, i)
                payload = track[i:i + ln]; i += ln
                if meta == 0x51 and ln == 3 and not bpm_set:
                    bpm = 60_000_000 / int.from_bytes(payload, "big")
                    bpm_set = True
                elif meta == 0x03 and ti not in track_name:
                    track_name[ti] = payload.decode("latin-1", "replace").strip()
                elif meta == 0x2F:
                    break
                continue
            if status in (0xF0, 0xF7):             # SysEx — length-prefixed, skip
                ln, i = _read_vlq(track, i)
                i += ln
                continue
            kind = status & 0xF0
            ch = status & 0x0F
            if kind in (0x90, 0x80):
                note, vel = track[i], track[i + 1]
                i += 2
                v = voice(ti, ch)
                if kind == 0x90 and vel:
                    v["active"].setdefault(note, []).append((tick, vel))
                elif v["active"].get(note):
                    st, vv = v["active"][note].pop(0)
                    # Floor duration: zero-length hits (same-tick on/off, common
                    # for percussion) would violate the IR's dur_beats minimum.
                    dur = max(round((tick - st) / division, 6), _MIN_DUR_BEATS)
                    v["notes"].append({
                        "note": _note_name(note),
                        "start_beat": round(st / division, 6),
                        "dur_beats": dur,
                        "vel": round(vv / 127.0, 4),
                    })
            elif kind == 0xC0:                     # program change
                voice(ti, ch)["program"] = track[i]; i += 1
            elif kind == 0xD0:                     # channel pressure
                i += 1
            elif kind == 0xA0:                     # poly aftertouch
                i += 2
            elif kind == 0xB0:                     # control change
                controller, value = track[i], track[i + 1]
                i += 2
                v = voice(ti, ch)
                if controller == 101:
                    v["rpn"][0] = value
                elif controller == 100:
                    v["rpn"][1] = value
                elif controller == 6 and v["rpn"] == [0, 0]:
                    v["bend_range_cents"] = float(value) * 100.0
                elif controller == 38 and v["rpn"] == [0, 0]:
                    v["bend_range_cents"] = (
                        int(v["bend_range_cents"] // 100.0) * 100.0 + float(value))
            elif kind == 0xE0:                     # pitch bend
                lsb, msb = track[i], track[i + 1]
                i += 2
                v = voice(ti, ch)
                raw = (msb << 7) | lsb
                d = raw - 8192
                denom = 8191.0 if d >= 0 else 8192.0
                cents = round((d / denom) * v["bend_range_cents"], 6)
                v["pitch_points"].append([round(tick / division, 6), cents])
            else:
                raise ValueError(f"unsupported MIDI event 0x{status:02x}")

    layers = []
    used_names: set[str] = set()
    for (ti, ch), v in voices.items():
        if not v["notes"]:
            continue
        is_drums = ch == _GM_DRUM_CHANNEL
        osc = "pluck" if is_drums else _osc_for_program(v["program"])
        base = track_name.get(ti) or (
            "drums" if is_drums else f"trk{ti}_ch{ch + 1}")
        name = _layer_ident(base, f"layer{ti}_{ch + 1}", used_names)
        used_names.add(name)
        layer = {
            "name": name, "type": "notes", "osc": osc,
            "env": _env_for_osc(osc),
            "notes": sorted(v["notes"],
                            key=lambda n: (n["start_beat"], n["note"])),
        }
        if v["pitch_points"]:
            layer["automation"] = [{
                "target": "pitch_cents",
                "time_basis": "layer_beats",
                "points": v["pitch_points"],
            }]
        layers.append(layer)

    if not layers:
        layers = [{"name": "midi", "type": "notes", "osc": "sine",
                   "env": {"attack": 0.01, "decay": 0.1,
                           "sustain": 0.8, "release": 0.1},
                   "notes": []}]
    dur_beats = max(
        (n["start_beat"] + n["dur_beats"]
         for layer in layers for n in layer["notes"]),
        default=1.0)
    return {
        "id": asset_id, "kind": "cue", "duration_s": round(dur_beats * 60 / bpm, 3),
        "bpm": round(bpm, 6),
        "layers": layers,
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
        dur_beats = round(dur / divisions, 6)
        event = {"note": f"{step}{acc}{octave}",
                 "start_beat": round(tick / divisions, 6),
                 "dur_beats": dur_beats}
        bend_alter = n.findtext(".//bend/bend-alter")
        if bend_alter is not None:
            event["curves"] = [{
                "target": "pitch_cents",
                "time_basis": "note_beats",
                "points": [[0.0, 0.0],
                           [dur_beats, round(float(bend_alter) * 100.0, 6)]],
            }]
        notes.append(event)
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
