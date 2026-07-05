"""Generate + drift-check the docs-site reference pages (roadmap item AF-R11).

Two site pages are GENERATED from the committed contract artifacts (ADR-0006):
`docs/reference.md` from `docs/ir.schema.json`, and `docs/capabilities.md` from
`docs/capability-manifest.json`. This tool owns them:

    python -m audioforge.tools.gen_docs --write   # regenerate both pages (default)
    python -m audioforge.tools.gen_docs --check    # fail on drift OR a missing nav page

`make docs` runs `--write` then `mkdocs build --strict`; `make docs-gen-check`
runs `--check` and is a `make check` prerequisite (no mkdocs needed for the gate).
Never hand-edit the generated pages — edit the source artifact (or its generator)
and rerun `--write`.
"""
from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
IR_SCHEMA = ROOT / "docs" / "ir.schema.json"
MANIFEST = ROOT / "docs" / "capability-manifest.json"
REFERENCE = ROOT / "docs" / "reference.md"
CAPABILITIES = ROOT / "docs" / "capabilities.md"
MKDOCS = ROOT / "mkdocs.yml"

_FRONTMATTER = (
    "---\n"
    "disclaimer:\n"
    "  notice: >-\n"
    "    No information within this document should be taken for granted. Any statement\n"
    "    or premise not backed by a real logical definition or verifiable reference may\n"
    "    be invalid, erroneous, or a hallucination.\n"
    '  generated_by: "audioforge.tools.gen_docs"\n'
    '  date: "2026-07-05"\n'
    "---\n\n"
    "<!-- GENERATED — do not hand-edit. Run `python -m audioforge.tools.gen_docs --write`. -->\n\n"
)


def render_reference() -> str:
    schema = json.loads(IR_SCHEMA.read_text(encoding="utf-8"))
    defs = schema.get("$defs", {})
    lines = [
        _FRONTMATTER,
        "# IR reference\n",
        f"The AudioForge IR (`{schema.get('$id', 'ir')}`, "
        f"version {schema.get('x-audioforge', {}).get('version', '?')}) as **{len(defs)}** "
        "structured definitions, generated from `docs/ir.schema.json` "
        "(itself generated from `audioforge/ir_schema.py`).\n",
        "| Definition | Type | Properties |",
        "|------------|------|------------|",
    ]
    for name in sorted(defs):
        d = defs[name]
        props = ", ".join(f"`{p}`" for p in sorted(d.get("properties", {}))) or "—"
        if len(props) > 90:
            props = props[:88].rsplit(",", 1)[0] + ", …"
        lines.append(f"| `{name}` | {d.get('type', '—')} | {props} |")
    return "\n".join(lines) + "\n"


def render_capabilities() -> str:
    m = json.loads(MANIFEST.read_text(encoding="utf-8"))

    def _count(v):
        return len(v) if isinstance(v, (list, dict)) else "—"

    osc_status = m.get("statuses", {}).get("by_capability", {}).get("oscillators", {})
    experimental = sorted(k for k, v in osc_status.items() if v == "experimental")
    lines = [
        _FRONTMATTER,
        "# Capabilities\n",
        f"Machine-readable surface of AudioForge **engine {m.get('engine_version')} · "
        f"DSL {m.get('dsl_version')}**, generated from `docs/capability-manifest.json` "
        "(itself generated from `audioforge/capabilities.py`).\n",
        "| Group | Count |",
        "|-------|------:|",
    ]
    for key in ("kinds", "layer_types", "oscillators", "fx", "articulations", "grooves",
                "style_packs", "automation_targets", "diagnostic_codes"):
        if key in m:
            lines.append(f"| {key.replace('_', ' ')} | {_count(m[key])} |")
    lines += [
        "",
        "## Per-capability status\n",
        "Status is derived by predicate (ADR-0006 / AF-R07): `stable` = pure-Python, "
        "always available; `experimental` = requires the native C-kernel toolchain "
        "(fails loudly if absent).\n",
        f"**Experimental oscillators:** {', '.join(f'`{o}`' for o in experimental) or 'none'}.\n",
        "Every diagnostic code is documented in "
        "[`DIAGNOSTIC_CODES.md`](DIAGNOSTIC_CODES.md).\n",
    ]
    return "\n".join(lines) + "\n"


def _nav_pages() -> list[str]:
    """Every `*.md` page referenced in mkdocs.yml's nav (order-preserving)."""
    if not MKDOCS.exists():
        return []
    return re.findall(r":\s*([\w./-]+\.md)\s*$", MKDOCS.read_text(encoding="utf-8"), re.M)


def _targets():
    return [(REFERENCE, render_reference()), (CAPABILITIES, render_capabilities())]


def write() -> list[Path]:
    written = []
    for path, content in _targets():
        path.write_text(content, encoding="utf-8")
        written.append(path)
    return written


def check() -> tuple[bool, list[str]]:
    report: list[str] = []
    ok = True
    for path, fresh in _targets():
        current = path.read_text(encoding="utf-8") if path.exists() else ""
        if current != fresh:
            ok = False
            report.append(f"STALE {path.name}:\n" + "".join(
                difflib.unified_diff(current.splitlines(True), fresh.splitlines(True),
                                     fromfile="committed", tofile="fresh", n=1)))
    for page in _nav_pages():
        if not (ROOT / "docs" / page).exists():
            ok = False
            report.append(f"mkdocs nav references a missing page: docs/{page}")
    if ok:
        report.append(f"docs pages in sync; all {len(_nav_pages())} nav pages resolve")
    return ok, report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m audioforge.tools.gen_docs",
        description="Generate or drift-check the docs-site reference pages.",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--write", action="store_const", dest="mode", const="write",
                      help="regenerate docs/reference.md + docs/capabilities.md (default)")
    mode.add_argument("--check", action="store_const", dest="mode", const="check",
                      help="fail on stale pages or a missing nav page; writes nothing")
    parser.set_defaults(mode="write")
    args = parser.parse_args(argv)

    if args.mode == "check":
        ok, report = check()
        stream = sys.stdout if ok else sys.stderr
        for line in report:
            stream.write(f"docs-gen-check: {line}\n")
        return 0 if ok else 1

    for path in write():
        print(f"wrote {path}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
