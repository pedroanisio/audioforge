"""MIDI/MusicXML interop for the explicit note-event IR."""
from __future__ import annotations

import hashlib
import json
import struct
import xml.etree.ElementTree as ET
from pathlib import Path

from .determinism import spec_hash
from .tuning import Tuning
from . import synth
from .musicxml import (TPQ, _key_fifths, _key_points, _midi_note, _note_name,  # noqa: F401
                       _pitched_layers, _sections, export_musicxml,
                       export_notated_musicxml, import_musicxml, layer_ident,
                       performed, repeats_align_with_barlines, tempo_marks,
                       tempo_points)

_layer_ident = layer_ident


# ------------------------------------------------------------- coverage ----
# One registry says what every export keeps. `coverage()` renders it (manifest,
# docs/INTEROP.md via audioforge.tools.gen_interop) and `interop_diagnostics()`
# reports from it, so a construct can never be dropped silently: it is either
# preserved, quantized (documented), or carries a registered lossy code.
FORMATS = ("midi", "musicxml", "musicxml_notated")
STATUSES = ("preserved", "quantized", "lossy", "unsupported", "conditional")


def _P(note: str = "") -> tuple:
    return ("preserved", None, note)


def _Q(note: str) -> tuple:
    return ("quantized", None, note)


def _L(code: str, note: str) -> tuple:
    return ("lossy", code, note)


def _U(code: str, note: str) -> tuple:
    return ("unsupported", code, note)


def _cond(fn, code: str, note: str):
    """A per-spec cell; its documentation form is `conditional` with the code it may emit."""
    fn.static = ("conditional", code, note)
    return fn


def _score(spec: dict) -> dict:
    return spec.get("score") or {}


def _notation(spec: dict) -> dict:
    return spec.get("notation") or {}


def _note_events(spec: dict):
    for li, layer in enumerate(spec.get("layers", [])):
        for ni, ev in enumerate(layer.get("notes") or []):
            if "note" in ev:
                yield li, layer, ni, ev


def _curve_paths(spec: dict, target: str) -> list[str]:
    paths = []
    for li, layer in enumerate(spec.get("layers", [])):
        for ni, ev in enumerate(layer.get("notes") or []):
            if any(c.get("target") == target for c in ev.get("curves") or []):
                paths.append(f"layers[{li}].notes[{ni}].curves")
        for ci, curve in enumerate(layer.get("automation") or []):
            if curve.get("target") == target:
                paths.append(f"layers[{li}].automation[{ci}]")
    return paths


def _note_curve_paths(spec: dict, target: str) -> list[str]:
    return [p for p in _curve_paths(spec, target) if ".notes[" in p]


def _layer_paths(spec: dict, pred) -> list[str]:
    return [f"layer:{layer.get('name', layer.get('type'))}"
            for layer in spec.get("layers", []) if pred(layer)]


def _has_chords(spec: dict) -> bool:
    for layer in _pitched_layers(spec):
        starts = [round(e["start_beat"], 6) for e in layer["notes"] if "note" in e]
        if len(starts) != len(set(starts)):
            return True
    return False


def _pow2(n: int) -> bool:
    return n > 0 and n & (n - 1) == 0


def _pickup_signature(beats: float):
    """(numerator, denominator) writing an anacrusis of `beats` quarter notes as a
    time signature, or None when it is not a whole number of 64th notes."""
    for den in (4, 8, 16, 32, 64):
        num = beats * den / 4
        if abs(num - round(num)) < 1e-9 and round(num) >= 1:
            return int(round(num)), den
    return None


def _midi_meter(spec):
    unit = int((_score(spec).get("meter") or {}).get("unit", 4))
    return _P("time-signature meta event") if _pow2(unit) else \
        _L("lossy_meter_unit", "MIDI time signatures need a power-of-two unit; none is written")


def _midi_pickup(spec):
    return _P("the anacrusis is its own time signature before the meter") \
        if _pickup_signature(float(_score(spec).get("pickup_beats", 0.0))) else \
        _L("lossy_pickup", "the anacrusis is not a whole number of 64ths; bar phase starts at beat 0")


def _notated_repeats(spec):
    return _P("repeat barlines with `times`") if repeats_align_with_barlines(spec) else \
        _L("lossy_repeat", "a repeated section starts or ends inside a bar; "
                           "MIDI and the exact-tick export carry the performed form")


def _exact_key(spec):
    return _L("lossy_key_change", "initial key only in the single-measure view") \
        if len(spec.get("key_map") or []) > 1 else _P("key signature")


BEND_RANGE_CENTS = 200.0   # RPN 0 pitch-bend sensitivity written by the export: ±2 semitones


def _bend_cents(tuning: Tuning, note: str) -> tuple[int, float]:
    """(nearest 12-TET note number, cents to bend it by) for a note in `tuning`."""
    midi_f = float(synth.freq_to_midi(tuning.note_to_freq(note)))
    n = int(round(midi_f))
    return max(0, min(127, n)), (midi_f - n) * 100.0


def _midi_tuning(spec):
    tuning = Tuning.from_spec(spec)
    if tuning.is_default:
        return _P("12-TET note numbers")
    for layer in _pitched_layers(spec):
        by_start: dict[float, set[int]] = {}
        for ev in layer["notes"]:
            if "note" in ev:
                by_start.setdefault(round(ev["start_beat"], 6), set()).add(round(_bend_cents(tuning, ev["note"])[1]))
        if any(len(v) > 1 for v in by_start.values()):
            return _L("lossy_tuning", "simultaneous notes in one layer need different pitch bends; "
                                      "one channel carries one bend")
    return _P(f"nearest note number plus a per-note pitch bend (RPN range ±{BEND_RANGE_CENTS:g} cents)")


def _has_dynamic_marks(spec: dict) -> bool:
    return any(layer.get("dynamic") for layer in spec.get("layers", [])) or \
        any(".automation[" in p for p in _curve_paths(spec, "dynamic"))


COVERAGE: list[dict] = [
    dict(construct="pitch", description="note pitch",
         present=lambda s: bool(_pitched_layers(s)),
         midi=_P("note number"), musicxml=_P("step, alter, octave"),
         musicxml_notated=_P("step, alter, octave")),
    dict(construct="timing", description="note start and duration",
         present=lambda s: bool(_pitched_layers(s)),
         midi=_P("exact to the tick (480 per quarter)"),
         musicxml=_P("exact `<duration>` in divisions"),
         musicxml_notated=_Q("snapped to the grid (default a 16th); same-onset notes share the "
                             "longest duration, truncated at the next onset")),
    dict(construct="velocity", description="note velocity (`vel`)",
         present=lambda s: any("vel" in ev for *_, ev in _note_events(s)),
         midi=_P("velocity 1..127 (vel × 96)"),
         musicxml=_P("note `dynamics` attribute (% of velocity 90)"),
         musicxml_notated=_P("note `dynamics` attribute (% of velocity 90)")),
    dict(construct="layers", description="one part or track per pitched layer, named after it",
         present=lambda s: bool(_pitched_layers(s)),
         midi=_P("one track per layer on its own channel"),
         musicxml=_P("one `<part>` per layer"), musicxml_notated=_P("one `<part>` per layer")),
    dict(construct="chords", description="simultaneous onsets within a layer",
         present=_has_chords,
         midi=_P("same channel, independent note-offs"),
         musicxml=_P("`<chord/>`; one group per duration, joined with `<backup>`"),
         musicxml_notated=_Q("one `<chord/>` carrying the longest duration")),
    dict(construct="unpitched_layers",
         description="layers without note events (drums, noise, samples, tone, sweeps)",
         present=lambda s: any(layer not in _pitched_layers(s) for layer in s.get("layers", [])),
         midi=_U("unsupported_layer_type", "no note events to write"),
         musicxml=_U("unsupported_layer_type", "no note events to write"),
         musicxml_notated=_U("unsupported_layer_type", "no note events to write"),
         paths=lambda s: _layer_paths(s, lambda l: l not in _pitched_layers(s))),
    dict(construct="meter", description="`score.meter` (beats and unit)",
         present=lambda s: "meter" in _score(s),
         midi=_cond(_midi_meter, "lossy_meter_unit", "time-signature meta event when the unit is a power of two"),
         musicxml=_P("`<time>` (declared; the exact-tick view is one measure)"),
         musicxml_notated=_P("`<time>` and the bar length")),
    dict(construct="pickup", description="`score.pickup_beats` (anacrusis)",
         present=lambda s: float(_score(s).get("pickup_beats", 0.0)) > 0,
         midi=_cond(_midi_pickup, "lossy_pickup", "a partial first bar when the anacrusis is a whole number of 64ths"),
         musicxml=_L("lossy_pickup", "single measure; no barlines to phase"),
         musicxml_notated=_P("implicit measure 0")),
    dict(construct="polymeter", description="`score.polymeter` (per-layer meter)",
         present=lambda s: bool(_score(s).get("polymeter")),
         midi=_L("lossy_polymeter", "one time signature per file"),
         musicxml=_L("lossy_polymeter", "the single-measure view carries the score meter only"),
         musicxml_notated=_P("per-part time signatures and bar lengths")),
    dict(construct="sections", description="`score.sections` (form)",
         present=lambda s: bool(_sections(s)),
         midi=_P("marker meta events"), musicxml=_P("rehearsal-mark directions"),
         musicxml_notated=_P("rehearsal-mark directions")),
    dict(construct="repeats", description="`score.repeats`",
         present=lambda s: bool(_score(s).get("repeats")),
         midi=_P("expanded as performed"), musicxml=_P("expanded as performed"),
         musicxml_notated=_cond(_notated_repeats, "lossy_repeat", "repeat barlines when the section sits on barlines")),
    dict(construct="key", description="`key` and `key_map`",
         present=lambda s: bool(s.get("key") or s.get("key_map")),
         midi=_P("key-signature meta events, one per change"),
         musicxml=_cond(_exact_key, "lossy_key_change", "initial key; changes need the notated view"),
         musicxml_notated=_Q("key signatures; a change inside a bar takes effect at the next barline")),
    dict(construct="tempo", description="`bpm` and `tempo_map`",
         present=lambda s: "bpm" in s or "tempo_map" in s,
         midi=_P("one tempo event per point (ramps stepped)"),
         musicxml=_P("one metronome direction per point (ramps stepped)"),
         musicxml_notated=_Q("thinned to the grid; changes under 0.1 bpm collapse; ramps stepped")),
    dict(construct="holds", description="`holds` (fermata with a length in seconds)",
         present=lambda s: bool(s.get("holds")),
         midi=_L("lossy_hold", "no pause is inserted"),
         musicxml=_L("lossy_hold", "no pause is inserted"),
         musicxml_notated=_Q("fermata on the note or rest ending at the hold; the length is not encoded")),
    dict(construct="dynamic_marks", description="layer `dynamic` points (pp … fff)",
         present=_has_dynamic_marks,
         midi=_L("lossy_dynamic_curve", "no controller data is written"),
         musicxml=_L("lossy_dynamic_curve", "marks are not written in the exact-tick view"),
         musicxml_notated=_P("dynamic marks, with hairpins between differing marks"),
         paths=lambda s: [p for p in _curve_paths(s, "dynamic") if ".automation[" in p]),
    dict(construct="note_dynamic_curves", description="through-note `dynamic` curves",
         present=lambda s: bool(_note_curve_paths(s, "dynamic")),
         midi=_L("lossy_dynamic_curve", "through-note shaping is not projected"),
         musicxml=_L("lossy_dynamic_curve", "through-note shaping is not projected"),
         musicxml_notated=_L("lossy_dynamic_curve", "through-note shaping is not projected"),
         paths=lambda s: _note_curve_paths(s, "dynamic")),
    dict(construct="pitch_curves", description="`pitch_cents` note curves and layer automation",
         present=lambda s: bool(_curve_paths(s, "pitch_cents")),
         midi=_L("lossy_pitch_curve", "arbitrary pitch curves are not projected"),
         musicxml=_L("lossy_pitch_curve", "arbitrary pitch curves are not projected"),
         musicxml_notated=_L("lossy_pitch_curve", "arbitrary pitch curves are not projected"),
         paths=lambda s: _curve_paths(s, "pitch_cents")),
    dict(construct="articulations", description="note `art`",
         present=lambda s: any(ev.get("art") not in (None, "sustain") for *_, ev in _note_events(s)),
         midi=_L("lossy_articulation", "SMF carries no articulation data"),
         musicxml=_L("lossy_articulation", "marks are not written in the exact-tick view"),
         musicxml_notated=_P("staccato, spiccato, marcato and tremolo as notations; legato as a slur; "
                             "pizzicato as pizz./arco directions"),
         paths=lambda s: _layer_paths(s, lambda l: any(e.get("art") not in (None, "sustain")
                                                       for e in l.get("notes") or []))),
    dict(construct="slurs", description="`slur( … )` groups",
         present=lambda s: any(ev.get("slur") is not None for *_, ev in _note_events(s)),
         midi=_L("lossy_slur", "SMF carries no phrasing data"),
         musicxml=_L("lossy_slur", "slurs are not written in the exact-tick view"),
         musicxml_notated=_P("`<slur>` start and stop")),
    dict(construct="tuplets", description="`notation.tuplets`",
         present=lambda s: bool(_notation(s).get("tuplets")),
         midi=_P("sounding durations are exact"), musicxml=_P("sounding durations are exact"),
         musicxml_notated=_P("`<time-modification>` and tuplet brackets")),
    dict(construct="lyrics", description="`notation.lyrics`",
         present=lambda s: bool(_notation(s).get("lyrics")),
         midi=_P("lyric meta events, one per syllable"),
         musicxml=_L("lossy_lyrics", "not written in the exact-tick view"),
         musicxml_notated=_P("`<lyric>` per syllable")),
    dict(construct="tuning", description="`notation.tuning` other than 12-EDO",
         present=lambda s: int((_notation(s).get("tuning") or {}).get("divisions", 12)) != 12,
         midi=_cond(_midi_tuning, "lossy_tuning", "per-note pitch bend unless a layer needs two bends at once"),
         musicxml=_P("decimal `<alter>` relative to the 12-TET natural"),
         musicxml_notated=_P("decimal `<alter>` relative to the 12-TET natural")),
    dict(construct="string_fret", description="note `string` / `fret` fields",
         present=lambda s: any("string" in ev or "fret" in ev for *_, ev in _note_events(s)),
         midi=_L("lossy_string_fret", "not written"), musicxml=_L("lossy_string_fret", "not written"),
         musicxml_notated=_L("lossy_string_fret", "not written")),
    dict(construct="markers", description="`markers` (labels in real seconds)",
         present=lambda s: bool(s.get("markers")),
         midi=_L("lossy_marker", "markers are in seconds and are not converted to ticks"),
         musicxml=_L("lossy_marker", "not written"), musicxml_notated=_L("lossy_marker", "not written")),
]


def _cell(cell, spec: dict | None) -> tuple:
    if callable(cell):
        return cell(spec) if spec is not None else cell.static
    return cell


def coverage(spec: dict | None = None) -> list[dict]:
    """The construct × format matrix. Without a spec: the documentation form
    (conditional cells name the code they may emit). With a spec: cells evaluated
    for that spec plus a `present` flag."""
    rows = []
    for entry in COVERAGE:
        row = {"construct": entry["construct"], "description": entry["description"]}
        if spec is not None:
            row["present"] = bool(entry["present"](spec))
        for fmt in FORMATS:
            status, code, note = _cell(entry[fmt], spec)
            row[fmt] = {"status": status, "code": code, "note": note}
        rows.append(row)
    return rows


def interop_diagnostics(spec: dict, format: str) -> list[dict]:
    """Structured lossy-conversion warnings for an export target, read from the
    coverage registry: one warning per dropped construct (per path where known)."""
    if format not in FORMATS:
        raise ValueError(f"unknown interop format {format!r}; expected one of {FORMATS}")
    warnings = []
    for entry in COVERAGE:
        if not entry["present"](spec):
            continue
        status, code, note = _cell(entry[format], spec)
        if status not in ("lossy", "unsupported") or not code:
            continue
        paths = entry["paths"](spec) if "paths" in entry else [None]
        for path in paths or [None]:
            w = {"severity": "warning", "code": code,
                 "message": f"{format} export: {entry['description']} — {note}"}
            if path:
                w["path"] = path
            warnings.append(w)
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


def _time_signature(beats: int, unit: int) -> bytes:
    return _meta(0x58, bytes([beats, unit.bit_length() - 1, 24, 8]))


def export_midi_bytes(spec: dict) -> bytes:
    """Format-1 Standard MIDI File of the spec *as performed* (repeats expanded):
    a conductor track (sequence name, time signature — with the anacrusis as its
    own signature when it is a whole number of 64ths — key signatures for every
    key change, one tempo event per `tempo_map` point, a marker per section)
    plus one track per pitched layer on its own channel (so equal pitches in
    different layers never cut each other off) carrying its notes and lyric
    events. What is not written is listed by ``interop_diagnostics(spec, "midi")``."""
    spec = performed(spec)
    score = spec.get("score") or {}
    conductor = [(0, _meta(0x03, str(spec.get("id", "AudioForge")).encode("latin-1", "replace")))]
    meter = score.get("meter")
    if meter and _pow2(int(meter.get("unit", 4))):
        pickup = float(score.get("pickup_beats", 0.0))
        sig = _pickup_signature(pickup) if pickup > 0 else None
        if sig:
            conductor.append((0, _time_signature(*sig)))
            conductor.append((int(round(pickup * TPQ)), _time_signature(int(meter["beats"]), int(meter["unit"]))))
        else:
            conductor.append((0, _time_signature(int(meter["beats"]), int(meter["unit"]))))
    if spec.get("key") or spec.get("key_map"):
        for tick, fifths, mode in _key_points(spec):
            conductor.append((tick, _meta(0x59, bytes([fifths & 0xFF, int(mode == "minor")]))))
    for beat, bpm in tempo_points(spec):
        conductor.append((int(round(beat * TPQ)),
                          _meta(0x51, int(round(60_000_000 / bpm)).to_bytes(3, "big"))))
    for sec in _sections(spec):
        conductor.append((int(round(float(sec["start_beat"]) * TPQ)),
                          _meta(0x06, str(sec["name"]).encode("latin-1", "replace"))))
    chunks = [_track_chunk(conductor)]
    lyrics = (spec.get("notation") or {}).get("lyrics") or []
    tuning = Tuning.from_spec(spec)
    for i, layer in enumerate(_pitched_layers(spec)):
        ch = _midi_channel(i)
        events = [(0, _meta(0x03, str(layer.get("name", f"layer{i + 1}")).encode("latin-1", "replace")))]
        if not tuning.is_default:      # RPN 0: pitch-bend sensitivity = 2 semitones, then per-note bends
            for cc, val in ((101, 0), (100, 0), (6, int(BEND_RANGE_CENTS // 100)), (38, 0), (101, 127), (100, 127)):
                events.append((0, bytes([0xB0 | ch, cc, val])))
        notes = sorted((e for e in layer["notes"] if "note" in e), key=lambda e: (e["start_beat"], e["note"]))
        for ev in notes:
            start = int(round(ev["start_beat"] * TPQ))
            end = int(round((ev["start_beat"] + ev["dur_beats"]) * TPQ))
            if tuning.is_default:
                note = max(0, min(127, _midi_note(ev["note"])))
            else:
                note, cents = _bend_cents(tuning, ev["note"])
                bend = int(round(8192 + cents / BEND_RANGE_CENTS * 8192))
                bend = max(0, min(16383, bend))
                events.append((start, bytes([0xE0 | ch, bend & 0x7F, bend >> 7])))
            vel = max(1, min(127, int(round(96 * float(ev.get("vel", 0.8))))))
            events.append((start, bytes([0x90 | ch, note, vel])))
            events.append((end, bytes([0x80 | ch, note, 0])))
        onsets = sorted({int(round(e["start_beat"] * TPQ)) for e in notes})
        for entry in lyrics:
            if entry.get("layer") != layer.get("name"):
                continue
            first = int(round(float(entry.get("start_beat", 0.0)) * TPQ))
            for tick, syllable in zip([t for t in onsets if t >= first], str(entry.get("text", "")).split()):
                events.append((tick, _meta(0x05, syllable.encode("latin-1", "replace"))))
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
