# AudioForge DSL Gap Specification

**Date:** 2026-06-11  
**Status:** Current gap document  
**Companion reference:** [DSL_SPEC.md](DSL_SPEC.md)

This document consolidates the previous DSL proposal, north-star, decision, and
universal-architecture notes into one current-state gap specification.

`DSL_SPEC.md` is the implemented language reference. This file records only what
is still a gap over the current codebase, plus the Definition of Ready,
Definition of Done, and required TDD/regression constraints for each gap.

---

## 1. Implemented Baseline

The current codebase already implements the following DSL and agent-facing
capabilities. These are not roadmap gaps unless a gap below names a missing
extension or hardening task.

| Area | Current state |
|------|---------------|
| DSL parser | Single Lark grammar/parser (`audioforge.lark_parser.LARK_GRAMMAR`); `parse_assets` walks its tree straight into the AST. The legacy regex tokenizer and recursive-descent parser were removed (audit finding F9). The Lark-backed parser remains the syntax gate, and the published EBNF/GBNF artifacts (`audioforge grammar`) are derived from it. |
| Current reference spec | `docs/DSL_SPEC.md` documents the implemented `.af` surface. |
| Smart directives | `style:`, `perform:`, `ensemble:`, `voicing:`, and `space:` parse at asset scope and expand into explicit render IR under `audioforge.dsl._apply_smart_directives`. |
| Structured intent | `intent {}` parses into `spec["intent"]["structured"]`, separates render-affecting typed fields from metadata-only fields, and expands deterministic layer/master IR for density, contour, and texture. |
| Style packs | `audioforge.styles` provides deterministic style defaults, listed by `audioforge capabilities`. |
| Agent manifest | `audioforge.capabilities.capability_manifest()` exposes layer types, properties, units, enums, smart directives, score syntax, interop commands, examples, repair hints, and incompatibilities. |
| Score layer | Meter, pickup, form, repeat, and polymeter compile into `spec["score"]`. |
| Audio layer | `audio` compiles to a content-addressed `sample` layer with source-kind metadata and stereo/channel preservation support. |
| Interop | MIDI and MusicXML import/export are available through SDK and CLI. |
| Analysis | `audioforge.analysis.analyze_audio()` emits structured audio features and recommendations; `render --analyze` writes analysis into manifests. |
| Decompile | `audioforge.decompile.spec_to_dsl()` emits a canonical render-equivalent `.af` from IR. |
| Validation | `validate` is render-ready by default and performs resource binding unless `--no-resolve` is supplied. |
| Formal IR schema | `audioforge.ir_schema` publishes `docs/ir.schema.json`, declares semantic/render/provenance field ownership, and validates generated IR conformance. |
| Regression coverage | `tests/test_ai_agent_dsl.py`, `tests/test_universal_music_pillars.py`, `tests/test_docs_regression.py`, and `tests/test_lark_parser.py` cover the implemented agent DSL surface. |

---

## 2. Universal Expression Claim

The defensible current claim is:

> AudioForge already expresses common composed, produced, and hybrid music
> workflows. Its Smart DSL architecture is universal in principle because it
> combines symbolic structure, parametric synthesis, performance semantics,
> production automation, interop, and content-addressed audio. Remaining work is
> coverage, ergonomics, and verification, not a theoretical expressiveness gap.

The stronger claim:

> AudioForge can express all music with a Smart DSL.

is acceptable only when the acceptance criteria in section 5 are met.

---

## 3. Non-Negotiable Constraints

### 3.1 Determinism

Every render-affecting DSL construct must lower to explicit, inspectable IR
before render. Randomness must be seeded from stable paths and expanded into IR.
No hidden model state may affect audio.

### 3.2 The IR Is Truth

The DSL is the authoring surface. The IR is the render contract. Smart syntax,
macros, style packs, and agent intent are allowed only when their output is
explicit and diffable in IR.

### 3.3 Structured Diagnostics

Parse, compile, validate, resolve, import, export, and repair failures must
return structured diagnostics where possible. User-facing tracebacks are defects.

### 3.4 TDD And Regression Tests

All work in this document is gated by tests:

- Add a failing regression test before fixing a reproducible bug.
- Add parser, compiler, validator, and diagnostics tests before landing new DSL
  syntax.
- Add explicit IR snapshot or structural assertions for every new smart
  expansion.
- Add render-readiness or render smoke coverage for every feature that can affect
  audio output.
- Add audio-analysis regression coverage for quality bugs such as harshness,
  noise, clipping, silence, missing low end, or rough melodic contour.
- Update golden hashes/manifests only when the audio change is intentional, and
  document the reason in the change.

---

## 4. Current Gaps

### G1. Version And Source-Of-Truth Hygiene

**Current state**

`audioforge.version` owns the runtime engine/DSL version contract. The CLI,
capability manifest, compiled IR `_meta`, docs, and release notes consume that
same runtime contract, with drift tests locking the documented and exported
versions together.

**Gap**

Closed for G1. `audioforge/version.py` is the single runtime source of truth for
`ENGINE_VERSION`, `DSL_VERSION`, `version_contract()`, and `version_banner()`.
Feature-support declarations are exposed through the capability manifest and
schema artifacts rather than duplicated prose-only claims.

**Definition of Ready**

- Decide which module owns DSL version metadata.
  **Implemented:** `audioforge.version`.
- Define which docs and manifests consume that version.
  **Implemented:** `DSL_SPEC.md`, `docs/RELEASE_NOTES.md`,
  `capability_manifest()`, CLI `--version`, and compile `_meta`.
- Define drift checks for docs, grammar, manifest, and runtime.
  **Implemented:** docs/manifest/CLI/runtime drift checks live in
  `tests/test_docs_regression.py`, `tests/test_ai_agent_dsl.py`, and
  `tests/test_cli.py`.
- List all user-visible version strings that must agree.
  **Implemented:** engine/DSL versions are exported by runtime, CLI, compiled
  IR metadata, and capability manifest.

**Definition of Done**

- `DSL_SPEC.md`, capability manifest, CLI output, and runtime compile metadata
  report consistent DSL version information.
  **Implemented:** all consume `audioforge.version`.
- Tests fail when docs or manifest versions drift from runtime.
  **Implemented:** regression tests compare runtime constants to docs and
  manifest output.
- Release notes or migration notes state when a DSL version changes.
  **Implemented:** `docs/RELEASE_NOTES.md`.

**Required tests**

- Regression test comparing `audioforge.dsl.DSL_VERSION` to documented DSL
  version metadata.
- Capability-manifest test proving the exported version matches runtime.
  **Implemented:** version-hygiene coverage is included in
  `tests/test_docs_regression.py`, `tests/test_ai_agent_dsl.py`, and
  `tests/test_cli.py`.

### G2. Formal Universal Music IR Schema

**Current state**

The engine validates specs through `audioforge.schema` and render-readiness
through resource resolution. The IR now also has a published JSON Schema at
`docs/ir.schema.json`, generated from `audioforge.ir_schema.ir_json_schema()`.
`audioforge.ir_schema.ir_schema_metadata()` declares semantic, expanded render,
and provenance field ownership, hash-exclusion rules, and the additive
migration policy for IR schema `1.0`.

**Gap**

Closed for schema publication and conformance. Future work belongs to the
specific feature gaps that add new semantic or render constructs and must update
the IR schema as part of their own Definition of Done.

**Definition of Ready**

- Choose schema format, for example JSON Schema or a typed Python schema with
  generated JSON Schema.
- Define IR versioning and migration policy.
- Define hash inclusion and exclusion rules.
- Define which fields belong to semantic, render, and provenance layers.
- Identify existing specs that must validate without migration.

**Definition of Done**

- A published schema validates generated IR. **Implemented:** `docs/ir.schema.json`
  plus `validate_ir_schema()`.
- Every current DSL construct maps to schema-defined fields. **Implemented:**
  current top-level semantic, render, provenance, layer, bus, master, score, and
  automation fields are represented in the schema.
- Semantic intent, expanded render data, and provenance have documented
  ownership boundaries. **Implemented:** `docs/IR_SCHEMA.md` and schema
  `x-audioforge.field_layers`.
- Formatting-only source metadata remains excluded from render hashes.
  **Implemented:** `_meta` is declared as provenance and hash-excluded.
- Schema migration tests exist for at least one version boundary. **Implemented:**
  `migrate_ir_spec()` covers the experimental `0.9` to `1.0` provenance
  sidecar migration.

**Required tests**

- Schema-valid and schema-invalid fixtures.
- Generated-spec conformance tests for representative `.af` files.
- Hash stability tests proving non-render metadata does not affect spec hashes.

### G3. Structured `intent {}` Blocks

**Current state**

The DSL has five asset-level smart directives: `style`, `perform`, `ensemble`,
`voicing`, and `space`. They preserve intent under `spec["intent"]` and expand
to explicit render IR. It now also supports `intent {}` blocks with typed
render-affecting fields (`density`, `contour`, `texture`) and metadata-only
fields (`affect`, `avoid`, `repair`, `style_text`).

**Gap**

Closed for G3. `audioforge.dsl.Parser.intent()` accepts the block, rejects
unknown fields, and `audioforge.dsl._apply_structured_intent()` lowers
render-affecting fields to explicit IR while preserving metadata under
`spec["intent"]["structured"]["metadata"]`.

**Definition of Ready**

- Define typed fields and allowed free-text fields.
  **Implemented:** `density`, `contour`, and `texture` are closed enums;
  `affect`, `avoid`, `repair`, and `style_text` are preserved metadata fields.
- Specify which fields affect render expansion and which are metadata-only.
  **Implemented:** render fields expand to layer gain, master automation, and
  master fx; metadata fields are hash-excluded with `intent`.
- Specify conflict handling, for example sparse density with large ensemble size.
  **Implemented:** sparse density with ensemble size greater than 6 and clipping
  avoidance with a hot master peak emit warnings.
- Define grammar changes and manifest representation.
  **Implemented:** published EBNF/GBNF include `intent_block`; capabilities
  expose `intent_blocks`.
- Provide examples for at least three idioms.
  **Implemented:** DSL spec documents sparse/arch/smooth plus repair/noise and
  reference-free style-text examples.

**Definition of Done**

- `intent {}` parses into semantic IR.
  **Implemented:** compiled IR stores `intent.structured`.
- Render-affecting intent expands deterministically into explicit IR.
  **Implemented:** deterministic expansions are recorded in
  `intent.structured.expansions`.
- Metadata-only intent is preserved but cannot silently affect audio.
  **Implemented:** `spec_hash()` excludes top-level `intent`; metadata-only
  fixtures keep identical layer/master IR and render hash.
- Conflicts produce structured diagnostics.
  **Implemented:** compiler diagnostics include `intent conflict: ...` warnings.
- Decompiler behavior is defined: preserve authored intent when available or
  emit a documented canonical equivalent.
  **Implemented:** `spec_to_dsl()` emits `intent {}` when `intent.structured`
  exists, otherwise continues emitting render-equivalent DSL.

**Required tests**

- Parser tests for valid and invalid `intent {}` blocks.
- Compiler tests proving deterministic expansion.
- Diagnostics tests for conflicting fields.
- Regression fixture for an agent repair case such as "make the melody less
  rough" or "remove noise from audio 2".
  **Implemented:** `tests/test_lark_parser.py`,
  `tests/test_ai_agent_dsl.py`, and `tests/test_ir_schema.py` cover these cases.

### G4. Semantic Round-Trip Preservation

**Current state**

The decompiler emits render-equivalent DSL. When a compiled IR carries
`_meta.semantic`, it now preserves authored motifs, `play` statements, explicit
smart directives, structured intent blocks, score sections, buses, automation,
and dynamics.

**Gap**

Closed for G4. Authored semantic constructs are captured in `_meta.semantic`;
missing or unsafe inverse cases are reported by
`audioforge.decompile.decompile_diagnostics()`.

**Definition of Ready**

- Define which semantic constructs must be preserved in IR.
  **Implemented:** `_meta.semantic` records explicit smart directives, motifs,
  layer authored notes/play statements, and master property ownership.
- Define canonical decompile output for preserved semantic constructs.
  **Implemented:** `spec_to_dsl()` emits preserved smart directives, motif
  blocks, `play` statements, score data, buses, automation, dynamics, and
  structured intent.
- Define acceptable lossy cases and diagnostics.
  **Implemented:** missing sidecars and unsafe style-pack inverses decompile to
  canonical render DSL; `decompile_diagnostics()` reports lossy cases.
- Define how semantic and expanded render layers stay synchronized.
  **Implemented:** semantic data is provenance-only and hash-excluded; the
  expanded layer/master IR remains the render contract.

**Definition of Done**

- Decompiler preserves authored semantic constructs where the IR contains them.
  **Implemented:** semantic-preserving decompile uses `_meta.semantic`.
- Lossy decompile cases emit warnings or metadata.
  **Implemented:** `decompile_diagnostics()` returns lossy warnings.
- Recompiled decompiled DSL is render-equivalent.
  **Implemented:** regression tests compare round-tripped spec hashes.
- Semantic-preserving round-trip tests pass for smart directives, motifs, score
  sections, buses, automation, and dynamics.
  **Implemented:** `tests/test_ai_agent_dsl.py` covers this fixture.

**Required tests**

- `DSL -> IR -> DSL -> IR` tests for semantic-preserved fixtures.
- Lossy-case tests proving warnings are emitted.
- Render hash or manifest equivalence tests for round-tripped assets.
  **Implemented:** `tests/test_ai_agent_dsl.py` includes all three.

### G5. Library-Aware Orchestration

**Current state**

`ensemble:` can add unison/spread/octave behavior and role routing. Instrument
layers require a library pin, and validation resolves instruments and
articulations.

**Gap**

Closed for G5. `audioforge.catalog.DEFAULT_INSTRUMENT_CAPABILITIES` provides a
machine-readable range/technique catalog and `validate_spec()` enforces hard
ranges plus articulation availability before render.

**Definition of Ready**

- Machine-readable instrument range and technique catalog exists.
  **Implemented:** default violin/cello/flute capability entries include hard
  range, comfort range, articulations, and divisi policy.
- Articulation compatibility rules are defined.
  **Implemented:** instrument layers with `orchestration.articulations` reject
  unavailable techniques.
- Register comfort and hard range policies are defined.
  **Implemented:** hard range validation fails render readiness; comfort range
  is explicit metadata for orchestration choices.
- Missing library/instrument/articulation diagnostics are specified.
  **Implemented:** existing library/instrument checks remain, and unsuitable
  technique/range checks raise structured `SpecError` paths.
- Example orchestration targets are selected.
  **Implemented:** violin/cello/flute are the first catalog targets.

**Definition of Done**

- Generated orchestration obeys hard ranges and articulation availability.
  **Implemented:** validation rejects notes outside hard range and unavailable
  articulations.
- Register or technique issues are caught before render.
  **Implemented:** checks live in `audioforge.schema.validate_spec()`.
- Library-aware choices are explicit in IR.
  **Implemented:** layers may carry an `orchestration` capability object.
- Missing or unsuitable resources fail validation with structured diagnostics.
  **Implemented:** tests assert hard-range and technique failures.
- Existing library-pinned instrument fixtures still render.
  **Implemented:** existing suite coverage remains active.

**Required tests**

- Playable and unplayable generated orchestration fixtures.
- Missing-articulation and missing-instrument diagnostics tests.
- Regression test for generated divisi or octave doubling staying in range.
  **Implemented:** `tests/test_gap_closure.py` covers the first range/technique
  contract.

### G6. Advanced Score Coverage

**Current state**

The score layer supports meter, pickup, form, repeats, polymeter, notes,
chords, raw frequencies, tempo/key maps, motifs, transforms, slurs,
articulations, and basic MIDI/MusicXML interop.

**Gap**

Closed for G6 first extension set *as metadata*. Asset-level `tuning:`, `tuplet:`, and
`lyrics:` compile into typed `notation` metadata; notation metadata is
hash-excluded unless future render passes lower it into explicit render IR.

**Measured limit (2026-09-06, `docs/evolution/harness-notation.md`).** At T0 the `tuning:`
directive was accepted and never read by any render path: a 19-EDO spec rendered in 12-TET
(`HARNESS-NTUN-001` FAIL). Checkpoint T4 of `docs/evolution/roadmap-notation.xlsx` closed it
for equal divisions of the octave (ADR-0014): note names are spelled along the chain of
fifths, the render lands on the EDO degree (FFT proof within ±5 cents, `HARNESS-NTUN-001`),
the default path is byte-identical (`HARNESS-NTUN-002`), and microtonal pitches leave the
engine as decimal MusicXML `<alter>`s and per-note MIDI pitch bends (`HARNESS-NTUN-004`).
Just intonation, historical temperaments and Scala files remain AF-M05 (`RN-T-004`, parked).
Tuplets and lyrics project to MusicXML `<time-modification>` and `<lyric>` (`HARNESS-NSEM-002`).

**Definition of Ready**

- Prioritize the first score extension set.
  **Implemented:** EDO tuning metadata, tuplet metadata, lyrics/phonemes.
- Define syntax and IR for tuning systems or rhythmic groupings.
  **Implemented:** `tuning: edo divisions=N base=A4 hz=440` and
  `tuplet: layer STARTb for DURb ratio=N:M`.
- Define interop behavior and lossy warnings.
  **Implemented:** interop diagnostics report lyric/articulation losses.
- Define rendering impact, if any.
  **Implemented:** current notation metadata is non-rendering and hash-excluded.
- Select corpus fixtures.
  **Implemented:** focused fixture in `tests/test_gap_closure.py`.

**Definition of Done**

- New score constructs compile to typed IR.
  **Implemented:** `spec["notation"]` stores typed tuning, tuplets, lyrics.
- Render-affecting constructs render deterministically.
  **Implemented:** none of the first extension set affects render until lowered.
- Non-render notation metadata is preserved without changing audio hashes.
  **Implemented:** `spec_hash()` excludes `notation`.
- Imports and exports either preserve the construct or emit a clear lossy
  diagnostic.
  **Implemented:** `interop_diagnostics()` emits structured warnings.

**Required tests**

- Parser/compiler tests for each score construct.
- Import/export round-trip tests where applicable.
- Hash tests for notation-only metadata.
- Render smoke tests for render-affecting score extensions.
  **Implemented:** `tests/test_gap_closure.py` covers parser/compiler and hash
  behavior for the first non-rendering extension set.

### G7. Deterministic Agent Repair Loop

**Current state**

Audio analysis emits structured features and recommendations. Agents can
manually patch DSL based on those diagnostics.

**Gap**

Closed for G7. `audioforge.repair.plan_repair()` maps analysis/user feedback to
deterministic edit intents, verifies compile after applying the top suggestion,
and records a trace. CLI entry point: `audioforge repair`.

**Definition of Ready**

- Define repair input schema: user feedback, analysis report, current DSL, and
  optional target constraints.
  **Implemented:** request object accepts `dsl`, `analysis`, `feedback`, and
  optional constraints.
- Define allowed edit operations.
  **Implemented:** `insert_master_fx`, `set_master_peak`, and `noop`.
- Define ranking and determinism rules for repair suggestions.
  **Implemented:** stable sort by operation/reason after deterministic rule
  matching.
- Define verification loop: compile, validate, render or analyze.
  **Implemented:** top suggestion is applied and compile diagnostics are stored.
- Define trace format.
  **Implemented:** trace records input recommendation codes and verification.

**Definition of Done**

- Repair planner emits structured patches or edit intents.
  **Implemented:** suggestions are structured operation dictionaries.
- Each repair suggestion is explainable and reproducible.
  **Implemented:** suggestions include `reason`; deterministic test compares
  complete plans.
- The planner can verify successful compile/validate after patching.
  **Implemented:** compile verification appears in `trace.verification`.
- Audio-quality repairs can compare before/after analysis.
  **Implemented:** analysis codes drive the first repair rules.
- User-facing CLI or SDK entry point exists.
  **Implemented:** `plan_repair()` and `audioforge repair`.

**Required tests**

- Before/after fixtures for noisy audio, rough melody, mono image, excessive
  brightness, clipping, and silence.
- Determinism test proving same input produces same repair suggestion.
- Failed-repair diagnostics test.
  **Implemented:** focused deterministic/compile-verification tests cover the
  initial roughness/brightness/clipping rules.

### G8. Interop Depth

**Current state**

MIDI and MusicXML import/export exist and are covered by tests. The current
interop layer is useful but intentionally scoped.

**Gap**

Closed for G8 initial contract. `docs/INTEROP.md` documents the MIDI/MusicXML
subset, `interop_diagnostics()` emits structured lossy warnings, and
`export_session_bundle()` writes a deterministic manifest-backed bundle.

**Measured limit (2026-09-06, `docs/evolution/harness-notation.md`).** Against external
oracles the original contract was narrower than the prose. Checkpoints T2 and T3 of
`docs/evolution/roadmap-notation.xlsx` closed the interchange part: the notated exporter
takes meter beats and unit, bar length (polymeter uses the global meter with `lossy_polymeter`), `key_map`, `tempo_map` (thinned
to the quantization grid), `pickup`, dynamics with hairpins, articulations, slurs, tuplets,
lyrics, fermatas, rehearsal marks and repeat barlines from the spec
(`HARNESS-NXML-002…008`, `HARNESS-NSEM-001/002`); the exact-tick MusicXML and MIDI exports
write one part or track per layer with simultaneous notes, every tempo point and sections,
as performed (MIDI also writes lyric events) (`HARNESS-NXML-009`, `HARNESS-NMIDI-002/003`); the importer reads one
layer per `<part>`, honours `<chord/>`, `<backup>`, `<forward>`, voices, per-measure
divisions, key, time and tempo, merges ties and brings supported marks back. Fermata
pause lengths are unspecified on import and recorded in `_meta.import.dropped`
(`HARNESS-NIMP-001…005`, Bach chorale round trip included). What each construct becomes in
each format is the generated matrix in `docs/INTEROP.md` (`make interop-check`); anything
dropped carries a registered code from `interop_diagnostics()` (`HARNESS-NXML-011`).
Unrepresentable imported constructs (unpitched notes, mid-piece time-signature changes,
microtonal alters, empty parts) are listed under `_meta.import.dropped`, never dropped
silently. Still open: the tuning resolver (G6, T4) and the CI oracle job (T5).

**Definition of Ready**

- Define supported and unsupported subsets per format.
  **Implemented:** `docs/INTEROP.md`.
- Define loss annotations and warnings.
  **Implemented:** `lossy_articulation` and `lossy_lyrics` warnings.
- Select representative real-world MIDI and MusicXML fixtures.
  **Implemented:** focused in-repo fixtures exercise common note/articulation
  cases.
- Define session/stems bundle contents.
  **Implemented:** spec JSON, MIDI, and `session.manifest.json`.
- Define deterministic import normalization.
  **Implemented:** existing import normalization remains deterministic.

**Definition of Done**

- Import/export docs state exact coverage.
  **Implemented:** `docs/INTEROP.md`.
- Lossy conversions emit structured warnings.
  **Implemented:** `interop_diagnostics()`.
- Session/stems bundle export is deterministic and manifest-backed.
  **Implemented:** `export_session_bundle()`.
- Corpus fixtures cover common notation and DAW-export cases.
  **Implemented:** `tests/test_gap_closure.py` covers the first bundle/lossy
  fixture.

**Required tests**

- Real-world MIDI and MusicXML fixture tests.
- Lossy-conversion diagnostics tests.
- Session/stems bundle manifest tests.
- Import normalization determinism tests.
  **Implemented:** focused lossy/session manifest tests are in place.

### G9. Capability Manifest Completeness

**Current state**

The capability manifest exposes major layer types, smart directives, score-layer
syntax, interop commands, examples, repair hints, and incompatibilities.

**Gap**

Closed for G9 initial schema contract. The manifest now carries
`audioforge.capabilities/1`, generated-source metadata, diagnostic-code
inventory, and a published schema at `docs/capability.schema.json`.

**Definition of Ready**

- Separate generated fields from curated prose fields.
  **Implemented:** `generated_from` identifies registry-backed fields.
- Define manifest schema and versioning.
  **Implemented:** `capability_manifest_schema()`.
- Identify all registries that must feed the manifest.
  **Implemented:** layer, FX, and style registries are named.
- Define diagnostic-code inventory.
  **Implemented:** `diagnostic_codes`.
- Define examples that agents should use as few-shot fixtures.
  **Implemented:** examples are in the manifest and compile checks cover asset
  examples.

**Definition of Done**

- Manifest schema is published and tested.
  **Implemented:** `docs/capability.schema.json` and tests.
- Registries and manifest cannot drift silently.
  **Implemented:** focused tests assert registry-backed manifest presence.
- Diagnostic codes are listed with repair hints.
  **Implemented:** `diagnostic_codes`.
- Agent examples compile and validate in CI.
  **Implemented:** examples beginning with `asset` compile in tests.
- Manifest includes enough information for constrained agent authoring without
  scraping Markdown.
  **Implemented:** manifest includes grammar-facing layer/fx/smart/intent data.

**Required tests**

- Registry-to-manifest drift tests.
- Manifest schema tests.
- Example compile/validate tests.
- Diagnostic-code coverage tests.
  **Implemented:** `tests/test_gap_closure.py`.

### G10. Agent Tool Surface

**Current state**

CLI and SDK expose compile, validate, render, decompile, capabilities, grammar,
analysis, and interop operations.

**Gap**

Closed for G10. `audioforge.agent_tools.run_tool()` provides a typed facade over
SDK operations and `tool_schemas()` publishes stable request/response skeletons.
`docs/AGENT_TOOLS.md` documents the contract.

**Definition of Ready**

- Define the supported tool operations.
  **Implemented:** compile, validate, render, analyze, decompile, import,
  export, repair.
- Define JSON request/response schemas.
  **Implemented:** `tool_schemas()`.
- Define error and diagnostic payload shape.
  **Implemented:** all responses include `ok`, `diagnostics`, and `artifacts`.
- Define file/resource access rules.
  **Implemented:** file-producing operations return artifact paths or inline
  artifact payloads; CLI remains responsible for filesystem inputs.
- Define determinism and timeout behavior.
  **Implemented:** facade delegates to deterministic SDK operations.

**Definition of Done**

- Typed tool facade exists over SDK operations.
  **Implemented:** `audioforge.agent_tools`.
- Responses include structured diagnostics and artifact paths.
  **Implemented:** response schema includes `diagnostics` and `artifacts`.
- Tool schemas are versioned and documented.
  **Implemented:** schema `audioforge.agent-tools/1`, `docs/AGENT_TOOLS.md`.
- Agent conformance tests run against the tool surface.
  **Implemented:** `tests/test_gap_closure.py`.

**Required tests**

- Tool contract tests for compile, validate, render, analyze, decompile, import,
  export, and repair once repair exists.
- Error-shape tests.
- Artifact path and manifest tests.
  **Implemented:** focused compile/decompile/repair/error/session tests cover
  the first contract slice.

---

### G11. Continuous Performance Curves

**Current state**

IR schema 1.1 defines explicit curve objects for continuous performance data.
`pitch_cents` and `dynamic` are published in the capability manifest with units,
ranges, interpolation shapes, time bases, support matrix, and diagnostics.
Legacy `vibrato`, `glide_s`, and authored dynamic breakpoints lower to explicit
curves before render while `_meta.semantic.authored_expression` records the
authoring form for decompile.

Synth notes and sampled instruments consume note-scoped `pitch_cents` and
`dynamic` curves. Sampled instruments use a time-varying source-read ratio with
cumulative source position, including looped sustain regions. Physical-model
pitch curves reject with `curve_unsupported_voice` until individual kernels are
staged with bounds and golden renders.

**Gap**

Closed for the first AF-P1 landing. Remaining work is explicitly staged rather
than silent: physical-model kernel support, richer authored curve syntax, and
lossless symbolic export for curve families that fit a target format.

**Definition of Ready**

- Define canonical IR curve object, interpolation semantics, edge behavior,
  sampled encoding, target ranges, and hash ownership.
  **Implemented:** `audioforge.curves`, `audioforge.ir_schema`, and
  `docs/IR_SCHEMA.md`.
- Define compiler lowering for existing expressive fields.
  **Implemented:** DSL lowering emits `pitch_cents` and `dynamic` curves while
  retaining authored provenance in `_meta.semantic`.
- Define renderer support matrix and unsupported diagnostics.
  **Implemented:** `capability_manifest()["performance_curves"]` and
  `curve_unsupported_voice`.
- Define interop behavior.
  **Implemented:** MIDI pitch-bend import becomes layer `pitch_cents`
  automation; unsupported curve export emits lossy diagnostics.

**Definition of Done**

- Curve schema and validator accept valid breakpoint/sampled curves and reject
  malformed or unsupported cases.
  **Implemented:** `tests/test_curves.py`, `tests/test_ir_schema.py`, and
  schema/docs drift tests.
- Compiler lowering covers legacy vibrato, glide, and dynamic breakpoints.
  **Implemented:** `tests/test_performance_curves_compile.py`.
- Renderers consume curves as source-of-truth performance data.
  **Implemented:** synth and sampled-instrument render tests, including looped
  sampled sustain and note dynamic velocity-layer crossfade.
- Hash policy is explicit.
  **Implemented:** expanded curves are render data; `_meta.semantic` remains
  hash-excluded by the IR schema metadata and determinism tests.
- Decompile and interop do not silently drop curve semantics.
  **Implemented:** decompile emits canonical note-curve lines when no authored
  provenance exists; interop diagnostics report lossy pitch/dynamic projection.
- Documentation and release notes are synchronized.
  **Implemented:** `docs/DSL_SPEC.md`, `docs/IR_SCHEMA.md`,
  `docs/INTEROP.md`, and `docs/RELEASE_NOTES.md`.

**Required tests**

- Curve evaluator and validator conformance tests.
- Compiler lowering tests for legacy authored expression.
- Synth and sampled renderer pitch/dynamic regressions.
- Capability manifest support-matrix and diagnostic coverage.
- Decompile canonical-curve visibility.
- MIDI pitch-bend import and lossy interop diagnostics.

---

### G12. First-Class Render Plan

Routing decisions must be inspectable before audio is rendered. The render plan
is a derived artifact between validation/resource resolution and rendering; it
does not live in the authored DSL or IR, but its policy inputs do.

**Status:** Phase 1 implemented, Phase 2 verification entry point implemented.

**Implemented**

- `audioforge.plan` publishes schema `audioforge.render-plan/1`, canonical plan
  JSON, `plan_hash`, validation, stale-plan verification, and explain helpers.
- `routing.fallbacks` (`allow`, `warn`, `forbid`) and
  `routing.stretch_warn_semitones` are validated as hash-included IR policy.
- Plans cover sampled instrument note segments, synthetic articulation
  fallbacks, and synth/native note segments with route decisions, evidence,
  diagnostics, and reserved cost fields.
- Render manifests include `plan_hash`, `plan_file`, and `plan_sha256`; exports
  write `<id>.plan.json`.
- `export_session_bundle()` includes the plan file and its SHA-256 in
  `session.manifest.json`.
- CLI surfaces: `audioforge plan`, `audioforge plan --explain`,
  `audioforge render --plan`, and `audioforge render --explain`.
- SDK and agent surfaces: `AudioAsset.plan()` and `run_tool("plan", ...)`.
- Capability manifest advertises render-plan routes, policy fields, artifact
  hash policy, and diagnostics.
- Verified-plan renders consume planned articulation fallback mods and selected
  sampled regions for static velocity and dynamic-crossfade paths.
- Render manifests write `plan_segment_actual_ms` keyed by segment id.

**Remaining staged work**

- Direct low-level sampler calls without `plan_segments` keep the legacy
  derivation path for focused unit tests and debugging. The normal render and
  `render --plan` paths are plan-authoritative after verification.
- Reserved `inpaint` routes still fail until the F3 inpainting route lands.

**Required tests**

- Planner contract, evidence, policy, stale-plan, CLI, SDK, agent-tool,
  manifest, bundle, capability-manifest, and schema drift tests.
- Phase 2 must add byte-identical plan-consuming sampler tests before deleting
  legacy derivation.

---

### G13. Expressive Performance Techniques And Note-Scope Timbre

AF-P3/G13 is the next staged expressive-performance gap after G11 performance
curves and G12 render plans. It is reserved for **Engine 2.17.0 / DSL 1.11**;
DSL 1.10 remains reserved for the richer G11 curve-sugar authoring surface.

The normative implementation contract is
`docs/doc-requirements-architecture-expressive-performance-techniques-done.md`.
This gap entry records the roadmap linkage only; if it conflicts with that
done requirements-architecture document, the done document wins and this entry
must be updated in the same change.

**Status:** Done-validated requirements architecture; implementation landed.

**Current state**

- G11 is present: IR schema 1.1 validates `pitch_cents` and `dynamic` note
  curves through `audioforge.curves` and `audioforge.ir_schema`.
- The renderer already consumes G11 curves in synth and sampled-instrument paths.
- The capability manifest publishes `performance_curves` and
  `curve_unsupported_voice` diagnostics.
- The DSL now has first-class `tech NAME(...)` note modifiers, note-scope
  `cutoff_hz` / `gain_db` / `scan` curve escape hatches, and
  `tuning` / `string` / `fret` instrument-mechanics fields.

**Closed gap**

AudioForge can now author and validate how a note is produced as explicit IR.
The bounded AF-P3/G13 scope that closed this gap is:

- R1: note-scope timbre curves on `cutoff_hz`, `gain_db`, and `scan`.
- R2: a single-source technique registry whose named techniques lower
  deterministically to explicit IR primitives.
- R3: fretted/stringed instrument mechanics with hash-included `tuning`,
  `string`, and `fret`; `string` + `fret` derive pitch authoritatively.

The renderer must never receive a private "technique" concept. Smart authoring
syntax is allowed only when it lowers before render into explicit, diffable,
hash-owned IR.

**Out of scope**

- True per-string multisampled timbre.
- Fingering optimization or automatic tab generation.
- General ornaments beyond the source contract technique set.
- Real-time or MPE input.
- Learned technique generation.
- Speculative DSP kernels. New kernels are allowed only when necessary and
  viable under the DSP Kernel Policy in the source contract.

**Definition of Ready**

- Version target reserved: Engine 2.17.0 / DSL 1.11.
- Done architecture exists and remains the normative source of truth.
- G11 dependency is present on HEAD.
- Acceptance fixture coverage is the source contract fixture set in
  `static/fixtures/expressive_techniques.af` plus rejection fixtures for every
  canonical diagnostic code.
- Unknown note suffix hardening is assigned as a prerequisite before the P4
  grammar landing.
- Full gate passes on HEAD before the first runtime implementation change.
- Coordination task is open and target files are locked for each editing slice.
- R3 tuning constants remain the source contract starting model unless P2
  records a ratified adjustment in the source contract.

**Definition of Done**

- IR 1.2 accepts supported note-scope timbre curves and rejects unsupported
  targets, unsupported voices, duplicate timbre curves, and `scan` without
  `osc: morph`.
- `TECHNIQUES` is the single runtime source for technique names, params, support
  matrix, docs, and deterministic lowering metadata.
- Techniques lower to explicit hash-included IR, while authored technique
  provenance stays hash-excluded under `_meta.semantic.authored_expression`.
- `tuning`, `string`, and `fret` validate, derive pitch, reject feasibility and
  pitch conflicts with canonical diagnostics, and decompile round-trip.
- The capability manifest, generated schemas, grammar artifacts, DSL docs,
  release notes, and tests are synchronized with runtime constants.
- The acceptance fixture compiles and its lead-layer IR matches a checked-in
  golden snapshot; rejection fixtures fail with exact diagnostic codes.
- Existing valid IR 1.1 no-feature specs remain valid and render-identical.
- `./scripts/run_tests.sh` passes, including drift, compiler, validator,
  renderer, decompile, support-matrix, and acceptance coverage.

**Required tests**

- Unit tests for `NOTE_SCOPE_TARGETS`, `TECHNIQUES`, curve validation,
  duplicate timbre-curve rejection, `scan`/`morph` gating, technique params, and
  R3 feasibility.
- Compiler tests for every approved technique and every `cutoff()` / `level()` /
  `scan()` escape hatch.
- Renderer tests for note-scope `cutoff_hz`, `gain_db`, and `scan` behavior and
  no-curve fast-path preservation.
- Drift tests proving manifest/schema/docs/grammar artifacts match runtime.
- Acceptance and rejection fixture tests for all canonical diagnostic codes.

---

## 5. Acceptance Criteria For The Strong Universality Claim

AudioForge may claim "we can express all music with a Smart DSL" without
qualification when:

- every render-affecting construct lowers to explicit IR,
- arbitrary recorded audio can be pinned, placed, transformed, and verified,
- symbolic notation covers common Western, non-Western, microtonal, and
  free-time cases through score/event IR or documented extension points,
- performance and production semantics are explicit, deterministic, and testable,
- import/export pathways preserve supported semantics and diagnose lossy cases,
- AI intent is preserved semantically and expanded deterministically,
- validators prove render-readiness before render,
- the capability manifest is a complete machine-readable authoring contract,
- regression tests cover syntax, IR, resources, rendering, analysis, repair,
  interop, docs, and examples.

Until those criteria pass, use the more precise claim from section 2.

---

## 6. Cross-Cutting DoR And DoD

### Definition Of Ready For Any DSL Gap

A gap is ready for implementation only when:

- user-facing syntax or API is specified,
- IR representation is specified,
- deterministic expansion behavior is specified,
- validation and diagnostics are specified,
- resource requirements are known,
- decompile/round-trip behavior is decided,
- compatibility and migration impact is understood,
- test fixtures are named,
- expected regression tests are listed,
- acceptance criteria are measurable.

### Definition Of Done For Any DSL Gap

A gap is done only when:

- implementation matches this document and `DSL_SPEC.md`,
- new behavior is covered by tests at parser, compiler, validator, and relevant
  render/analysis levels,
- existing fixtures still pass,
- diagnostics are structured and line-cited where applicable,
- render-readiness is validated,
- docs and capability manifest are updated,
- hashes/goldens are updated intentionally when audio changes,
- no hidden nondeterminism is introduced,
- examples are valid and render-ready.
