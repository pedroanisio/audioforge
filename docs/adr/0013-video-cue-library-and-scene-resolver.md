---
disclaimer:
  notice: >-
    No information within this document should be taken for granted. Any statement
    or premise not backed by a real logical definition or verifiable reference may
    be invalid, erroneous, or a hallucination.
  generated_by: "Claude Opus 5.5 via Claude Code"
  date: "2026-09-28"
---

# ADR-0013: Prebuilt cue library and the scene-render resolver

- **Status:** Accepted
- **Date:** 2026-09-28

## Context
Our videos are rendered from `scene-render 1.1` documents by four engines (Python,
Rust, C, JS). Each production so far hand-made its music beds, stings and sound effects
with one-off scripts or placeholder files. The scene format already reserves a
deterministic hook for provider-made media: a `<generated kind="music|sound-effect">`
asset whose `@cache` the renderer reads only after checking `@cacheSha256`, with a
separate "resolve" step expected to fill the cache. No resolver existed.

## Decision
We will ship a library of parameterized cues (`audioforge.cues`: music beds, stings,
transitions, UI, foley, ambience) that compile to ordinary `.af` source, and a resolver
(`audioforge.scene`) for `provider="audioforge"` generated assets. The public surface is
two CLI verbs — `cue` (`list`, `show`, `dsl`, `render`, `gallery`) and `scene`
(`resolve`, `add`) — plus the `cues` section of the capability manifest. Contracts:

- `@model` is a cue id, `@prompt` holds `name=value` parameters, `@seed` is the
  performance seed; `duration=auto` sizes beds and ambiences to the project from the
  playing `audioTrack`'s start.
- The resolver writes only the cache file, its provenance sidecar and the
  `cacheSha256` attribute (in place, preserving the document text).
- Cues are delivered at a fixed loudness per category (beds −18 LUFS, stings −16 LUFS,
  ambience −30 LUFS, effects peak −3 dBFS).
- A cue's `version` changes whenever its composition does; the resolver re-renders when
  the cue version, parameters, format or engine version differ from the sidecar.

## Consequences
Any scene engine gets AudioForge audio with no engine changes, and scenes stay
reproducible: the hash in the document pins the exact bytes. `scene resolve --check`
(exit 3 when stale) is the CI gate; it matters because the Python engine mutes, rather
than fails on, a generated cache that fails its hash check. Cue sounds are synthesized
and their fitness for a mood is a listening judgment (`cue gallery`). Enforced by
`tests/test_cues.py` (registry, compile ranges, loudness/duration contract,
reproducibility), `tests/test_scene.py` (resolve, incrementality, check, add, CLI),
`tests/test_manifest_registry_coverage.py` and the CLI doc gates.
