"""CLI.

  python -m audioforge.cli render   spec.json [-o outdir]
  python -m audioforge.cli batch    specs_dir [-o outdir]
  python -m audioforge.cli validate spec.json
  python -m audioforge.cli verify   spec.json manifest.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

from .dsl import DSLError
from .render import render_to_wav, verify
from .schema import SpecError, validate_spec
from .sdk import AudioForge
from .version import version_banner


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
    argv = sys.argv[1:] if argv is None else list(argv)
    if argv in (["--version"], ["-V"]):
        print(version_banner())
        return 0

    ap = argparse.ArgumentParser(prog="audioforge")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("render"); p.add_argument("spec")
    p.add_argument("-o", "--out", default="out")
    p.add_argument("--stems", action="store_true")
    p.add_argument("--preset", default=None)
    p.add_argument("--variant", default=None)
    p.add_argument("--intensity", type=float, default=None)
    p.add_argument("--jobs", type=int, default=None,
                   help="render layers across N threads (deterministic; "
                        "default 1 / $AUDIOFORGE_JOBS)")
    p.add_argument("--analyze", action="store_true")

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

    p = sub.add_parser("decompile"); p.add_argument("spec")

    p = sub.add_parser("repair"); p.add_argument("spec")
    p.add_argument("--analysis", default=None)
    p.add_argument("--feedback", default="")

    sub.add_parser("capabilities")

    p = sub.add_parser("grammar")
    p.add_argument("--format", choices=("ebnf", "gbnf"), default="ebnf")

    p = sub.add_parser("export-midi"); p.add_argument("spec")
    p.add_argument("-o", "--out", required=True)

    p = sub.add_parser("export-musicxml"); p.add_argument("spec")
    p.add_argument("-o", "--out", required=True)
    p.add_argument("--notated", action="store_true",
                   help="formal quantized score (figures+rests) for MuseScore")
    p.add_argument("--bars", type=int, default=4, help="beats per measure")

    p = sub.add_parser("score"); p.add_argument("spec")
    p.add_argument("-o", "--out", default=None)
    p.add_argument("--title", default=None)
    p.add_argument("--bars", type=int, default=10)

    p = sub.add_parser("import-midi"); p.add_argument("midi")
    p.add_argument("--id", default="imported_midi")

    p = sub.add_parser("import-musicxml"); p.add_argument("musicxml")
    p.add_argument("--id", default="imported_musicxml")

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
        elif args.cmd == "decompile":
            for a in _assets(args.spec):
                print(a.to_dsl())
        elif args.cmd == "repair":
            from .repair import plan_repair
            analysis = json.loads(Path(args.analysis).read_text()) if args.analysis else {}
            print(json.dumps(plan_repair({
                "dsl": Path(args.spec).read_text(),
                "analysis": analysis,
                "feedback": args.feedback,
            }), indent=2, sort_keys=True))
        elif args.cmd == "capabilities":
            from .capabilities import capability_manifest
            print(json.dumps(capability_manifest(), indent=2,
                             sort_keys=True))
        elif args.cmd == "grammar":
            from .grammar import dsl_ebnf, dsl_gbnf
            print(dsl_ebnf() if args.format == "ebnf" else dsl_gbnf())
        elif args.cmd == "export-midi":
            from .interop import export_midi_bytes
            assets = list(_assets(args.spec))
            if len(assets) != 1:
                raise SpecError("export-midi expects exactly one asset")
            Path(args.out).write_bytes(export_midi_bytes(assets[0].spec))
            print(f"MIDI -> {args.out}")
        elif args.cmd == "export-musicxml":
            from .interop import export_musicxml, export_notated_musicxml
            exporter = ((lambda s: export_notated_musicxml(s, beats_per_bar=args.bars))
                        if args.notated else export_musicxml)
            assets = list(_assets(args.spec))
            out = Path(args.out)
            if len(assets) == 1:
                out.write_text(exporter(assets[0].spec))
                print(f"MusicXML -> {out}")
            else:
                for a in assets:
                    fp = out.with_name(f"{out.stem}.{a.spec.get('id', 'asset')}"
                                       f"{out.suffix}")
                    fp.write_text(exporter(a.spec))
                    print(f"MusicXML -> {fp}")
        elif args.cmd == "score":
            from .score import score_pdf
            assets = list(_assets(args.spec))
            specs = [a.spec for a in assets]
            out = args.out or (Path(args.spec).stem + ".pdf")
            program = None
            try:
                lines = []
                for ln in Path(args.spec).read_text().splitlines():
                    s = ln.strip()
                    if s.startswith("asset"):
                        break
                    if s.startswith("#"):
                        t = s.lstrip("#").strip()
                        if t and not set(t) <= set("=-~_· "):
                            lines.append(t)
                program = "\n".join(lines) if lines else None
            except Exception:
                program = None
            score_pdf(specs if len(specs) > 1 else specs[0], out,
                      title=args.title, program=program,
                      bars_per_system=args.bars)
            print(f"score -> {out}  ({len(specs)} movement"
                  f"{'s' if len(specs) != 1 else ''})")
        elif args.cmd == "import-midi":
            from .interop import import_midi_bytes
            print(json.dumps(import_midi_bytes(Path(args.midi).read_bytes(),
                                               asset_id=args.id),
                             indent=2, sort_keys=True))
        elif args.cmd == "import-musicxml":
            from .interop import import_musicxml
            print(json.dumps(import_musicxml(Path(args.musicxml).read_text(),
                                             asset_id=args.id),
                             indent=2, sort_keys=True))
        elif args.cmd == "render":
            if args.jobs is not None:
                os.environ["AUDIOFORGE_JOBS"] = str(args.jobs)
            for a in _assets(args.spec, variant=args.variant):
                if args.intensity is not None:
                    a = a.with_intensity(args.intensity)
                meta = a.export(args.out, preset=args.preset,
                                stems=args.stems, analyze=args.analyze)
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
