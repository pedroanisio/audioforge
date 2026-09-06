"""Catalog, document and render the repository's composition examples.

Run from any directory with the project's Python interpreter. Audio stays local;
the catalog, DSL sources and generated Markdown pages are versioned.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "docs" / "examples"
CATALOG = BASE / "catalog.json"
FRONT = '''---
disclaimer:
  notice: >-
    Examples describe authored intent. Render manifests and measurements provide
    technical evidence; they do not certify musical quality.
  generated_by: "scripts/examples.py via Codex"
  date: "2026-09-06"
---

<!-- Generated from catalog.json and the adjacent DSL by scripts/examples.py docs. -->

'''
CATEGORIES = {
    "sound-design": "Start here: sound design",
    "electronic": "Electronic music",
    "orchestral": "Orchestral compositions",
    "road-trip": "Five Seats, One Horizon: road trip suite",
    "guitar": "Guitar studies",
    "jazz": "Jazz compositions",
    "arrangements": "Arrangements and import studies",
    "archive": "Historical scores and diagnostic examples",
}


def load_catalog():
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    entries = data["examples"]
    ids = [item["id"] for item in entries]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate example ID")
    for item in entries:
        source = (ROOT / item["source"]).resolve()
        if not source.is_relative_to(BASE) or source.suffix != ".af":
            raise ValueError(f"invalid source path: {item['source']}")
    return entries


def page(item):
    source = ROOT / item["source"]
    preview = "\n".join(source.read_text(encoding="utf-8").splitlines()[:35])
    note = item["description"]
    status = "Compiles with the current engine" if item["compiles"] else "Historical DSL; requires migration before rendering"
    pins = ", ".join(f"`{pin}`" for pin in item["libraries"]) or "No external instrument library."
    lines = [FRONT, f"# {item['title']}\n", note + "\n",
             "[All examples](../../index.md) · " + f"[Download the complete DSL]({source.name})\n",
             f"**Source status:** {status}.\n", f"**Instrument resources:** {pins}\n",
             "## Render and listen\n",
             "Run from the repository root after installing AudioForge and any pinned libraries:\n",
             "```sh", f".venv/bin/python scripts/examples.py render {item['id']}",
             ".venv/bin/python scripts/examples.py gallery", "```\n",
             "Open `docs/examples/listen.html` in a browser. It pairs local audio with the DSL "
             "and reports missing renders. New renders go into this example's `audio/current/`; "
             "earlier audio and manifests remain in `audio/`. WAVs, MP3s, stems and detailed "
             "render evidence are local artifacts and are not included in a source-only checkout.\n",
             "The render command records compilation, resource and rendering failures in "
             "`docs/examples/render-report.json`; a historical score is never silently skipped.\n"]
    if item.get("diagnostics"):
        lines += ["## Recorded source limitations\n"]
        lines += [f"- {message}" for message in item["diagnostics"]]
        lines += [""]
    if item.get("recording_note"):
        lines += ["## Historical recording\n", item["recording_note"] + "\n"]
    supporting = [("delivery.md", "Composition and delivery notes"),
                  ("design.md", "Historical design notes"),
                  ("compose.py", "Composition generator"), ("validate.py", "Delivery validator"),
                  ("prepare_library.py", "Local library preparation")]
    links = [f"[{label}]({name})" for name, label in supporting if (source.parent / name).is_file()]
    if links:
        lines += ["## Supporting material\n", " · ".join(links) + "\n"]
    lines += ["## DSL preview\n", "The download above contains the full score.\n", "```text", preview, "```\n"]
    return "\n".join(lines)


def index(entries):
    lines = [FRONT, "# Composition examples\n",
             "Read the DSL, reproduce a render, and compare the available recordings. "
             "Each composition has one directory containing its score, documentation, "
             "supporting scripts and local audio. Variants retain their own identities.\n",
             "Start with [Transition sweep](sound-design/transition-sweep/index.md), "
             "a two-second example with no external instrument library.\n",
             "## Listen locally\n", "```sh", ".venv/bin/python scripts/examples.py gallery", "```\n",
             "Open `docs/examples/listen.html`. The gallery provides search, category filters, "
             "audio playback, source previews and links to full scores. Audio is loaded only "
             "when requested. Rebuild the gallery after adding renders.\n",
             "## Reproduce an example\n", "```sh",
             ".venv/bin/python scripts/examples.py render transition-sweep",
             ".venv/bin/python scripts/examples.py check", "```\n",
             "Pass one or more catalog IDs to `render`, or use `--all` explicitly. "
             "It writes fresh output into `audio/current/`, preserves earlier renders and "
             "records every selected example's outcome. Add `--stems` when separate parts "
             "are needed. Pinned sample libraries must be installed locally.\n",
             "A compilable score may still need an instrument library. Historical examples "
             "with invalid DSL or placeholder pins are retained for study and regression coverage; "
             "their pages disclose those limitations. Existing renders may belong to earlier "
             "engine versions; consult their manifests before claiming reproduction.\n"]
    for category, title in CATEGORIES.items():
        lines += [f"## {title}\n", "| Composition | Source status |", "|---|---|"]
        for item in entries:
            if item["category"] == category:
                path = Path(item["source"]).parent.relative_to("docs/examples") / "index.md"
                status = "Compiles; pinned library required" if item["libraries"] else "Compiles; self-contained"
                if not item["compiles"]:
                    status = "Historical DSL; migration required"
                lines.append(f"| [{item['title']}]({path}) | {status} |")
        lines.append("")
    lines += ["## Other retained material\n",
              "The historical [riff image](archive/unassigned-assets/riff.png) and "
              "[vector version](archive/unassigned-assets/riff.svg) are retained separately; "
              "their association with a particular score is not recorded.\n",
              "## Build the documentation site\n",
              "The site configuration excludes local WAV masters, stems and Python caches. "
              "MP3 listening copies are included when available.\n",
              "```sh",
              ".venv/bin/python scripts/examples.py previews",
              ".venv/bin/python scripts/examples.py gallery",
              "uv run --no-project --with mkdocs-material mkdocs build --strict",
              "```\n",
              "## Organization and maintenance\n",
              "The [layout decision](../adr/0010-composition-examples-layout.md) explains "
              "source ownership, generated artifacts and historical recordings.\n",
              "`catalog.json` owns the IDs, categories, descriptions and recorded source status. "
              "`scripts/examples.py docs` generates this index and each example page. "
              "`scripts/examples.py check` checks coverage, compile expectations and documentation drift.\n",
              "`migration.json` records every relocated file, its old and new paths and byte hashes. "
              "Historical evidence retains its original content and recorded paths. "
              "The old `compositions/` and `renders/` directories are no longer authoring locations.\n",
              "Python SDK recipes remain in the repository's `examples/` directory. "
              "Purpose-built acceptance and rejection fixtures remain under `static/fixtures/` "
              "and `tests/fixtures/`; they are not listening examples.\n"]
    return "\n".join(lines)


def documents(entries):
    return [(BASE / "index.md", index(entries))] + [
        (ROOT / Path(item["source"]).parent / "index.md", page(item)) for item in entries]


def audio_files(item):
    directory = (ROOT / item["source"]).parent / "audio"
    # A master is a direct child; stem directories are deliberately excluded.
    files = [p for parent in (directory / "current", directory)
             for p in sorted(parent.glob("*")) if p.suffix in (".mp3", ".wav")]
    files = [p for p in files if not (
        p.suffix == ".mp3" and p.parent.name == "current"
        and p.with_suffix(".wav").is_file()
        and p.stat().st_mtime_ns < p.with_suffix(".wav").stat().st_mtime_ns)]
    previews_available = set(files)
    files = [p for p in files if p.suffix != ".wav" or p.with_suffix(".mp3") not in previews_available]
    return sorted(files, key=lambda p: (p.parent.name != "current", p.suffix != ".mp3", p.name))


def previews(entries):
    """Create playback copies, refreshing stale current previews and keeping history."""
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise RuntimeError("MP3 previews require ffmpeg; local WAV playback is available without it")
    written = []
    for item in entries:
        directory = (ROOT / item["source"]).parent / "audio"
        for parent in (directory, directory / "current"):
            for wav in sorted(parent.glob("*.wav")):
                mp3 = wav.with_suffix(".mp3")
                if mp3.exists() and (parent.name != "current"
                                     or mp3.stat().st_mtime_ns >= wav.stat().st_mtime_ns):
                    continue
                with tempfile.TemporaryDirectory(prefix=".preview-", dir=parent) as temporary:
                    output = Path(temporary) / mp3.name
                    subprocess.run([ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "error", "-n",
                                    "-i", str(wav), "-codec:a", "libmp3lame", "-b:a", "192k", str(output)],
                                   check=True, capture_output=True, text=True)
                    output.replace(mp3)
                written.append(mp3)
    return written


def gallery(entries):
    rows = []
    for item in entries:
        source = ROOT / item["source"]
        rows.append(dict(item, source=str(source.relative_to(BASE)),
                         preview="\n".join(source.read_text().splitlines()[:60]),
                         audio=[str(p.relative_to(BASE)) for p in audio_files(item)]))
    payload = json.dumps(rows, ensure_ascii=False).replace("<", "\\u003c")
    template = (ROOT / "scripts/examples_gallery.html").read_text(encoding="utf-8")
    path = BASE / "listen.html"
    path.write_text(template.replace("__EXAMPLES_JSON__", payload), encoding="utf-8")
    return path


def check(entries):
    from audioforge import AudioForge

    errors = []
    expected = {ROOT / item["source"] for item in entries}
    actual = set(BASE.rglob("*.af"))
    if expected != actual:
        errors.append(f"catalog/source mismatch: {sorted(str(p) for p in expected ^ actual)}")
    for item in entries:
        source = ROOT / item["source"]
        if not source.is_file():
            errors.append(f"missing source: {source}")
            continue
        compiled = AudioForge().compile(source.read_text(encoding="utf-8"))
        if compiled.ok != item["compiles"]:
            errors.append(f"compile expectation changed: {item['id']}")
        if (ROOT / item["legacy_source"]).exists():
            errors.append(f"duplicate legacy source: {item['legacy_source']}")
    if errors:
        return errors
    for path, content in documents(entries):
        if not path.is_file() or path.read_text(encoding="utf-8") != content:
            errors.append(f"stale documentation: {path.relative_to(ROOT)}; run scripts/examples.py docs")
    return errors


def render_examples(entries, stems=False):
    results = []
    pythonpath = os.pathsep.join(filter(None, (str(ROOT), os.environ.get("PYTHONPATH"))))
    env = dict(os.environ, PYTHONPATH=pythonpath, OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1")
    for item in entries:
        source = ROOT / item["source"]
        output = source.parent / "audio/current"
        command = [sys.executable, "-m", "audioforge.cli", "render", str(source), "-o", str(output)]
        if stems:
            command.append("--stems")
        print(f"Rendering {item['id']}", flush=True)
        result = subprocess.run(command, cwd=ROOT, env=env, text=True, capture_output=True)
        results.append(dict(id=item["id"], status="rendered" if result.returncode == 0 else "failed",
                            exit_code=result.returncode, output=str(output.relative_to(ROOT)),
                            stdout=result.stdout, stderr=result.stderr))
        (BASE / "render-report.json").write_text(json.dumps({"results": results}, indent=2) + "\n")
    return results


def main(argv=None):
    sys.path.insert(0, str(ROOT))
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for verb in ("check", "docs", "gallery", "previews"):
        sub.add_parser(verb)
    render = sub.add_parser("render")
    render.add_argument("ids", nargs="*")
    render.add_argument("--all", action="store_true", help="render every catalog entry, including historical sources")
    render.add_argument("--stems", action="store_true")
    args = parser.parse_args(argv)
    entries = load_catalog()
    if args.command == "docs":
        for path, content in documents(entries):
            path.write_text(content, encoding="utf-8")
        print(f"Wrote {len(entries) + 1} documentation pages")
    elif args.command == "gallery":
        print(gallery(entries))
    elif args.command == "previews":
        print(f"Created {len(previews(entries))} MP3 previews; master WAVs unchanged")
    elif args.command == "check":
        errors = check(entries)
        for error in errors:
            print(error, file=sys.stderr)
        if errors:
            return 1
        print(f"Examples check passed: {len(entries)} scores and {len(entries) + 1} documentation pages")
    else:
        if bool(args.ids) == args.all:
            parser.error("render requires catalog IDs or --all")
        missing = set(args.ids) - {item["id"] for item in entries}
        if missing:
            parser.error(f"unknown example IDs: {', '.join(sorted(missing))}")
        selected = entries if args.all else [item for item in entries if item["id"] in args.ids]
        results = render_examples(selected, args.stems)
        gallery(entries)
        print(json.dumps({"rendered": sum(r['status'] == 'rendered' for r in results),
                          "failed": sum(r['status'] == 'failed' for r in results)}))
        return int(any(r["status"] == "failed" for r in results))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
