"""Shared, deterministic performance scheduling for planning and rendering."""
from __future__ import annotations

import numpy as np

from .determinism import note_seed_paths, rng_for
from .synth import freq_to_midi, note_to_freq


def conductor_spans(spec: dict, spans: list[dict]) -> list[dict]:
    """Resolve a single tempo-shaping span at every beat across all parts."""
    sections = spec.get("score", {}).get("sections", [])
    if sections:
        return [{"start_beat": section["start_beat"],
                 "end_beat": section["start_beat"] + section["dur_beats"]}
                for section in sections]
    merged = []
    for span in sorted(spans, key=lambda item: item["start_beat"]):
        if merged and span["start_beat"] < merged[-1]["end_beat"]:
            merged[-1]["end_beat"] = max(merged[-1]["end_beat"], span["end_beat"])
        else:
            merged.append({"start_beat": span["start_beat"], "end_beat": span["end_beat"]})
    return merged


def phrase_spans(track: dict, spec: dict) -> list[dict]:
    """Prefer authored form/slurs; describe rest-delimited activity otherwise."""
    events = sorted(track.get("notes", []), key=lambda event: event["start_beat"])
    if not events:
        return []
    score = spec.get("score", {})
    sections = score.get("sections", [])
    groups = []
    if sections:
        for section in sections:
            start, end = section["start_beat"], section["start_beat"] + section["dur_beats"]
            selected = [e for e in events if start <= e["start_beat"] < end]
            if selected:
                groups.append((start, end, selected, "authored_form"))
    else:
        meter = score.get("polymeter", {}).get(track.get("name"), score.get("meter", {}))
        pulse = 4 / meter.get("unit", 4)
        current, end = [], 0.0
        for event in events:
            split = current and (event["start_beat"] - end >= pulse or
                    (event.get("slur") != current[-1].get("slur") and
                     (event.get("slur") or current[-1].get("slur")) and
                     event["start_beat"] >= end))
            if split:
                evidence = "authored_slur" if current[0].get("slur") else "activity_span"
                groups.append((current[0]["start_beat"], end, current, evidence))
                current = []
            current.append(event)
            end = max(end if len(current) > 1 else 0, event["start_beat"] + event["dur_beats"])
        evidence = "authored_slur" if current[0].get("slur") else "activity_span"
        groups.append((current[0]["start_beat"], end, current, evidence))
    from .harmony import cadence_candidates
    candidates = cadence_candidates(spec, track.get("name", ""))
    return [{"id": index + 1, "start_beat": start, "end_beat": end,
             "note_count": len(group), "boundary_evidence": evidence,
             "contour_policy": "midpoint_arch",
             "cadence_candidates": [c for c in candidates if start <= c["beat"] < end]}
            for index, (start, end, group, evidence) in enumerate(groups)]


def timing_deviation(track: dict, beat: float, rng_factory) -> float:
    """A shared beat clock plus part offset keeps chords and sections together.

    Linear interpolation between beat anchors correlates nearby onsets. At most
    30% of the requested timing spread is independent between parts/players.
    """
    anchor = int(np.floor(beat))
    fraction = beat - anchor
    root = track.get("_performance_root")
    def draw(index):
        generator = (rng_for(root, "ensemble_clock", str(index)) if root
                     else rng_factory(f"clock:{index}"))
        return generator.random() * 2 - 1
    shared = (1 - fraction) * draw(anchor) + fraction * draw(anchor + 1)
    local = rng_factory(f"onset:{float(beat):.12g}").random() * 2 - 1
    return 0.7 * shared + 0.3 * local


def groove_slot(beat: float, layer_name: str, score: dict, slots: int) -> int:
    """Sixteenth-note groove indexing restarts at each local notated bar.

    Beats always denote quarter notes. Pickup audio begins at beat zero; the
    first full bar begins after pickup_beats. Meter never rescales note times.
    """
    meter = score.get("polymeter", {}).get(layer_name, score.get("meter", {"beats": 4, "unit": 4}))
    bar_beats = meter["beats"] * 4 / meter["unit"]
    phase = (beat - score.get("pickup_beats", 0)) % bar_beats
    return int(round(phase * 4)) % slots


def note_events(track: dict, end_beat: float) -> list[dict]:
    """Expand an explicit loop and order events identically at every consumer."""
    events = list(track["notes"])
    loop_beats = track.get("loop_beats")
    if loop_beats:
        repetitions = int(np.ceil(end_beat / loop_beats))
        events = [{**event, "start_beat": event["start_beat"] + repeat * loop_beats,
                   **({"id": f"{event['id']}__loop{repeat}"} if "id" in event else {})}
                  for repeat in range(repetitions) for event in events]
    return sorted(events, key=lambda event: (
        event["start_beat"], event.get("note", ""), event.get("freq_hz", 0.0)))


def legato_links(schedule: list[dict]) -> list[tuple[int | None, int | None]]:
    """Join contiguous monophonic slurs within a voice, never across rests."""
    links = [[None, None] for _ in schedule]
    voices = {}
    for index, note in enumerate(schedule):
        voices.setdefault(note["event"].get("voice", "default"), []).append(index)
    for indices in voices.values():
        counts = {}
        for index in indices:
            beat = schedule[index]["start_beat"]
            counts[beat] = counts.get(beat, 0) + 1
        for previous, current in zip(indices, indices[1:]):
            a, b = schedule[previous], schedule[current]
            end = a["start_beat"] + a["event"]["dur_beats"]
            gap = b["start_beat"] - end
            if (a["slur"] and a["slur"] == b["slur"]
                    and counts[a["start_beat"]] == counts[b["start_beat"]] == 1
                    and b["start_beat"] > a["start_beat"] and -0.25 <= gap <= 0.02):
                links[previous][1], links[current][0] = current, previous
    return [tuple(link) for link in links]


def section_player(track: dict, player: int, rng_factory) -> tuple[float, float, float]:
    """Return the player's timing offset, MIDI offset and pan from one take."""
    section = track["section"]
    count = int(section["size"])
    rng = rng_factory(f"player{player}:static")
    timing = (rng.random() * 2 - 1) * float(section.get("timing_s", 0.009))
    pitch = (rng.random() * 2 - 1) * float(section.get("detune_c", 7.0)) / 100
    position = float(track.get("pan", 0.0)) + float(section.get("spread", 0.6)) * (
        -1 + 2 * player / (count - 1) if count > 1 else 0.0)
    return timing, pitch, float(np.clip(position, -1, 1))


def schedule_notes(track: dict, total_n: int, sr: int, timeline, rng_factory,
                   groove: dict | None = None, time_offset_s: float = 0.0,
                   midi_offset: float = 0.0) -> list[dict]:
    """Resolve note timing, velocity and RNG state before choosing samples.

    Planning and rendering call this same function so humanization and phrasing
    cannot make the planner select a different velocity layer or round robin.
    Returned RNGs are local to this schedule; no global state is consumed.
    """
    events = note_events(track, timeline.beat_at(total_n / sr))
    paths = note_seed_paths(events)
    humanize = track.get("humanize")
    timing = (groove or {}).get("timing")
    accents = (groove or {}).get("accent")
    scheduled = []
    for index, (event, path) in enumerate(zip(events, paths)):
        frequency = event.get("freq_hz") or note_to_freq(event["note"])
        velocity = float(event.get("vel", 1.0))
        beat = event["start_beat"]
        slot = groove_slot(beat, track.get("name", ""), track.get("_score", {}), len(timing or accents or [0] * 16))
        if timing:
            beat += timing[slot] * 0.25
        if accents:
            velocity *= accents[slot]
        start_time = timeline.sec(beat) + time_offset_s
        rng = rng_factory(path)
        if humanize:
            rng.random()  # Keep velocity/sample selection on their own draw.
            start_time += timing_deviation(track, beat, rng_factory) * humanize.get("timing_s", 0.0)
            velocity *= 1 + (rng.random() * 2 - 1) * humanize.get("vel", 0.0)
        start = int(round(max(start_time, 0) * sr))
        gate_n = int(round((timeline.sec(event["start_beat"] + event["dur_beats"])
                            - timeline.sec(event["start_beat"])) * sr))
        if start >= total_n or gate_n <= 0:
            continue
        scheduled.append({
            "midi": freq_to_midi(frequency) + midi_offset,
            "vel": velocity, "start": start, "dur_n": gate_n, "rng": rng,
            "art": event.get("art", track.get("articulation", "sustain")),
            "slur": event.get("slur"), "event": event,
            "start_beat": event["start_beat"], "start_time_s": start_time,
            "note_index": index,
        })
    phrasing = float(track.get("phrasing", 0.0))
    if phrasing > 0:
        groups: dict[int, list[int]] = {}
        for index, note in enumerate(scheduled):
            if note["slur"]:
                groups.setdefault(note["slur"], []).append(index)
        for indices in groups.values():
            if len(indices) < 2:
                continue
            start = min(scheduled[index]["start_beat"] for index in indices)
            end = max(scheduled[index]["start_beat"] for index in indices)
            for index in indices:
                position = (scheduled[index]["start_beat"] - start) / max(end - start, 1e-9)
                x = 1 - abs(2 * position - 1)
                scheduled[index]["vel"] *= 1 + 0.18 * phrasing * (x - 0.5) * 2
    for note in scheduled:
        note["vel"] = float(np.clip(note["vel"], 0.0, 1.3))
    return scheduled
