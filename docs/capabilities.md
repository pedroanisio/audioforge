---
disclaimer:
  notice: >-
    No information within this document should be taken for granted. Any statement
    or premise not backed by a real logical definition or verifiable reference may
    be invalid, erroneous, or a hallucination.
  generated_by: "audioforge.tools.gen_docs"
  date: "2026-07-05"
---

<!-- GENERATED — do not hand-edit. Run `python -m audioforge.tools.gen_docs --write`. -->


# Capabilities

Machine-readable surface of AudioForge **engine 3.3.1 · DSL 2.0**, generated from `docs/capability-manifest.json` (itself generated from `audioforge/capabilities.py`).

| Group | Count |
|-------|------:|
| kinds | 8 |
| layer types | 10 |
| oscillators | 15 |
| fx | 26 |
| articulations | 8 |
| grooves | 6 |
| style packs | 12 |
| automation targets | 5 |
| diagnostic codes | 54 |

## Per-capability status

Status is derived by predicate (AF-R07; ADR-0004, ADR-0012): `stable` = rendered by the core engine kernels; `experimental` = also needs a dedicated physical-model or effect kernel. Every render requires a C compiler since engine 3.2.

**Experimental oscillators:** `blown`, `bowed`, `brass`, `struck`, `sympathetic`.

Every diagnostic code is documented in [`DIAGNOSTIC_CODES.md`](DIAGNOSTIC_CODES.md).

