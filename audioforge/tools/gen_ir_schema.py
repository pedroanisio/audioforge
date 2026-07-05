"""Generator + drift gate for ``docs/ir.schema.json`` (roadmap item AF-R05).

``docs/ir.schema.json`` is a **generated artifact**: it is the published
serialization of :func:`audioforge.ir_schema.ir_json_schema`. This module owns
that file so it can never be silently hand-edited into drift.

    python -m audioforge.tools.gen_ir_schema --write   # regenerate (default)
    python -m audioforge.tools.gen_ir_schema --check    # exit non-zero on drift

Never hand-edit ``docs/ir.schema.json``: edit the source (``audioforge/ir_schema.py``)
and rerun ``--write``. ``make schema-check`` runs ``--check``; CI runs it via
``make check`` (AF-R01), so drift is a loud failure, not a latent inconsistency.

Bumping the schema version: change ``IR_SCHEMA_VERSION`` in
``audioforge/ir_schema.py`` (the single source), then run this generator with
``--write`` to republish ``docs/ir.schema.json``. ``tests/test_ir_schema.py``
pins ``$id``/``x-audioforge.version`` to ``IR_SCHEMA_VERSION`` and this
generator's byte output, so a half-done bump fails the suite.

⚠ ARCHITECTURAL CONTRACT (PALS's LAW): the published schema is derived output.
Treating derived output as authoritative is exactly how it drifts from the
runtime source. The ``--check`` twin turns that drift into a gate failure.
"""
from __future__ import annotations

import argparse
import difflib
import json
import sys
from pathlib import Path

from audioforge.ir_schema import ir_json_schema

# Repo-relative published artifact this generator owns. Resolved at call time
# (via the module global) so tests can retarget it with monkeypatch.
PUBLISHED_SCHEMA = Path(__file__).resolve().parents[2] / "docs" / "ir.schema.json"


def render_schema() -> str:
    """Canonical, byte-stable serialization of the runtime IR JSON Schema.

    ``sort_keys=True`` makes the output independent of dict insertion order in
    :func:`ir_json_schema`; ``indent=2`` + a trailing newline match the
    committed file. This is the **single source of formatting** — the ``--write``
    path and the drift test (``tests/test_ir_schema.py``) both go through it.
    """
    return json.dumps(ir_json_schema(), indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def write(path: Path | None = None) -> Path:
    """Write the canonical schema to *path* (default: the committed artifact)."""
    target = path or PUBLISHED_SCHEMA
    target.write_text(render_schema(), encoding="utf-8")
    return target


def check(path: Path | None = None) -> tuple[bool, str]:
    """Return ``(ok, diff)``: ``ok`` iff *path* matches a fresh render.

    On mismatch, ``diff`` is a unified diff (committed → fresh). Writes nothing.
    """
    target = path or PUBLISHED_SCHEMA
    fresh = render_schema()
    current = target.read_text(encoding="utf-8") if target.exists() else ""
    if fresh == current:
        return True, ""
    diff = "".join(
        difflib.unified_diff(
            current.splitlines(keepends=True),
            fresh.splitlines(keepends=True),
            fromfile=f"{target} (committed)",
            tofile=f"{target} (fresh render)",
        )
    )
    return False, diff


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m audioforge.tools.gen_ir_schema",
        description="Generate or drift-check docs/ir.schema.json from ir_json_schema().",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--write", action="store_const", dest="mode", const="write",
        help="regenerate docs/ir.schema.json from the runtime source (default)",
    )
    mode.add_argument(
        "--check", action="store_const", dest="mode", const="check",
        help="exit non-zero (with a diff) if the committed file is stale; writes nothing",
    )
    parser.set_defaults(mode="write")
    args = parser.parse_args(argv)

    if args.mode == "check":
        ok, diff = check()
        if ok:
            print(f"schema-check: {PUBLISHED_SCHEMA} is in sync with ir_json_schema()")
            return 0
        sys.stderr.write(diff)
        sys.stderr.write(
            f"\nschema-check: {PUBLISHED_SCHEMA} is STALE. Run "
            "`python -m audioforge.tools.gen_ir_schema --write` "
            "(never hand-edit the generated file).\n"
        )
        return 1

    target = write()
    print(f"wrote {target}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
