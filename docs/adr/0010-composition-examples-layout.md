---
disclaimer:
  notice: >-
    This record describes repository organization; executable checks establish
    source coverage and path consistency.
  generated_by: "Codex"
  date: "2026-09-06"
---

# ADR-0010: Composition examples travel with their documentation and local renders

**Status:** Accepted (2026-09-06)

## Context

Scores were scattered across `compositions/` and `static/fixtures/`; audio and
manifests lived under `renders/`, beside fixtures, or inside composition folders.
Broad ignore rules concealed most scores from source control. Relative paths in
generators, delivery validators and tests depended on those locations.

## Decision

`docs/examples/<collection>/<example>/` is the canonical composition location.
Each directory holds its named `.af` source, generated `index.md`, supporting
authoring scripts when present, and local `audio/` artifacts. Source filenames
and asset IDs are preserved. New renders use `audio/current/`, keeping earlier
recordings and their manifests intact.

`docs/examples/catalog.json` owns example identity, classification and recorded
compile expectations. `scripts/examples.py docs` owns the Markdown indexes;
`gallery` generates the local listening page; `check` detects missing scores,
unexpected compile behavior and documentation drift. `render` records every
selected result, including errors, without running composition generators.

Audio, large derived IR, detailed historical evidence and the local gallery are
gitignored. Source code, DSL, catalog and documentation are trackable. WAVs are
never committed. A source-only checkout can validate the catalog and generate
the gallery before audio or external libraries are installed.

Historical invalid scores remain explicitly classified and continue serving
their diagnostic tests. Focused acceptance/rejection fixtures remain in their
existing fixture directories. Python integration recipes remain in `examples/`.

## Consequences

Tests and generators use the canonical paths. The relocation manifest records
old/new file locations and hashes, including preserved audio bytes. Historical
evidence is retained verbatim; its original paths describe the prior delivery.

The documentation navigation and home page link to the example index. The normal
site build includes available MP3 previews and excludes WAV masters, stems and
Python caches. This does not change
the engine, DSL, IR contract or render identity. A local render's presence is
not evidence that an earlier engine's output matches the current engine.
