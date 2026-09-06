#!/usr/bin/env python3
"""tune_scom.py — produce a *tuned* AudioForge arrangement from the imported
Sweet Child O' Mine MIDI.

The bare `import-midi` decompile is correct but un-voiced: every guitar is a
`pluck`, drums are pitched beeps, there is no mix. This pass re-voices it with
AudioForge's real feature surface (DSL_SPEC §5–9, §16):

* pitched parts  -> `saw` with unison/spread, drive/cab-EQ guitar chains,
  saturated bass; panned into a stereo image; velocity->brightness coupling.
  Their note bodies AND the lead's `auto pitch_cents:` bends are lifted verbatim
  from the bare decompile (lossless — nothing re-quantized).
* percussion     -> the channel-10 note events become real `drums`-voice
  pattern layers (kick/snare/hat/open_hat/tom) on a 16th grid, plus `modal`
  cymbal strikes — authentic drum synthesis instead of pitched tones.
* mix            -> drum-glue bus, guitar bus (glue + width reverb), bass bus
  sidechain-ducked by the kick, and a mastering chain at -11 LUFS.

⚠ ARCHITECTURAL CONTRACT (PALS's LAW): the emitted DSL is untrusted until the
engine compiles it. This script compiles the result and fails on any error.
"""
from __future__ import annotations

import math
import re
import sys
from pathlib import Path

from audioforge import AudioForge, interop
from audioforge.decompile import spec_to_dsl

MIDI = Path("docs/examples/arrangements/sweet-child-o-mine/inputs/sweetchildofmine.mid")
OUT = Path("docs/examples/arrangements/sweet-child-o-mine-tuned/sweet_child_o_mine.tuned.af")

# GM percussion -> drum strategy (mirrors scripts/general_translator.py).
GM_KICK = {35, 36}
GM_SNARE = {37, 38, 39, 40}
GM_TOM = {41, 43, 45, 47, 48, 50}
GM_HAT_CLOSED = {42, 44}
GM_HAT_OPEN = {46}
GM_CRASH = {49, 52, 55, 57}
GM_RIDE = {51, 53, 59}

# Per pitched part: (osc-header lines). Roles assigned from the GM voicing the
# importer recovered: P2 picked bass, P6 the main riff, P4 second rhythm, P7 the
# lead (carries the whammy bends), P10 a third rhythm voice.
PITCHED = {
    "P2_Picked": [          # electric bass
        "    osc:       saw",
        "    gain:      -4db",
        "    pan:       0",
        "    env:       a=0.004s d=0.09s s=0.9 r=0.12s",
        "    humanize:  0.05",
        "    velbright: 0.3",
        "    fx:        highpass(35hz), saturate(amount=0.3, warmth=0.5),",
        "               lowpass(2600hz), peak(700hz, gain=2, q=1)",
        "    bus:       af_low",
    ],
    "P6_Steel": [           # main rhythm riff (panned left)
        "    osc:       saw",
        "    unison:    2",
        "    spread:    12c",
        "    gain:      -8db",
        "    pan:       -0.42",
        "    env:       a=0.003s d=0.08s s=0.8 r=0.12s",
        "    humanize:  0.06",
        "    velbright: 0.4",
        "    fx:        highpass(95hz), drive(amount=0.65), peak(450hz, gain=-3, q=1.1),",
        "               peak(2300hz, gain=4, q=1.2), lowpass(5400hz)",
        "    bus:       af_gtr",
    ],
    "P4_Overdr": [          # second rhythm (panned right)
        "    osc:       saw",
        "    unison:    2",
        "    spread:    12c",
        "    gain:      -8db",
        "    pan:       0.42",
        "    env:       a=0.003s d=0.08s s=0.8 r=0.12s",
        "    humanize:  0.06",
        "    velbright: 0.4",
        "    fx:        highpass(95hz), drive(amount=0.6), peak(450hz, gain=-3, q=1.1),",
        "               peak(2300hz, gain=4, q=1.2), lowpass(5400hz)",
        "    bus:       af_gtr",
    ],
    "P7_Distor": [          # lead (centre, brighter, more sustain — keeps bends)
        "    osc:       saw",
        "    unison:    2",
        "    spread:    8c",
        "    gain:      -7db",
        "    pan:       0.08",
        "    env:       a=0.004s d=0.12s s=0.85 r=0.18s",
        "    humanize:  0.03",
        "    velbright: 0.45",
        "    fx:        highpass(110hz), drive(amount=0.8), peak(900hz, gain=2, q=1),",
        "               peak(3200hz, gain=5, q=1.1), lowpass(6500hz)",
        "    bus:       af_gtr",
    ],
    "P10_ROCK": [           # third rhythm voice (near centre)
        "    osc:       saw",
        "    unison:    2",
        "    spread:    10c",
        "    gain:      -9db",
        "    pan:       0.16",
        "    env:       a=0.003s d=0.08s s=0.78 r=0.12s",
        "    humanize:  0.06",
        "    velbright: 0.4",
        "    fx:        highpass(95hz), drive(amount=0.5), peak(2300hz, gain=3, q=1.2),",
        "               lowpass(5200hz)",
        "    bus:       af_gtr",
    ],
}


def parse_pitched_bodies(bare_af: str) -> dict[str, list[str]]:
    """Lift each pitched layer's note body (the `notes:`/`auto` lines, with any
    comma-continuation lines) from the bare decompile — lossless."""
    lines = bare_af.splitlines()
    bodies: dict[str, list[str]] = {}
    i = 0
    while i < len(lines):
        m = re.match(r"\s*layer (\S+) : notes \{", lines[i])
        if not m:
            i += 1
            continue
        name = m.group(1)
        i += 1
        body: list[str] = []
        capture = False
        while i < len(lines) and not re.match(r"\s*\}", lines[i]):
            stripped = lines[i].strip()
            if stripped.startswith(("notes:", "auto ", "play ")):
                capture = True
            elif re.match(r"\w+:", stripped) and not stripped[0].isspace():
                capture = stripped.startswith(("notes:", "auto "))
            if capture:
                body.append(lines[i])
            i += 1
        bodies[name] = body
    return bodies


def drum_events(spec: dict) -> list[tuple[float, float, list[int], float]]:
    """All channel-10 note events, as (start_beat, dur_beats, [midi], vel)."""
    out = []
    for layer in spec["layers"]:
        if not layer["name"].lower().startswith("drum"):
            continue
        for ev in layer["notes"]:
            midi = interop._midi_note(ev["note"])
            out.append((ev["start_beat"], ev["dur_beats"], [midi],
                        float(ev.get("vel", 0.7))))
    return out


def drum_pattern(events, hits: set[int], n_steps: int) -> tuple[str, int]:
    grid = ["."] * n_steps
    off = 0
    for start, _d, midis, vel in events:
        if not any(m in hits for m in midis):
            continue
        step = int(round(start * 4.0))
        if abs(start * 4.0 - step) > 1e-6:
            off += 1
        if 0 <= step < n_steps:
            if vel >= 0.80 or grid[step] == "X":
                grid[step] = "X"
            elif grid[step] != "X":
                grid[step] = "x"
    return "".join(grid), off


def note_token(midi: int) -> str:
    from audioforge import theory
    return theory.semis_to_note(midi - 12)


def emit_drums(events, n_steps: int) -> tuple[list[str], list[str], set[str]]:
    lines: list[str] = []
    warns: list[str] = []
    emitted: set[str] = set()
    voice_defs = [
        ("drumkick", "kick", GM_KICK, "-3db",
         ["    tune:    -1st", "    bend:    0.7"], "0.08"),
        ("drumsnare", "snare", GM_SNARE, "-5db", ["    snap:    0.7"], "0.12"),
        ("drumtom", "tom", GM_TOM, "-7db",
         ["    tune:    -4st", "    decay:   0.9"], "0.10"),
        ("drumhat", "hat", GM_HAT_CLOSED, "-12db", ["    decay:   0.35"], "0.15"),
        ("drumopenhat", "open_hat", GM_HAT_OPEN, "-13db",
         ["    decay:   0.9"], "0.12"),
    ]
    for lname, voice, hits, gain, depth, hum in voice_defs:
        pattern, off = drum_pattern(events, hits, n_steps)
        if "x" not in pattern and "X" not in pattern:
            continue
        if off:
            warns.append(f"{voice}: {off} hit(s) snapped to the 16th grid")
        emitted.add(lname)
        lines.append(f"  layer {lname} : drums {{")
        lines.append(f"    voice:   {voice}")
        lines.append(f"    gain:    {gain}")
        lines.append(f"    humanize: {hum}")
        lines += depth
        lines.append("    bus:     af_drums")
        lines.append(f'    pattern: "{pattern}"')
        lines.append("  }")
        lines.append("")

    # Cymbals -> modal resonator strikes on note layers (no drum voice).
    cymbals = [
        ("drumcrash", GM_CRASH, "gong", "2.6s", "-9db", "0.18", "highpass(280hz)", 12),
        ("drumride", GM_RIDE, "steel", "1.4s", "-11db", "-0.18", "highpass(360hz)", 12),
    ]
    for lname, hits, material, decay, gain, pan, fx, oct_up in cymbals:
        evs = [(s, m) for (s, _d, midis, _v) in events
               for m in midis if m in hits]
        if not evs:
            continue
        emitted.add(lname)
        toks = [f"{note_token(m + oct_up)} @ {s:.4f}b for 0.25b vel 0.7"
                for s, m in evs]
        lines.append(f"  layer {lname} : notes {{")
        lines.append("    osc:      modal")
        lines.append(f"    material: {material}")
        lines.append(f"    modedecay: {decay}")
        lines.append(f"    gain:     {gain}")
        lines.append(f"    pan:      {pan}")
        lines.append(f"    env:      a=0.001s d=0.08s s=0.85 r={decay}")
        lines.append(f"    fx:       {fx}")
        lines.append("    bus:      af_drums")
        lines.append("    notes:    " + ", ".join(toks))
        lines.append("  }")
        lines.append("")
    return lines, warns, emitted


def main() -> int:
    data = MIDI.read_bytes()
    spec = interop.import_midi_bytes(data, asset_id="sweet_child_o_mine")
    bare = spec_to_dsl(spec)
    bodies = parse_pitched_bodies(bare)

    bpm = spec["bpm"]
    dur = spec["duration_s"]
    devs = drum_events(spec)
    max_beat = max((s + d for s, d, _m, _v in devs), default=0.0)
    n_steps = int(math.ceil(max_beat * 4.0)) + 4

    out: list[str] = [
        "# " + "=" * 74,
        "# AudioForge DSL — TUNED arrangement (scripts/tune_scom.py)",
        "# Source: docs/examples/arrangements/sweet-child-o-mine/inputs/sweetchildofmine.mid (import-midi -> tuned mix)",
        "# ARCHITECTURAL REQUIREMENT (PALS's LAW): verified by compiling this DSL.",
        "# " + "=" * 74,
        "",
        "asset sweet_child_o_mine {",
        "  kind:       soundtrack",
        f"  duration:   {dur}s",
        "  samplerate: 48000",
        "  bitdepth:   24",
        f"  tempo:      {bpm:.3f}bpm",
        "",
        "  bus af_drums {",
        "    gain: 0db",
        "    fx: transient(attack=3, sustain=-1),",
        "        comp(threshold=-13, ratio=3, attack=0.004, release=0.11, knee=4),",
        "        peak(75hz, gain=2, q=0.9), peak(5000hz, gain=2, q=0.8)",
        "  }",
        "",
        "  bus af_gtr {",
        "    gain: -1db",
        "    fx: comp(threshold=-15, ratio=2, attack=0.012, release=0.14, knee=6),",
        "        reverb(decay=0.8, mix=0.06)",
        "  }",
        "",
    ]

    # Drums first: a sidechain source layer must exist before the bass bus
    # names it (duck sources must be declared earlier).
    out.append("  # --- drum kit (channel 10 -> real drum voices) ---")
    drum_lines, warns, emitted = emit_drums(devs, n_steps)
    out += drum_lines

    # This MIDI's percussion has no kick; only sidechain the bass if a kick
    # voice was actually emitted (honest: no fabricated kick).
    out.append("  bus af_low {")
    if "drumkick" in emitted:
        out.append("    duck: source=drumkick amount=4db attack=0.004s "
                   "release=0.13s threshold=-32db")
    else:
        warns.append("no kick in percussion -> bass bus left un-ducked")
    out += [
        "    gain: 0db",
        "    fx: saturate(amount=0.2, warmth=0.5)",
        "  }",
        "",
    ]

    for name, header in PITCHED.items():
        body = bodies.get(name)
        if not body:
            print(f"warning: pitched layer {name} not found in decompile",
                  file=sys.stderr)
            continue
        out.append(f"  # --- {name} ---")
        out.append(f"  layer {name} : notes {{")
        out += header
        out += body
        out.append("  }")
        out.append("")

    out += [
        "  master {",
        "    width:   1.0",
        "    lufs:    -11",
        "    peak:    -1.0",
        "    fadeout: 1.5s",
        "    fx: highpass(28hz),",
        "        comp(threshold=-16, ratio=2.2, attack=0.01, release=0.18, knee=6),",
        "        reverb(decay=1.1, mix=0.05), highshelf(9000hz, gain=1)",
        "  }",
        "}",
        "",
    ]

    text = "\n".join(out)
    OUT.write_text(text)
    print(f"wrote {OUT} ({len(text)} bytes)")
    for w in warns:
        print(f"  note: {w}")

    res = AudioForge().compile(text)
    errs = [d for d in res.diagnostics if d.severity == "error"]
    warns2 = [d for d in res.diagnostics if d.severity == "warning"]
    print(f"compile ok: {res.ok} | errors: {len(errs)} | warnings: {len(warns2)}")
    for d in (errs + warns2)[:12]:
        print(f"  {d.severity}: {d.message} {getattr(d, 'path', '') or ''}")
    return 0 if res.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
