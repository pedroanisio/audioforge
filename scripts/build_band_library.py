#!/usr/bin/env python3
"""Merge the song's sampled instruments into one AudioForge library.

AudioForge pins exactly one `library:` per asset and applies it to every
`instrument` layer, so a multi-sampled arrangement needs all its instruments
in a single content-addressed library. This script assembles:

  * eguitar_dist     — freepats-eguitar    (CC0 distorted electric guitar)
  * finger_bass      — freepats-fingerbass  (CC0 finger electric bass)
  * muldjord_kit     — freepats-muldjordkit (CC BY 4.0 acoustic kit, GM-keyed)

Their sample files don't collide (guitar: samples/<note>.wav, bass:
samples/finger/, drums: samples/<piece>/), so the merge is a plain copy with
no SFZ path rewriting. The result is `libraries/freepats-band` with one pin
covering all three instruments.

Prereqs (run first): scripts/import_sfz_library.py -> freepats-eguitar,
scripts/build_muldjord_gm.py -> freepats-muldjordkit, and the imported
freepats-fingerbass.
    python scripts/build_band_library.py
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

LIBS = Path("libraries")
DST = LIBS / "freepats-band"

# (source library, [paths to copy relative to that library]).
SOURCES = [
    (LIBS / "freepats-eguitar", ["eguitar_dist.sfz", "samples"]),
    (LIBS / "freepats-fingerbass", ["finger_bass.sfz", "samples"]),
    (LIBS / "freepats-muldjordkit",
     ["muldjord_kit.sfz", "samples", "ATTRIBUTION.txt"]),
]


def main() -> int:
    for src, _ in SOURCES:
        if not src.exists():
            print(f"error: missing source library {src}", file=sys.stderr)
            return 2

    if DST.exists():
        shutil.rmtree(DST)
    DST.mkdir(parents=True)

    for src, items in SOURCES:
        for item in items:
            s = src / item
            if not s.exists():
                continue
            d = DST / item
            if s.is_dir():
                # merge into an existing dir (samples/ is shared by 2 sources)
                d.mkdir(parents=True, exist_ok=True)
                for child in s.iterdir():
                    target = d / child.name
                    if child.is_dir():
                        shutil.copytree(child, target, dirs_exist_ok=True)
                    else:
                        shutil.copy(child, target)
            else:
                shutil.copy(s, d)

    sys.path.insert(0, str(Path.cwd()))
    from audioforge.library import generate_manifest
    m = generate_manifest(str(DST), name="freepats-band", version="1.0.0",
                          license_str="CC0-1.0 + CC-BY-4.0 (see ATTRIBUTION.txt)")
    print("instruments:", sorted(m["instruments"]))
    print(f"pin: freepats-band@{m['manifest_sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
