"""Generator + drift gate for the capability manifest (roadmap item AF-R07).

`docs/capability-manifest.json` is the committed, machine-readable serialization
of :func:`audioforge.capabilities.capability_manifest` — a `git diff`-able surface
an agent can read without running the CLI. `docs/DIAGNOSTIC_CODES.md` is the
generated documentation of every diagnostic code the engine can emit. Both are
owned by this tool:

    python -m audioforge.tools.gen_capability --write   # regenerate both
    python -m audioforge.tools.gen_capability --check    # fail on drift

Never hand-edit either artifact: change the source (`audioforge/capabilities.py`)
and rerun `--write`. `make manifest-check` runs `--check`; CI runs it via
`make check` (AF-R01), so a stale committed manifest is a loud failure.

The per-capability `status` in the manifest is DERIVED by predicate
(`_capability_statuses`), never hand-labelled — see that function's docstring.

⚠ ARCHITECTURAL CONTRACT (PALS's LAW): a capability surface an agent consumes is
untrusted until it is verified against the live registries. The committed
manifest + `--check` twin make that verification a gate, not a hope.
"""
from __future__ import annotations

import argparse
import difflib
import json
import sys
from pathlib import Path

from audioforge.capabilities import capability_manifest

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "docs" / "capability-manifest.json"
CODES_DOC = ROOT / "docs" / "DIAGNOSTIC_CODES.md"

_DOC_DATE = "2026-07-04"  # generator authorship date; pinned for byte-stable output


def render_manifest() -> str:
    """Canonical, byte-stable serialization of the runtime capability manifest."""
    return json.dumps(capability_manifest(), indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def render_codes_doc() -> str:
    """Generated Markdown: every diagnostic code + its repair hint (sorted)."""
    m = capability_manifest()
    codes = m["diagnostic_codes"]
    hints = m.get("repair_hints", {})
    rows = []
    for code in sorted(codes):
        entry = codes[code] or {}
        hint_key = entry.get("repair_hint", code) if isinstance(entry, dict) else code
        text = hints.get(hint_key) or hints.get(code) or "_(see repair_hints in the manifest)_"
        text = text.replace("|", "\\|").replace("\n", " ").strip()
        rows.append(f"| `{code}` | {text} |")
    body = "\n".join(rows)
    return (
        "---\n"
        "disclaimer:\n"
        "  notice: >-\n"
        "    No information within this document should be taken for granted. Any statement\n"
        "    or premise not backed by a real logical definition or verifiable reference may\n"
        "    be invalid, erroneous, or a hallucination.\n"
        '  generated_by: "audioforge.tools.gen_capability (from capability_manifest)"\n'
        f'  date: "{_DOC_DATE}"\n'
        "---\n\n"
        "# AudioForge Diagnostic Codes\n\n"
        "<!-- GENERATED — do not hand-edit. Run `python -m audioforge.tools.gen_capability --write`. -->\n\n"
        "Every diagnostic code the engine can emit, with its repair hint. Generated from\n"
        "`capability_manifest()[\"diagnostic_codes\"]` and gated by `gen_capability.py --check`\n"
        "(`make manifest-check`), so a new code cannot land undocumented.\n\n"
        f"There are **{len(codes)}** diagnostic codes.\n\n"
        "| Code | Repair hint |\n"
        "|------|-------------|\n"
        f"{body}\n"
    )


def _targets() -> list[tuple[Path, str]]:
    return [(MANIFEST, render_manifest()), (CODES_DOC, render_codes_doc())]


def write() -> list[Path]:
    written = []
    for path, content in _targets():
        path.write_text(content, encoding="utf-8")
        written.append(path)
    return written


def check() -> tuple[bool, str]:
    ok = True
    diffs = []
    for path, fresh in _targets():
        current = path.read_text(encoding="utf-8") if path.exists() else ""
        if current == fresh:
            continue
        ok = False
        diffs.append(
            "".join(
                difflib.unified_diff(
                    current.splitlines(keepends=True),
                    fresh.splitlines(keepends=True),
                    fromfile=f"{path} (committed)",
                    tofile=f"{path} (fresh)",
                )
            )
        )
    return ok, "\n".join(diffs)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m audioforge.tools.gen_capability",
        description="Generate or drift-check docs/capability-manifest.json + docs/DIAGNOSTIC_CODES.md.",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--write", action="store_const", dest="mode", const="write",
                      help="regenerate the committed manifest + diagnostic-codes doc (default)")
    mode.add_argument("--check", action="store_const", dest="mode", const="check",
                      help="exit non-zero if either committed artifact is stale; writes nothing")
    parser.set_defaults(mode="write")
    args = parser.parse_args(argv)

    if args.mode == "check":
        ok, diff = check()
        if ok:
            print("manifest-check: docs/capability-manifest.json + DIAGNOSTIC_CODES.md are in sync")
            return 0
        sys.stderr.write(diff)
        sys.stderr.write(
            "\nmanifest-check: a committed capability artifact is STALE. Run "
            "`python -m audioforge.tools.gen_capability --write`.\n"
        )
        return 1

    for path in write():
        print(f"wrote {path}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
