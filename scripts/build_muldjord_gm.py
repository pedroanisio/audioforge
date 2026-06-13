#!/usr/bin/env python3
"""Build a GM-keyed, AudioForge-subset SFZ kit from the MuldjordKit FreePats
samples (CC BY 4.0).

The upstream MuldjordKit SFZ is not usable as-is by AudioForge's sampler:
it keys the kit on a bespoke layout (kick at 48, snare at 51, ...) and uses
`lorand`/`hirand` random round-robins, which the sampler does not honour
(it supports seeded `seq_length`/`seq_position`). This script:

  * parses the upstream <global>/<group>/<region> SFZ,
  * keeps one source instrument per General-MIDI drum we need and remaps its
    key to the GM number (36 kick, 38 snare, 41 tom, 42 hat, 46 open-hat,
    49 crash, 51 ride),
  * converts each group's `lorand/hirand` round-robin set into
    `seq_length`/`seq_position` (seeded, deterministic),
  * copies only the referenced WAVs,
  * writes a flat, include-free SFZ and a pinned library manifest.

Run after extracting the upstream release to /tmp/mkit:
    python scripts/build_muldjord_gm.py
"""
from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

SRC_DIR = Path("/tmp/mkit/MuldjordKit SFZ+WAV-20201018")
OUT_DIR = Path("libraries/freepats-muldjordkit")
INSTRUMENT = "muldjord_kit"

# One upstream key per GM drum (avoids stacking L/R mic variants). Values are
# the GM note our translator already emits for that drum.
MULDJORD_TO_GM = {
    48: 36,   # KdrumL          -> kick
    51: 38,   # Snare           -> snare
    53: 42,   # HihatClosed     -> closed hat
    54: 46,   # HihatOpen       -> open hat
    59: 49,   # CrashL          -> crash
    55: 51,   # RideL           -> ride
    62: 41,   # Tom1            -> low tom
    63: 43,   # Tom2
    64: 45,   # Tom3
    65: 47,   # Tom4
}


def parse_groups(sfz_text: str):
    """Yield (key, lovel, hivel, [sample, ...]) per <group>, honouring
    <global>/<group> inheritance. Region order is preserved for RR."""
    glob: dict[str, str] = {}
    group: dict[str, str] = {}
    samples: list[str] = []
    section = None

    def kv(line: str, into: dict):
        for tok in line.split():
            if "=" in tok:
                k, v = tok.split("=", 1)
                into[k] = v

    groups = []

    def flush():
        if group and samples:
            groups.append((int(group["key"]),
                           int(group.get("lovel", 0)),
                           int(group.get("hivel", 127)),
                           list(samples)))

    for raw in sfz_text.splitlines():
        line = raw.split("//", 1)[0].strip()
        if not line:
            continue
        if line.startswith("<global>"):
            flush(); group.clear(); samples.clear(); section = "global"
            line = line[len("<global>"):].strip()
        elif line.startswith("<group>"):
            flush(); group.clear(); samples.clear()
            group.update(glob); section = "group"
            line = line[len("<group>"):].strip()
        elif line.startswith("<region>"):
            section = "region"; samples.append("")
            line = line[len("<region>"):].strip()
        if not line:
            continue
        if section == "global":
            kv(line, glob)
        elif section == "group":
            kv(line, group)
        elif section == "region":
            d: dict[str, str] = {}
            kv(line, d)
            if "sample" in d:
                samples[-1] = d["sample"]
    flush()
    return groups


def main() -> int:
    sfz_path = next(SRC_DIR.glob("*.sfz"), None)
    if sfz_path is None:
        print(f"error: SFZ not found under {SRC_DIR}", file=sys.stderr)
        return 2
    groups = parse_groups(sfz_path.read_text(encoding="utf-8", errors="ignore"))

    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    (OUT_DIR / "samples").mkdir(parents=True)

    out_lines = [
        "// MuldjordKit FreePats (CC BY 4.0) — GM-remapped for AudioForge.",
        "// Source: http://freepats.zenvoid.org/Percussion/acoustic-drum-kit.html",
        "<global>",
        " ampeg_release=0.6",
        " loop_mode=no_loop",
        "",
    ]
    copied: set[str] = set()
    n_regions = 0
    kept_keys: dict[int, int] = {}
    for key, lovel, hivel, samples in groups:
        if key not in MULDJORD_TO_GM:
            continue
        gm = MULDJORD_TO_GM[key]
        rr = [s for s in samples if s]
        if not rr:
            continue
        kept_keys[gm] = kept_keys.get(gm, 0) + 1
        for i, sample in enumerate(rr, start=1):
            src = SRC_DIR / sample
            if not src.exists():
                continue
            rel = sample  # preserve samples/<inst>/<file>.wav layout
            dst = OUT_DIR / rel
            if rel not in copied:
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(src, dst)
                copied.add(rel)
            out_lines.append("<region>")
            out_lines.append(f" key={gm} lovel={lovel} hivel={hivel}")
            out_lines.append(f" seq_length={len(rr)} seq_position={i}")
            out_lines.append(f" sample={rel}")
            n_regions += 1
    out_lines.append("")
    (OUT_DIR / f"{INSTRUMENT}.sfz").write_text("\n".join(out_lines),
                                               encoding="utf-8")

    sys.path.insert(0, str(Path.cwd()))
    from audioforge.library import generate_manifest
    m = generate_manifest(str(OUT_DIR), name="freepats-muldjordkit",
                          version="2020.10.18", license_str="CC-BY-4.0")
    # Carry the upstream attribution next to the manifest (CC BY requires it).
    for lic in SRC_DIR.glob("LICENSE*"):
        shutil.copy(lic, OUT_DIR / lic.name)
    (OUT_DIR / "ATTRIBUTION.txt").write_text(
        "MuldjordKit by FreePats — Creative Commons Attribution 4.0.\n"
        "http://freepats.zenvoid.org/Percussion/acoustic-drum-kit.html\n"
        "Remapped to General MIDI keys and seeded round-robins for AudioForge.\n",
        encoding="utf-8")

    print(f"instrument: {INSTRUMENT}")
    print(f"GM keys kept: {sorted(kept_keys)} ({n_regions} regions, "
          f"{len(copied)} samples)")
    print(f"pin: freepats-muldjordkit@{m['manifest_sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
