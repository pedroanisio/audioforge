#!/usr/bin/env python3
"""Import an external SFZ instrument into an AudioForge-compatible library.

AudioForge's sampler reads a documented SFZ subset and consumes WAV PCM.
Many freely-licensed libraries (FreePats, etc.) ship as **SFZ + FLAC**, so
this capability:

  1. decodes every referenced FLAC sample to WAV PCM (24-bit) via libsndfile,
  2. rewrites the SFZ `sample=` paths (.flac -> .wav),
  3. flattens <global>/<group>/<region> inheritance into a single
     include-free SFZ, preserving each region's key map, velocity layers,
     and round-robin opcodes (`seq_length`/`seq_position` and
     `lorand`/`hirand` — both are honoured natively by the sampler),
  4. emits a pinned `library.manifest.json`.

It preserves the instrument's own key map (no GM remapping — that belongs to
a drum-specific step). WAV inputs pass through unchanged. Unknown opcodes are
carried verbatim; the sampler reports the ones it does not honour.

Usage:
    python scripts/import_sfz_library.py SRC_DIR OUT_LIB_DIR \\
        --name LIB_NAME [--instrument NAME] [--license "CC0-1.0"]

SRC_DIR is an extracted release directory containing exactly one .sfz.
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

def parse_regions(sfz_text: str):
    """Return (global_opcodes, [region_opcode_dict, ...]) with
    <global>/<group>/<region> inheritance resolved. Region order preserved."""
    glob: dict[str, str] = {}
    group: dict[str, str] = {}
    region: dict[str, str] | None = None
    regions: list[dict[str, str]] = []
    section = None

    def kv(line: str, into: dict):
        # opcodes are whitespace-separated key=value; sample= may hold a path
        # with no spaces (true for FreePats). Split on whitespace.
        for tok in line.split():
            if "=" in tok:
                k, v = tok.split("=", 1)
                into[k] = v

    for raw in sfz_text.splitlines():
        line = raw.split("//", 1)[0].strip()
        if not line:
            continue
        for header in ("<global>", "<group>", "<region>", "<control>"):
            if line.startswith(header):
                if header == "<global>":
                    section = "global"
                elif header == "<control>":
                    section = "control"
                elif header == "<group>":
                    group = {}
                    section = "group"
                elif header == "<region>":
                    region = {}
                    regions.append(region)
                    section = "region"
                line = line[len(header):].strip()
                break
        if not line:
            continue
        if section == "global":
            kv(line, glob)
        elif section == "group":
            kv(line, group)
        elif section == "region" and region is not None:
            d: dict[str, str] = {}
            kv(line, d)
            # effective = group defaults then region overrides
            for k, v in {**group, **d}.items():
                region[k] = v
    return glob, regions


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("src", type=Path, help="extracted release dir (has one .sfz)")
    ap.add_argument("out", type=Path, help="output library dir")
    ap.add_argument("--name", required=True, help="library name (manifest)")
    ap.add_argument("--instrument", default=None,
                    help="instrument name (default: SFZ stem, sanitized)")
    ap.add_argument("--license", default="UNKNOWN")
    args = ap.parse_args()

    sfz_path = next(args.src.rglob("*.sfz"), None)
    if sfz_path is None:
        print(f"error: no .sfz under {args.src}", file=sys.stderr)
        return 2
    sfz_root = sfz_path.parent
    glob, regions = parse_regions(sfz_path.read_text(encoding="utf-8",
                                                      errors="ignore"))

    instrument = args.instrument or "".join(
        c if c.isalnum() else "_" for c in sfz_path.stem).strip("_").lower()

    if args.out.exists():
        shutil.rmtree(args.out)
    args.out.mkdir(parents=True)

    import soundfile as sf

    converted: dict[str, str] = {}   # src rel .flac -> out rel .wav

    def materialize(sample_rel: str) -> str | None:
        if sample_rel in converted:
            return converted[sample_rel]
        src = sfz_root / sample_rel
        if not src.exists():
            return None
        out_rel = sample_rel
        dst = args.out / out_rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.suffix.lower() == ".flac":
            out_rel = sample_rel[:-5] + ".wav"
            dst = args.out / out_rel
            data, sr = sf.read(str(src), always_2d=False)
            sf.write(str(dst), data, sr, subtype="PCM_24")
        else:
            shutil.copy(src, dst)
        converted[sample_rel] = out_rel
        return out_rel

    lines = [f"// {args.name} — imported for AudioForge "
             "(FLAC->WAV, random-RR -> seeded seq).",
             f"// Source SFZ: {sfz_path.name}",
             "<global>"]
    for k, v in glob.items():
        lines.append(f" {k}={v}")
    lines.append("")

    n_regions = 0
    for r in regions:
        if "sample" not in r:
            continue
        out_rel = materialize(r["sample"])
        if out_rel is None:
            continue
        opcodes = {k: v for k, v in r.items() if k != "sample"}
        lines.append("<region>")
        lines.append(" " + " ".join(f"{k}={v}" for k, v in opcodes.items()))
        lines.append(f" sample={out_rel}")
        n_regions += 1
    lines.append("")
    (args.out / f"{instrument}.sfz").write_text("\n".join(lines),
                                                encoding="utf-8")

    # Carry any license/readme for provenance.
    for pat in ("LICENSE*", "README*", "*.txt"):
        for f in args.src.rglob(pat):
            if f.is_file():
                shutil.copy(f, args.out / f.name)
                break

    sys.path.insert(0, str(Path.cwd()))
    from audioforge.library import generate_manifest
    m = generate_manifest(str(args.out), name=args.name, version="1.0.0",
                          license_str=args.license)
    print(f"instrument: {instrument}")
    print(f"regions: {n_regions} | samples converted/copied: {len(converted)}")
    print(f"pin: {args.name}@{m['manifest_sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
