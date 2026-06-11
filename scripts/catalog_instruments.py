#!/usr/bin/env python3
"""Automate a machine-readable catalog of every instrument across SFZ libraries.

Discovers each library under a root (default `libraries/`), finds every `*.sfz`
patch *recursively*, and parses it with AudioForge's own SFZ interpreter — so
the catalog reflects exactly what the render engine sees. Sample paths are
resolved the way the engine resolves them (relative to each SFZ's own folder,
after `default_path`), so the integrity check is real.

For each instrument it records a `renderable` verdict plus `render_blockers`,
the genuinely useful signal: AudioForge can only render a patch whose SFZ it
can parse (no `#include` / `$define` Aria extensions) and whose samples are
WAV (the engine decodes WAV only, not FLAC) and present on disk.

Handles flat libraries (VSCO-2-CE: SFZ at root, family in `default_path`) and
deeply-nested ones (VCSL: SFZ inside `Chordophones/Zithers/…`).

    python3 scripts/catalog_instruments.py [ROOT] [-o catalog.json]

ROOT may be the libraries root (auto-discovers sub-libraries) or one library
dir. Default ROOT = libraries, output = <ROOT>/catalog.json.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from audioforge.sampler import parse_sfz  # noqa: E402

_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
_MISSING_CAP = 12
_AUDIO_EXTS = (".wav", ".flac", ".ogg", ".aif", ".aiff")
_PLAYABLE_EXT = "wav"          # the only format AudioForge's sampler decodes

_ARTIC_TOKENS = [
    "susvib", "susnv", "sustain", "sus", "staccato", "stac", "spiccato",
    "spic", "pizzicato", "pizz", "tremolo", "trem", "vibrato", "vib",
    "legato", "rolls", "roll", "mute", "muted", "harmon", "straight",
    "keyswitch", "-ks", "ks", "normal", "quiet", "loud", "pedal",
    "non-vibrato", "expvib",
]


def note_name(midi: int) -> str:
    return f"{_NAMES[midi % 12]}{midi // 12 - 1}"


def has_sfz(d: Path) -> bool:
    return any(d.rglob("*.sfz"))


def _ext(path: str) -> str:
    return path.rsplit(".", 1)[-1].lower() if "." in path else ""


def articulation_of(stem: str, category: str, sample_rel: str) -> str:
    if " - " in stem:                                  # VCSL: "Name - Artic"
        return stem.split(" - ", 1)[1].strip().lower()
    folders = [p.lower() for p in
               (sample_rel.replace("\\", "/").split("/")[:-1]
                + category.split("/"))]
    for p in reversed(folders):
        if any(tok in p for tok in _ARTIC_TOKENS):
            return p
    low = stem.lower()
    for tok in _ARTIC_TOKENS:
        if tok in low:
            return tok.lstrip("-")
    return "default"


def catalog_instrument(sfz_path: Path, libdir: Path) -> dict:
    text = sfz_path.read_text(encoding="utf-8", errors="replace")
    rel_sfz = sfz_path.relative_to(libdir).as_posix()
    rel_parent = sfz_path.parent.relative_to(libdir).as_posix()
    uses_include = "#include" in text or "$" in text
    base = {"library": libdir.name, "id": sfz_path.stem, "sfz": rel_sfz,
            "category": rel_parent if rel_parent != "." else None}

    try:
        regions, ignored = parse_sfz(text)
    except Exception as e:                      # $vars / #include / #define …
        return {**base, "renderable": False,
                "render_blockers": ["parse_error"],
                "parse_error": f"{type(e).__name__}: "
                               f"{str(e).splitlines()[0][:80]}",
                "regions": 0,
                "samples": {"unique": 0, "present": 0, "missing": 0,
                            "formats": []},
                "_resolved": []}

    sdir = sfz_path.parent
    samples = sorted({r.sample for r in regions if r.sample})
    resolved = {s: (sdir / s) for s in samples}
    present = {s: p for s, p in resolved.items() if p.is_file()}
    missing = sorted(set(samples) - set(present))
    formats = sorted({_ext(s) for s in samples if _ext(s)})
    total_bytes = sum(p.stat().st_size for p in present.values())

    keycenters = sorted({r.pitch_keycenter for r in regions})
    vel_bands = sorted({(r.lovel, r.hivel) for r in regions})
    lokeys = [r.lokey for r in regions] or [0]
    hikeys = [r.hikey for r in regions] or [127]
    lo, hi = min(lokeys), max(hikeys)

    if rel_parent == ".":
        comps = (samples[0].split("/") if samples else [])
        category = comps[0] if len(comps) > 1 else "Unknown"
    else:
        category = rel_parent

    blockers = []
    if uses_include:
        blockers.append("uses_include")          # paths below are approximate
    if not regions:
        blockers.append("no_regions")
    bad_fmt = [f for f in formats if f != _PLAYABLE_EXT]
    if bad_fmt:
        blockers.append("non_wav_samples")
    if missing and not uses_include:
        blockers.append("missing_samples")
    renderable = not blockers

    return {
        **base, "category": category,
        "renderable": renderable,
        "render_blockers": blockers,
        "articulation": articulation_of(sfz_path.stem, category,
                                        samples[0] if samples else ""),
        "uses_include": uses_include,
        "regions": len(regions),
        "key_range": {"low_midi": lo, "high_midi": hi,
                      "low_note": note_name(lo), "high_note": note_name(hi)},
        "pitch_keycenters": keycenters,
        "velocity_layers": [[a, b] for a, b in vel_bands],
        "round_robin_max": max((r.seq_length for r in regions), default=1),
        "samples": {"unique": len(samples), "present": len(present),
                    "missing": len(missing), "formats": formats,
                    "total_bytes": total_bytes},
        "missing_samples": ([] if uses_include else missing[:_MISSING_CAP]),
        "ignored_opcodes": sorted(ignored),
        "_resolved": [str(p) for p in present.values()],
    }


def catalog_library(libdir: Path) -> dict:
    insts = [catalog_instrument(p, libdir) for p in sorted(libdir.rglob("*.sfz"))]
    referenced = set()
    for i in insts:
        referenced.update(i.pop("_resolved"))
    on_disk = {str(p) for p in libdir.rglob("*")
               if p.suffix.lower() in _AUDIO_EXTS}
    cats: dict[str, list[str]] = {}
    for i in insts:
        cats.setdefault(i.get("category") or "Unknown", []).append(i["id"])
    fmts: set[str] = set()
    for i in insts:
        fmts.update(i["samples"]["formats"])
    return {
        "name": libdir.name,
        "instrument_count": len(insts),
        "renderable_count": sum(1 for i in insts if i["renderable"]),
        "parse_errors": sum(1 for i in insts if "parse_error" in i),
        "sample_formats": sorted(fmts),
        "audio_files_on_disk": len(on_disk),
        "audio_files_referenced": len(referenced & on_disk),
        "audio_files_orphan": len(on_disk - referenced),
        "categories": {k: sorted(v) for k, v in sorted(cats.items())},
        "_instruments": insts,
    }


def build_catalog(root: Path) -> dict:
    libs = sorted(c for c in root.iterdir() if c.is_dir() and has_sfz(c))
    if not libs and has_sfz(root):
        libs = [root]
    reports = [catalog_library(d) for d in libs]
    instruments = []
    for r in reports:
        instruments.extend(r.pop("_instruments"))
    return {
        "schema": "audioforge.instrument-catalog/2",
        "root": str(root),
        "generated_by": "scripts/catalog_instruments.py",
        "engine_sfz_subset": "audioforge.sampler.parse_sfz",
        "renderable_note": "renderable = SFZ parses (no #include/$define) AND "
                           "all samples are WAV and present on disk",
        "library_count": len(reports),
        "instrument_count": len(instruments),
        "renderable_count": sum(r["renderable_count"] for r in reports),
        "parse_errors_total": sum(r["parse_errors"] for r in reports),
        "libraries": reports,
        "instruments": instruments,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("root", nargs="?", default="libraries")
    ap.add_argument("-o", "--out", default=None,
                    help="output JSON (default: <root>/catalog.json)")
    a = ap.parse_args(argv)
    root = Path(a.root)
    if not root.is_dir():
        print(f"not a directory: {root}", file=sys.stderr)
        return 2
    cat = build_catalog(root)
    out = Path(a.out) if a.out else root / "catalog.json"
    out.write_text(json.dumps(cat, indent=2) + "\n")
    print(f"catalog -> {out}")
    print(f"{cat['library_count']} libraries, {cat['instrument_count']} "
          f"instruments, {cat['renderable_count']} renderable by AudioForge\n")
    print(f"  {'library':24} {'instr':>5} {'rend':>5}  formats / blockers")
    for l in cat["libraries"]:
        note = "/".join(l["sample_formats"]) or "-"
        if l["parse_errors"]:
            note += f"  !{l['parse_errors']} parse-err"
        print(f"  {l['name']:24} {l['instrument_count']:5} "
              f"{l['renderable_count']:5}  {note}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
