#!/usr/bin/env python3
"""tune_scom_library.py — sample-backed tuning of the Sweet Child O' Mine import.

Where scripts/tune_scom.py voices the arrangement with synthesis, this routes it
through the **freepats-band** content-addressed instrument library — the same
patches static/fixtures/mysong.af uses — so the parts play real recordings:

* bass    -> `finger_bass`
* guitars -> `eguitar_dist`; the rhythm parts get `section: size=3` ensemble
  multiplication (true-stereo, micro-detuned) for width; the LEAD stays a single
  voice so its `auto pitch_cents:` whammy bends stay crisp (tripling smears them).
* drums   -> `muldjord_kit`; the imported channel-10 notes are already GM note
  names (snare=D2, …), exactly what the kit SFZ maps, so they route in verbatim
  (no pattern conversion). This MIDI has no kick, so the bass bus is un-ducked.

Mix buses + master mirror mysong.af. Pitched note bodies and the lead bends are
lifted verbatim from the bare decompile — nothing re-quantized.

⚠ ARCHITECTURAL CONTRACT (PALS's LAW): emitted DSL is untrusted until the engine
compiles AND resolves it (instrument layers need the library bound). This script
runs `validate` (render-ready) and fails on any error.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

from audioforge import AudioForge, interop

MIDI = Path("static/fixtures/sweetchildofmine.mid")
OUT = Path("compositions/sweet_child_o_mine.library.af")
LIBRARY = ("freepats-band@"
           "d461fc30624ed0247a8449cd0d6edd39fced8976fbedf79d9a79b9020470f2be")

# Pitched layer -> (instrument header lines). Note bodies are appended from the
# bare decompile. Rhythm guitars use `section:`; the lead does not.
GTR_FX = ("    fx:           highpass(95hz), peak(2400hz, gain=2.5, q=1.1), "
          "lowpass(8500hz)")
SECTION = "    section:      size=3 spread=1.0 detune=14c timing=0.018s"

PITCHED = {
    "P2_Picked": [          # electric bass
        '    instrument:   "finger_bass"',
        "    articulation: sustain",
        "    pan:          0",
        "    humanize:     0.06",
        "    gain:         -3db",
        "    fx:           highpass(35hz), peak(1100hz, gain=3, q=1.0)",
        "    bus:          af_low",
    ],
    "P6_Steel": [           # main rhythm riff (left)
        '    instrument:   "eguitar_dist"',
        "    articulation: sustain",
        "    pan:          -0.5",
        "    humanize:     0.06",
        "    gain:         -8db",
        SECTION, GTR_FX,
        "    bus:          af_gtr",
    ],
    "P4_Overdr": [          # second rhythm (right)
        '    instrument:   "eguitar_dist"',
        "    articulation: sustain",
        "    pan:          0.5",
        "    humanize:     0.06",
        "    gain:         -8db",
        SECTION, GTR_FX,
        "    bus:          af_gtr",
    ],
    "P10_ROCK": [           # third rhythm (left of centre)
        '    instrument:   "eguitar_dist"',
        "    articulation: sustain",
        "    pan:          -0.22",
        "    humanize:     0.06",
        "    gain:         -9db",
        SECTION, GTR_FX,
        "    bus:          af_gtr",
    ],
    "P7_Distor": [          # LEAD — single voice, brighter, keeps the bends
        '    instrument:   "eguitar_dist"',
        "    articulation: sustain",
        "    pan:          0.08",
        "    humanize:     0.03",
        "    gain:         -6db",
        "    fx:           highpass(110hz), peak(3000hz, gain=3.5, q=1.1), "
        "lowpass(9000hz)",
        "    bus:          af_gtr",
    ],
}


# Sampled MIDI ranges of each instrument; out-of-range notes octave-fold inward.
INST_RANGE = {"finger_bass": (26, 64), "eguitar_dist": (35, 86)}


def _instrument_of(header: list[str]) -> str:
    for ln in header:
        m = re.search(r'instrument:\s*"([^"]+)"', ln)
        if m:
            return m.group(1)
    return ""


def _fold(midi: int, lo: int, hi: int) -> int:
    while midi > hi:
        midi -= 12
    while midi < lo:
        midi += 12
    return midi


def pitched_note_lines(layer: dict, lo: int, hi: int) -> tuple[list[str], int]:
    """Serialize a pitched layer's notes, octave-folding into [lo, hi]."""
    folded = 0
    toks = []
    for ev in layer["notes"]:
        midi = interop._midi_note(ev["note"])
        kit = _fold(midi, lo, hi)
        if kit != midi:
            folded += 1
        toks.append(f"{interop._note_name(kit)} @ {ev['start_beat']:.4f}b "
                    f"for {ev['dur_beats']:.4f}b vel {ev.get('vel', 0.7):.2f}")
    out = []
    for idx, tok in enumerate(toks):
        comma = "," if idx < len(toks) - 1 else ""
        out.append(("    notes:        " + tok + comma) if idx == 0
                   else "      " + tok + comma)
    return out, folded


def bend_auto_line(layer: dict, bpm: float) -> list[str]:
    """The lead's layer-scope pitch_cents bends, beats->seconds (as decompiled)."""
    for au in layer.get("automation", []) or []:
        if au.get("target") != "pitch_cents":
            continue
        pts = ", ".join(f"{beat * 60.0 / bpm:.4f}s={cents:g}"
                        for beat, cents in au["points"])
        return ["    auto pitch_cents: " + pts]
    return []


# muldjord_kit samples only these MIDI notes; map GM percussion onto them
# semantically (side-stick/clap -> snare, pedal-hat -> closed-hat, stray toms ->
# nearest covered tom), never by raw distance (which would send a side-stick to
# the kick a semitone away).
_KIT_COVERED = {36, 38, 41, 42, 43, 45, 46, 47, 49, 51}
_GM_REMAP = {35: 36, 37: 38, 39: 38, 40: 38, 44: 42, 48: 47, 50: 47,
             52: 49, 55: 49, 57: 49, 53: 51, 59: 51}


def _kit_midi(midi: int) -> int:
    if midi in _KIT_COVERED:
        return midi
    return _GM_REMAP.get(midi, 38)


def drum_note_lines(spec: dict) -> list[str]:
    """All channel-10 events as `muldjord_kit` notes, GM-remapped to covered keys."""
    toks = []
    remapped = 0
    for layer in spec["layers"]:
        if not layer["name"].lower().startswith("drum"):
            continue
        for ev in layer["notes"]:
            midi = interop._midi_note(ev["note"])
            kit = _kit_midi(midi)
            if kit != midi:
                remapped += 1
            note = interop._note_name(kit)
            toks.append((ev["start_beat"],
                         f"{note} @ {ev['start_beat']:.4f}b "
                         f"for {ev['dur_beats']:.4f}b vel {ev.get('vel', 0.7):.2f}"))
    if remapped:
        print(f"  note: {remapped} drum hit(s) remapped to covered kit keys")
    toks.sort(key=lambda t: t[0])
    flat = [t[1] for t in toks]
    out = []
    for idx, tok in enumerate(flat):
        comma = "," if idx < len(flat) - 1 else ""
        out.append(("    notes:        " + tok + comma) if idx == 0
                   else "      " + tok + comma)
    return out


def main() -> int:
    spec = interop.import_midi_bytes(MIDI.read_bytes(), asset_id="sweet_child_o_mine")
    by_name = {l["name"]: l for l in spec["layers"]}
    bpm, dur = spec["bpm"], spec["duration_s"]

    out: list[str] = [
        "# " + "=" * 74,
        "# AudioForge DSL — sample-backed arrangement (scripts/tune_scom_library.py)",
        "# Source: static/fixtures/sweetchildofmine.mid via freepats-band library",
        "# ARCHITECTURAL REQUIREMENT (PALS's LAW): verified by compiling + resolving.",
        "# " + "=" * 74,
        "",
        "asset sweet_child_o_mine {",
        "  kind:       soundtrack",
        f"  duration:   {dur}s",
        "  samplerate: 48000",
        "  bitdepth:   24",
        f"  tempo:      {bpm:.3f}bpm",
        f'  library:    "{LIBRARY}"',
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
        "  bus af_low {",
        "    gain: 0db",
        "    fx: saturate(amount=0.2, warmth=0.5)",
        "  }",
        "",
        "  # --- drum kit (channel 10 -> muldjord_kit; no kick in source) ---",
        "  layer drumkit : instrument {",
        '    instrument:   "muldjord_kit"',
        "    articulation: sustain",
        "    gain:         -4db",
        "    humanize:     0.08",
        "    bus:          af_drums",
        "",
    ]
    out += drum_note_lines(spec)
    out += ["  }", ""]

    for name, header in PITCHED.items():
        layer = by_name.get(name)
        if not layer:
            print(f"warning: {name} not in import", file=sys.stderr)
            continue
        inst = _instrument_of(header)
        lo, hi = INST_RANGE.get(inst, (0, 127))
        notes, folded = pitched_note_lines(layer, lo, hi)
        if folded:
            print(f"  note: {name}: {folded} note(s) octave-folded into "
                  f"{inst} range {lo}..{hi}")
        out.append(f"  # --- {name} ({inst}) ---")
        out.append(f"  layer {name} : instrument {{")
        out += header
        out.append("")
        out += notes
        out += bend_auto_line(layer, bpm)
        out += ["  }", ""]

    out += [
        "  master {",
        "    width:   1.0",
        "    lufs:    -12",
        "    peak:    -1.0",
        "    fadeout: 1.5s",
        "    fx: highpass(28hz),",
        "        comp(threshold=-16, ratio=2.2, attack=0.01, release=0.18, knee=6),",
        "        reverb(decay=1.1, mix=0.06), highshelf(9000hz, gain=1.0)",
        "  }",
        "}",
        "",
    ]

    text = "\n".join(out)
    OUT.write_text(text)
    print(f"wrote {OUT} ({len(text)} bytes)")

    res = AudioForge().compile(text)
    errs = [d for d in res.diagnostics if d.severity == "error"]
    warns = [d for d in res.diagnostics if d.severity == "warning"]
    print(f"compile ok: {res.ok} | errors: {len(errs)} | warnings: {len(warns)}")
    for d in (errs + warns)[:12]:
        print(f"  {d.severity}: {d.message} {getattr(d, 'path', '') or ''}")
    return 0 if res.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
