"""Resource binding ("resolve") — the pass that makes `validate` mean
"this will render" (v2.14, from the 2026-06-10 external review, P0).

`schema.validate_spec` is structural: it checks the *shape* of resource
references. This module performs the binding that rendering would perform —
libraries located and manifest-verified, instruments and articulations
resolved, sample/IR files found and hash-checked, native kernels available —
and reports every failure as a structured diagnostic string carrying the
layer path and, when the compiler provided a line sidecar (`spec["_meta"]
["lines"]`), the DSL source line.

Placeholder pins (a 64-hex value that is one repeated character, e.g. the
all-zeros pin) get a distinct message: they are unbound placeholders, not
real-but-missing assets.

resolve_spec() never raises for resource problems — it returns the list.
Render refuses with the same list, so a raw resource traceback can no
longer escape the documented agent loop.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

_PLACEHOLDER_RE = re.compile(r"^(.)\1{63}$")


def _line_of(spec: dict, layer_name: str) -> str:
    lines = spec.get("_meta", {}).get("lines", {})
    ln = lines.get(layer_name)
    return f" (line {ln})" if ln else ""


def _is_placeholder(sha: str) -> bool:
    return bool(_PLACEHOLDER_RE.match(sha.lower()))


def _check_pin(name: str, sha: str, what: str, where: str) -> str | None:
    if _is_placeholder(sha):
        return (f"{where}: {what} '{name}@{sha[:8]}…' is an unbound "
                f"placeholder pin — substitute the real content hash "
                f"(generate one with `audioforge libgen` for libraries, or "
                f"sha256 of the file for samples/IRs)")
    return None


def resolve_spec(spec: dict) -> list[str]:
    """Bind every external resource the render would touch; return a list
    of diagnostic strings (empty = render-ready, resource-wise)."""
    problems: list[str] = []

    # ---- library + instruments + articulations ----------------------------
    lib_ref = spec.get("library")
    lib = None
    if lib_ref:
        name = lib_ref["name"]
        sha = lib_ref["manifest_sha256"]
        p = _check_pin(name, sha, "library pin", "spec.library")
        if p:
            problems.append(p)
        else:
            from .library import load_library
            try:
                lib = load_library(lib_ref)
            except Exception as e:
                problems.append(f"spec.library: {e}")
    for i, layer in enumerate(spec.get("layers", [])):
        lname = layer.get("name", f"layer{i}")
        where = f"layers[{i}] '{lname}'{_line_of(spec, lname)}"
        if layer.get("type") != "instrument":
            continue
        if lib_ref is None:
            problems.append(f"{where}: instrument layer needs a spec-level "
                            f"library: pin")
            continue
        if lib is None:
            continue                      # library problem already reported
        inst = layer.get("instrument")
        if inst not in lib.manifest.get("instruments", {}):
            problems.append(
                f"{where}: instrument '{inst}' is not in library "
                f"'{lib.manifest['name']}' (available: "
                f"{sorted(lib.manifest.get('instruments', {}))})")
            continue
        from .sampler import resolve_articulation
        arts = {layer.get("articulation", "sustain")}
        arts |= {ev["art"] for ev in layer.get("notes", []) if "art" in ev}
        for art in sorted(arts):
            if art == "trill":
                continue                  # compiles away
            try:
                regions, _, _ = resolve_articulation(lib, inst, art)
            except ValueError as e:
                problems.append(f"{where}: {e}")
                continue
            for r in regions:             # cheap stat per referenced file
                if not (lib.root / r.sample).exists():
                    problems.append(
                        f"{where}: library sample file missing on disk: "
                        f"{r.sample}")
                    break

    # ---- samples, convolve IRs, stage hall --------------------------------
    from .samples import _find_bytes

    def check_file(name: str, sha: str, what: str, where: str):
        p = _check_pin(name, sha, what, where)
        if p:
            problems.append(p)
            return
        try:
            data = _find_bytes(name)
        except Exception as e:
            problems.append(f"{where}: {what} '{name}': {e}")
            return
        actual = hashlib.sha256(data).hexdigest()
        if actual != sha.lower():
            problems.append(
                f"{where}: {what} '{name}' content hash mismatch — spec "
                f"pins {sha[:16]}…, file on disk is {actual[:16]}…")

    stg = spec.get("stage")
    if stg:
        check_file(stg["hall_file"], stg["hall_sha256"], "stage hall IR",
                   "spec.stage")

    from ._native import native_available
    from .schema import NATIVE_OSC_SHAPES, fx_needs_native
    have_native = native_available()

    def _native_gap(needs: bool, what: str, where: str):
        if needs and not have_native:
            problems.append(
                f"{where}: '{what}' needs the native kernel and no C "
                f"compiler is available on this machine")

    for i, layer in enumerate(spec.get("layers", [])):
        lname = layer.get("name", f"layer{i}")
        where = f"layers[{i}] '{lname}'{_line_of(spec, lname)}"
        if layer.get("type") == "sample":
            check_file(layer["file"], layer["sha256"], "sample", where)
        for fx in (layer.get("fx") or []):
            if fx.get("type") == "convolve":
                check_file(fx["file"], fx["sha256"], "convolve IR", where)
            _native_gap(fx_needs_native(fx), fx.get("type", ""), where)
        voice = layer.get("osc") or layer.get("voice")
        if voice in NATIVE_OSC_SHAPES:
            _native_gap(True, voice, where)
    for fx in (spec.get("master", {}).get("fx") or []):
        if fx.get("type") == "convolve":
            check_file(fx["file"], fx["sha256"], "convolve IR",
                       "spec.master")
        _native_gap(fx_needs_native(fx), fx.get("type", ""), "spec.master")
    return problems
