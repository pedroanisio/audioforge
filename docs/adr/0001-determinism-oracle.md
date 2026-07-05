---
disclaimer:
  notice: >-
    No information within this document should be taken for granted. Any statement
    or premise not backed by a real logical definition or verifiable reference may
    be invalid, erroneous, or a hallucination.
  generated_by: "Claude Opus 4.8 via Claude Code"
  date: "2026-07-05"
---

# ADR-0001: SHA-256 re-render is the reproducibility oracle

- **Status:** Accepted (records existing practice)
- **Date:** 2026-07-05

## Context
`PURPOSE.md` makes reproducibility a product feature: an output is not complete
unless it can be recreated and verified from its source. AudioForge is
synthesis-only and seed-deterministic.

## Decision
The reproducibility contract is a SHA-256 hash. `spec_hash` = SHA-256 over
`ENGINE_VERSION + canonical_json(spec)` (excluding `_meta`/`intent`/`notation`);
every render manifest records `output_sha256`; `audioforge verify` re-renders and
compares bytes. All randomness derives from per-component seeds rooted in the spec
hash — no wall clocks, no global RNG. A committed golden corpus lock
(`tests/golden/audio.lock.json`, AF-R06) gates a small corpus.

## Consequences
Determinism is guaranteed *within one numeric environment*; cross-environment
float reproducibility is *checked* (the golden gate is env-aware: strict same-env,
advisory cross-env) rather than assumed — closing that gap loudly is AF-R16.
