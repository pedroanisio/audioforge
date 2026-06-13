#!/usr/bin/env python3
"""general_translator.py — Songsterr-style tab JSON  ->  AudioForge `.af` DSL.

Each input JSON is one instrument of a song (Songsterr-family export):

    { name, capo, strings, tunings?, instrument, instrumentId,
      automations: { tempo: [ { bpm, ... } ] },
      measures: [
        { signature?: [num, den],
          voices: [ { beats: [ { notes:[{fret,string}], duration:[n,d],
                                  velocity?:"f", rest? } ] } ] } ] }

Pass several files and they are arranged into ONE `.af` asset, one (or
more) layers per instrument, voiced with AudioForge's native synthesis
for render quality rather than a single flat tone:

* Drums (string==null; `fret` is the absolute GM MIDI note) split by
  instrument: 35/36->kick, 37-40->snare, 41-50->tom, 42/44->closed hat,
  46->open hat as real `drums` voices fed a full-song 16th-note pattern
  (the engine tiles the pattern; hits on the 8th/16th grid stay exact).
  Cymbals (49/52/55/57 crash, 51/53/59 ride) have no drum voice, so they
  render as `modal` (gong/steel) resonator strikes on note layers.

* Electric bass -> `saw` + saturation + low-pass cab, centred.

* Distortion / overdriven guitar -> `saw` + `drive` + scooped, present
  cab EQ, the layers panned apart so a two-guitar song images wide.

* Any other pitched part -> a clean `triangle`/`saw` synth layer.

Pitches resolve deterministically: with a real `string`, MIDI =
tunings[string] + fret + capo (the file's own `tunings` array is
authoritative); when `string==null`, `fret` IS the MIDI note.

⚠ ARCHITECTURAL CONTRACT (PALS's LAW) — generated output is untrusted.
With `--validate` (default) the emitted DSL is compiled through
`audioforge`; every diagnostic is printed and a hard error fails the run.

CLI:
    python scripts/general_translator.py in1.json [in2.json ...] [-o out.af]
           [--id ASSET_ID] [--no-validate]
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path

# DSL dynamic marks -> normalized 0..1 (mirrors audioforge.dsl.DYNAMIC_MARKS).
DYNAMIC_MARKS = {"ppp": 0.10, "pp": 0.22, "p": 0.35, "mp": 0.48,
                 "mf": 0.60, "f": 0.74, "ff": 0.87, "fff": 1.00}

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
STANDARD_GUITAR = [64, 59, 55, 50, 45, 40]  # high E -> low E, Songsterr order

A4_MIDI, A4_HZ = 69, 440.0

# General MIDI percussion -> AudioForge drum strategy.
GM_KICK = {35, 36}
GM_SNARE = {37, 38, 39, 40}
GM_TOM = {41, 43, 45, 47, 48, 50}
GM_HAT_CLOSED = {42, 44}
GM_HAT_OPEN = {46}
GM_CRASH = {49, 52, 55, 57}            # -> modal gong
GM_RIDE = {51, 53, 59}                 # -> modal steel

# `--sampled` routes these families to a content-addressed sampled library
# instead of a synth voice. Only families with a library compatible with
# AudioForge's SFZ subset (no `#include`, no CC layering) are listed: the
# Virtuosity drum kit and the VCSL percussion are `#include`/CC-based and
# do not load, and the repo ships no electric-bass library — so drums and
# bass stay on their (already realistic) synth path.
# All sampled instruments live in one merged library (AudioForge pins a
# single `library:` per asset). See scripts/build_band_library.py.
_BAND = "freepats-band"
SAMPLED_FAMILIES = {
    "guitar": {"library_dir": _BAND, "instrument": "eguitar_dist",
               "articulation": "sustain"},
    "bass": {"library_dir": _BAND, "instrument": "finger_bass",
             "articulation": "sustain"},
    # `drums` is special-cased in build_asset: a GM-keyed sampled kit routed
    # through emit_sampled_drums (kick split out so it can drive the
    # bass sidechain).
    "drums": {"library_dir": _BAND, "instrument": "muldjord_kit",
              "articulation": "sustain"},
}


def find_lib_root(start: Path) -> Path | None:
    """Walk up from `start` looking for a `libraries/` directory."""
    for base in [start, *start.parents]:
        if (base / "libraries").is_dir():
            return base
    return None


def library_pin(lib_root: Path, dir_name: str, instrument: str):
    """Return a `name@manifest_sha256` pin if the library exists and maps
    `instrument`, else None."""
    mf = lib_root / "libraries" / dir_name / "library.manifest.json"
    if not mf.exists():
        return None
    try:
        m = json.loads(mf.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if instrument not in (m.get("instruments") or {}):
        return None
    sha = m.get("manifest_sha256")
    return f"{m.get('name', dir_name)}@{sha}" if sha else None


def midi_to_token(midi: int) -> str:
    """MIDI -> a pitch token the grammar accepts (A4=69). Sub-octave-0
    notes (which would need a `-` the IDENT lexer rejects) fall back to an
    explicit frequency token, also valid anywhere a pitch is."""
    octave = midi // 12 - 1
    if octave < 0:
        return f"{A4_HZ * (2.0 ** ((midi - A4_MIDI) / 12.0)):.2f}hz"
    return f"{NOTE_NAMES[midi % 12]}{octave}"


def fmt(value: float) -> str:
    """Compact decimal for the DSL: up to 4 dp, no trailing zeros."""
    text = f"{value:.4f}".rstrip("0").rstrip(".")
    return text or "0"


def note_midi(note: dict, tuning: list[int], capo: int) -> int | None:
    fret = note.get("fret")
    if fret is None:
        return None
    string = note.get("string")
    if string is None:
        return int(fret)                      # absolute (drums)
    if not (0 <= string < len(tuning)):
        return None
    return int(tuning[string]) + int(fret) + int(capo)


def extract(data: dict) -> dict:
    """Parse one instrument file into a normalized intermediate form.

    voices maps a voice index to a list of
        (start_beat, dur_beats, [midi, ...], vel)
    with MIDI notes (not tokens) so drum-vs-pitched emitters can branch.
    """
    capo = int(data.get("capo", 0) or 0)
    raw_tuning = data.get("tunings") or data.get("tuning")
    tuning = ([int(t) for t in raw_tuning]
              if isinstance(raw_tuning, list) and raw_tuning else STANDARD_GUITAR)

    tempo_auto = (data.get("automations", {}) or {}).get("tempo") or []
    bpm = 120.0
    if tempo_auto and isinstance(tempo_auto[0], dict):
        bpm = float(tempo_auto[0].get("bpm", 120) or 120)

    voices: dict[int, list] = {}
    last_mark: dict[int, str] = {}
    any_string = False

    measure_start = 0.0
    sig = (4, 4)
    for measure in data.get("measures", []) or []:
        raw_sig = measure.get("signature")
        if isinstance(raw_sig, list) and len(raw_sig) == 2:
            sig = (int(raw_sig[0]), int(raw_sig[1]))
        bar_len = sig[0] * 4.0 / sig[1]
        for vi, voice in enumerate(measure.get("voices", []) or []):
            cursor = measure_start
            for beat in voice.get("beats", []) or []:
                dur = beat.get("duration")
                dur_beats = ((dur[0] / dur[1]) * 4.0
                             if isinstance(dur, list) and len(dur) == 2 and dur[1]
                             else bar_len)
                mark = beat.get("velocity")
                if isinstance(mark, str) and mark in DYNAMIC_MARKS:
                    last_mark[vi] = mark
                vel = DYNAMIC_MARKS.get(last_mark.get(vi, "mf"), 0.60)
                notes = beat.get("notes") or []
                if not (beat.get("rest") or not notes):
                    midis = []
                    for note in notes:
                        if note.get("string") is not None:
                            any_string = True
                        midi = note_midi(note, tuning, capo)
                        if midi is not None:
                            midis.append(midi)
                    if midis:
                        voices.setdefault(vi, []).append(
                            (cursor, dur_beats, midis, vel))
                cursor += dur_beats
        measure_start += bar_len

    instrument = str(data.get("instrument", "") or "")
    is_drums = "drum" in instrument.lower() or (not any_string and bool(voices))
    return {"bpm": bpm, "total_beats": measure_start, "voices": voices,
            "instrument": instrument, "is_drums": is_drums,
            "bar_beats": sig[0] * 4.0 / sig[1], "name": data.get("name") or ""}


# ---------------------------------------------------------------------------
# Dynamics model — Songsterr tabs rarely carry per-note velocity, so the raw
# translation is flat (one dynamic for the whole song). This synthesizes
# musical velocity from metric position and instrument role, which both grooves
# and — crucially — makes the multi-velocity sampled instruments switch sample
# layers (soft vs. hard hits are different recordings, not just amplitude).
# ---------------------------------------------------------------------------

def _drum_velocity(midi: int, start: float, bar: float) -> float:
    pos = start % bar
    beat = round(pos)
    on_beat = abs(pos - beat) < 1e-6
    if midi in GM_KICK:
        return 0.90 if beat % 2 == 0 else 0.66           # downbeat push
    if midi in GM_SNARE:
        return 0.95 if beat in (1, 3) else 0.40          # backbeat vs ghost
    if midi in GM_HAT_CLOSED:
        return 0.72 if on_beat else 0.45                 # accented vs ghosted
    if midi in GM_HAT_OPEN:
        return 0.82
    if midi in GM_CRASH:
        return 0.96
    if midi in GM_RIDE:
        return 0.72 if on_beat else 0.55
    if midi in GM_TOM:
        return 0.82
    return 0.70


def _melodic_velocity(start: float, bar: float) -> float:
    pos = start % bar
    beat = round(pos)
    if abs(pos - beat) < 1e-6:
        return 0.86 if beat % 2 == 0 else 0.78           # strong vs weak beat
    if abs(pos * 2 - round(pos * 2)) < 1e-6:
        return 0.66                                      # eighth offbeat
    return 0.56                                          # sixteenth offbeat


def apply_dynamics(song: dict, role: str) -> None:
    """Rewrite event velocities in place from metric position. Drum events are
    exploded per-instrument so each piece gets its own accent."""
    bar = song.get("bar_beats", 4.0) or 4.0
    for vi, evs in list(song["voices"].items()):
        out = []
        for start, dur, midis, _vel in evs:
            if role == "drums":
                for m in midis:
                    out.append((start, dur, [m], _drum_velocity(m, start, bar)))
            else:
                out.append((start, dur, midis, _melodic_velocity(start, bar)))
        song["voices"][vi] = out


# ---------------------------------------------------------------------------
# Intensity arc — the tab has no song-level dynamics, so derive an arc from
# the music itself: per-bar note density (all parts) → a smoothed envelope.
# Busy sections (choruses, fills) read as peaks. The envelope drives the
# asset `intensity:` curve (master build) and a coarse `dynamic:` curve on the
# guitar layers (velocity-layer crossfade into the peaks).
# ---------------------------------------------------------------------------

def intensity_envelope(songs, bar_beats, total_beats):
    bars = max(1, int(math.ceil(total_beats / bar_beats)))
    dens = [0.0] * bars
    for s in songs:
        for evs in s["voices"].values():
            for start, _dur, midis, _vel in evs:
                b = int(start // bar_beats)
                if 0 <= b < bars:
                    dens[b] += len(midis)
    sm = []  # 3-bar moving average
    for i in range(bars):
        lo, hi = max(0, i - 1), min(bars, i + 2)
        sm.append(sum(dens[lo:hi]) / (hi - lo))
    mx = max(sm) or 1.0
    return [0.45 + 0.55 * (v / mx) for v in sm]   # normalize to 0.45..1.0


def _mark_for(v: float) -> str:
    return "mp" if v < 0.58 else "mf" if v < 0.72 else "f" if v < 0.86 else "ff"


# ---------------------------------------------------------------------------
# Layer emitters — each returns a list of text lines for one or more layers.
# ---------------------------------------------------------------------------

def _note_lines(header_indent: str, events, transpose: int = 0):
    """Render `(start,dur,[midi],vel)` events as a `notes:` body. First
    event sits on the `notes:` line; the rest continue with commas."""
    tokens: list[str] = []
    for start, dur, midis, vel in events:
        sb, db, vb = fmt(start), fmt(dur), f"{vel:.2f}"
        for midi in midis:
            tokens.append(f"{midi_to_token(midi + transpose)} @ {sb}b for {db}b vel {vb}")
    out = []
    for idx, tok in enumerate(tokens):
        comma = "," if idx < len(tokens) - 1 else ""
        out.append((f"{header_indent}notes:      {tok}{comma}" if idx == 0
                    else f"{header_indent}  {tok}{comma}"))
    return out


def _pattern_for(events, hits_midi: set[int], n_steps: int):
    """Build a tiled 16th-note pattern string for one drum voice. Returns
    (pattern, off_grid_count). A hit is accented (`X`) at vel>=0.8."""
    grid = ["."] * n_steps
    off = 0
    for start, _dur, midis, vel in events:
        if not any(m in hits_midi for m in midis):
            continue
        step = int(round(start * 4.0))
        if abs(start * 4.0 - step) > 1e-6:
            off += 1
        if 0 <= step < n_steps:
            grid[step] = "X" if (vel >= 0.80 and grid[step] != "X") else (
                grid[step] if grid[step] == "X" else "x")
    return "".join(grid), off


def emit_drums(prefix: str, song: dict, n_steps: int,
               bus: str | None = None) -> tuple[list[str], list[str], bool]:
    """Drum kit -> real drum-voice pattern layers + modal cymbal layers.
    Returns (lines, off_grid_notes, has_kick)."""
    events = [e for evs in song["voices"].values() for e in evs]
    lines: list[str] = []
    warns: list[str] = []
    has_kick = False

    voice_defs = [
        ("kick", GM_KICK, "    tune:    -1st\n    bend:    0.7", "-3db", "humanize: 0.08"),
        ("snare", GM_SNARE, "    snap:    0.7", "-5db", "humanize: 0.12"),
        ("tom", GM_TOM, "    tune:    -4st\n    decay:   0.9", "-7db", "humanize: 0.10"),
        ("hat", GM_HAT_CLOSED, "    decay:   0.35", "-12db", "humanize: 0.15"),
        ("open_hat", GM_HAT_OPEN, "    decay:   0.9", "-13db", "humanize: 0.12"),
    ]
    for voice, hits, depth, gain, hum in voice_defs:
        pattern, off = _pattern_for(events, hits, n_steps)
        if "x" not in pattern and "X" not in pattern:
            continue
        if off:
            warns.append(f"{voice}: {off} hit(s) off the 16th grid, snapped")
        if voice == "kick":
            has_kick = True
        lines.append(f"  layer {prefix}_{voice} : drums {{")
        lines.append(f"    voice:   {voice}")
        lines.append(f"    gain:    {gain}")
        lines.append(f"    {hum}")
        for ln in depth.split("\n"):
            lines.append(ln)
        if bus:
            lines.append(f"    bus:     {bus}")
        lines.append(f'    pattern: "{pattern}"')
        lines.append("  }")
        lines.append("")

    # Cymbals -> modal resonator strikes on note layers (no drum voice).
    cymbals = [
        ("crash", GM_CRASH, "gong", "2.6s", "-9db", "0.18", "highpass(280hz)", 12),
        ("ride", GM_RIDE, "steel", "1.4s", "-11db", "-0.18", "highpass(360hz)", 12),
    ]
    for name, hits, material, decay, gain, pan, fx, oct_up in cymbals:
        evs = [(s, d, [m for m in midis if m in hits], v)
               for (s, d, midis, v) in events if any(m in hits for m in midis)]
        if not evs:
            continue
        lines.append(f"  layer {prefix}_{name} : notes {{")
        lines.append("    osc:      modal")
        lines.append(f"    material: {material}")
        lines.append(f"    modedecay: {decay}")
        lines.append(f"    gain:     {gain}")
        lines.append(f"    pan:      {pan}")
        lines.append(f"    env:      a=0.001s d=0.08s s=0.85 r={decay}")
        lines.append(f"    fx:       {fx}")
        if bus:
            lines.append(f"    bus:      {bus}")
        lines.append("")
        lines += _note_lines("    ", evs, transpose=oct_up)
        lines.append("  }")
        lines.append("")
    return lines, warns, has_kick


def emit_pitched(prefix: str, song: dict, family: str, pan: float,
                 bus: str | None = None) -> list[str]:
    """Bass / distortion guitar / generic pitched part -> one notes layer
    voiced for its family."""
    events = [e for evs in song["voices"].values() for e in evs]
    lines = [f"  layer {prefix} : notes {{"]
    if family == "bass":
        lines += [
            "    osc:        saw",
            "    gain:       -4db",
            "    pan:        0",
            "    env:        a=0.004s d=0.09s s=0.9 r=0.12s",
            "    humanize:   0.06",
            "    velbright:  0.3",
            # Grind + a 1.1 kHz presence bump so the bass is audible through
            # the guitars and on speakers that can't reproduce its <80 Hz
            # fundamentals; lowpass opened up to pass those harmonics.
            "    fx:         highpass(35hz), drive(amount=0.28),",
            "                saturate(amount=0.3, warmth=0.5),",
            "                peak(1100hz, gain=4, q=1.0), lowpass(3800hz)",
        ]
    elif family == "guitar":
        lines += [
            "    osc:        saw",
            "    unison:     2",
            "    spread:     12c",
            "    gain:       -8db",
            f"    pan:        {fmt(pan)}",
            "    env:        a=0.002s d=0.06s s=0.85 r=0.09s",
            "    humanize:   0.08",
            "    velbright:  0.35",
            "    fx:         highpass(130hz), drive(amount=0.7), peak(450hz, gain=-3, q=1.1),",
            "                peak(2300hz, gain=4, q=1.2), lowpass(5200hz)",
        ]
    else:
        lines += [
            "    osc:        triangle",
            "    gain:       -6db",
            f"    pan:        {fmt(pan)}",
            "    env:        a=0.005s d=0.10s s=0.7 r=0.20s",
            "    humanize:   0.06",
        ]
    if bus:
        lines.append(f"    bus:        {bus}")
    lines.append("")
    lines += _note_lines("    ", events)
    lines.append("  }")
    lines.append("")
    return lines


def emit_sampled(prefix: str, song: dict, spec: dict, family: str,
                 pan: float, bus: str | None = None,
                 dynamic_line: str | None = None) -> list[str]:
    """Pitched part -> a sampled `instrument` layer. For distorted guitar
    the clean samples are driven through an amp/cab fx chain."""
    events = [e for evs in song["voices"].values() for e in evs]
    lines = [f"  layer {prefix} : instrument {{",
             f'    instrument:   "{spec["instrument"]}"',
             f"    articulation: {spec['articulation']}",
             f"    pan:          {fmt(pan)}",
             "    humanize:     0.06"]
    if dynamic_line:
        lines.append(f"    dynamic:      {dynamic_line}")
    if family == "guitar":
        lines += [
            "    gain:         -8db",
            # Real distorted-guitar samples — no synth drive needed. Section
            # double-tracks the (per-RR) samples into a true-stereo wall;
            # light tone shaping tightens lows and adds cab presence.
            # Keep each guitar on its own side (moderate spread) so the two
            # distinct parts separate hard L/R instead of overlapping centre.
            "    section:      size=2 spread=0.5 detune=12c timing=0.014s",
            "    fx:           highpass(95hz), peak(2400hz, gain=2.5, q=1.1), lowpass(8500hz)",
        ]
    elif family == "bass":
        lines += [
            "    gain:         -3db",
            # Real bass sample: keep it natural, just add a presence bump so
            # it reads through the guitars and on small speakers (drive/glue
            # live on the af_low bus).
            "    fx:           highpass(35hz), peak(1100hz, gain=3, q=1.0)",
        ]
    else:
        lines.append("    gain:         -6db")
    if bus:
        lines.append(f"    bus:          {bus}")
    lines.append("")
    lines += _note_lines("    ", events)
    lines.append("  }")
    lines.append("")
    return lines


# Kit imaging (drummer's perspective, modest spread): kick/snare centred,
# hats and ride to one side, crash to the other, toms a touch left.
DRUM_PAN_GROUPS = [
    ("kick", GM_KICK, 0.0, "-3db"),                 # sidechain source
    ("snare", GM_SNARE, -0.05, "-4db"),
    ("hats", GM_HAT_CLOSED | GM_HAT_OPEN, 0.30, "-6db"),
    ("toms", GM_TOM, -0.12, "-5db"),
    ("crash", GM_CRASH, -0.42, "-6db"),
    ("ride", GM_RIDE, 0.40, "-6db"),
]


def emit_sampled_drums(prefix: str, song: dict, spec: dict,
                       bus: str | None = None,
                       spatial: bool = False) -> tuple[list[str], str | None]:
    """Drum kit -> sampled GM-keyed `instrument` layers. The kick is always
    its own layer (so it can drive the bass sidechain). With `spatial`, each
    kit piece becomes its own panned layer for a real stereo kit image;
    otherwise snare/toms/hats/cymbals share one centred layer. Returns
    (lines, kick_name)."""
    events = [e for evs in song["voices"].values() for e in evs]
    inst, art = spec["instrument"], spec["articulation"]
    lines: list[str] = []
    kick_name = None

    def layer(name, evs, gain, pan=None):
        block = [f"  layer {name} : instrument {{",
                 f'    instrument:   "{inst}"',
                 f"    articulation: {art}",
                 f"    gain:         {gain}",
                 "    humanize:     0.08"]
        if pan is not None:
            block.append(f"    pan:          {fmt(pan)}")
        if bus:
            block.append(f"    bus:          {bus}")
        block.append("")
        block += _note_lines("    ", evs)
        block += ["  }", ""]
        return block

    def evs_for(midi_set):
        out = []
        for start, dur, midis, vel in events:
            sel = [m for m in midis if m in midi_set]
            if sel:
                out.append((start, dur, sel, vel))
        return out

    if spatial:
        for name, mset, pan, gain in DRUM_PAN_GROUPS:
            evs = evs_for(mset)
            if not evs:
                continue
            lname = f"{prefix}_{name}"
            lines += layer(lname, evs, gain, pan=pan)
            if name == "kick":
                kick_name = lname
    else:
        kick_events = evs_for(GM_KICK)
        kit_events = [(s, d, [m for m in ms if m not in GM_KICK], v)
                      for (s, d, ms, v) in events if any(m not in GM_KICK
                                                         for m in ms)]
        if kick_events:
            kick_name = f"{prefix}_kick"
            lines += layer(kick_name, kick_events, "-3db")
        if kit_events:
            lines += layer(f"{prefix}_kit", kit_events, "-4db")
    return lines, kick_name


def sanitize_id(text: str, fallback: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_]", "_", (text or "").strip()).strip("_")
    if not cleaned or not re.match(r"[A-Za-z_]", cleaned):
        cleaned = fallback
    return cleaned


def build_asset(songs: list[dict], asset_id: str, sampled: bool = False,
                lib_root: Path | None = None,
                dynamics: bool = False, space: bool = False
                ) -> tuple[str, list[str]]:
    bpm = next((s["bpm"] for s in songs), 120.0)
    total_beats = max((s["total_beats"] for s in songs), default=0.0)
    tail_s = 2.0
    duration_s = round(total_beats * 60.0 / bpm + tail_s, 3)
    # Pad drum patterns past every step the engine will index (it tiles to
    # ceil(beats*4)); padding to len==n_steps prevents the pattern wrapping
    # back to bar 1 inside the tail.
    n_steps = int(math.ceil(duration_s * bpm / 60.0 * 4.0)) + 16

    warns: list[str] = []

    # --- Plan parts up front so buses (declared first) know their members
    # and the bass sidechain can name the kick layer. ---
    guitar_pans = [-0.72, 0.72, -0.4, 0.4]
    guitar_idx = 0
    plan = []  # (song, prefix, role, family/None, pan/None)
    for i, song in enumerate(songs):
        prefix = f"{sanitize_id(song['instrument'], f'part{i + 1}').lower()}_{i + 1}"
        if song["is_drums"]:
            plan.append((song, prefix, "drums", None, None))
        else:
            name = song["instrument"].lower()
            if "bass" in name:
                plan.append((song, prefix, "pitched", "bass", 0.0))
            elif "guitar" in name or "dist" in name or "overdri" in name:
                plan.append((song, prefix, "pitched", "guitar",
                             guitar_pans[guitar_idx % len(guitar_pans)]))
                guitar_idx += 1
            else:
                plan.append((song, prefix, "pitched", "other", 0.0))

    if dynamics:
        for song, _prefix, role, _family, _pan in plan:
            apply_dynamics(song, role)

    # Intensity arc from per-bar density -> master `intensity:` + guitar
    # `dynamic:` build (only meaningful once velocities vary, i.e. --dynamics).
    bar_beats = next((s.get("bar_beats", 4.0) for s in songs), 4.0) or 4.0
    beat_s = 60.0 / bpm
    intensity_line = None
    gtr_dynamic = None
    if dynamics:
        env = intensity_envelope(songs, bar_beats, total_beats)
        bars = len(env)
        ipts = [f"{fmt(round(i * bar_beats * beat_s, 2))}s={fmt(round(env[i], 2))}"
                for i in range(0, bars, 4)]
        ipts.append(f"{fmt(round(total_beats * beat_s, 2))}s={fmt(round(env[-1], 2))}")
        intensity_line = ", ".join(ipts)
        dpts, last = [], None
        for i in range(0, bars, 8):
            m = _mark_for(env[i])
            if m != last:
                dpts.append(f"{fmt(i * bar_beats)}b={m}")
                last = m
        gtr_dynamic = ", ".join(dpts) or None

    has_drums = any(p[2] == "drums" for p in plan)
    has_guitar = any(p[3] == "guitar" for p in plan)
    has_bass = any(p[3] == "bass" for p in plan)
    # The kick layer name (for the bass sidechain) is the kick voice on the
    # first drum part that actually plays a kick.
    kick_layer = None
    for song, prefix, role, _f, _p in plan:
        if role == "drums" and any(
                m in GM_KICK
                for evs in song["voices"].values() for (_s, _d, ms, _v) in evs
                for m in ms):
            kick_layer = f"{prefix}_kick"
            break

    drum_bus = "af_drums" if has_drums else None
    gtr_bus = "af_gtr" if has_guitar else None
    low_bus = "af_low" if has_bass else None

    # Resolve sampled-instrument libraries (--sampled). Only families with a
    # subset-compatible library that actually maps the instrument are taken.
    sampled_specs: dict[str, dict] = {}
    library_pins: list[str] = []
    if sampled:
        root = lib_root or Path.cwd()
        families = {p[3] for p in plan if p[3]}
        if has_drums:
            families.add("drums")
        for fam in families:
            cfg = SAMPLED_FAMILIES.get(fam)
            if not cfg:
                continue
            pin = library_pin(root, cfg["library_dir"], cfg["instrument"])
            if pin:
                sampled_specs[fam] = cfg
                if pin not in library_pins:
                    library_pins.append(pin)
            else:
                warns.append(f"{fam}: sampled library unresolved, using synth")

    lines = [
        "# " + "=" * 75,
        "# AudioForge DSL — generated by scripts/general_translator.py",
        "#",
        f"# Song:   {songs[0]['name'] or '(untitled)'}",
        f"# Tempo:  {fmt(bpm)} bpm    Bars: {fmt(total_beats / 4)} (4/4)",
        "# Parts:  " + ", ".join(s["instrument"] or "unknown" for s in songs),
        "#",
        "# Mix: drum-glue bus (transient + comp + tone), guitar bus (glue +",
        "#      stereo reverb for width), bass bus sidechain-ducked by the kick.",
        "#",
        "# ARCHITECTURAL REQUIREMENT (PALS's LAW): translator output is verified",
        "# by compiling this DSL through audioforge (--validate).",
        "# " + "=" * 75,
        "",
        f"asset {asset_id} {{",
        "",
        "  kind:       soundtrack",
        f"  duration:   {fmt(duration_s)}s",
        "  samplerate: 48000",
        "  bitdepth:   24",
        f"  tempo:      {fmt(bpm)}bpm",
        "",
    ]
    if intensity_line:
        lines.append(f"  intensity:  {intensity_line}")
        lines.append("")
    for pin in library_pins:
        lines.append(f'  library:    "{pin}"')
    if library_pins:
        lines.append("")

    # --- Buses (must be declared before any layer references them) ---
    if drum_bus:
        drum_fx = [
            "    fx: transient(attack=3, sustain=-1),",
            "        comp(threshold=-13, ratio=3, attack=0.004, release=0.11, knee=4),",
            "        peak(75hz, gain=2, q=0.9),",
            "        peak(5000hz, gain=2, q=0.8)" + ("," if space else ""),
        ]
        if space:                      # short, bright drum room for depth
            drum_fx.append("        plate(decay=0.6, damp=0.45, mix=0.10)")
        lines += [f"  bus {drum_bus} {{", "    gain: 0db", *drum_fx, "  }", ""]
    if gtr_bus:
        gtr_verb = ("hall(rt60=1.6, damp=0.35, mix=0.14)" if space
                    else "reverb(decay=0.8, mix=0.06)")
        lines += [
            f"  bus {gtr_bus} {{",
            "    gain: -1db",
            "    fx: comp(threshold=-15, ratio=2, attack=0.012, release=0.14, knee=6),",
            f"        {gtr_verb}",
            "  }",
            "",
        ]
    if low_bus:
        lines.append(f"  bus {low_bus} {{")
        if kick_layer:
            lines.append(f"    duck: source={kick_layer} amount=4db "
                         "attack=0.004s release=0.13s threshold=-32db")
        lines += [
            "    gain: 0db",
            "    fx: saturate(amount=0.2, warmth=0.5)",
            "  }",
            "",
        ]

    # --- Layers ---
    for song, prefix, role, family, pan in plan:
        lines.append(f"  # --- {song['instrument'] or 'part'} ---")
        if role == "drums":
            if "drums" in sampled_specs:
                dl, _ = emit_sampled_drums(prefix, song,
                                           sampled_specs["drums"], bus=drum_bus,
                                           spatial=space)
                lines += dl
            else:
                dl, dw, _ = emit_drums(prefix, song, n_steps, bus=drum_bus)
                lines += dl
                warns += [f"{prefix}: {w}" for w in dw]
        else:
            bus = {"bass": low_bus, "guitar": gtr_bus}.get(family)
            dyn = gtr_dynamic if family == "guitar" else None
            if family in sampled_specs:
                lines += emit_sampled(prefix, song, sampled_specs[family],
                                      family, pan, bus=bus, dynamic_line=dyn)
            else:
                lines += emit_pitched(prefix, song, family, pan, bus=bus)

    # Master space: a true-stereo FDN tail widens and deepens the whole mix.
    master_verb = ("fdn(rt60=1.9, rt60_high=0.9, crossover=2600, mix=0.13)"
                   if space else "reverb(decay=1.1, mix=0.06)")
    lines += [
        "  master {",
        "    width:   1.0",
        "    lufs:    -12",
        "    peak:    -1.0",
        "    fadeout: 1.5s",
        "    fx: highpass(28hz),",
        "        comp(threshold=-16, ratio=2.2, attack=0.01, release=0.18, knee=6),",
        f"        {master_verb},",
        "        highshelf(9000hz, gain=1.0)",
        "  }",
        "}",
    ]
    return "\n".join(lines) + "\n", warns


def validate_af(text: str) -> tuple[bool, list[str]]:
    try:
        from audioforge import AudioForge
    except Exception as exc:  # pragma: no cover
        return True, [f"skipped validation (audioforge not importable: {exc})"]
    result = AudioForge().compile(text)
    msgs = [f"{d.severity}: {d.message}"
            + (f"  [{d.path}]" if getattr(d, "path", None) else "")
            for d in result.diagnostics]
    return result.ok, msgs


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Translate one or more Songsterr-style instrument JSON "
                    "files into a single AudioForge .af arrangement.")
    parser.add_argument("inputs", type=Path, nargs="+", help="input .json file(s)")
    parser.add_argument("-o", "--output", type=Path, help="output .af file")
    parser.add_argument("--id", dest="asset_id", default=None, help="asset id")
    parser.add_argument("--sampled", action="store_true",
                        help="route supported families (guitar) to sampled "
                             "instrument libraries instead of synth voices")
    parser.add_argument("--dynamics", action="store_true",
                        help="synthesize per-note velocity from metric position "
                             "(accents/ghosts) plus a density-driven intensity arc")
    parser.add_argument("--space", action="store_true",
                        help="pan the drum kit into a stereo image and add "
                             "room/hall/FDN reverb for depth and width")
    parser.add_argument("--no-validate", action="store_true")
    args = parser.parse_args(argv)

    songs = []
    for path in args.inputs:
        if not path.exists():
            print(f"error: input not found: {path}", file=sys.stderr)
            return 2
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            print(f"error: invalid JSON in {path}: {exc}", file=sys.stderr)
            return 2
        songs.append(extract(data))

    base = args.inputs[0]
    asset_id = sanitize_id(
        args.asset_id or songs[0]["name"] or re.sub(r"-\d+$", "", base.stem),
        fallback=sanitize_id(base.stem, "song"))

    lib_root = find_lib_root(base.resolve().parent) or Path.cwd()
    text, warns = build_asset(songs, asset_id, sampled=args.sampled,
                              lib_root=lib_root, dynamics=args.dynamics,
                              space=args.space)
    out_path = args.output or base.with_name(
        re.sub(r"-\d+$", "", base.stem) + ".af")
    out_path.write_text(text, encoding="utf-8")
    print(f"wrote {out_path}  (asset {asset_id}, {len(songs)} part(s))")
    for w in warns:
        print(f"  note: {w}")

    if not args.no_validate:
        ok, msgs = validate_af(text)
        for msg in msgs:
            print(f"  {msg}")
        if not ok:
            print("  -> validation FAILED", file=sys.stderr)
            return 1
        print("  -> OK: valid — render-ready")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
