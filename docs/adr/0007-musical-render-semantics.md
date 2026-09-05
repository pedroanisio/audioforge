---
disclaimer:
  notice: >-
    No information within this document should be taken for granted. Decisions
    below require verification against code and acceptance tests.
  generated_by: "GPT-6 via Codex"
  date: "2026-09-05"
---

# ADR-0007: Faithful musical instructions and stable performance identity

- **Status:** Accepted and implemented
- **Date:** 2026-09-05

## Context

The September review reproduced doubled instrument gain, inconsistent note-off
semantics, aliased sample transposition, implicit peak normalization, inert score
repeats and unrelated performance changes during mix edits. It also found
musical heuristics whose labels exceeded the evidence available to them.

## Decision

Musical instructions must lower to inspectable render data. Performance identity
is explicit and separate from the content hash of the complete output contract.
Mix edits preserve a performance; intentional variation changes its declared seed.
Notes hold until note-off and then release. Gain is applied once. Sample-rate
conversion filters frequencies that would alias at the playback rate. Mastering
preserves authored levels by default and applies a ceiling; peak normalization
requires an explicit request, while an explicit LUFS target requests loudness
normalization. Harmony, phrase, technique and quality decisions must retain their
evidence and report ambiguity or approximation rather than claim unsupported
musical meaning.

## Consequences

These corrections intentionally change audio and some authoring semantics.
The release must update engine/DSL/IR contracts, migration documentation and
generated goldens together. Previous hashes are not evidence for the corrected
sound. The complete acceptance ledger is `docs/MUSICAL_CORRECTNESS.md`.

Validation has separate responsibilities: schema/resource validation establishes
renderability, numerical and musical fixtures establish specified behavior,
golden hashes establish reproducibility, and actual listening reviews establish
the reported subjective judgments. No one layer substitutes for the others.


## Implementation and validation

Engine 3.0.0 / DSL 2.0 / IR 2.0 implement these decisions. Repeat expansion
validates its resulting contract, consumes executable repeats, and preserves
curve functions through explicit input-clock mapping. Shared scheduling drives
both sample plans and runtime players. Fidelity comes from the technique
registry; strict routes reject approximations. Default readiness validation
also measures loop seams and tails.

The composed local gate, coverage result and seven before/after numerical
cases are recorded in [the acceptance ledger](../MUSICAL_CORRECTNESS.md).
See [the migration guide](../MIGRATION_3.md) before re-rendering older specs.
Listening forms remain unreviewed; this ADR does not claim subjective ratings.
