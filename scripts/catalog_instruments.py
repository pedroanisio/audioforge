#!/usr/bin/env python3
"""Emit a machine-readable catalog of every instrument across SFZ libraries.

Thin CLI over the catalog SDK (`audioforge.catalog.Catalog`): the discovery,
SFZ parsing and renderability logic live in the package so the API and this
script never diverge.

    python3 scripts/catalog_instruments.py [ROOT] [-o catalog.json]

ROOT may be the libraries root (auto-discovers sub-libraries) or one library
dir. Default ROOT = libraries, output = <ROOT>/catalog.json.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from audioforge.catalog import Catalog  # noqa: E402


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
    cat = Catalog.build(root)
    out = cat.save(Path(a.out) if a.out else root / "catalog.json")
    d = cat.to_dict()
    print(f"catalog -> {out}")
    print(f"{d['library_count']} libraries, {d['instrument_count']} "
          f"instruments, {d['renderable_count']} renderable by AudioForge\n")
    print(f"  {'library':24} {'instr':>5} {'rend':>5}  formats / blockers")
    for l in cat.libraries:
        note = "/".join(l.sample_formats) or "-"
        if l.parse_errors:
            note += f"  !{l.parse_errors} parse-err"
        print(f"  {l.name:24} {l.instrument_count:5} "
              f"{l.renderable_count:5}  {note}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
