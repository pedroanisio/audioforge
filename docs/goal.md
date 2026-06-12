---
title: "AudioForge Goal: Continuous Performance Curves"
status: active-goal
source_proposal: "../static/refs/AF-P1-performance-curves-proposal-v2.1.md"
scope: "AF-P1 / G11 continuous pitch and dynamic curves"
owner: "AudioForge maintainers"
---

# Goal: Continuous Performance Curves

AudioForge must make continuous expressive performance stateable in the IR,
not invented privately by the renderer. The target is a first-class,
diffable, hash-included curve contract for pitch and through-note dynamics
that follows the existing AudioForge rule: smart authoring surface in the DSL,
austere explicit data in the IR, deterministic rendering from that data.

This goal implements the AF-P1 proposal as a disciplined compiler and IR
upgrade. It closes the known gap where `glide_s`, `vibrato`, and some dynamic
behavior affect rendered audio but are not represented at performance
resolution in the IR.

## Current Problem

The current tree exposes these constraints:

- `audioforge/schema.py` limits automation targets to `gain_db`, `cutoff_hz`,
  and `scan`; there is no IR target for continuous pitch.
- `audioforge/sequencer.py` and `audioforge/synth.py` derive glide and vibrato
  as renderer-private pitch envelopes from scalar layer parameters.
- `audioforge/sampler.py` already has meaningful time-varying dynamic behavior,
  but it is not normalized under a general curve contract.
- Physical model voices document that they ignore pitch envelopes; that
  limitation must stay loud and declared until each kernel is staged in.
- `perform: rubato` already demonstrates the preferred pattern: macro-level
  musical intent compiles to dense explicit points, while the runtime consumes
  simple verifiable primitives.

The result is an expressiveness gap: bends, evolving vibrato, micro-timed
slides, and through-note dynamics cannot be stated, diffed, hashed,
decompiled, or validated as explicit render data.

## Target State

Implement additive IR support for continuous performance curves:

- Extend existing automation machinery instead of adding a second curve system.
- Add `pitch_cents` as relative pitch offset in cents.
- Promote `dynamic` to the same curve machinery with the existing musical
  meaning: time-varying performance dynamic in `[0, 1]`.
- Add note-scoped curves on note events and preserve layer-scoped automation.
- Define normative interpolation semantics for every curve at every sample
  time.
- Lower all authored performance sugar to explicit curve data before render.
- Store authored sugar in `_meta.semantic` only for provenance and round-trip.
- Include expanded curve data in spec hashes and render manifests.
- Reject unsupported voice or target combinations with structured diagnostics.
- Publish the support matrix in the capability manifest so agents can plan
  before compiling.

Version target:

- IR schema: `1.1`, additive.
- DSL and engine version: use the next available minor version in the live
  release line. If the tree already advertises DSL 1.8 / Engine 2.15 for other
  shipped work, assign AF-P1 to the next unused pair before release notes are
  finalized.

## Non-Goals

- Do not enrich `tempo_map`. Tempo maps remain only `[beat, bpm]` points
  integrated exactly. Fermatas and holds remain first-class absolute-second
  hold events. Rubato remains a smart directive that compiles to dense
  piecewise-linear tempo points within the documented error bound.
- Do not add real-time MPE input in this phase.
- Do not add learned curve generation in this phase. The curve contract is the
  interface that future learned renderers may consume.
- Do not silently approximate unsupported physical-model curves. Staging is
  allowed; silent ignore is not.
- Do not add splines, arbitrary expressions, or unbounded pitch excursions.
  Dense breakpoints are the escape hatch for complex shapes.

## Design Rules

1. One machinery: extend automation and validation paths already used by the
   IR; do not create a sibling curve subsystem.
2. Compiler owns expressivity: DSL sugar, `perform:` directives, legacy
   `glide_s`, legacy `vibrato`, and symbolic imports must compile to explicit
   curve data.
3. Runtime consumes data: renderers evaluate curves; they do not invent
   render-affecting performance shapes from hidden scalar policy.
4. Normative interpolation: shape semantics, edge behavior, sampled encodings,
   time bases, and evaluation points must be documented and tested.
5. Hash honesty: expanded curves are render data and must affect spec hashes;
   `_meta.semantic` provenance must not.
6. Loud partiality: unsupported target and voice combinations fail validation
   with named diagnostics and manifest-declared support.
7. Determinism first: every implementation choice that can affect samples
   needs a testable rule and a golden or conformance fixture.

## Required IR Contract

Curve object fields:

- `target`: one of `pitch_cents`, `dynamic`, or existing automation targets.
- `time_basis`: one of `note_beats`, `note_seconds`, `layer_seconds`, or
  `layer_beats`, as valid for the scope.
- Breakpoint encoding: `points` as `[t, value]` or `[t, value, shape]`.
- Sampled encoding: `t0`, `rate_hz`, `values`, defined as linear breakpoints.

Interpolation shapes:

- `linear`: default linear interpolation.
- `hold`: previous value until the endpoint.
- `pow:k`: power curve where `k` is validated in `[0.1, 10]`.

Edge behavior:

- Before the first point, hold the first value.
- After the last point, hold the last value.
- A single-point curve is a constant function.

Pitch rule:

- `pitch_cents = 0` always means the note or layer base pitch.
- Multiple in-scope `pitch_cents` curves sum in cents.
- Rendered frequency is `f_base * 2 ** (cents / 1200)`.
- Exceeding configured pitch bounds is a validation error, not clamping.

Dynamic rule:

- Values must be in `[0, 1]`.
- At most one dynamic curve is allowed per scope.
- A note-scoped dynamic curve replaces the layer-scoped dynamic curve for that
  note span and emits an informational diagnostic when both are present.

## Implementation Plan

### Phase 0: Preflight and Source of Truth

- Confirm the exact release target and update version policy before changing
  version constants.
- Add or update the gap entry for G11 in `docs/DSL_GAP_SPEC.md`.
- Identify all render-affecting fields owned by curve lowering in
  `audioforge/ir_schema.py`.
- Keep docs, schema, capability manifest, grammar artifacts, and tests in one
  synchronized change set.

### Phase 1: Schema, Manifest, and Validation

- Extend `AUTO_TARGETS` with `pitch_cents` and `dynamic`.
- Add curve schema definitions to `audioforge/ir_schema.py`.
- Add `notes[].curves` support for note events.
- Add `time_basis`, shape, strict point ordering, sampled-curve, and range
  validation.
- Add structured diagnostic codes for invalid curve shape, unsupported target,
  unsupported voice, out-of-range pitch, duplicate dynamic curve, invalid time
  basis, and note-span overrun.
- Publish curve metadata in `capability_manifest()`:
  - targets,
  - units,
  - ranges,
  - shapes,
  - support matrix,
  - per-kernel physical-model bounds.
- Regenerate `docs/ir.schema.json`, `docs/capability.schema.json`, grammar
  artifacts, and any manifest snapshots required by the repo.

### Phase 2: Reference Evaluator

- Add one reference curve evaluator shared by compiler tests and renderers.
- Evaluate both breakpoint and sampled encodings through the same semantics.
- Keep the evaluator deterministic, pure, and independent of renderer-specific
  side effects.
- Use vectorized NumPy paths where this affects render throughput, but keep a
  simple reference path for conformance tests.

### Phase 3: Compiler Lowering

- Lower legacy `vibrato` to dense sampled `pitch_cents` curves.
- Raise curve rate automatically when configured vibrato would exceed the
  stated pitch-error bound.
- Lower `glide_s` exactly as a linear-in-cents curve from previous pitch offset
  to zero.
- Re-emit existing sampled-layer dynamic breakpoint lists as `dynamic` curves.
- Keep authored forms under `_meta.semantic.authored_expression` with source
  spans for decompile and diagnostics.
- Ensure `_meta.semantic` changes do not alter spec hashes.

### Phase 4: Renderer Integration

- Update synth note rendering to consume evaluated `pitch_cents` and `dynamic`
  curves instead of deriving private glide or vibrato envelopes at render time.
- Update sampled instruments with a normatively specified time-varying-ratio
  resampler using cumulative source position.
- Specify and test loop behavior under varying ratio in source coordinates.
- Preserve current synth dynamic behavior unless a separate engine-semantics
  change intentionally upgrades brightness to fully time-varying.
- Keep static fast paths for notes without curves.

### Phase 5: Support Matrix and Physical Models

- In the first AF-P1 landing, unsupported physical-model `pitch_cents` curves
  must reject with `curve_unsupported_voice`.
- Stage physical-model support after the IR contract lands:
  1. `struck`
  2. `blown`
  3. `sympathetic`
  4. `bowed`
  5. `brass`
- Each kernel stage requires an explicit excursion bound, sweep validation,
  pitch-tracking evidence, and golden renders before the manifest advertises
  support.

### Phase 6: Interop and Decompile

- Decompile to authored syntax when `_meta.semantic` provenance exists.
- Decompile to canonical curve syntax when provenance is absent.
- Import MusicXML bend hints as canonical curves.
- Export MusicXML bends with lossiness diagnostics when a curve cannot be
  represented symbolically.
- Import MIDI pitch bend as layer-scope sampled `pitch_cents` curves, honoring
  bend range when present.
- Keep MPE and MIDI 2.0 per-note export out of this phase unless the support is
  fully specified and tested.

### Phase 7: Documentation and Release

- Update `docs/DSL_SPEC.md`, `docs/IR_SCHEMA.md`, `docs/DSL_GAP_SPEC.md`, and
  `docs/RELEASE_NOTES.md` together.
- Document the hash transition honestly: engine version changes already alter
  hashes by policy; legacy glide/vibrato lowering also changes compiled IR.
- Document per-voice support, unsupported diagnostics, and staged kernel plan.
- Add examples for bend-hold-vibrato-release and through-note dynamics.

## Definition of Done

AF-P1 is done only when all items below are true:

- IR schema `1.1` validates curve objects, note-scoped curves, sampled curves,
  time bases, and interpolation shapes.
- `pitch_cents` and `dynamic` are published in the manifest with units, ranges,
  shape metadata, and support matrix.
- Legacy `glide_s`, `vibrato`, and dynamic breakpoints lower to explicit
  curves before rendering.
- Renderers consume curves as the source of performance truth.
- Unsupported voices fail validation with structured diagnostics that match
  the manifest.
- Spec hash changes when expanded curve values change.
- Spec hash does not change when only `_meta.semantic` authored provenance
  changes.
- Decompile preserves authored forms when provenance exists and emits canonical
  curve syntax otherwise.
- MusicXML and MIDI projection paths either preserve the curve or emit
  documented lossiness diagnostics.
- Docs, schema, grammar, manifest, examples, and release notes are synchronized.
- All required tests pass locally through the canonical runner.

## Required Tests

All tests must be deterministic, isolated, and realistic. Prefer real compiler,
validator, and renderer paths over mocks.

### Unit and Contract Tests

- Curve schema accepts valid breakpoint and sampled curves.
- Curve schema rejects malformed points, unsorted times, bad shapes, duplicate
  dynamic curves, invalid `time_basis`, and out-of-range values.
- The reference evaluator covers:
  - `linear`,
  - `hold`,
  - `pow:k`,
  - before-first edge hold,
  - after-last edge hold,
  - single-point curves,
  - sampled-curve equivalence to linear breakpoints.
- Capability manifest coverage tests compare targets, shapes, diagnostic codes,
  support matrix, and schema publication against runtime sources.

### Compiler Tests

- `vibrato` lowers to sampled `pitch_cents` within the documented cents-error
  bound across normal and edge settings.
- `glide_s` lowers exactly to linear cents over the glide duration.
- Existing dynamic breakpoints round-trip into `dynamic` curve objects.
- `perform:` directives that generate expression lower to explicit IR curves.
- `_meta.semantic` preserves authored expression without affecting hashes.

### Renderer Tests

- Synth bend-hold-vibrato-release renders deterministically and follows the
  expected pitch track.
- Sampled-instrument bend-hold-vibrato-release renders deterministically using
  the time-varying resampler.
- Looped sustain regions under varying ratio have golden renders and specified
  loop-crossfade behavior.
- Through-note sampled dynamics continue to move through velocity layers.
- Static no-curve notes stay on the fast path and preserve existing behavior.

### Support Matrix Tests

- Unsupported physical-model pitch curves reject with `curve_unsupported_voice`.
- Manifest-declared support matches validator behavior for every layer family.
- Each staged physical-model kernel has sweep tests before support is enabled.
- Bounds are enforced per voice and widen only with empirical test evidence.

### Interop and Round-Trip Tests

- MusicXML bend import expands to a canonical curve snapshot.
- MusicXML bend export emits lossiness diagnostics for non-symbolic curves.
- MIDI pitch-bend import honors bend range and produces `pitch_cents`.
- DSL to IR to DSL to IR preserves authored expression where possible.

### Drift and Documentation Tests

- `docs/ir.schema.json` equals `audioforge.ir_schema.ir_schema()`.
- `docs/capability.schema.json` equals the runtime capability schema.
- DSL docs enumerate every public curve target, shape, diagnostic, and support
  status.
- Release notes mention both engine-version hash shift and legacy-expression
  curve-lowering transition.

### Required Commands

Run these before declaring the goal complete:

```bash
./scripts/run_tests.sh
python3 -m pytest -q
python3 -m coverage run -m pytest
python3 -m coverage report
```

Focused development slices may run narrower commands, but final completion
requires the full gate above.

Coverage must respect the repository threshold in `pyproject.toml`
(`fail_under = 90.1`). Critical curve, validator, hash, and renderer paths must
be covered at or above 95%.

---

My suggestion: don't propose one patch — propose a **stacked series of seven small, independently revertable patches**, ordered so that every commit leaves the tree green, hash-transitions are isolated into named commits, and the fixture acts as the acceptance thread throughout. The series maps onto goal.md's phases but resequences the two urgent items in front. Concretely:

**P0 — Hardening + drift repair (ships now, zero feature content).** Unknown note-suffix tokens become a line-cited structured `DSLError` instead of the `Tok` leak into `_semantic_sidecar` (Finding V2), plus the V1 decision — either implement `slur(play, play)` or amend DSL_SPEC, with the missing grammar-by-example regression fixture either way. Gate: the *stripped* fixture twin compiles and is checked in as a 1.9 regression fixture; the full fixture now fails with a clean diagnostic at line 135. Touches: `dsl.py` (suffix tokenizer path), `tests/`, possibly `docs/DSL_SPEC.md`. This PR is deliberately boring so it can merge while the rest is debated.

**P1 — Schema and validation (goal Phase 1, no emitter).** `AUTO_TARGETS` gains `pitch_cents`/`dynamic`; curve object definitions in `ir_schema.py` (`points`, sampled encoding, `time_basis`, shape strings); the structured diagnostic codes; capability manifest publishes targets/units/ranges/shapes + support matrix; `docs/ir.schema.json` and grammar artifacts regenerate. Key property to state in the PR description: **no compiler path emits curves yet, so no existing spec hash or golden changes** — schema-only, hash-inert, easy review.

**P2 — Reference evaluator + conformance vectors.** The single shared evaluator (breakpoint + sampled, edge holds, `pow:k`), pure addition, with the golden vector suite including both edge cases. This is the commit future kernels and learned renderers prove themselves against, so it merges before anything consumes it.

**P3 — Legacy lowering: the first hash-transition commit.** `vibrato{}`/`glide_s`/sampler `dynamic` lists compile to explicit curves (glide **linear-in-cents**, k=1 — keep the v2.1 correction visible in the test name), authored forms to `_meta.semantic`, with the analysis-based equivalence regression (pitch-track/loudness deltas under threshold). This is where golden hashes move; isolate it, name both causes in RELEASE_NOTES per the standing policy, and let nothing else ride in this commit.

**P4 — Renderer consumption, split in two.** P4a: the synth path consumes curves through the evaluator (phase-integration path exists; low risk). P4b: the **time-varying sinc resampler + loop law** as its own sub-series — normative kernel/accumulation spec written *first*, golden renders including the looped-sustain case gating it. This is the riskiest patch in the series; giving it its own revert boundary is the point.

**P5 — The DSL sugar (where your grammar gap closes).** Lexer first: the `..` range token (with the decimal-collision test — `0.9b..1.7b` must tokenize as three units, this is the one genuinely new lexical form), the shape token (ratify `pow2.5` single-token; kill the `pow 2.5` spaced variant from my prose sketch), signed unit values in mod position. Then the three `note_mod` alternatives in **both** parsers in the same commit — legacy `dsl.py` and `lark_parser.py` — plus `grammar.py`, regenerated EBNF/GBNF, decompiler emission, and the drift tests binding them; landing it in one parser only manufactures the next V1. Gate: **the full fixture compiles, and its lead-layer IR snapshot matches the conformance doc's §3 excerpt** — that snapshot is the patch's acceptance test, written before the patch.

**P6/P7 — Support-matrix rejection diagnostics (physical models), then interop/decompile round-trip and docs**, per goal Phases 5–6–7, each with its drift tests.

Three mechanics suggestions for *how* you propose it, beyond the ordering. First, write the series as a one-page `docs/PATCH_PLAN_G11.md` that names each PR's gate, file touch-list, and hash impact (none / golden-transition / none…), and link it from goal.md — your repo's culture is "claims carry their evidence," and a patch plan with declared hash impact per commit is the reviewable artifact. Second, make the fixture pair the spine: stripped twin green from P0 onward in CI, full fixture's compile attempt running as an *expected-failure* test that flips to expected-pass at P5 — that gives you a mechanical "are we there yet" signal instead of a judgment call. Third, ride the AF-P4 timing capture (manifest `timing` block + golden-identity quarantine) alongside P1 as its own parallel PR — it's an afternoon, it's hash-inert, and it means P4b's resampler lands against a measured baseline instead of an unmeasured one.

--

## Strict Coding Standards

- Keep changes source-of-truth driven. Do not duplicate registries in docs,
  schema, manifest, or tests when they can be imported from runtime sources.
- Use structured parsers and schema builders instead of ad hoc string parsing
  for IR, DSL, manifest, and JSON behavior.
- Every render-affecting behavior must be explicit in IR or a documented,
  hash-owned renderer primitive.
- No silent fallback. Unsupported native kernels, missing compilers, invalid
  curves, and lossy interop projections must emit structured diagnostics.
- Preserve determinism: no unseeded randomness, no wall-clock dependencies, no
  filesystem-order dependence, and no platform-dependent floating policy
  without a golden test.
- Keep public validation errors stable and specific. A failing test should tell
  the user what contract drifted and how to repair it.
- Prefer small pure functions for curve evaluation, lowering, and validation.
  Renderer integration may be optimized, but the normative rule must remain
  readable and independently testable.
- Preserve fast paths for specs that do not use curves.
- Do not change existing audio semantics accidentally. Any intentional audio
  semantic change needs release-note coverage and golden-hash updates.
- Do not add dependencies without a documented need and a deterministic
  version story.
- Keep code comments sparse and normative: comment DSP laws, hash policy,
  migration behavior, and non-obvious validation choices.
- Tests must follow `test_<unit>_<scenario>_<expected>` naming where practical.
- Tests must not require network access.
- Tests that need large local libraries must fail loudly when the library is
  part of the contract and skip only when the test is explicitly optional.
- Commit implementation and regression tests together.

## Completion Checklist

- [ ] Release target chosen and documented.
- [ ] G11 gap entry present and accurate.
- [ ] IR schema `1.1` published and regenerated.
- [ ] Capability manifest exposes curve metadata and support matrix.
- [ ] Validator rejects all invalid and unsupported curve states loudly.
- [ ] Compiler lowering covers legacy and new performance syntax.
- [ ] Renderers consume curves instead of private expression scalars.
- [ ] Sampler varying-ratio law and loop behavior are specified and goldened.
- [ ] Physical-model staging is manifest-declared and test-gated.
- [ ] Interop import/export behavior is implemented with lossiness diagnostics.
- [ ] Decompile behavior preserves authored expression when available.
- [ ] Docs, schema, grammar, release notes, and examples are synchronized.
- [ ] Full test and coverage gates pass.
