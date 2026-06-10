"""CLI.

  python -m audioforge.cli render   spec.json [-o outdir]
  python -m audioforge.cli batch    specs_dir [-o outdir]
  python -m audioforge.cli validate spec.json
  python -m audioforge.cli verify   spec.json manifest.json
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

from .dsl import DSLError
from .render import render_to_wav, verify
from .schema import SpecError, validate_spec
from .sdk import AudioForge


def _assets(path: str, variant=None):
    forge = AudioForge()
    if variant is not None and str(path).endswith(".af"):
        res = forge.compile(Path(path).read_text(), variant=variant)
    else:
        res = forge.load_file(path)
    for d in res.diagnostics:
        print(f"{d.severity.upper()}: {d.message}", file=sys.stderr)
    if not res.ok:
        raise SpecError("compilation failed")
    return res.assets


def _load(path: str) -> dict:
    return json.loads(Path(path).read_text())


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="audioforge")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("render"); p.add_argument("spec")
    p.add_argument("-o", "--out", default="out")
    p.add_argument("--stems", action="store_true")
    p.add_argument("--preset", default=None)
    p.add_argument("--variant", default=None)
    p.add_argument("--intensity", type=float, default=None)

    p = sub.add_parser("pack"); p.add_argument("spec")
    p.add_argument("-o", "--out", default="pack_out")
    p.add_argument("--variants", type=int, default=8)
    p.add_argument("--preset", default=None)

    p = sub.add_parser("libgen"); p.add_argument("directory")
    p.add_argument("--name", default=None)
    p.add_argument("--version", default="0.0.0")
    p.add_argument("--license", dest="license_str", default="UNKNOWN")

    p = sub.add_parser("ingest"); p.add_argument("directory")
    p.add_argument("-o", "--out", default=None)

    p = sub.add_parser("campaign"); p.add_argument("spec")
    p.add_argument("-o", "--out", default="campaign_out")
    p.add_argument("--preset", default=None)
    p.add_argument("--intensity", type=float, default=None)

    p = sub.add_parser("compile"); p.add_argument("spec")

    p = sub.add_parser("batch"); p.add_argument("specs_dir")
    p.add_argument("-o", "--out", default="out")

    p = sub.add_parser("validate"); p.add_argument("spec")
    p.add_argument("--no-resolve", action="store_true",
                   help="structural check only (skip resource binding)")

    p = sub.add_parser("verify"); p.add_argument("spec")
    p.add_argument("manifest")

    args = ap.parse_args(argv)

    try:
        if args.cmd == "validate":
            failed = False
            for a in _assets(args.spec):
                for d in a.validate(resolve=not args.no_resolve):
                    print(f"{d.severity.upper()}: {d.message}")
                    failed = failed or d.severity == "error"
            if failed:
                print("FAILED: not render-ready")
                sys.exit(1)
            print("OK: valid" + (" (structural only)" if args.no_resolve
                                 else " — render-ready"))
        elif args.cmd == "compile":
            for a in _assets(args.spec):
                print(a.to_json())
        elif args.cmd == "render":
            for a in _assets(args.spec, variant=args.variant):
                if args.intensity is not None:
                    a = a.with_intensity(args.intensity)
                meta = a.export(args.out, preset=args.preset, stems=args.stems)
                print(json.dumps(meta, indent=2))
        elif args.cmd == "pack":
            from .sdk import AudioForge
            pack = AudioForge().export_pack(
                Path(args.spec).read_text(), args.out, n=args.variants,
                preset=args.preset)
            for v in pack["variants"]:
                print(f"{v['file']:48s} {v['output_sha256'][:16]}")
            print(f"pack.manifest.json: {len(pack['variants'])} renders")
        elif args.cmd == "libgen":
            from .library import generate_manifest
            m = generate_manifest(args.directory, name=args.name,
                                  version=args.version,
                                  license_str=args.license_str)
            print(f"library '{m['name']}' v{m['version']} "
                  f"({m['license']}): {len(m['files'])} files, "
                  f"{len(m['instruments'])} instruments")
            print(f"pin: {m['name']}@{m['manifest_sha256']}")
        elif args.cmd == "ingest":
            from .samples import ingest
            cat = ingest(args.directory)
            for c in cat:
                if "error" in c:
                    print(f"SKIP {c['file']}: {c['error']}")
                    continue
                print(f"# {c['file']}  {c['duration_s']}s  "
                      f"{c['guess']}  {c['sha256'][:12]}")
                print(c["snippet"].replace("\\n", "\n"))
                print()
            if args.out:
                Path(args.out).write_text(json.dumps(cat, indent=1))
                print(f"catalog -> {args.out}")
        elif args.cmd == "campaign":
            for a in _assets(args.spec):
                if args.intensity is not None:
                    a = a.with_intensity(args.intensity)
                full = a.export(args.out, preset=args.preset)
                print(f"{full['file']:44s} full")
                for m in a.export_cutdowns(args.out, preset=args.preset):
                    print(f"{m['file']:44s} {m['cutdown']['length_s']}s cut")
        elif args.cmd == "batch":
            for f in sorted(list(Path(args.specs_dir).glob("*.json"))
                            + list(Path(args.specs_dir).glob("*.af"))):
                for a in _assets(str(f)):
                    meta = a.export(args.out)
                    print(f"{meta['file']:44s} {meta['output_sha256'][:16]}")
        elif args.cmd == "verify":
            expected = _load(args.manifest)["output_sha256"]
            with tempfile.TemporaryDirectory() as td:
                ok = verify(_load(args.spec), expected, td)
            print("REPRODUCIBLE" if ok else "MISMATCH — output drifted")
            return 0 if ok else 2
    except (SpecError, DSLError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
