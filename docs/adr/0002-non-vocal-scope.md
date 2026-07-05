---
disclaimer:
  notice: >-
    No information within this document should be taken for granted. Any statement
    or premise not backed by a real logical definition or verifiable reference may
    be invalid, erroneous, or a hallucination.
  generated_by: "Claude Opus 4.8 via Claude Code"
  date: "2026-07-05"
---

# ADR-0002: Non-vocal by design

- **Status:** Accepted (records `PURPOSE.md`)
- **Date:** 2026-07-05

## Context
The generative-audio space includes voice/speech synthesis, which carries distinct
ethical, legal, and quality concerns and a different engineering surface.

## Decision
AudioForge optimizes for music, sound design, effects, ambience, loops, cues, and
sonic branding. It does **not** generate vocals, speech, lyrics, or performer
likenesses.

## Consequences
The roadmap and capability surface exclude voice models. Recorded material (incl.
vocals a user supplies) enters only as a content-addressed sample layer, hashed
into the spec — the engine never *generates* a voice.
