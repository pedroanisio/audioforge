---
disclaimer:
  notice: >-
    No information within this document should be taken for granted. Any statement
    or premise not backed by a real logical definition or verifiable reference may
    be invalid, erroneous, or a hallucination.
  generated_by: "Claude Opus 4.8 via Claude Code"
  date: "2026-07-05"
---

# ADR-0006: Every generated artifact has a generator and a `--check` twin

- **Status:** Accepted
- **Date:** 2026-07-05

## Context
Committed files derived from the engine (the JSON Schema, the capability manifest,
the diagnostic-codes doc, the golden audio lock) silently rot if a human
regenerates them by hand or forgets to.

## Decision
Every committed derived artifact is **owned by a generator** with a write mode
(`--write`/`--update`) and a **`--check` twin** wired into `make check` (which CI
runs). Never hand-edit generated output — edit the source and rerun the generator.

## Consequences
Drift is a loud gate failure, not a latent inconsistency. Instantiated by
`gen_ir_schema` → `docs/ir.schema.json` (AF-R05), `gen_capability` →
`docs/capability-manifest.json` + `docs/DIAGNOSTIC_CODES.md` (AF-R07),
`render_golden` → `tests/golden/audio.lock.json` (AF-R06), and `gen_docs` → the
docs-site reference pages (AF-R11).
