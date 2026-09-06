"""MIDI/MusicXML interop for the explicit note-event IR."""
from __future__ import annotations

import hashlib
import json
import struct
import xml.etree.ElementTree as ET
from pathlib import Path

from .determinism import spec_hash
from .musicxml import (TPQ, _midi_note, _note_name, export_musicxml,  # noqa: F401
                       export_notated_musicxml, import_musicxml, layer_ident,
                       tempo_marks, tempo_points)

_layer_ident = layer_ident


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


def _notes(spec: dict) -> list[dict]:
    out = []
    for layer in spec.get("layers", []):
        for ev in layer.get("notes", []):
            if "note" in ev:
                out.append(ev)
    return sorted(out, key=lambda e: (e["start_beat"], e["note"]))


def _pitched_layers(spec: dict) -> list[dict]:
    return [layer for layer in spec.get("layers", [])
            if any("note" in e for e in (layer.get("notes") or []))]


def _midi_channel(index: int) -> int:
    """Layer index -> MIDI channel, skipping the GM percussion channel (10)."""
    ch = index % 15
    return ch if ch < 9 else ch + 1


def _meta(kind: int, payload: bytes) -> bytes:
    return b"\xff" + bytes([kind]) + _vlq(len(payload)) + payload


def _track_chunk(events: list[tuple[int, bytes]]) -> bytes:
    # At equal ticks note-offs precede note-ons so a re-struck pitch is not cut.
    events.sort(key=lambda x: (x[0], (x[1][0] & 0xF0) == 0x90))
    track = bytearray()
    last = 0
    for tick, payload in events:
        track.extend(_vlq(max(0, tick - last)))
        track.extend(payload)
        last = tick
    track.extend(_vlq(0))
    track.extend(b"\xff\x2f\x00")
    return b"MTrk" + struct.pack(">I", len(track)) + bytes(track)


def midi_tempo_events(spec: dict) -> list[tuple[float, float]]:
    """The ``(beat, bpm)`` tempo meta-events the MIDI export writes: every
    ``tempo_map`` point (ramps are stepped at their points), or the single ``bpm``."""
    return tempo_points(spec)


def export_midi_bytes(spec: dict) -> bytes:
    """Format-1 Standard MIDI File: a conductor track (sequence name, time and
    key signature, one tempo event per ``tempo_map`` point) plus one track per
    pitched layer on its own channel, so equal pitches in different layers
    never cut each other off. Velocities map ``vel`` 0..1 to 1..127."""
    conductor = [(0, _meta(0x03, str(spec.get("id", "AudioForge")).encode("latin-1", "replace")))]
    meter = (spec.get("score") or {}).get("meter")
    if meter and int(meter.get("unit", 4)) in (1, 2, 4, 8, 16, 32):
        conductor.append((0, _meta(0x58, bytes([int(meter["beats"]),
                                                int(meter["unit"]).bit_length() - 1, 24, 8]))))
    if spec.get("key"):
        from .musicxml import _key_fifths
        minor = spec["key"].lower().endswith("minor")
        conductor.append((0, _meta(0x59, bytes([_key_fifths(spec["key"]) & 0xFF, int(minor)]))))
    for beat, bpm in midi_tempo_events(spec):
        conductor.append((int(round(beat * TPQ)),
                          _meta(0x51, int(round(60_000_000 / bpm)).to_bytes(3, "big"))))
    chunks = [_track_chunk(conductor)]
    for i, layer in enumerate(_pitched_layers(spec)):
        ch = _midi_channel(i)
        events = [(0, _meta(0x03, str(layer.get("name", f"layer{i + 1}")).encode("latin-1", "replace")))]
        for ev in sorted((e for e in layer["notes"] if "note" in e),
                         key=lambda e: (e["start_beat"], e["note"])):
            start = int(round(ev["start_beat"] * TPQ))
            end = int(round((ev["start_beat"] + ev["dur_beats"]) * TPQ))
            note = max(0, min(127, _midi_note(ev["note"])))
            vel = max(1, min(127, int(round(96 * float(ev.get("vel", 0.8))))))
            events.append((start, bytes([0x90 | ch, note, vel])))
            events.append((end, bytes([0x80 | ch, note, 0])))
        chunks.append(_track_chunk(events))
    return (b"MThd" + struct.pack(">IHHH", 6, 1, len(chunks), TPQ) + b"".join(chunks))


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
