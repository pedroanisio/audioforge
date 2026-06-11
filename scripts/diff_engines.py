#!/usr/bin/env python3
"""Assert the capability diff between our engine and the `_tmp/audioforge`
stand-alone subset renderer, and flag what (if anything) is worth merging.

`_tmp/audioforge/audioforge_render.py` is a purpose-built, regex-based subset
interpreter of the same `.af` DSL — not a copy of this package, so a line diff
is meaningless. What matters is the *capability surface*: an item that exists
there but not here is a candidate to merge UP into the real engine.

Exit status: 0 if our engine covers every engine-level capability the subset
has (we are a superset); 1 if the subset exposes something we lack.

Usage:  python3 scripts/diff_engines.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TMP = os.path.join(ROOT, "_tmp", "audioforge")
sys.path.insert(0, ROOT)
sys.path.insert(0, TMP)

from audioforge import theory                       # noqa: E402
from audioforge.capabilities import capability_manifest  # noqa: E402

# --- our engine (authoritative: the capability manifest + theory) -----------
cm = capability_manifest()
OURS = {
    "chord_qualities": set(theory.CHORD_QUALITIES),
    "oscillators": set(cm["oscillators"]),
    "fx": set(cm["fx"]),
    "layer_types": set(cm["layer_types"]),
    "drum_voices": set(cm["layer_types"]["drums"]["properties"]["voice"]["enum"]),
}

# --- the subset engine ------------------------------------------------------
# chord qualities are a live dict; the rest live inside regex dispatch in
# audioforge_render.py, so they are curated here from its source (see the
# render_*_layer dispatch and the bus/master fx chains).
import audioforge_render as sub                      # noqa: E402
TMP_CAPS = {
    "chord_qualities": set(sub.CHORD_QUALITIES),
    "oscillators": {"pad", "pluck", "square", "triangle"},      # voices it renders
    "fx": {"lowpass", "highshelf", "saturate", "delay", "mbcomp", "drive"},
    "layer_types": {"notes", "instrument", "drums"},
    "drum_voices": {"kick", "hat", "clap", "snare"},
}
# stand-alone tools the subset ships that have no engine-capability equivalent
TMP_TOOLS = {
    "cellular_compose.py": "cellular-automata composition (rule90 -> .af)",
    "charts/*.png": "analysis visualizations (voice-leading, spectra, score fractal)",
    "midi_export.py": "MIDI export (we already have `export-midi`)",
}


def main():
    print("=" * 66)
    print(" capability diff:  ours  vs  _tmp/audioforge (subset renderer)")
    print("=" * 66)
    gaps = {}
    for cat in OURS:
        only_tmp = sorted(TMP_CAPS[cat] - OURS[cat])
        only_ours = sorted(OURS[cat] - TMP_CAPS[cat])
        both = len(OURS[cat] & TMP_CAPS[cat])
        print(f"\n[{cat}]  both={both}  ours-only={len(only_ours)}  "
              f"subset-only={len(only_tmp)}")
        if only_tmp:
            print(f"  ⚠ MERGE CANDIDATE (subset has, we lack): {only_tmp}")
            gaps[cat] = only_tmp
        if only_ours:
            print(f"  · we additionally have: {only_ours}")

    print("\n[stand-alone tools in the subset]")
    for f, what in TMP_TOOLS.items():
        print(f"  · {f:22} {what}")

    print("\n" + "-" * 66)
    if gaps:
        print("RESULT: subset exposes engine capabilities we lack — review to merge:")
        for cat, items in gaps.items():
            print(f"  {cat}: {items}")
        return 1
    print("RESULT: our engine is a superset of the subset's engine capabilities.")
    print("  (stand-alone tools above are optional additions, not engine gaps.)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
