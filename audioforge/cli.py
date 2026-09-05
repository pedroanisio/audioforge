"""CLI.

  python -m audioforge.cli render   spec.json [-o outdir]
  python -m audioforge.cli batch    specs_dir [-o outdir]
  python -m audioforge.cli validate spec.json
  python -m audioforge.cli verify   spec.json manifest.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
import urllib.parse
import urllib.request
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


def _load_json_object(path: str, label: str) -> dict:
    """Structured failure for non-JSON input (DSL_GAP_SPEC §3.3: no raw decoder errors)."""
    try:
        data = json.loads(Path(path).read_text())
    except json.JSONDecodeError as e:
        raise SpecError(
            f"{label}: {path} is not valid JSON (line {e.lineno}, column {e.colno}); "
            "pass compiled JSON IR, or an .af source for the spec") from e
    if not isinstance(data, dict):
        raise SpecError(f"{label}: {path} must contain a JSON object")
    return data


def _spec_for_verify(path: str) -> dict:
    """`verify` accepts compiled JSON IR or a single-asset .af source."""
    if str(path).endswith(".af"):
        assets = _assets(path)
        if len(assets) != 1:
            raise SpecError(f"verify: {path} compiles to {len(assets)} assets; verify needs exactly one")
        return assets[0].spec
    return _load_json_object(path, "verify: spec")


class _UrllibHttp:
    def get_json(self, url, *, params=None, headers=None):
        if params:
            url = url + ("&" if "?" in url else "?") + urllib.parse.urlencode(
                params, doseq=True)
        req = urllib.request.Request(url, headers=headers or {})
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def get_bytes(self, url, *, headers=None):
        req = urllib.request.Request(url, headers=headers or {})
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.read()


def _load_json_list(path: str | Path) -> list:
    data = _read_sample_catalog_json(path, "sample-catalog input")
    path = Path(path)
    if isinstance(data, list):
        items = data
    elif isinstance(data, dict):
        if "items" not in data:
            raise ValueError(
                "sample-catalog input: expected JSON list or object with "
                f"'items' list in {path}")
        items = data["items"]
        if not isinstance(items, list):
            raise ValueError(
                f"sample-catalog input: expected 'items' list in {path}")
    else:
        raise ValueError(
            f"sample-catalog input: expected JSON list or object in {path}")
    if not all(isinstance(item, dict) for item in items):
        raise ValueError(
            f"sample-catalog input: expected item objects in {path}")
    return items


def _load_analysis(path: str | Path) -> list[dict]:
    path = Path(path)
    if path.is_file():
        return _load_json_list(path)
    if not path.exists():
        raise ValueError(
            f"sample-catalog analysis: cannot read {path}: file not found")
    analysis_files = sorted(path.glob("*.json"))
    if not analysis_files:
        raise ValueError(
            f"sample-catalog analysis: no analysis files found in {path}")
    return [
        _sample_catalog_analysis_record(
            _read_sample_catalog_json(fp, "sample-catalog analysis"), fp)
        for fp in analysis_files
    ]


def _sample_catalog_analysis_record(data, path: Path) -> dict:
    if not isinstance(data, dict):
        raise ValueError(
            f"sample-catalog analysis: expected analysis object in {path}")
    return data


def _verify_analysis_source_hashes(records: list[dict]) -> None:
    for idx, record in enumerate(records):
        expected = str(record.get("sha256") or "").strip().lower()
        if not expected:
            raise ValueError(
                f"sample-catalog analysis: record {idx} missing sha256")
        path = Path(str(record.get("path") or ""))
        if not path.is_file():
            raise ValueError(
                "sample-catalog analysis: cannot verify source bytes for "
                f"record {idx}: {path} is not a file")
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != expected:
            raise ValueError(
                "sample-catalog analysis: sha256 mismatch for "
                f"{path}: expected {expected}, got {actual}")


def _verify_analysis_sample_names_unique(records: list[dict]) -> None:
    seen: dict[str, Path] = {}
    for record in records:
        path = Path(str(record.get("path") or ""))
        filename = path.name
        if filename in seen:
            raise ValueError(
                "sample-catalog analysis: duplicate sample filename "
                f"{filename}: {seen[filename]} and {path}")
        seen[filename] = path


def _load_evidence(path: str | Path | None) -> list[dict]:
    if not path:
        return []
    path = Path(path)
    if path.is_file():
        data = _read_sample_catalog_json(path, "sample-catalog evidence")
        return _sample_catalog_evidence_items(data, path)
    if not path.exists():
        raise ValueError(
            f"sample-catalog evidence: cannot read {path}: file not found")
    evidence_files = sorted(path.glob("*.json"))
    if not evidence_files:
        raise ValueError(
            f"sample-catalog evidence: no evidence files found in {path}")
    return [
        item
        for fp in evidence_files
        for item in _sample_catalog_evidence_items(
            _read_sample_catalog_json(fp, "sample-catalog evidence"), fp)
    ]


def _sample_catalog_evidence_items(data, path: Path) -> list[dict]:
    if isinstance(data, list):
        items = data
    elif isinstance(data, dict):
        payload = data.get("evidence")
        if isinstance(payload, list):
            from .sample_catalog.constants import LICENSE_BUNDLE_SCHEMA
            schema = data.get("schema")
            if schema != LICENSE_BUNDLE_SCHEMA:
                raise ValueError(
                    "sample-catalog evidence: unsupported sample catalog "
                    f"license bundle schema in {path}: {schema!r}")
            items = payload
        else:
            items = [data]
    else:
        raise ValueError(
            f"sample-catalog evidence: expected JSON object or list in {path}")
    if not all(isinstance(item, dict) for item in items):
        raise ValueError(
            f"sample-catalog evidence: expected evidence objects in {path}")
    return items


def _read_sample_catalog_json(path: str | Path, label: str):
    path = Path(path)
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError as e:
        raise ValueError(
            f"{label}: invalid JSON in {path}: line {e.lineno} "
            f"column {e.colno}") from e
    except OSError as e:
        if isinstance(e, FileNotFoundError):
            reason = "file not found"
        elif isinstance(e, PermissionError):
            reason = "permission denied"
        else:
            reason = "read failed"
        raise ValueError(f"{label}: cannot read {path}: {reason}") from e


def _download_manifest_for_analysis(path: Path) -> Path | None:
    candidates = (path / "downloads.json", path.parent / "downloads.json")
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def _candidate_resume_key(candidate: dict) -> tuple[str, str, str] | None:
    evidence = candidate.get("evidence")
    evidence_hash = ""
    if isinstance(evidence, dict):
        evidence_hash = str(evidence.get("evidence_hash") or "")
    source = str(candidate.get("source") or "")
    source_id = str(candidate.get("source_id") or "")
    if not source or not source_id:
        return None
    return source, source_id, evidence_hash


def _download_resume_index(path: str | Path) -> dict[tuple[str, str, str], str]:
    path = Path(path)
    if not path.is_file():
        return {}
    rows = _load_json_list(path)
    out = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        candidate = row.get("candidate")
        if not isinstance(candidate, dict):
            continue
        key = _candidate_resume_key(candidate)
        sha = str(row.get("sha256") or "").strip().lower()
        if key and sha:
            out[key] = sha
    return out


def _evidence_from_analysis(records: list[dict]) -> list[dict]:
    by_hash = {}
    for record in records:
        evidence = record.get("license_evidence")
        if not isinstance(evidence, dict):
            continue
        evidence_hash = evidence.get("evidence_hash")
        if evidence_hash:
            by_hash[evidence_hash] = evidence
    return [by_hash[key] for key in sorted(by_hash)]


def _analysis_summary(records: list[dict]) -> dict:
    quality_scores = [
        float(record["quality_score"])
        for record in records
        if record.get("quality_score") is not None
    ]
    summary = {"accepted_samples": len(records)}
    ia_context_needs_review = 0
    for record in records:
        descriptors = record.get("source_descriptors") or {}
        context = descriptors.get("source_context") if isinstance(descriptors, dict) else None
        if (record.get("source") == "internet_archive"
                and isinstance(context, dict)
                and context.get("status") == "manual_review_required"):
            ia_context_needs_review += 1
    if ia_context_needs_review:
        summary["internet_archive_source_context_review_required"] = (
            ia_context_needs_review
        )
    if quality_scores:
        summary.update({
            "quality_score_min": round(min(quality_scores), 6),
            "quality_score_mean": round(
                sum(quality_scores) / len(quality_scores), 6),
            "quality_score_max": round(max(quality_scores), 6),
        })
    return summary


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
    p.add_argument("--plan", default=None,
                   help="execute a precomputed render-plan JSON after "
                        "recompute verification")
    p.add_argument("--explain", action="store_true",
                   help="print the render plan routing table and exit")

    p = sub.add_parser("plan"); p.add_argument("spec")
    p.add_argument("-o", "--out", default=None)
    p.add_argument("--explain", action="store_true")

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

    from .sample_catalog.constants import SAMPLE_CATALOG_COMMANDS
    from .sample_catalog.sources import SOURCE_ADAPTER_CLI_NAMES

    p = sub.add_parser("sample-catalog")
    sc = p.add_subparsers(dest="sample_catalog_cmd", required=True)
    sample_catalog_parsers = {
        command: sc.add_parser(command)
        for command in SAMPLE_CATALOG_COMMANDS
    }
    q = sample_catalog_parsers["search"]
    q.add_argument("--source", choices=SOURCE_ADAPTER_CLI_NAMES, required=True)
    q.add_argument("--license", choices=("cc0",), default="cc0")
    q.add_argument("--instrument", required=True)
    q.add_argument("--limit", type=int, default=50)
    q.add_argument("--token", default=None)
    q.add_argument("--out", required=True)
    q.add_argument("--include-quarantine", action="store_true")
    ro = sample_catalog_parsers["resolve-openverse"]
    ro.add_argument("--candidates", required=True)
    ro.add_argument("--instrument", required=True)
    ro.add_argument("--out", required=True)
    ro.add_argument("--token", default=None)
    ro.add_argument("--include-quarantine", action="store_true")
    d = sample_catalog_parsers["download"]
    d.add_argument("--candidates", required=True)
    d.add_argument("--out", required=True)
    d.add_argument("--token", default=None)
    d.add_argument("--manifest", default=None)
    d.add_argument("--min-interval", type=float, default=0.0)
    d.add_argument("--retries", type=int, default=1)
    d.add_argument("--retry-sleep", type=float, default=0.0)
    a = sample_catalog_parsers["analyze"]
    a.add_argument("--downloads", required=True)
    a.add_argument("--out", required=True)
    b = sample_catalog_parsers["build-sfz"]
    b.add_argument("--instrument", required=True)
    b.add_argument("--analysis", required=True)
    b.add_argument("--out", required=True)
    b.add_argument("--name", default=None)
    b.add_argument("--version", default="0.0.0")
    b.add_argument("--evidence", default=None)
    au = sample_catalog_parsers["audit-license"]
    au.add_argument("candidate")
    au.add_argument("--require-approved", action="store_true")
    r = sample_catalog_parsers["review"]
    r.add_argument("candidate")
    r.add_argument("--reviewer", default=None)
    r.add_argument("--reviewed-at", default=None)
    r.add_argument("--notes", default="")
    r.add_argument("--approve-to", default=None)

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
        elif args.cmd == "plan":
            from .plan import dumps_plan, explain_plan
            for a in _assets(args.spec):
                result = a.plan()
                if args.explain:
                    print(explain_plan(result["plan"]))
                else:
                    text = dumps_plan(result["plan"])
                    if args.out:
                        Path(args.out).write_text(text)
                        print(f"plan -> {args.out}")
                    else:
                        print(text, end="")
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
            if args.explain:
                from .plan import explain_plan
                for a in _assets(args.spec, variant=args.variant):
                    if args.intensity is not None:
                        a = a.with_intensity(args.intensity)
                    print(explain_plan(a.plan()["plan"]))
                return 0
            for a in _assets(args.spec, variant=args.variant):
                if args.intensity is not None:
                    a = a.with_intensity(args.intensity)
                kwargs = {}
                if args.plan:
                    kwargs["plan_path"] = args.plan
                meta = a.export(args.out, preset=args.preset,
                                stems=args.stems, analyze=args.analyze,
                                **kwargs)
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
        elif args.cmd == "sample-catalog":
            if args.sample_catalog_cmd == "search":
                from .sample_catalog.sources import (
                    SOURCE_ADAPTER_CLI_TO_ID, FreesoundAdapter,
                    InternetArchiveAdapter, OpenverseDiscoveryAdapter,
                    WikimediaCommonsAdapter)
                http = _UrllibHttp()
                source_id = SOURCE_ADAPTER_CLI_TO_ID[args.source]
                if source_id == "freesound":
                    adapter = FreesoundAdapter(http, token=args.token)
                    candidates = adapter.search(
                        instrument=args.instrument,
                        limit=args.limit,
                        include_quarantine=args.include_quarantine)
                elif source_id == "internet_archive":
                    adapter = InternetArchiveAdapter(http)
                    candidates = adapter.search(
                        query=args.instrument,
                        limit=args.limit,
                        include_quarantine=args.include_quarantine)
                elif source_id == "wikimedia_commons":
                    adapter = WikimediaCommonsAdapter(http)
                    candidates = adapter.search(
                        query=args.instrument,
                        limit=args.limit,
                        include_quarantine=args.include_quarantine)
                else:
                    adapter = OpenverseDiscoveryAdapter(http)
                    candidates = adapter.search(
                        query=args.instrument,
                        limit=args.limit)
                out = Path(args.out)
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_text(json.dumps([c.to_dict() for c in candidates],
                                          indent=2, sort_keys=True) + "\n")
                print(f"sample-catalog search -> {out} "
                      f"({len(candidates)} candidates)")
            elif args.sample_catalog_cmd == "resolve-openverse":
                from .sample_catalog.sources import (
                    Candidate, FreesoundAdapter, InternetArchiveAdapter,
                    OpenverseDiscoveryAdapter, WikimediaCommonsAdapter)
                http = _UrllibHttp()
                resolver = OpenverseDiscoveryAdapter(http)
                upstream = {
                    "freesound": FreesoundAdapter(http, token=args.token),
                    "internet_archive": InternetArchiveAdapter(http),
                    "wikimedia_commons": WikimediaCommonsAdapter(http),
                }
                resolved = []
                for row in _load_json_list(args.candidates):
                    candidate = Candidate.from_dict(row)
                    if candidate.source != "openverse_discovery":
                        resolved.append(candidate)
                        continue
                    resolved.append(resolver.resolve(
                        candidate,
                        upstream_adapters=upstream,
                        instrument=args.instrument,
                        include_quarantine=args.include_quarantine,
                    ))
                out = Path(args.out)
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_text(json.dumps([c.to_dict() for c in resolved],
                                          indent=2, sort_keys=True) + "\n")
                print(f"sample-catalog resolve-openverse -> {out} "
                      f"({len(resolved)} candidates)")
            elif args.sample_catalog_cmd == "download":
                from .sample_catalog.download import (
                    download_candidate, save_download_results)
                candidates = _load_json_list(args.candidates)
                headers = ({"Authorization": f"Bearer {args.token}"}
                           if args.token else None)
                results = []
                last_request_at = None
                import time as _time
                http = _UrllibHttp()
                manifest = args.manifest or str(Path(args.out) / "downloads.json")
                resume_index = _download_resume_index(manifest)
                for c in candidates:
                    expected = (
                        c.get("sha256")
                        or c.get("expected_sha256")
                        or resume_index.get(_candidate_resume_key(c))
                    )
                    result = download_candidate(
                        c, args.out, http, headers=headers,
                        expected_sha256=expected,
                        min_interval_s=args.min_interval,
                        last_request_at=last_request_at,
                        max_attempts=args.retries,
                        retry_sleep_s=args.retry_sleep)
                    results.append(result)
                    if not result.reused:
                        last_request_at = _time.monotonic()
                save_download_results(results, manifest)
                print(f"sample-catalog download -> {manifest} "
                      f"({len(results)} files)")
            elif args.sample_catalog_cmd == "analyze":
                from .sample_catalog.analyze import analyze_downloads, analyze_sample
                src = Path(args.downloads)
                out = Path(args.out)
                if src.is_file():
                    records = analyze_downloads(_load_json_list(src), out)
                elif (manifest := _download_manifest_for_analysis(src)) is not None:
                    records = analyze_downloads(_load_json_list(manifest), out)
                elif not src.exists():
                    raise ValueError(
                        "sample-catalog downloads: cannot read "
                        f"{src}: file not found")
                else:
                    sample_files = sorted(
                        p for p in src.rglob("*") if p.is_file())
                    if not sample_files:
                        raise ValueError(
                            "sample-catalog downloads: no files found in "
                            f"{src}")
                    out.mkdir(parents=True, exist_ok=True)
                    records = []
                    for fp in sample_files:
                        rec = analyze_sample(fp)
                        (out / f"{rec['sha256']}.json").write_text(
                            json.dumps(rec, indent=2, sort_keys=True) + "\n")
                        records.append(rec)
                print(f"sample-catalog analyze -> {out} "
                      f"({len(records)} files)")
            elif args.sample_catalog_cmd == "build-sfz":
                from .sample_catalog.analyze import validate_analysis_record_schema
                from .sample_catalog.manifest import (
                    audit_catalog, copy_samples, write_library_manifest,
                    write_license_bundle)
                from .sample_catalog.sfz import build_region_sets, write_sfz
                analyses = _load_analysis(args.analysis)
                for record in analyses:
                    validate_analysis_record_schema(record)
                accepted = [a for a in analyses if a.get("status") == "accepted"]
                if not accepted:
                    raise SpecError("sample-catalog build-sfz: no accepted analyses")
                _verify_analysis_source_hashes(accepted)
                _verify_analysis_sample_names_unique(accepted)
                evidence = (
                    _load_evidence(args.evidence)
                    or _evidence_from_analysis(accepted)
                )
                if not evidence:
                    raise SpecError(
                        "sample-catalog build-sfz: license evidence is required")
                out = Path(args.out)
                copied = copy_samples([a["path"] for a in accepted],
                                      out / "samples")
                copied_by_name = {p.name: p for p in copied}
                rewritten = []
                for a in accepted:
                    row = dict(a)
                    row["path"] = str(copied_by_name[Path(a["path"]).name])
                    rewritten.append(row)
                region_sets = build_region_sets(rewritten)
                articulations = {}
                for articulation, regions in region_sets.items():
                    sfz_name = ("instrument.sfz" if articulation == "sustain"
                                else f"instrument_{articulation}.sfz")
                    write_sfz(regions, out / sfz_name)
                    articulations[articulation] = sfz_name
                bundle = write_license_bundle(evidence, out / "LICENSES.json")
                bundle_hash = json.loads(
                    bundle.read_text())["license_evidence_hash"]
                sample_mechanics = {}
                sample_loop_candidates = {}
                for a in rewritten:
                    sample = f"samples/{Path(a['path']).name}"
                    mechanics = {
                        key: a[key]
                        for key in ("string", "fret", "tuning", "position",
                                    "session")
                        if a.get(key) is not None
                    }
                    if ("session" not in mechanics
                            and a.get("session_id") is not None):
                        mechanics["session"] = a["session_id"]
                    if mechanics:
                        sample_mechanics[sample] = mechanics
                    if isinstance(a.get("loop_candidate"), dict):
                        sample_loop_candidates[sample] = a["loop_candidate"]
                manifest = write_library_manifest(
                    out,
                    name=args.name or args.instrument,
                    version=args.version,
                    instrument=args.instrument,
                    license_evidence_hash=bundle_hash,
                    license_evidence=evidence,
                    sample_evidence_ids={
                        f"samples/{Path(a['path']).name}": a["source_evidence_id"]
                        for a in rewritten
                        if a.get("source_evidence_id")
                    },
                    sample_mechanics=sample_mechanics,
                    sample_loop_candidates=sample_loop_candidates,
                    sample_analysis_records=rewritten,
                    articulations=articulations,
                    analysis_summary=_analysis_summary(accepted),
                )
                audit_catalog(out)
                print(f"sample-catalog build-sfz -> {out}")
                print(f"pin: {manifest['name']}@{manifest['manifest_sha256']}")
            elif args.sample_catalog_cmd == "audit-license":
                from .sample_catalog.manifest import audit_catalog
                result = audit_catalog(args.candidate,
                                       require_approved=args.require_approved)
                print(json.dumps(result, indent=2, sort_keys=True))
            elif args.sample_catalog_cmd == "review":
                from .sample_catalog.review import promote_candidate, write_review
                if args.approve_to:
                    if not args.reviewed_at:
                        raise ValueError("reviewed_at is required for promotion")
                    dest = promote_candidate(args.candidate, args.approve_to,
                                             reviewer=args.reviewer or "",
                                             reviewed_at=args.reviewed_at)
                    print(f"sample-catalog approved -> {dest}")
                else:
                    path = write_review(args.candidate, reviewer=args.reviewer,
                                        reviewed_at=args.reviewed_at,
                                        notes=args.notes)
                    print(f"sample-catalog review -> {path}")
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
            manifest = _load_json_object(args.manifest, "verify: manifest")
            if "output_sha256" not in manifest:
                raise SpecError(f"verify: manifest {args.manifest} lacks output_sha256")
            spec = _spec_for_verify(args.spec)
            with tempfile.TemporaryDirectory() as td:
                ok = verify(spec, manifest["output_sha256"], td)
            print("REPRODUCIBLE" if ok else "MISMATCH — output drifted")
            return 0 if ok else 2
    except (SpecError, DSLError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
