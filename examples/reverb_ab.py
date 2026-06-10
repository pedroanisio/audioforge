"""Reverb A/B/C: renders one identical bell-and-pluck phrase through the
three spaces (hall / plate / fdn) so producers can audition the character
difference directly. Each output is a fully hash-tracked asset.

Run:  python examples/reverb_ab.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from audioforge import AudioForge

PHRASE = """
asset reverb_ab_{name} {{
  kind: cue
  duration: 8s
  tempo: 70bpm
  key: E minor

  layer bell : notes {{
    osc: modal
    material: bell
    modedecay: 2.5s
    gain: -9db
    env: a=0.001s d=2.5s s=0.2 r=0.8s
    notes: E5 @ 0b for 3b, B4 @ 3b for 3b vel 0.8
  }}
  layer strings : notes {{
    osc: pluck
    damping: 0.8
    brightness: 0.65
    gain: -10db
    pan: 0.2
    env: a=0.002s d=1.5s s=0.4 r=0.5s
    notes: E3 @ 1b for 2b, G3 @ 2b for 2b vel 0.8, B3 @ 4b for 3b
  }}
  master {{
    width: 0.85
    lufs: -16
    peak: -1db
    fadeout: 1.5s
    fx: {space}
  }}
}}
"""

SPACES = {
    "hall":  "hall(rt60=4, damp=0.45, mix=0.35)",
    "plate": "plate(decay=0.82, damp=0.3, predelay=0.02, mix=0.35)",
    "fdn":   "fdn(rt60=5, rt60_high=1.8, crossover=2200, mix=0.35)",
}


def main():
    forge = AudioForge()
    out = Path(__file__).parent / "out"
    for name, space in SPACES.items():
        res = forge.compile(PHRASE.format(name=name, space=space))
        assert res.ok, [d.message for d in res.diagnostics]
        meta = res.assets[0].export(out)
        print(f"{name:6s} -> {meta['file']}  "
              f"lufs={meta['loudness']['final_lufs']}  "
              f"sha={meta['output_sha256'][:12]}")


if __name__ == "__main__":
    main()
