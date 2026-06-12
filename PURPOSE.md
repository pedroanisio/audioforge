---
disclaimer:
  notice: >-
    No information within this document should be taken for granted.
    Any statement or premise not backed by a real logical definition
    or verifiable reference may be invalid, erroneous, or a hallucination.
  generated_by: "GPT-5 Codex via Codex"
  date: "2026-06-11"
---

# AudioForge

## Why We Built This

We believe production audio should not depend on fragile memory, hidden
settings, or one-off manual sessions that no one can truly repeat.

Creative teams need music, cues, transitions, ambience, and sound design that
can evolve without losing trust. When an asset changes, they should know what
changed, why it changed, and whether the new result still matches the original
intent. Reproducing yesterday's sound should be a promise, not a negotiation.

AudioForge exists to make generated audio accountable: expressive enough for
real creative work, explicit enough for review, and repeatable enough for
production pipelines.

---

## How We Approach This

- **Reproducibility is a product feature** — An output is not complete unless it can be recreated and verified from its source.
- **The contract must be inspectable** — Creative intent is allowed, but it must turn into explicit data that people and agents can review.
- **Controlled variation beats accidental drift** — Variation should be declared and traceable, never leaked from clocks, hidden randomness, or hidden tool state.
- **Failure should be loud and local** — Missing resources, ambiguous input, and unsupported behavior should produce clear error reports instead of surprising audio.
- **Scope stays non-vocal by design** — The project optimizes for music, sound design, effects, ambience, loops, cues, and sonic branding rather than voice generation.

---

## What It Does

### Core Capabilities

- Compiles `.af` source into a JSON intermediate representation that serves as the render contract.
- Renders deterministic WAV assets, stems, manifests, markers, cutdowns, variants, and export presets.
- Provides a Python SDK and CLI for validation, compilation, rendering, batch generation, mutation, preview, and verification.
- Supports synthesis, sampled instruments, orchestral performance modeling, automation, mixing, loudness targeting, spatial rendering, plugins, and content-addressed audio resources.
- Gives agents an explicit authoring and inspection surface so generated assets can be checked before they enter a production workflow.

### What This Is Not

This project does **not**:

- Generate vocals, speech, lyrics, or performer likenesses.
- Replace human creative direction, taste, or final mastering judgment.
- Promise certified broadcast metering; reference checks still matter where compliance is required.
- Treat undocumented randomness, implicit plugin behavior, or manual session state as acceptable production inputs.

---

## Who This Is For

- **Production teams** — Need repeatable audio assets with manifests, stems, and verification gates.
- **Developers and pipeline engineers** — Need audio generation that behaves like inspectable build output.
- **AI agents and agent builders** — Need a structured surface for authoring, mutating, and validating audio without relying on a human-operated UI.
