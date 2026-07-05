---
disclaimer:
  notice: >-
    No information within this document should be taken for granted. Any statement
    or premise not backed by a real logical definition or verifiable reference may
    be invalid, erroneous, or a hallucination.
  generated_by: "Claude Opus 4.8 via Claude Code"
  date: "2026-07-05"
---

# ADR-0005: One IR source of truth — derive, gate; defer the typed model (AF-R08)

- **Status:** Accepted (Phase A); **Phase B deferred to the operator**
- **Date:** 2026-07-05

## Context
The IR contract lives in `audioforge/schema.py` (the `KINDS`/`LAYER_TYPES`/
`OSC_SHAPES`/`FX_TYPES`/`AUTO_TARGETS`/... registries + the imperative
`validate_spec`) and `audioforge/ir_schema.py` (the JSON Schema built in code +
`validate_ir_schema`). The roadmap (AF-R08) flags a HIGH-severity risk of the two
"encoding the same facts twice." In practice `ir_schema.py` already **derives** its
enums from `schema.py` (`_string_enum(sorted(REGISTRY))`), but (a) one literal —
the filter modes `{lowpass, highpass, bandpass}` — was stated in both files, and
(b) nothing *gated* the derivation, so a future hardcoded enum could silently
re-introduce drift.

## Decision
`schema.py`'s registries are the **single source of truth** for IR enums.
**Phase A (done):** extract `FILTER_MODES` as a `schema.py` registry (both
`validate_spec` and `ir_json_schema` consume it), and add
`tests/test_schema_sources_sync.py` asserting every generated JSON-Schema enum
equals its `schema.py` registry — converting the derivation into a gated invariant.
**Phase B (deferred):** replacing the dual layer with a single *typed* model
(Pydantic v2 `model_json_schema()` + validation) is **not** taken now. It is an
L-effort refactor that adds a runtime dependency and rewrites `validate_spec`; the
current approach is not broken. Revisit only on operator sign-off.

## Consequences
The dual-source *enum* coupling is closed and gated (no hand-sync). The two
*validators* remain by design — `validate_spec` does semantic/binding checks a JSON
Schema cannot express, `validate_ir_schema` does the structural check — they are
layers, not duplicates. If the hand-authored JSON-Schema *structure* becomes a
maintenance burden, reopen Phase B.
