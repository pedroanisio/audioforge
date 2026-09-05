"""Evidence-based chord identity and explicit voicing transformations.

Roots and quality are independent of inversion/doubling. See Open Music Theory:
https://viva.pressbooks.pub/openmusictheory/chapter/seventh-chords/
https://viva.pressbooks.pub/openmusictheory/chapter/inversion/
The register-search cost below is an engineering policy, not a rule of taste.
"""
from __future__ import annotations

import numpy as np

from .theory import CHORD_QUALITIES, note_to_semis, semis_to_note

# `<status>_harmony` diagnostics for unresolved collections (registered in the capability manifest).
HARMONY_DIAGNOSTIC_CODES = frozenset({"ambiguous_harmony", "unrecognized_harmony"})


def identify_chord(events: list[dict]) -> dict:
    """Identify exact pitch collections or report competing interpretations.

    Explicit chord symbols resolve otherwise ambiguous collections such as
    C6/Am7. Matching never assumes that the lowest sounding note is the root.
    """
    pitches = {note_to_semis(event["note"]) % 12 for event in events if "note" in event}
    authored = [event["harmony"] for event in events if event.get("harmony")]
    if authored and all(value == authored[0] for value in authored):
        value = authored[0]
        root, quality = value["root_pc"], value["quality"]
        expected = {(root + interval) % 12 for interval in CHORD_QUALITIES[quality]}
        if expected <= pitches:
            return {**value, "status": "resolved", "evidence": "authored_chord"}
    matches = {}
    for root in range(12):
        for quality, intervals in CHORD_QUALITIES.items():
            relative = frozenset(interval % 12 for interval in intervals)
            if {(root + interval) % 12 for interval in relative} == pitches:
                matches.setdefault((root, relative), {
                    "root_pc": root, "quality": quality,
                    "status": "resolved", "evidence": "exact_pitch_collection",
                })
    if len(matches) == 1:
        return next(iter(matches.values()))
    return {
        "status": "ambiguous" if matches else "unrecognized",
        "pitch_classes": sorted(pitches), "candidates": list(matches.values()),
    }


def _extension(chord: dict, number: int, pitch_classes: set[int],
               scale: list[int] | None) -> int | None:
    root = chord["root_pc"]
    intervals = {interval % 12 for interval in CHORD_QUALITIES[chord["quality"]]}
    relative = {(pitch - root) % 12 for pitch in pitch_classes}
    if number == 7:
        if relative & {10, 11} or (9 in intervals and "dim7" == chord["quality"]):
            return None
        if scale and root in scale:
            return (scale[(scale.index(root) + 6) % len(scale)] - root) % 12
        return 9 if {3, 6} <= intervals else (10 if 3 in intervals else 11)
    if number not in {9, 11, 13}:
        return None
    if scale and root in scale:
        interval = (scale[(scale.index(root) + number - 1) % len(scale)] - root) % 12
    else:
        interval = {9: 2, 11: 5, 13: 9}[number]
    return interval + 12


def _lead_register(previous: list[dict], current: list[dict]) -> list[dict]:
    """Search inversions/octaves for minimum squared voice motion.

    Pitch classes, event count, onset and gate are invariants. Authored string
    positions remain untouched because register changes would alter fingering.
    """
    if any("string" in event for event in current):
        return current
    previous_pitches = sorted(note_to_semis(event["note"]) for event in previous)
    ordered = sorted(current, key=lambda event: note_to_semis(event["note"]))
    pitches = [note_to_semis(event["note"]) for event in ordered]
    references = np.interp(np.linspace(0, 1, len(pitches)),
                           np.linspace(0, 1, len(previous_pitches)), previous_pitches)
    candidates = []
    for rotation in range(len(pitches)):
        rotated = list(zip(pitches[rotation:], ordered[rotation:])) + [
            (pitch + 12, event) for pitch, event in zip(pitches[:rotation], ordered[:rotation])]
        center = round((float(np.mean(references)) - np.mean([p for p, _ in rotated])) / 12)
        for octave in range(center - 2, center + 3):
            candidate = sorted(((pitch + octave * 12, event) for pitch, event in rotated),
                               key=lambda item: item[0])
            if any(pitch < -12 or pitch > 119 for pitch, _ in candidate):
                continue
            motion = sum((pitch - reference) ** 2
                         for (pitch, _), reference in zip(candidate, references))
            displacement = sum(abs(pitch - note_to_semis(event["note"]))
                               for pitch, event in candidate)
            candidates.append((motion, displacement, tuple(p for p, _ in candidate), candidate))
    if not candidates:
        return current
    chosen = min(candidates, key=lambda item: item[:3])[-1]
    return [{**event, "note": semis_to_note(pitch),
             **({"voicing_before": event["note"], "generated": "voice_leading"}
                if pitch != note_to_semis(event["note"]) else {})}
            for pitch, event in chosen]


def apply_voicing(layer: dict, directive: dict, scale: list[int] | None,
                  diagnostics: list[str], key_scales: list | None = None) -> None:
    """Add requested, quality-aware extensions and optionally lead registers."""
    richness = max(0.0, min(1.0, float(directive.get("richness", 0.0))))
    leading = directive.get("voice_leading") in (True, "on", "true")
    if not richness and not leading:
        return
    extensions = [int(number) for number in directive.get("extensions", [])] if richness else []
    groups: dict[tuple[float, float], list[dict]] = {}
    unpitched = []
    for event in layer.get("notes", []):
        if "note" in event:
            groups.setdefault((event["start_beat"], event["dur_beats"]), []).append(event)
        else:
            unpitched.append(event)
    output = list(unpitched)
    previous = None
    for (beat, _duration), events in sorted(groups.items()):
        local_scale = scale
        for start, value in key_scales or []:
            if start <= beat:
                local_scale = value
        if len(events) < 3:
            output.extend(events)
            previous = None
            continue
        chord = identify_chord(events)
        if chord["status"] != "resolved":
            diagnostics.append(
                f"{chord['status']}_harmony: layer '{layer.get('name')}' at {beat:g}b; "
                "preserved notes; author a chord symbol to select root and quality")
            output.extend(events)
            previous = None
            continue
        events = [dict(event) for event in events]
        pitch_classes = {note_to_semis(event["note"]) % 12 for event in events}
        bass = min(note_to_semis(event["note"]) for event in events)
        root = bass - (bass - chord["root_pc"]) % 12
        for number in extensions:
            interval = _extension(chord, number, pitch_classes, local_scale)
            if interval is None or (root + interval) % 12 in pitch_classes:
                continue
            template = {key: value for key, value in events[0].items()
                        if key not in {"id", "note", "freq_hz", "string", "fret"}}
            events.append({**template, "note": semis_to_note(root + interval),
                           "vel": round(events[0].get("vel", 1.0) * (0.72 + 0.2 * richness), 4),
                           "generated": "chord_extension", "extension": number})
            pitch_classes.add((root + interval) % 12)
        if leading and previous:
            events = _lead_register(previous, events)
        previous = events
        output.extend(events)
    layer["notes"] = sorted(output, key=lambda event: (
        event["start_beat"], event.get("note", ""), event.get("freq_hz", 0)))


def cadence_candidates(spec: dict, layer_name: str) -> list[dict]:
    """Conservative V-to-I candidates on a declared local downbeat.

    Harmonic roots, key and metric position are necessary evidence here; phrase
    endings without that evidence stay unclassified. This does not infer vocal
    leading, genre-specific cadences or subjective finality.
    """
    score = spec.get("score", {})
    meter = score.get("polymeter", {}).get(layer_name, score.get("meter", {"beats": 4, "unit": 4}))
    bar = meter["beats"] * 4 / meter["unit"]
    groups = {}
    for layer in spec.get("layers", []):
        for event in layer.get("notes", []):
            if "note" in event:
                groups.setdefault(event["start_beat"], []).append(event)
    previous, out = None, []
    for beat, events in sorted(groups.items()):
        chord = identify_chord(events)
        key = spec.get("key", "")
        for point in spec.get("key_map", []):
            if point[0] <= beat:
                key = " ".join(point[1:])
        parts = key.split()
        if len(parts) != 2 or parts[1] not in {"major", "minor"}:
            previous = chord
            continue
        tonic = note_to_semis(parts[0] + "4") % 12
        phase = (beat - score.get("pickup_beats", 0)) % bar
        downbeat = min(phase, bar - phase) < 1e-8
        if (downbeat and previous and previous.get("status") == chord.get("status") == "resolved"
                and previous["root_pc"] == (tonic + 7) % 12 and chord["root_pc"] == tonic):
            prior = set(CHORD_QUALITIES[previous["quality"]])
            target = set(CHORD_QUALITIES[chord["quality"]])
            if {0, 4, 7} <= prior and {0, 7, 4 if parts[1] == "major" else 3} <= target:
                out.append({"beat": float(beat), "type": "dominant_to_tonic", "status": "candidate",
                            "evidence": ["resolved_chord_roots", "declared_key", "local_downbeat"]})
        previous = chord
    return out
