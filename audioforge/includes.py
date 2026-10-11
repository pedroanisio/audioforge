"""Content-pinned `.af` includes: textual resolution before parsing.

An `import` directive pulls reusable `motif`/`bus` definitions from an `.afi`
fragment into the importing file, pinned by SHA-256:

    import "stdlib/rock_buses.afi" @ sha256:ab3f…

Resolution is pure substitution — it runs *before* the parser and produces a
single, fully-materialised `.af` source. It never computes: it reads, verifies,
de-duplicates, and inlines. This keeps every downstream validation property
intact and preserves the engine's reproducibility contract:

  * **Integrity** — the pinned SHA-256 must match the file's bytes, or
    resolution refuses (loud and local). An unpinned include silently changing
    under a rendered song is exactly the drift this prevents.
  * **Reproducibility** — the resolved source is what compiles, so identical
    music hashes identically whether it was authored inline or imported. The
    import pins are recorded as provenance (`_meta.imports`); the rendered
    identity comes from the expanded events, which are already hash-included.
  * **Acyclic** — the import graph is a DAG; cycles refuse. Diamonds (the same
    pinned file reached by two paths) de-duplicate to one inclusion.
  * **Materialisable** — `expand` always writes the single resolved file, so an
    agent can read exactly what will render.

Scope (first slice): flat names with collision detection (two definitions of
the same name refuse). Namespacing (`import … as ns` + `ns.name` references) is
a deliberate follow-up that requires a grammar change; see docs/adr/0001.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path

from .dsl import DSLError


class IncludeError(DSLError):
    """A hard include-resolution failure (subclasses DSLError so the SDK's
    `compile` turns it into a structured diagnostic rather than raising)."""


_IMPORT_RE = re.compile(
    r'^\s*import\s+"([^"]+)"\s*@\s*sha256:([0-9a-fA-F]{64})\s*(?:#.*)?$')
_DEF_RE = re.compile(r'^\s*(motif|bus)\s+([A-Za-z_][A-Za-z0-9_#]*)\b')
_ASSET_OPEN_RE = re.compile(r'(\basset\s+[A-Za-z_][A-Za-z0-9_#]*\s*\{)')


@dataclass
class ResolveResult:
    source: str
    imports: list = field(default_factory=list)


def _is_blank_or_comment(line: str) -> bool:
    s = line.strip()
    return not s or s.startswith("#")


def _def_names(text: str) -> list[str]:
    out = []
    for line in text.splitlines():
        m = _DEF_RE.match(line)
        if m:
            out.append(m.group(2))
    return out


def resolve_includes(source: str, base_dir: Path | str | None, *,
                     _stack: tuple = (), _seen: dict | None = None
                     ) -> ResolveResult:
    """Resolve `import` directives in ``source`` into a single materialised
    source. ``base_dir`` is the directory imports resolve against (the importing
    file's directory). Returns the resolved text and a flat provenance list of
    the unique pinned imports.
    """
    seen = _seen if _seen is not None else {}
    base = Path(base_dir) if base_dir is not None else None

    lines = source.splitlines()
    imports: list[tuple[int, str, str]] = []   # (lineno, rel_path, sha256)
    body_lines: list[str] = []
    seen_body = False
    for i, line in enumerate(lines, start=1):
        m = _IMPORT_RE.match(line)
        if m:
            if seen_body:
                raise IncludeError(
                    "import must appear before any asset or definition", i)
            imports.append((i, m.group(1), m.group(2).lower()))
            continue
        if not _is_blank_or_comment(line):
            seen_body = True
        body_lines.append(line)
    body = "\n".join(body_lines)

    def_blocks: list[str] = []
    manifest: list[dict] = []
    for lineno, rel, sha in imports:
        if base is None:
            raise IncludeError(
                f"import \"{rel}\" requires a file context (compile from a "
                f"path, not a bare string)", lineno)
        rel_path = Path(rel)
        if rel_path.is_absolute():
            raise IncludeError(
                f"import path must be relative, got absolute \"{rel}\"", lineno)
        target = (base / rel_path).resolve()
        if target in _stack:
            chain = " -> ".join(p.name for p in (*_stack, target))
            raise IncludeError(f"cyclic import: {chain}", lineno)
        if not target.is_file():
            raise IncludeError(f"import not found: \"{rel}\" ({target})", lineno)
        actual = hashlib.sha256(target.read_bytes()).hexdigest()
        if actual != sha:
            raise IncludeError(
                f"import hash mismatch for \"{rel}\": declared sha256:{sha}, "
                f"actual sha256:{actual}", lineno)
        if target in seen:
            if seen[target] != sha:                 # same path, two pins
                raise IncludeError(
                    f"import \"{rel}\" pinned to two different hashes", lineno)
            continue                                # diamond: include once
        seen[target] = sha
        inner = resolve_includes(
            target.read_text(), target.parent,
            _stack=(*_stack, target), _seen=seen)
        def_blocks.append(inner.source.strip("\n"))
        manifest.append({"path": rel, "sha256": sha, "resolved": str(target)})
        manifest.extend(inner.imports)

    # collision check across all imported definitions + the body's own defs
    names: dict[str, str] = {}
    for block in def_blocks:
        for name in _def_names(block):
            if name in names:
                raise IncludeError(
                    f"duplicate definition '{name}' across imports")
            names[name] = "import"
    for name in _def_names(body):
        if name in names:
            raise IncludeError(
                f"definition '{name}' collides with an imported definition")

    if not def_blocks:
        return ResolveResult(body, manifest)

    injected = "\n".join("  " + ln if ln.strip() else ln
                         for block in def_blocks for ln in block.splitlines())

    if _ASSET_OPEN_RE.search(body):
        # `.af` with assets: motif/bus are asset-scoped, so inline the imported
        # definitions just inside each asset's opening brace.
        resolved = _ASSET_OPEN_RE.sub(
            lambda mm: mm.group(1) + "\n" + injected, body)
    else:
        # `.afi` fragment (no asset): prepend the (nested) imported defs to the
        # fragment's own definitions, returning a flat definition body.
        resolved = injected + "\n" + body
    return ResolveResult(resolved, manifest)


def has_imports(source: str) -> bool:
    return any(_IMPORT_RE.match(ln) for ln in source.splitlines())
