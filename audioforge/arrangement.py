"""Compile authored repeats into an explicit, single-pass render timeline.

Repeat counts include the original pass. The source duration is extended;
following material moves with it. Notes are re-articulated at discontinuous
cuts and retain release tails. Continuous generators/sample clips repeat dry
source windows, before their effect chains and the master are processed.
"""
from __future__ import annotations

import copy
import math

import numpy as np

from .sequencer import TempoMap, TimelineMap


def validate_score(spec: dict) -> None:
    from .schema import SpecError
    score = spec.get("score", {})
    if not isinstance(score, dict):
        raise SpecError("spec.score: object")
    meters = {"meter": score.get("meter", {"beats": 4, "unit": 4})}
    polymeter = score.get("polymeter", {})
    if not isinstance(polymeter, dict):
        raise SpecError("spec.score.polymeter: layer-to-meter object")
    names = {layer.get("name") for layer in spec["layers"]}
    for name, meter in polymeter.items():
        if name not in names:
            raise SpecError(f"spec.score.polymeter: unknown layer '{name}'")
        meters[name] = meter
    for name, meter in meters.items():
        if not isinstance(meter, dict):
            raise SpecError(f"spec.score.{name}: meter object")
        beats, unit = meter.get("beats"), meter.get("unit")
        if (type(beats) is not int or not 1 <= beats <= 32
                or type(unit) is not int or unit not in {1, 2, 4, 8, 16, 32}):
            raise SpecError(f"spec.score.{name}: positive integer beats <= 32 and power-of-two unit <= 32")
    pickup = score.get("pickup_beats", 0)
    meter = meters["meter"]
    if (not isinstance(pickup, (int, float)) or not math.isfinite(pickup)
            or not 0 <= pickup < meter["beats"] * 4 / meter["unit"]):
        raise SpecError("spec.score.pickup_beats: must be shorter than the main bar")
    sections = score.get("sections", [])
    if not isinstance(sections, list):
        raise SpecError("spec.score.sections: list")
    names, last = set(), 0
    for section in sections:
        if not isinstance(section, dict) or not isinstance(section.get("name"), str):
            raise SpecError("spec.score.sections: named sections required")
        a, d = section.get("start_beat"), section.get("dur_beats")
        if (not all(isinstance(v, (int, float)) and math.isfinite(v) for v in (a, d))
                or a < last or d <= 0 or section["name"] in names):
            raise SpecError("spec.score.sections: unique names, ascending nonoverlapping positive spans")
        last = a + d
        names.add(section["name"])
    repeats = score.get("repeats", [])
    if not isinstance(repeats, list):
        raise SpecError("spec.score.repeats: list")
    seen = set()
    for repeat in repeats:
        if not isinstance(repeat, dict) or repeat.get("section") not in names:
            raise SpecError("spec.score.repeats: unknown section")
        count = repeat.get("count")
        if type(count) is not int or not 1 <= count <= 32:
            raise SpecError("spec.score.repeats.count: integer in 1..32, including the first pass")
        if repeat["section"] in seen:
            raise SpecError("spec.score.repeats: a section can be repeated only once")
        seen.add(repeat["section"])


def _timeline(spec):
    return TimelineMap(TempoMap(spec.get("tempo_map") or [[0, spec.get("bpm", 120)]]),
                       spec.get("holds"))


def _before(timeline, beat):
    return timeline.sec(beat) - sum(h["duration_s"] for h in timeline.holds if h["beat"] == beat)


def _windows(spec, timeline):
    end = timeline.beat_at(spec["duration_s"])
    count = {r["section"]: r["count"] for r in spec["score"]["repeats"]}
    raw, cursor = [], 0.0
    for section in spec["score"].get("sections", []):
        a, b = section["start_beat"], section["start_beat"] + section["dur_beats"]
        if section["name"] not in count:
            continue
        if b > end + 1e-8:
            from .schema import SpecError
            raise SpecError("spec.score.repeats: section exceeds source duration")
        if a > cursor:
            raw.append((cursor, a))
        raw.extend([(a, b)] * count[section["name"]])
        cursor = b
    if cursor < end:
        raw.append((cursor, end))
    merged = []
    for a, b in raw:
        if merged and abs(merged[-1][1] - a) < 1e-9:
            merged[-1] = (merged[-1][0], b)
        else:
            merged.append((a, b))
    beat, second, out = 0.0, 0.0, []
    for index, (a, b) in enumerate(merged):
        ta, tb = _before(timeline, a), _before(timeline, b)
        if index == len(merged) - 1 and abs(b - end) < 1e-8:
            tb = spec["duration_s"]  # retain all/part of a terminal hold
        out.append({"a": a, "b": b, "beat": beat, "ta": ta, "tb": tb, "second": second})
        beat += b - a
        second += tb - ta
    return out, float(second)


def _points(points, windows, *, beats=False):
    """Slice a piecewise-linear curve, preserving both sides of repeat jumps."""
    out = []
    xs, ys = zip(*points)
    for window in windows:
        a, b, dest = (window["a"], window["b"], window["beat"]) if beats else (
            window["ta"], window["tb"], window["second"])
        out.append([dest, float(np.interp(a, xs, ys))])
        out.extend([[float(t - a + dest), v] for t, v in points if a < t < b])
        out.append([float(b - a + dest), float(np.interp(b, xs, ys))])
    return out


def _map_events(events, windows, field, *, beats=True):
    out = []
    for index, window in enumerate(windows):
        a, b, dest = (window["a"], window["b"], window["beat"]) if beats else (
            window["ta"], window["tb"], window["second"])
        for event in events:
            t = event[field]
            if a <= t < b:
                out.append({**copy.deepcopy(event), field: float(t - a + dest)})
    return out


def _compose_clock(windows: list, previous: list | None) -> list:
    """Compose two piecewise translations without refitting the source curve."""
    if not previous:
        return windows
    out = []
    for start, end, destination in windows:
        cuts = [start, *[w[2] for w in previous if start < w[2] < end], end]
        for a, b in zip(cuts, cuts[1:]):
            prior = next((w for w in reversed(previous) if w[2] <= a), previous[0])
            source = a - prior[2] + prior[0]
            out.append([source, source + b - a, destination + a - start])
    return out


def compile_repeats(spec: dict) -> dict:
    """Return expanded IR without retaining executable repeat instructions.

    Idempotent: consumed repeats become provenance in intent. All subsequent
    edits apply to the explicit expanded timeline; decompilation emits it.
    """
    if not spec.get("score", {}).get("repeats"):
        return spec
    from .performance import note_events
    from .schema import SpecError
    source = copy.deepcopy(spec)
    timeline = _timeline(source)
    windows, duration = _windows(source, timeline)
    if not .05 <= duration <= 600:
        raise SpecError("spec.score.repeats: expanded duration must be in 0.05..600 seconds")
    out = copy.deepcopy(source)
    out["duration_s"] = duration
    out["score"].pop("repeats")
    # BPM ramps are linear in beat space. Duplicate boundary beats encode
    # the tempo reset at a repeat jump, with the right-hand value last.
    out["tempo_map"] = _points(timeline.tempo_map.pts, windows, beats=True)
    if source.get("holds"):
        out["holds"] = _map_events(source["holds"], windows, "beat")
        last = windows[-1]
        terminal = last["tb"] - _before(timeline, last["b"])
        if terminal > 1e-9:
            out["holds"].append({"beat": last["beat"] + last["b"] - last["a"],
                                 "duration_s": terminal})
    sections = []
    for wi, window in enumerate(windows):
        for section in source["score"].get("sections", []):
            a = max(section["start_beat"], window["a"])
            b = min(section["start_beat"] + section["dur_beats"], window["b"])
            if b > a:
                start = a - window["a"] + window["beat"]
                sections.append({"name": f"{section['name']}__{wi+1}", "start_beat": start,
                                 "dur_beats": b - a, "end_beat": start + b - a})
    out["score"]["sections"] = sections
    if source.get("markers"):
        out["markers"] = _map_events(source["markers"], windows, "time_s", beats=False)
    if source.get("key_map"):
        # Key maps use [beat, root, mode], with a value reset at each jump.
        key_map = source["key_map"]
        if isinstance(key_map[0], list):
            mapped = []
            for window in windows:
                prior = next((point[1:] for point in reversed(key_map) if point[0] <= window["a"]), None)
                if prior:
                    mapped.append([window["beat"], *prior])
                mapped.extend([[point[0]-window["a"]+window["beat"], *point[1:]]
                               for point in key_map if window["a"] < point[0] < window["b"]])
            out["key_map"] = mapped
    for layer, original in zip(out["layers"], source["layers"]):
        if original.get("notes"):
            events = note_events(original, timeline.beat_at(source["duration_s"]))
            notes = []
            for wi, window in enumerate(windows):
                for event in events:
                    # Layer offsets are seconds; resolve them before slicing.
                    offset = original.get("start_s", 0)
                    # beat -> seconds -> beat is not exact in floating point (4 -> 3.9999999999999996
                    # at 44 bpm); snap to a nanobeat so a boundary note is not left as a sliver
                    # inside the neighbouring window and rejected by the minimum-gate rule.
                    start = round(timeline.beat_at(timeline.sec(event["start_beat"]) + offset), 9)
                    end = round(timeline.beat_at(timeline.sec(event["start_beat"] + event["dur_beats"]) + offset), 9)
                    a, b = max(start, window["a"]), min(end, window["b"])
                    if b - a <= 1e-9:
                        continue
                    note = copy.deepcopy(event)
                    note["start_beat"] = float(a - window["a"] + window["beat"])
                    note["dur_beats"] = float(b - a)
                    if note.get("slur"):
                        note["slur"] = int(note["slur"]) + wi * (1 + max(e.get("slur", 0) or 0 for e in events))
                    if "id" in note:
                        note["id"] = f"{note['id']}__pass{wi+1}"
                    if a > start:
                        for curve in note.get("curves", []):
                            shift = a - start if curve.get("time_basis", "note_beats") == "note_beats" else timeline.sec(a)-timeline.sec(start)
                            curve["time_offset"] = curve.get("time_offset", 0) + shift
                    notes.append(note)
            layer["notes"] = sorted(notes, key=lambda event: (event["start_beat"], event.get("note", "")))
            # Keep an out-of-window part valid but silent (a zero-velocity note).
            if not layer["notes"]:
                layer["notes"] = [{**copy.deepcopy(events[0]), "start_beat": 0, "dur_beats": .001, "vel": 0}]
            layer.pop("loop_beats", None)
            layer.pop("start_s", None)
            layer.pop("duration_s", None)
        else:
            layer["clip_source"] = {"duration_s": source["duration_s"],
                                    "start_s": original.get("start_s", 0),
                                    "layer_duration_s": original.get("duration_s", source["duration_s"]),
                                    "tempo_map": source.get("tempo_map") or [[0, source.get("bpm", 120)]],
                                    "holds": source.get("holds", []),
                                    "score": source.get("score", {}),
                                    "automation": original.get("automation", [])}
            layer["clip_map"] = [[w["ta"], w["tb"], w["second"]] for w in windows]
            layer.pop("start_s", None)
            layer.pop("duration_s", None)
        if original.get("dynamic"):
            layer["dynamic"] = _points(original["dynamic"], windows, beats=True)
    targets = [*out["layers"], *out.get("buses", []), out.get("master", {})]
    originals = [*source["layers"], *source.get("buses", []), source.get("master", {})]
    for target, original in zip(targets, originals):
        for automation in target.get("automation", []):
            basis = automation.get("time_basis", "layer_seconds")
            beat_basis = basis.endswith("beats")
            offset = original.get("start_s", 0)
            if (offset or automation.get("time_map") or automation.get("time_offset")
                    or "points" not in automation or automation["target"] == "cutoff_hz"
                    or any(len(p) == 3 for p in automation["points"])):
                # Retain the original curve function, including cropped powers
                # and logarithmic cutoff ramps, and splice its input clock.
                offset = timeline.beat_at(offset) if beat_basis else offset
                mapped = [[w["a"]-offset, w["b"]-offset, w["beat"]]
                          if beat_basis else [w["ta"]-offset, w["tb"]-offset, w["second"]]
                          for w in windows]
                automation["time_map"] = _compose_clock(mapped, automation.get("time_map"))
            else:
                automation["points"] = _points(automation["points"], windows, beats=beat_basis)
    # Flatten generated authoring sugar: reapplying it would generate a second
    # set of parts/effects. Preserve context/provenance, never executable sugar.
    old_intent = out.get("intent", {})
    out["intent"] = {**old_intent, "arrangement": {"source_duration_s": source["duration_s"],
                                     "repeats": source["score"]["repeats"],
                                     "windows": windows}}
    if "analysis_context" in old_intent:
        out["intent"]["analysis_context"] = old_intent["analysis_context"]
    if old_intent.get("analysis", {}).get("phrases"):
        from .performance import phrase_spans
        out["intent"]["arrangement"]["source_analysis"] = old_intent["analysis"]
        out["intent"]["analysis"] = {**old_intent["analysis"], "phrases": [
            {**phrase, "layer": layer["name"]} for layer in out["layers"]
            for phrase in phrase_spans(layer, out)]}
    out.get("_meta", {}).pop("semantic", None)
    return out


def validate_clip(layer: dict, path: str, duration_s: float) -> None:
    from .schema import (SpecError, _num, _validate_automation,
                         TEMPO_MAP_BPM_MIN, TEMPO_MAP_BPM_MAX)
    if "clip_map" not in layer and "clip_source" not in layer:
        return
    if layer["type"] in {"notes", "instrument"}:
        raise SpecError(f"{path}.clip_map: note layers use explicit events")
    source = layer.get("clip_source")
    windows = layer.get("clip_map")
    if not isinstance(source, dict) or not isinstance(windows, list) or not windows:
        raise SpecError(f"{path}.clip_map: paired source object and non-empty window list")
    _num(source, "duration_s", path + ".clip_source", .05, 600)
    _num(source, "layer_duration_s", path + ".clip_source", .05, 600)
    _num(source, "start_s", path + ".clip_source", 0, 600)
    previous_end = 0
    for window in windows:
        if (not isinstance(window, list) or len(window) != 3 or
                not all(isinstance(v, (int, float)) and math.isfinite(v) for v in window)):
            raise SpecError(f"{path}.clip_map: [source_start_s, source_end_s, destination_s]")
        a, b, dest = window
        if not (0 <= a < b <= source["duration_s"] + 1e-8 and dest >= previous_end - 1e-8
                and dest + b - a <= duration_s + 1e-8):
            raise SpecError(f"{path}.clip_map: bounded source windows and ordered nonoverlapping destinations")
        previous_end = dest + b - a
    tempo = source.get("tempo_map")
    if (not isinstance(tempo, list) or not tempo or
            not all(isinstance(p, list) and len(p) == 2 and all(isinstance(v, (int, float)) and math.isfinite(v) for v in p)
                    and p[0] >= 0 and TEMPO_MAP_BPM_MIN <= p[1] <= TEMPO_MAP_BPM_MAX for p in tempo) or
            tempo[0][0] != 0 or
            any(a[0] > b[0] for a, b in zip(tempo, tempo[1:]))):
        raise SpecError(f"{path}.clip_source.tempo_map: ascending positive tempo map")
    holds = source.get("holds", [])
    if not isinstance(holds, list):
        raise SpecError(f"{path}.clip_source.holds: list required")
    for hold in holds:
        if not isinstance(hold, dict):
            raise SpecError(f"{path}.clip_source.holds: hold objects")
        _num(hold, "beat", path + ".clip_source.holds", 0, 100000)
        _num(hold, "duration_s", path + ".clip_source.holds", 0, 600)
    score = source.get("score", {})
    if not isinstance(score, dict) or not isinstance(score.get("polymeter", {}), dict):
        raise SpecError(f"{path}.clip_source.score: score object required")
    names = {layer.get("name"), *score.get("polymeter", {})}
    validate_score({"score": score, "layers": [{"name": name} for name in names]})
    _validate_automation(source.get("automation", []), path + ".clip_source.automation",
                         layer.get("fx"), scope="layer", layer_type=layer["type"], osc=layer.get("osc"))
