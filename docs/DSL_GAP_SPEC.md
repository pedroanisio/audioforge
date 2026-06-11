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
| DSL parser | Lark-backed syntax gate via `audioforge.lark_parser`, with generated EBNF/GBNF artifacts exposed by `audioforge grammar`. |
| Current reference spec | `docs/DSL_SPEC.md` documents the implemented `.af` surface. |
| Smart directives | `style:`, `perform:`, `ensemble:`, `voicing:`, and `space:` parse at asset scope and expand into explicit render IR under `audioforge.dsl._apply_smart_directives`. |
| Style packs | `audioforge.styles` provides deterministic style defaults, listed by `audioforge capabilities`. |
| Agent manifest | `audioforge.capabilities.capability_manifest()` exposes layer types, properties, units, enums, smart directives, score syntax, interop commands, examples, repair hints, and incompatibilities. |
| Score layer | Meter, pickup, form, repeat, and polymeter compile into `spec["score"]`. |
| Audio layer | `audio` compiles to a content-addressed `sample` layer with source-kind metadata and stereo/channel preservation support. |
| Interop | MIDI and MusicXML import/export are available through SDK and CLI. |
| Analysis | `audioforge.analysis.analyze_audio()` emits structured audio features and recommendations; `render --analyze` writes analysis into manifests. |
| Decompile | `audioforge.decompile.spec_to_dsl()` emits a canonical render-equivalent `.af` from IR. |
| Validation | `validate` is render-ready by default and performs resource binding unless `--no-resolve` is supplied. |
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

`DSL_SPEC.md` advertises a DSL/engine version, while `audioforge.dsl.DSL_VERSION`
is maintained independently. The docs, manifest, grammar artifacts, and runtime
version fields can drift unless tests explicitly lock the contract.

**Gap**

There is no single generated source of truth for DSL version metadata and
feature-support declarations.

**Definition of Ready**

- Decide which module owns DSL version metadata.
- Define which docs and manifests consume that version.
- Define drift checks for docs, grammar, manifest, and runtime.
- List all user-visible version strings that must agree.

**Definition of Done**

- `DSL_SPEC.md`, capability manifest, CLI output, and runtime compile metadata
  report consistent DSL version information.
- Tests fail when docs or manifest versions drift from runtime.
- Release notes or migration notes state when a DSL version changes.

**Required tests**

- Regression test comparing `audioforge.dsl.DSL_VERSION` to documented DSL
  version metadata.
- Capability-manifest test proving the exported version matches runtime.

### G2. Formal Universal Music IR Schema

**Current state**

The engine validates specs through `audioforge.schema` and render-readiness
through resource resolution. The IR exists as dictionaries and is well covered by
behavioral tests, but there is no published formal schema that describes a
multi-altitude Universal Music IR.

**Gap**

The project still needs a versioned, published IR schema with clear separation
between semantic intent, expanded render data, and provenance.

**Definition of Ready**

- Choose schema format, for example JSON Schema or a typed Python schema with
  generated JSON Schema.
- Define IR versioning and migration policy.
- Define hash inclusion and exclusion rules.
- Define which fields belong to semantic, render, and provenance layers.
- Identify existing specs that must validate without migration.

**Definition of Done**

- A published schema validates generated IR.
- Every current DSL construct maps to schema-defined fields.
- Semantic intent, expanded render data, and provenance have documented
  ownership boundaries.
- Formatting-only source metadata remains excluded from render hashes.
- Schema migration tests exist for at least one version boundary.

**Required tests**

- Schema-valid and schema-invalid fixtures.
- Generated-spec conformance tests for representative `.af` files.
- Hash stability tests proving non-render metadata does not affect spec hashes.

### G3. Structured `intent {}` Blocks

**Current state**

The DSL has five asset-level smart directives: `style`, `perform`, `ensemble`,
`voicing`, and `space`. They preserve intent under `spec["intent"]` and expand
to explicit render IR.

**Gap**

There is no structured free-form `intent {}` block for higher-level agent goals
such as affect, density, contour, texture, avoid-list, reference-free style
description, or repair target.

**Definition of Ready**

- Define typed fields and allowed free-text fields.
- Specify which fields affect render expansion and which are metadata-only.
- Specify conflict handling, for example sparse density with large ensemble size.
- Define grammar changes and manifest representation.
- Provide examples for at least three idioms.

**Definition of Done**

- `intent {}` parses into semantic IR.
- Render-affecting intent expands deterministically into explicit IR.
- Metadata-only intent is preserved but cannot silently affect audio.
- Conflicts produce structured diagnostics.
- Decompiler behavior is defined: preserve authored intent when available or
  emit a documented canonical equivalent.

**Required tests**

- Parser tests for valid and invalid `intent {}` blocks.
- Compiler tests proving deterministic expansion.
- Diagnostics tests for conflicting fields.
- Regression fixture for an agent repair case such as "make the melody less
  rough" or "remove noise from audio 2".

### G4. Semantic Round-Trip Preservation

**Current state**

The decompiler emits render-equivalent DSL. It intentionally does not reconstruct
high-level sugar such as motifs and smart directives from expanded IR.

**Gap**

Agents cannot yet round-trip at the same semantic altitude for authored smart
directives, motifs, and future intent blocks.

**Definition of Ready**

- Define which semantic constructs must be preserved in IR.
- Define canonical decompile output for preserved semantic constructs.
- Define acceptable lossy cases and diagnostics.
- Define how semantic and expanded render layers stay synchronized.

**Definition of Done**

- Decompiler preserves authored semantic constructs where the IR contains them.
- Lossy decompile cases emit warnings or metadata.
- Recompiled decompiled DSL is render-equivalent.
- Semantic-preserving round-trip tests pass for smart directives, motifs, score
  sections, buses, automation, and dynamics.

**Required tests**

- `DSL -> IR -> DSL -> IR` tests for semantic-preserved fixtures.
- Lossy-case tests proving warnings are emitted.
- Render hash or manifest equivalence tests for round-tripped assets.

### G5. Library-Aware Orchestration

**Current state**

`ensemble:` can add unison/spread/octave behavior and role routing. Instrument
layers require a library pin, and validation resolves instruments and
articulations.

**Gap**

The orchestration pass is not yet library-aware in the musical sense: it does
not choose playable instruments from a catalog, enforce comfortable ranges
during generation, select articulations by technique, or create divisi from
instrument capabilities.

**Definition of Ready**

- Machine-readable instrument range and technique catalog exists.
- Articulation compatibility rules are defined.
- Register comfort and hard range policies are defined.
- Missing library/instrument/articulation diagnostics are specified.
- Example orchestration targets are selected.

**Definition of Done**

- Generated orchestration obeys hard ranges and articulation availability.
- Register or technique issues are caught before render.
- Library-aware choices are explicit in IR.
- Missing or unsuitable resources fail validation with structured diagnostics.
- Existing library-pinned instrument fixtures still render.

**Required tests**

- Playable and unplayable generated orchestration fixtures.
- Missing-articulation and missing-instrument diagnostics tests.
- Regression test for generated divisi or octave doubling staying in range.

### G6. Advanced Score Coverage

**Current state**

The score layer supports meter, pickup, form, repeats, polymeter, notes,
chords, raw frequencies, tempo/key maps, motifs, transforms, slurs, articulations,
and basic MIDI/MusicXML interop.

**Gap**

Universal score expression still needs deeper coverage for microtonal tuning
systems, alternate temperaments, tuplets and nested rhythmic groupings, free-time
notation, lyrics, phonemes, vocal phrasing, advanced notation metadata, and more
complete import/export semantics.

**Definition of Ready**

- Prioritize the first score extension set.
- Define syntax and IR for tuning systems or rhythmic groupings.
- Define interop behavior and lossy warnings.
- Define rendering impact, if any.
- Select corpus fixtures.

**Definition of Done**

- New score constructs compile to typed IR.
- Render-affecting constructs render deterministically.
- Non-render notation metadata is preserved without changing audio hashes.
- Imports and exports either preserve the construct or emit a clear lossy
  diagnostic.

**Required tests**

- Parser/compiler tests for each score construct.
- Import/export round-trip tests where applicable.
- Hash tests for notation-only metadata.
- Render smoke tests for render-affecting score extensions.

### G7. Deterministic Agent Repair Loop

**Current state**

Audio analysis emits structured features and recommendations. Agents can
manually patch DSL based on those diagnostics.

**Gap**

There is no first-class deterministic repair planner that maps analysis findings
or user feedback into proposed DSL edits, verifies them, and records the repair
trace.

**Definition of Ready**

- Define repair input schema: user feedback, analysis report, current DSL, and
  optional target constraints.
- Define allowed edit operations.
- Define ranking and determinism rules for repair suggestions.
- Define verification loop: compile, validate, render or analyze.
- Define trace format.

**Definition of Done**

- Repair planner emits structured patches or edit intents.
- Each repair suggestion is explainable and reproducible.
- The planner can verify successful compile/validate after patching.
- Audio-quality repairs can compare before/after analysis.
- User-facing CLI or SDK entry point exists.

**Required tests**

- Before/after fixtures for noisy audio, rough melody, mono image, excessive
  brightness, clipping, and silence.
- Determinism test proving same input produces same repair suggestion.
- Failed-repair diagnostics test.

### G8. Interop Depth

**Current state**

MIDI and MusicXML import/export exist and are covered by tests. The current
interop layer is useful but intentionally scoped.

**Gap**

The system needs documented interop subsets, broader real-world fixture coverage,
session/stems bundle export, and clearer lossy conversion diagnostics for
advanced notation, controller data, lyrics, tempo nuance, and articulations.

**Definition of Ready**

- Define supported and unsupported subsets per format.
- Define loss annotations and warnings.
- Select representative real-world MIDI and MusicXML fixtures.
- Define session/stems bundle contents.
- Define deterministic import normalization.

**Definition of Done**

- Import/export docs state exact coverage.
- Lossy conversions emit structured warnings.
- Session/stems bundle export is deterministic and manifest-backed.
- Corpus fixtures cover common notation and DAW-export cases.

**Required tests**

- Real-world MIDI and MusicXML fixture tests.
- Lossy-conversion diagnostics tests.
- Session/stems bundle manifest tests.
- Import normalization determinism tests.

### G9. Capability Manifest Completeness

**Current state**

The capability manifest exposes major layer types, smart directives, score-layer
syntax, interop commands, examples, repair hints, and incompatibilities.

**Gap**

The manifest is not yet a full generated contract for every parser rule, schema
field, resource capability, style-pack parameter, instrument catalog entry, and
diagnostic code.

**Definition of Ready**

- Separate generated fields from curated prose fields.
- Define manifest schema and versioning.
- Identify all registries that must feed the manifest.
- Define diagnostic-code inventory.
- Define examples that agents should use as few-shot fixtures.

**Definition of Done**

- Manifest schema is published and tested.
- Registries and manifest cannot drift silently.
- Diagnostic codes are listed with repair hints.
- Agent examples compile and validate in CI.
- Manifest includes enough information for constrained agent authoring without
  scraping Markdown.

**Required tests**

- Registry-to-manifest drift tests.
- Manifest schema tests.
- Example compile/validate tests.
- Diagnostic-code coverage tests.

### G10. Agent Tool Surface

**Current state**

CLI and SDK expose compile, validate, render, decompile, capabilities, grammar,
analysis, and interop operations.

**Gap**

There is no dedicated typed agent tool surface or MCP server contract that wraps
these operations with stable request/response schemas.

**Definition of Ready**

- Define the supported tool operations.
- Define JSON request/response schemas.
- Define error and diagnostic payload shape.
- Define file/resource access rules.
- Define determinism and timeout behavior.

**Definition of Done**

- Typed tool facade exists over SDK operations.
- Responses include structured diagnostics and artifact paths.
- Tool schemas are versioned and documented.
- Agent conformance tests run against the tool surface.

**Required tests**

- Tool contract tests for compile, validate, render, analyze, decompile, import,
  export, and repair once repair exists.
- Error-shape tests.
- Artifact path and manifest tests.

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

