# Goal Map: AF-P3 / G13 Expressive Performance Techniques

This file maps implementation work to
`docs/doc-requirements-architecture-expressive-performance-techniques-done.md`.
That done requirements-architecture document is the normative source of
truth. If this file and that document disagree, follow the done document and
update this map in the same change.

## Current State

- Source contract: `docs/doc-requirements-architecture-expressive-performance-techniques-done.md`
- Lifecycle state: `done`; the source contract filename suffix matches its
  lifecycle state
- Validation state: implementation validated by focused regression gates and the
  full repository gate
- Ledger state: P0, P1, P1·R3, P2, P2·R3, P3, P4, P4·R3, P5, and P6 are
  `done-validated`
- Implementation status: AF-P3/G13 source, fixtures, docs, release notes, and
  regression tests are mapped to the source contract
- Reserved target: Engine 2.17.0 / DSL 1.11; current runtime remains Engine
  2.16.0 / DSL 1.9
- Latest full gate: `./scripts/run_tests.sh` passed on 2026-06-12
  (`511 passed, 2 skipped, 6 warnings`)
- Latest focused AF-P3/G13 gate: `./.venv/bin/python -m pytest
  tests/test_docs_regression.py tests/test_expressive_techniques_acceptance.py
  tests/test_expressive_techniques_schema.py
  tests/test_expressive_techniques_lowering.py tests/test_ai_agent_dsl.py
  tests/test_manifest_registry_coverage.py tests/test_ir_schema.py
  tests/test_performance_curves_render.py -q` passed on 2026-06-12
  (`117 passed`)

## Objective

Implement AF-P3 / G13 so AudioForge can author and render expressive
performance techniques as explicit, deterministic IR rather than renderer-private
behavior.

The target outcome has three capabilities:

1. **R1: Note-scope timbre curves.**
   Notes can carry hash-included `cutoff_hz`, `gain_db`, and `scan` curves in
   addition to existing `pitch_cents` and `dynamic` curves.

2. **R2: Technique registry.**
   Named techniques such as `palm_mute`, `dead_note`, `let_ring`, `accent`,
   `tenuto`, `staccatissimo`, `harmonic`, `sul_ponticello`, and `sul_tasto`
   lower deterministically to explicit IR primitives.

3. **R3: Instrument mechanics.**
   Fretted/stringed authoring gains first-class `tuning`, `string`, and `fret`
   semantics. `string` + `fret` derive pitch authoritatively and are
   hash-included IR fields.

## Scope Boundaries

In scope:

- Add IR/schema validation for note-scope timbre curves.
- Add a single-source `TECHNIQUES` registry.
- Add pure lowering for techniques and timbre escape hatches.
- Add renderer support for supported note-scope timbre curves.
- Add `tuning`, `string`, and `fret` mechanics with deterministic pitch
  resolution.
- Add synth-only synthetic position-to-timbre lowering through `cutoff_hz`.
- Add validation diagnostics, capability manifest entries, fixtures, tests,
  docs, and release notes.

Out of scope:

- True per-string multisampled timbre.
- Fingering optimization or automatic tab generation.
- General ornament engine beyond the specified techniques.
- Per-note custom ADSR objects.
- Real-time or MPE input.
- Learned technique generation.
- Speculative DSP kernels. A kernel is allowed only when necessary and viable
  under the source contract's DSP Kernel Policy.

## Readiness Gates

Do not start Phase 1 until every DoR item in the source contract is satisfied.
The current known gates are:

- Reserve the DSL/engine version target for AF-P3/G13: done
  (Engine 2.17.0 / DSL 1.11).
- Add the G13 entry to `docs/DSL_GAP_SPEC.md`: done.
- Confirm G11 is present on HEAD: done.
- Agree the acceptance fixture coverage: done via the source contract fixture/rejection
  set in the source contract.
- Resolve or explicitly assign OQ-1: assigned as a standalone prerequisite
  before P4.
- Run the full gate on HEAD before first implementation change: done
  (`./scripts/run_tests.sh`).
- Open a coordination task and confirm a quiet tree for each editing session:
  repeat for every implementation slice.
- Accept or flag the R3 tuning model constants for P2 ratification: accepted as
  starting constants unless P2 records a ratified adjustment.

## Execution Order

Follow the source contract phase order exactly:

1. **P0: Preflight.**
   Reserve versions, add the G13 gap entry, confirm G11, verify the full DoR,
   and update the source contract ledger.

2. **P1: Schema, manifest, validation.**
   Add `NOTE_SCOPE_TARGETS`, `TECHNIQUES` skeleton, diagnostics,
   capability/schema generation, and R3 IR fields/validation. This phase must be
   hash-inert for existing golden outputs.
   **Status:** done-validated.

3. **P2: Pure lowering.**
   Add `lower_technique()`, `cutoff()` / `level()` / `scan()` lowering, pinned
   technique constants, string/fret pitch resolution, and synth
   position-to-timbre lowering.
   **Status:** done-validated.

4. **P3: Renderer integration.**
   Make renderers consume note-scope `cutoff_hz`, `gain_db`, and `scan` through
   the shared curve evaluator. This is the isolated hash-moving phase.
   **Status:** done-validated.

5. **P4: DSL, grammar, decompile, drift.**
   Add `tech NAME(params)`, curve escape hatches, layer `tuning`, note
   `string`/`fret`, decompile round-trip, and all grammar artifacts in one
   commit.
   **Status:** done-validated.

6. **P5: Support matrix and gating.**
   Enforce synth/sampled/physical support rules, exact diagnostic codes, and
   per-cell acceptance/rejection tests.
   **Status:** done-validated.

7. **P6: Docs, fixtures, release notes.**
   Add `static/fixtures/expressive_techniques.af`, rejection fixtures, golden IR
   snapshots, release notes, docs sync, and final ledger updates.
   **Status:** done-validated.

8. **Lifecycle closure.**
   Transition the source contract to `done` and update the filename suffix in
   the same change, per its §9 lifecycle rules.
   **Status:** done-validated.

## Required Diagnostics

Use the canonical codes from the source contract. Do not invent alternate
names.

- `note_curve_unsupported_target`
- `note_curve_unsupported_voice`
- `scan_requires_morph_osc`
- `duplicate_note_timbre_curve`
- `curve_unsupported_voice`
- `technique_unknown`
- `technique_unsupported_voice`
- `technique_param_out_of_range`
- `technique_layer_override`
- `technique_fallback`
- `tuning_required_for_string_fret`
- `string_out_of_tuning`
- `fret_out_of_range`
- `string_fret_pitch_conflict`
- `position_timbre_unsupported`

## Definition of Done

The work is done only when the source contract's DoD is satisfied. In this
map, that means:

- IR `1.2` validates supported note-scope timbre curves and rejects unsupported
  target/voice combinations.
- `TECHNIQUES` is the single source for technique definitions, params, support,
  and lowering docs.
- Techniques lower to explicit hash-included IR; renderers never receive a
  private "technique" concept.
- `string`/`fret`/`tuning` validate, resolve pitch authoritatively, reject
  conflicts, and round-trip through decompile.
- Capability manifest, schema docs, grammar artifacts, runtime constants, and
  tests are synchronized.
- Unsupported support-matrix cells fail with the canonical diagnostic codes.
- Acceptance and rejection fixtures compile/fail as expected.
- Existing valid IR `1.1` specs remain valid and no-feature renders stay
  byte-identical.
- No-curve render throughput regresses by no more than 2%; the regression guard
  proves no-curve synth and sampled renders do not invoke curve evaluation.
- `./scripts/run_tests.sh` passes.
- The source contract ledger reaches `done-validated`, lifecycle status
  reaches `done`, and filename suffix updates according to the lifecycle rules.

## Required Tests

Add or update tests in the same commits as implementation:

- Unit tests for `NOTE_SCOPE_TARGETS`, duplicate timbre curves, `scan`/`morph`
  gating, technique registry shape, params, and ranges.
- Compiler tests for every technique lowering and every escape-hatch lowering.
- R3 tests for standard tuning pitch resolution, open/fretted notes, tuning
  absence, string/fret range, and explicit-pitch conflict.
- Renderer tests for per-note `cutoff_hz`, `gain_db`, and `scan` behavior.
- Regression tests proving no-feature IR `1.1` behavior remains unchanged.
- Drift tests for generated schemas, capability manifest, techniques, targets,
  and grammar artifacts.
- Acceptance tests for `static/fixtures/expressive_techniques.af`.
- Rejection tests for every canonical diagnostic code.
- P6 acceptance/rejection coverage lives in
  `tests/test_expressive_techniques_acceptance.py`, with fixtures at
  `static/fixtures/expressive_techniques.af` and
  `static/fixtures/rejections/expressive_*.af`.

## Strict Coding Standards

- Define `NOTE_SCOPE_TARGETS` and `TECHNIQUES` once in runtime code.
- Reuse `audioforge.curves.validate_curve` and `evaluate_curve`.
- Keep lowering and validation pure and independently testable.
- Do not create a second curve or automation subsystem.
- Keep renderer behavior data-driven and hash-owned.
- Use typed `DSLError`, `SpecError`, or `CurveError`; do not raise raw user-input
  exceptions.
- Do not use `eval`, dynamic imports, or open-ended technique names.
- Keep diagnostics line/path cited where possible.
- Keep grammar, EBNF, GBNF, docs, and tests synchronized in the same change.
- Update the source contract's §10 ledger and `meta.updated`
  whenever implementation state changes.

## Guitar Fixture Implication

The current `slash_inspired_v3` experiment is only a stopgap. The durable path
for guitar-like expressivity is R1 + R2 + R3:

- R1 supplies explicit note-level timbre and level data.
- R2 makes techniques authorable as names rather than hand-authored curves.
- R3 gives guitar notes string/fret/tuning identity so a later per-string
  sampled library can consume those fields without changing the IR.

AF-P3/G13 closes the authoring and IR path for guitar-like expressivity, but
sampled guitar realism remains limited by the current sampler and available
libraries. Do not treat manual curve-heavy fixtures as the final architecture.
