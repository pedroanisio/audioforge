---
disclaimer:
  notice: >-
    No information within this document should be taken for granted. Any statement
    or premise not backed by a real logical definition or verifiable reference may
    be invalid, erroneous, or a hallucination.
  generated_by: "Claude Opus 4.8 via Claude Code"
  date: "2026-07-05"
---

# ADR-0003: The IR is truth; the DSL is sugar

- **Status:** Accepted (records existing practice)
- **Date:** 2026-07-05

## Context
Agents and reviewers need to read exactly what will render, not guess how
expressive authoring shorthand expands.

## Decision
The `.af` DSL is sugar; the JSON IR is the render contract. Emotion tags, intensity
curves, motifs, chord symbols, and key expand at **compile time** into explicit IR
parameters. The IR is the hashed ground truth (ADR-0001).

## Consequences
`audioforge compile` exposes the full IR for inspection; mutation and verification
operate on the IR. Two IR-facing artifacts derive from the same source registries
(ADR-0005).
