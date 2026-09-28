#!/usr/bin/env python3
"""Full drift inspection of the AudioForge codebase.

"Drift" = a single-source-of-truth registry going out of sync with one of its
consumers, so a spec can validate but not render (or render but be undocumented).
The schema names the discipline directly: NATIVE_OSC_SHAPES (schema), the
dispatch in synth.osc(), and the binding in _native.py "can't drift apart."

This checks, programmatically:
  · oscillators  — schema OSC_SHAPES vs synth.osc() dispatch vs capabilities
                   vs DSL_SPEC; native ones vs _native wrappers vs native/*.c
  · effects      — schema FX_TYPES vs fx.py dispatch vs capabilities vs docs;
                   native ones vs wrappers/kernels
  · native       — every native/*.c has a wrapper and a registry entry
  · chords       — theory.CHORD_QUALITIES vs DSL_SPEC
  · versions     — DSL_VERSION (code) vs DSL_SPEC header

Exit 0 = no drift; 1 = drift found.
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from audioforge import schema, theory          # noqa: E402
from audioforge.capabilities import capability_manifest  # noqa: E402
from audioforge.dsl import DSL_VERSION          # noqa: E402

A = os.path.join(ROOT, "audioforge")
findings = []   # (severity, area, message)


def _src(name):
    return open(os.path.join(A, name), encoding="utf-8").read()


def _spec_text():
    return open(os.path.join(ROOT, "docs", "DSL_SPEC.md"), encoding="utf-8").read()


def drift(area, msg):
    findings.append(("DRIFT", area, msg))


def note(area, msg):
    findings.append(("note", area, msg))


# ----------------------------------------------------------- oscillators ----
cm = capability_manifest()
synth = _src("synth.py")
native = _src("_native.py")
spec = _spec_text()
native_c = {f[:-2] for f in os.listdir(os.path.join(A, "native")) if f.endswith(".c")}

def _dispatched(src, var):
    """Names a render dispatch handles, via `var == "x"` OR `var in ("x","y")`."""
    out = set(re.findall(rf'{var} == "(\w+)"', src))
    for grp in re.findall(rf'{var} in \(([^)]*)\)', src):
        out |= set(re.findall(r'"(\w+)"', grp))
    return out


osc_dispatch = _dispatched(synth, "shape")
native_wrappers = set(re.findall(r"def (\w+)_native\(", native))
cap_osc = set(cm["oscillators"])

for s in sorted(schema.OSC_SHAPES):
    if s not in osc_dispatch:
        drift("oscillator", f"'{s}' in schema.OSC_SHAPES but NOT dispatched in "
              f"synth.osc() — validates, fails/falls back at render")
    if s not in cap_osc:
        drift("oscillator", f"'{s}' in schema.OSC_SHAPES but missing from "
              f"capabilities manifest")
    if not re.search(rf"\b{re.escape(s)}\b", spec):
        note("oscillator", f"'{s}' not documented in DSL_SPEC.md")
for s in sorted(cap_osc - schema.OSC_SHAPES):
    # plugin oscillators are legitimately outside the built-in set
    from audioforge.plugins import OSCILLATORS
    if s not in OSCILLATORS:
        drift("oscillator", f"'{s}' in capabilities but not schema.OSC_SHAPES "
              f"or plugins")

for s in sorted(schema.NATIVE_OSC_SHAPES):
    if s not in native_wrappers:
        drift("native-osc", f"'{s}' in NATIVE_OSC_SHAPES but no {s}_native() "
              f"wrapper in _native.py")
    if s not in native_c:
        drift("native-osc", f"'{s}' in NATIVE_OSC_SHAPES but no native/{s}.c")
    if s not in schema.OSC_SHAPES:
        drift("native-osc", f"'{s}' in NATIVE_OSC_SHAPES but not OSC_SHAPES")


# ---------------------------------------------------------------- effects ---
fx = _src("fx.py")
fx_dispatch = _dispatched(fx, "kind")
cap_fx = set(cm["fx"])

for t in sorted(schema.FX_TYPES):
    if t not in fx_dispatch:
        drift("effect", f"'{t}' in schema.FX_TYPES but NOT dispatched in "
              f"fx.apply_fx_chain()")
    if t not in cap_fx:
        drift("effect", f"'{t}' in schema.FX_TYPES but missing from capabilities")

for t in sorted(schema.NATIVE_FX_TYPES):
    if not re.search(rf"def {re.escape(t)}_native\(", native):
        drift("native-fx", f"'{t}' in NATIVE_FX_TYPES but no {t}_native() "
              f"wrapper in _native.py")
    if t not in native_c:
        drift("native-fx", f"'{t}' in NATIVE_FX_TYPES but no native/{t}.c")
    if not schema.fx_needs_native({"type": t}):
        drift("native-fx", f"fx_needs_native() returns False for native '{t}'")


# ---------------------------------------------------- native kernels (.c) ---
KNOWN_NONREGISTRY = {"plate_mod"}   # plate's modulated path, gated by mod>0
from audioforge._native import ENGINE_KERNELS   # engine infrastructure kernels
for c, wrappers in sorted(ENGINE_KERNELS.items()):
    if c not in native_c:
        drift("native", f"ENGINE_KERNELS lists '{c}' but no native/{c}.c")
    for w in wrappers:
        if not re.search(rf"^def {re.escape(w)}\(", native, re.M):
            drift("native", f"ENGINE_KERNELS['{c}'] names {w}() but _native.py "
                  f"defines no such wrapper")
for c in sorted(native_c):
    if c in KNOWN_NONREGISTRY or c in ENGINE_KERNELS:
        continue
    if c not in schema.NATIVE_OSC_SHAPES and c not in schema.NATIVE_FX_TYPES:
        drift("native", f"native/{c}.c exists but '{c}' is in no NATIVE_* set")
    if not re.search(rf"def {re.escape(c)}_native\(", native):
        drift("native", f"native/{c}.c exists but no {c}_native() wrapper")


# ---------------------------------------------------------------- chords ----
qm = re.search(r"[Qq]ualities:\s*`([^`]+)`", spec)
doc_chords = set(qm.group(1).split()) if qm else set()
for q in sorted(set(theory.CHORD_QUALITIES) - doc_chords):
    note("chord", f"quality '{q}' not in DSL_SPEC.md Qualities list")


# -------------------------------------------------------------- versions ----
m = re.search(r"\*\*DSL ([0-9.]+)", spec)
spec_ver = m.group(1) if m else "?"
if spec_ver != DSL_VERSION:
    drift("version", f"DSL_SPEC.md header says DSL {spec_ver} but code "
          f"DSL_VERSION = {DSL_VERSION}")


# ---------------------------------------------------------------- report ----
def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(
        description="Cross-check runtime registries against their consumers "
                    "(AF-R13, `make drift-check`). Exit 1 on drift, 0 if clean.",
    )
    parser.add_argument("--check", action="store_true",
                        help="gate mode (the default behaviour): exit non-zero on drift")
    parser.parse_args(argv)
    drifts = [f for f in findings if f[0] == "DRIFT"]
    notes = [f for f in findings if f[0] == "note"]
    print("=" * 68)
    print(" AudioForge drift inspection")
    print("=" * 68)
    print(f"\nregistries cross-checked: oscillators({len(schema.OSC_SHAPES)}) "
          f"fx({len(schema.FX_TYPES)}) native({len(native_c)}) "
          f"chords({len(theory.CHORD_QUALITIES)})")
    if drifts:
        print(f"\n⚠ {len(drifts)} DRIFT(S):")
        for _, area, msg in drifts:
            print(f"  [{area}] {msg}")
    else:
        print("\n✓ no registry drift — every source of truth matches its consumers")
    if notes:
        print(f"\n{len(notes)} advisory note(s) (docs lag, not render-breaking):")
        for _, area, msg in notes:
            print(f"  [{area}] {msg}")
    return 1 if drifts else 0


if __name__ == "__main__":
    sys.exit(main())
