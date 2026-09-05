---
disclaimer:
  notice: >-
    No information within this document should be taken for granted. Any statement
    or premise not backed by a real logical definition or verifiable reference may
    be invalid, erroneous, or a hallucination.
  generated_by: "Claude Fable 5.1 via Claude Code"
  date: "2026-09-05"
---

# ADR-0008: Every diagnostic carries a machine-readable code

- **Status:** Accepted (engine 3.0.0, branch `release/engine-3.0.0`)
- **Date:** 2026-09-05

## Context

`DSL_GAP_SPEC.md` §3.3 requires structured diagnostics and PURPOSE.md requires
failures to be loud and local, yet `Diagnostic(severity, message, path)` had no code
field: the code lived inside the message text (`"h: ambiguous_harmony: layer …"`,
`"loop_boundary_tail: …"`), the capability manifest listed 29 codes while the engine
emitted at least 38, and an agent choosing a repair had to substring-match prose.
The consumption model in AI-CORE.md makes agents the primary reader of diagnostics.
Adding a field to the agent-tools and MCP envelopes is a public-surface change, so the
AF-R12 adoption rule requires this record (decision D1 in `docs/evolution/report.md`).

## Decision

`Diagnostic` gains `code: str | None`. When a producer knows the code it passes it;
otherwise `__post_init__` infers it as the first registered `code:` token in the
message (asset-id prefixes and field paths are skipped). A code is valid only if it is
a key of `capability_manifest()["diagnostic_codes"]`, which now registers the harmony,
loop-safety and analysis families next to the plan and expressive ones; `tests/
test_diagnostic_codes.py` asserts that every emitted family is registered. The
agent-tools envelope (`audioforge.agent-tools/1`) and the MCP pass-through always
carry `code` (registered or `null`); the envelope schema version does not change
because the field is additive. Render-plan diagnostics pass their existing `code` and
`path` through unchanged. This ships in 3.0.0 rather than a later minor because 3.0.0
already changes hashes and audio, so it is the cheapest moment to add a surface field.

## Consequences

Agents branch on `code`, not on message text; new codes cannot be emitted without a
manifest entry (`make manifest-check` regenerates `docs/DIAGNOSTIC_CODES.md`);
messages keep their human-readable `code:` prefix so logs stay greppable. Inference is
a transitional mechanism: producers should pass explicit codes, and a future change
may make the inference a test-only check. Validation errors raised as `SpecError`
carry a code only when their message starts with a registered token; field-path
errors (`spec.layers[0]…`) intentionally carry `null`. Harness: `HARNESS-CON-001`,
`HARNESS-CON-002`.
