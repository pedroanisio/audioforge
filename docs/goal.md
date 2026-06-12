---
title: "AudioForge Goal: First-Class Render Plan"
status: active-goal
source_proposal: "../static/refs/AF-P2-render-plan-proposal.md"
scope: "AF-P2 / G12 render-plan artifact between validation and render"
owner: "AudioForge maintainers"
artifact_schema: "audioforge.render-plan/1"
phase_target: "Phase 1 formalization first; Phase 2 authority transfer next"
---

# Goal: First-Class Render Plan

AudioForge must make routing decisions inspectable before audio is rendered.
The target is a deterministic, serializable, diffable render-plan artifact
created after validation/resource resolution and before render. The renderer
must be able to execute exactly the reviewed plan, refuse stale plans, and
record the plan identity in the render manifest.

This goal implements AF-P2 as the next architecture contract after AF-P1. AF-P1
made continuous performance explicit in the IR; AF-P2 makes render routing
explicit outside the IR. The render plan is derived data, not authored data: it
is computed from the compiled spec, resolved library pins, catalog facts, and
engine version.

## Current Problem

The current tree exposes these constraints:

- `catalog.json` already contains the evidence a planner needs: instrument
  renderability, key ranges, pitch keycenters, velocity layers, round-robin
  depth, articulations, missing samples, ignored opcodes, blockers, and pins.
- `validate_spec()` and resource resolution are admission checks. They do not
  produce a whole-timeline routing artifact.
- `audioforge.sampler` makes region selection, velocity-layer selection,
  round-robin choice, and articulation fallback decisions privately at render
  time.
- Synthetic articulation fallbacks are recorded after the fact in the render
  manifest, so authors and agents cannot diff, gate, or repair them before
  compute is spent.
- There is no structural home for route cost estimates, budget-aware degrade
  decisions, future inpainting routes, or AF-P1 curve-excursion segmentation.

The result is a routing gap: a spec can be valid and resolved, yet still hide
important render decisions until after rendering. That blocks policy gates such
as "no synthetic fallback on the lead layer", makes repair agents weaker, and
keeps future throughput/inpainting work from having a stable data contract.

## Target State

Implement a first-class render plan:

- Add artifact schema `audioforge.render-plan/1`.
- Add a deterministic planner that computes `plan = f(spec, resolved pins,
  catalog facts, engine version)`.
- Emit `<id>.plan.json` as canonical JSON with `plan_hash =
  sha256(canonical_plan)`.
- Cover the whole timeline with per-segment decisions. Phase 1 segment
  granularity is one segment per `(layer, note event)` because that matches
  today's sampler decision boundary.
- Record routes, decisions, evidence, diagnostics, policy, and reserved cost
  fields.
- Stamp `plan_hash` into render manifests.
- Include the plan and SHA-256 in session bundles.
- Add CLI and agent-tool surfaces so the plan can be generated, explained, and
  executed intentionally.
- Keep Phase 1 byte-identical with current render behavior.
- Make Phase 2 authoritative: the sampler consumes plan decisions instead of
  re-deriving them.

The plan is outside the spec. Routing policy belongs in the spec and is
hash-included; routing decisions are derived and belong in the plan.

## Non-Goals

- Do not change sampler routing behavior in Phase 1.
- Do not embed derived routing decisions into the IR, `_meta`, or authored DSL.
- Do not implement inpainting in Phase 1. Reserve the `inpaint` route only.
- Do not define the final throughput cost model in Phase 1. Reserve cost fields
  with `estimated_ms: null`.
- Do not add cross-instrument substitution or creative re-orchestration.
- Do not add encryption or access control for plan files; document sensitivity.
- Do not delete the legacy sampler derivation until Phase 2 proves byte
  identity and drift checks are in place.

## Design Rules

1. Derived, not authored: plans are computed artifacts and never source of
   musical intent.
2. Plan/apply discipline: a saved plan is a saved decision; render-from-plan
   must execute exactly that plan or refuse it.
3. Recompute-verify: rendering with `--plan FILE` recomputes the plan and
   compares hashes before audio is computed.
4. Zero behavior change first: Phase 1 must be a formalization of existing
   sampler/native decisions, proven by byte-identical A/B renders.
5. Evidence on every decision: a segment without evidence is invalid for
   routes that depend on catalog or sampler facts.
6. Estimated and actual are separate: estimated costs live in the immutable
   plan; actual timings live in the render manifest.
7. Whole-timeline view: planning sees all layers and notes before any audio is
   rendered.
8. Loud policy: `forbid` failures happen at plan time, not mid-render.
9. Diffable artifacts: plan JSON must be canonical, stable, and reviewable.
10. No hidden fallback: every synthetic substitution, warning, or blocker must
    have a named diagnostic.

## Required Plan Contract

Top-level fields:

- `schema`: exactly `audioforge.render-plan/1`.
- `spec_hash`: render hash of the compiled spec used for planning.
- `engine_version`: current `ENGINE_VERSION`.
- `catalog_pin`: content identity of the catalog facts used for planning when
  available.
- `libraries`: resolved libraries and pins used by sampled layers.
- `policy_effective`: normalized routing policy after defaults.
- `segments`: ordered list of planned timeline segments.
- `plan_hash`: not stored inside the canonical payload being hashed; exposed by
  planner APIs and manifests as the SHA-256 of canonical plan JSON.

Segment fields:

- `id`: stable segment id such as `seg:<layer>:<ordinal>`.
- `layer`: layer name.
- `layer_type`: layer type after compile normalization.
- `note_index`: note-event index when applicable.
- `span`: `{start_beat, dur_beats}` for note-backed segments.
- `route`: one of `sample`, `synthetic_fallback`, `synth_native`; reserved:
  `inpaint`.
- `decision`: route-specific decision payload.
- `evidence`: facts used to justify the decision.
- `diagnostics`: structured strings or objects for fallback, blocker, and
  warning conditions.
- `cost`: object with `estimated_ms`, `estimated_ms: null` in Phase 1.

Route requirements:

- `sample`: must record instrument, articulation resolution, selected region
  identity, sample hash when known, keycenter distance, velocity band or
  dynamic crossfade data, and round-robin pick/path when applicable.
- `synthetic_fallback`: must record requested articulation, fallback name,
  reason, and documented fallback family.
- `synth_native`: must record voice/oscillator family and curve-support verdict
  where relevant.
- `inpaint`: reserved only. A plan using it must fail until F3 implements it.

Policy fields:

```
routing: {
  fallbacks: allow | warn | forbid
  stretch_warn_semitones: N
}
```

Policy defaults:

- Absent `routing` means today's behavior.
- `fallbacks: allow` keeps current fallback behavior.
- `fallbacks: warn` keeps fallback behavior and escalates diagnostics.
- `fallbacks: forbid` converts a would-be fallback into a plan-time failure.
- `stretch_warn_semitones` controls keycenter-distance diagnostics.

## Pipeline Contract

The pipeline must become:

```
compile -> validate -> resolve -> plan -> render
```

Surfaces:

- Python: `audioforge.plan` owns plan schema, construction, canonicalization,
  hashing, validation, and explanation helpers.
- SDK: `AudioAsset.plan()` returns the plan artifact and hash.
- CLI:
  - `audioforge plan spec.af -o out.plan.json`
  - `audioforge plan spec.af --explain`
  - `audioforge render spec.af --plan out.plan.json`
  - `audioforge render spec.af --explain`
- Agent tools:
  - `run_tool("plan", {"spec": ...})`
  - `tool_schemas()` advertises the `plan` operation.
- Capability manifest advertises render-plan support, routes, policy fields,
  and diagnostics.
- Session bundle includes `<id>.plan.json`, its SHA-256, and `plan_hash` in
  `session.manifest.json`.

## Implementation Plan

### Phase 0: Preflight and Source of Truth

- Add or update the G12 render-plan entry in `docs/DSL_GAP_SPEC.md`.
- Confirm existing library/catalog data surfaces and do not invent a duplicate
  catalog schema.
- Identify current sampler routing decisions and extract them into reusable
  pure helpers before adding planner logic.
- Define canonical JSON and hash policy in one place.
- Keep docs, capability manifest, CLI docs, agent-tool schemas, and tests in
  one synchronized change set.

### Phase 1: Formalize Existing Decisions

- Add `audioforge/plan.py`.
- Define `RENDER_PLAN_SCHEMA_VERSION = "audioforge.render-plan/1"`.
- Add plan object builders, canonical serialization, `plan_hash()`, and
  `validate_render_plan()`.
- Generate segments for:
  - sampled instrument notes,
  - synthetic articulation fallbacks,
  - notes/synth/native layers as `synth_native`.
- Record current sampler decisions without changing renderer behavior.
- Share decision helpers between planner and sampler where possible so Phase 1
  does not create two drifting implementations.
- Emit plan artifacts alongside render manifests without changing audio bytes.
- Add `plan_hash` to render manifests.
- Add plan file + hash to `export_session_bundle()`.

### Phase 2: Plan Execution and Staleness Refusal

- Add `render --plan FILE`.
- Recompute the plan from current inputs before render.
- Refuse stale plans with structured diagnostics that name the drifted
  precondition:
  - spec hash,
  - engine version,
  - library pin,
  - catalog pin,
  - policy.
- Make sampled rendering consume plan decisions for region selection,
  velocity-layer choice, round-robin pick, and fallback choice.
- Record actual per-segment timings in the manifest, keyed by segment id.
- Keep legacy derivation available only behind tests until the authority gate is
  proven, then delete it in a later minor release.

### Phase 3: Policy Gates

- Add `routing` policy validation to the IR schema and runtime validator.
- Ensure absent policy is hash-identical for existing specs.
- Implement `fallbacks: allow | warn | forbid`.
- Implement `stretch_warn_semitones`.
- Add plan-time diagnostics and failure modes for policy violations.
- Publish routing policy in `docs/DSL_SPEC.md`, `docs/IR_SCHEMA.md`, and the
  capability manifest.

### Phase 4: CLI, SDK, Agent, and Explain Surfaces

- Add `audioforge plan`.
- Add `--explain` to `plan` and `render`.
- Add human-readable routing tables for explain mode.
- Add `AudioAsset.plan()`.
- Add agent-tool operation `plan` with request/response schema.
- Add capability-manifest drift tests for route enum, policy fields, and
  diagnostics.

### Phase 5: Documentation and Release

- Update:
  - `docs/DSL_SPEC.md`,
  - `docs/IR_SCHEMA.md`,
  - `docs/INTEROP.md` if session bundles change there,
  - `docs/AGENT_TOOLS.md`,
  - `docs/DSL_GAP_SPEC.md`,
  - `docs/RELEASE_NOTES.md`.
- Document plan sensitivity: plan files expose library composition, sample
  paths, and routing decisions.
- Document migration and compatibility: Phase 1 has no IR schema change unless
  `routing` policy is introduced in the same landing.

### Phase 6: Future Intelligence Hooks

These are not Phase-1 completion requirements, but the plan must be shaped so
they can land without schema breakage:

- AF-P1 sub-note segmentation at curve-excursion or keycenter boundaries.
- F4 throughput cost estimator filling `cost.estimated_ms`.
- Budget-aware degrade decisions made visibly at plan time.
- F3 `inpaint` route activation and batch grouping.
- Adjacent fallback merging and expensive-route batching.

## Definition of Done

AF-P2 Phase 1 is done only when all items below are true:

- `audioforge.plan` exists and produces canonical `audioforge.render-plan/1`
  JSON.
- Plans are deterministic for identical spec, pins, catalog, policy, variant,
  and engine version.
- `plan_hash` is stable and changes when any render-relevant planning input
  changes.
- Every sampled-instrument note has a segment with route, decision, evidence,
  diagnostics, and cost fields.
- Every synth/native note-backed segment appears as `synth_native`.
- Synthetic articulation fallbacks appear as explicit `synthetic_fallback`
  decisions before render.
- Phase 1 rendering with planning enabled is byte-identical to rendering
  without planning.
- Render manifests include `plan_hash`.
- Session bundles include the plan file and its SHA-256.
- CLI `plan` and `--explain` surfaces work.
- Agent-tool `plan` operation works and is documented in `tool_schemas()`.
- Capability manifest publishes render-plan routes, schema version, policy
  fields, and diagnostics.
- G12 is present in `docs/DSL_GAP_SPEC.md`.
- Docs and release notes are synchronized.
- All required tests pass through the canonical runner and coverage gate.

AF-P2 Phase 2 is done only when all items below are true:

- `render --plan FILE` recompute-verifies the plan before audio computation.
- Stale plans fail loudly with structured diagnostics.
- The sampled renderer consumes plan decisions instead of privately
  re-deriving region, velocity, round-robin, and fallback choices.
- Per-segment actual timings are written to the manifest.
- Plan-consuming renders remain byte-identical to legacy derivation across the
  fixture corpus.
- Legacy duplicated decision logic is removed after the authority gate is
  proven.

## Required Tests

All tests must be deterministic, isolated, and realistic. Prefer real compiler,
resolver, planner, renderer, catalog, and sampler paths over mocks.

### Planner Contract Tests

- Plan schema accepts valid `audioforge.render-plan/1` artifacts.
- Plan schema rejects unknown routes, missing evidence, malformed spans, and
  missing route-specific decision fields.
- Identical inputs produce byte-identical canonical plan JSON and identical
  `plan_hash`.
- Changing the spec, engine version, library pin, catalog pin, variant, or
  routing policy changes `plan_hash` when it changes routing decisions.
- The plan contains no nondeterministic ordering.

### Evidence Tests

- Every `sample` segment's evidence re-checks against the pinned library/catalog
  facts.
- Key range and keycenter-distance evidence matches selected regions.
- Velocity-layer and dynamic-crossfade evidence matches sampler behavior.
- Round-robin picks match the existing seeded derivation and change across
  variants where current sampler behavior changes.
- Fallback decisions name the requested articulation, resolved fallback, and
  documented reason.

### Zero-Behavior Tests

- A fixture corpus renders byte-identically with and without Phase-1 planning.
- Corpus covers:
  - sampled layers across key ranges,
  - sparse and dense keycenters,
  - velocity layers,
  - dynamic curves,
  - round-robins,
  - supported articulations,
  - unsupported articulations with synthetic fallbacks,
  - synth/native layers.
- Render manifests differ only by planned additive metadata where expected.

### Recompute-Verify Tests

- `render --plan` accepts a fresh matching plan.
- Editing the spec after planning refuses the plan.
- Changing engine version metadata refuses the plan.
- Changing a library pin refuses the plan.
- Changing catalog pin/facts refuses the plan.
- Changing routing policy refuses the plan.
- Failure diagnostics name the drifted precondition.

### Policy Tests

- Absent `routing` preserves existing spec hash behavior.
- `fallbacks: allow` reproduces current behavior.
- `fallbacks: warn` preserves audio and emits escalated diagnostics.
- `fallbacks: forbid` fails at plan time before render.
- `stretch_warn_semitones` emits keycenter-distance diagnostics at the
  configured threshold.

### Surface Tests

- CLI `audioforge plan` writes canonical JSON.
- CLI `audioforge plan --explain` prints a stable routing table.
- CLI `audioforge render --explain` plans and exits without writing audio.
- CLI `audioforge render --plan FILE` executes a verified plan.
- SDK `AudioAsset.plan()` returns the same canonical artifact as CLI.
- Agent `run_tool("plan", ...)` returns structured diagnostics and artifacts.
- `tool_schemas()` includes the plan operation.
- Capability manifest and schema drift tests cover routes, policy fields, and
  diagnostics.

### Bundle and Manifest Tests

- Render manifest includes `plan_hash`.
- Session bundle includes `<id>.plan.json`.
- `session.manifest.json` lists the plan file and SHA-256.
- Actual per-segment timings are absent in Phase 1 or present only where the
  renderer actually records them; estimated costs remain in the plan.

### Drift and Documentation Tests

- Docs enumerate every route, policy field, diagnostic, and artifact field.
- `docs/DSL_GAP_SPEC.md` includes G12.
- `docs/AGENT_TOOLS.md` includes the plan operation.
- Release notes describe Phase 1 zero-behavior formalization and Phase 2
  authority transfer separately.
- Generated schemas and checked-in docs match runtime sources.

### Required Commands

Run these before declaring the goal complete:

```bash
./scripts/run_tests.sh
./.venv/bin/python -m pytest -q
./.venv/bin/python -m coverage run -m pytest
./.venv/bin/python -m coverage report
```

Coverage must respect the repository threshold in `pyproject.toml`
(`fail_under = 90.1`). Planner, hash, policy, recompute-verify, and routing
decision paths are critical paths and should be covered at or above 95%.

## Strict Coding Standards

- Keep the plan derived. Do not store derived routing decisions in the authored
  spec, `_meta`, DSL, or hand-written docs.
- Keep routing policy authored and hash-included. Do not hide policy in the
  plan.
- Use canonical JSON for plan hashing. Do not rely on insertion order that is
  not explicitly controlled.
- Do not duplicate catalog facts manually. Read from the same runtime catalog
  and library resolution surfaces the renderer uses.
- Extract shared decision helpers instead of maintaining separate planner and
  sampler implementations.
- Phase 1 must not change audio bytes. Any byte change is a failure unless the
  goal is explicitly revised.
- Every route decision must carry evidence. No evidence-free `sample` or
  fallback segments.
- No silent fallback. Every substitution, blocker, or warning must be named and
  surfaced before render.
- Recompute-verify must be strict. Do not execute a stale plan partially.
- Keep estimated cost and actual timing in separate artifacts.
- Preserve fast paths where planning is not requested until auto-plan behavior
  is intentionally enabled and tested.
- Keep errors structured and stable. Diagnostics must name the path, route,
  layer, segment, and drifted precondition where applicable.
- Do not add dependencies without a deterministic version and release-note
  rationale.
- Keep comments sparse and normative. Comment plan/hash policy, stale-plan
  refusal, and shared routing laws, not obvious assignments.
- Tests must follow `test_<unit>_<scenario>_<expected>` where practical.
- Tests must not require network access.
- Tests that require optional native kernels or external libraries must either
  use repo-local fixtures or skip with a precise reason already accepted by the
  repo's test style.
- Commit implementation, docs, schema artifacts, and regression tests together.

## Completion Checklist

- [ ] G12 gap entry present and accurate.
- [ ] `audioforge.render-plan/1` schema implemented.
- [ ] `audioforge.plan` planner implemented.
- [ ] Canonical plan JSON and `plan_hash` implemented.
- [ ] Planner covers sampled, synthetic fallback, and synth/native routes.
- [ ] Evidence payloads are complete and testable.
- [ ] Routing policy implemented and hash behavior tested.
- [ ] Manifest records `plan_hash`.
- [ ] Session bundles include plan artifacts.
- [ ] CLI `plan`, `--explain`, and `render --plan` implemented.
- [ ] SDK and agent-tool plan surfaces implemented.
- [ ] Capability manifest advertises render-plan support.
- [ ] Phase 1 zero-behavior A/B render gate passes.
- [ ] Phase 2 recompute-verify and plan-consuming sampler implemented when
      promoted from preview to authority.
- [ ] Docs, schemas, agent docs, gap spec, and release notes synchronized.
- [ ] Full test and coverage gates pass.
