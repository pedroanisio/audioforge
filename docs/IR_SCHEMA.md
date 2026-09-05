---
disclaimer:
  notice: >-
    No information within this document should be taken for granted. Claims
    require verification against the implementation and its acceptance tests.
  generated_by: "GPT-6 via Codex"
  date: "2026-09-05"
---

# AudioForge Universal Music IR Schema

`docs/ir.schema.json` is the published JSON Schema for compiled AudioForge IR
specs. The runtime source is `audioforge.ir_schema.ir_json_schema()`, and tests
fail if the checked-in JSON artifact drifts from that source.

## Versioning

- Current IR schema version: `2.0`
- Engine `3.0.0`, DSL `2.0`
- Structural migration inputs: `0.9`, `1.0`, `1.1`, `1.2`, `2.0`

`migrate_ir_spec` preserves numeric authoring intent and marks older inputs for audio review. Gate/release, gain, mastering, randomness and executable-repeat corrections intentionally change sound. This is not an audio-compatibility migration; review renders and regenerate manifests. See [migration guidance](MIGRATION_3.md).

## Field Ownership

The schema divides top-level fields into three ownership layers:

- Semantic intent: `intent`, `emotion`, `intensity_curve`, `score`, `key`,
  `key_map`, `tempo_map`, `markers`, `cutdowns`, `stage`, `library`,
  `routing`.
- Expanded render data: `id`, `kind`, `duration_s`, `sample_rate`,
  `bit_depth`, `bpm`, `swing`, `groove`, `loop_safe`, `layers`, `buses`, `master`, `variant`, `performance_seed`,
  `intensity_scale`.
- Provenance: `_meta`.

`_meta`, `intent`, and `notation` are excluded from render hashes. Source line
numbers, formatting markers, authored intent, notation-only score metadata, and
metadata-only repair notes can change without changing audio identity.
Render-affecting semantics must first expand into explicit `layers`, `buses`, or
`master` fields; those expanded fields remain hash-included.

`_meta.semantic` is the optional semantic preservation sidecar emitted by the
DSL compiler. It records authored smart directives that have a safe inverse,
motif definitions, layer `play` statements, authored note lists, and master
property ownership so decompile can preserve authoring-level constructs without
guessing from expanded render IR.

## Render-Plan Policy

`routing` is authored render policy and is hash-included. It currently supports:

- `fallbacks`: `allow`, `warn`, or `forbid`.
- `stretch_warn_semitones`: optional non-negative warning threshold.

Derived route decisions do not live in the IR. They are emitted as
`audioforge.render-plan/1` artifacts by `audioforge.plan`, keyed by
`plan_hash`, and stamped into render manifests. Rendering with `--plan` performs
recompute verification before audio is computed.

## Performance Curves

`time_offset` shifts the curve clock. `time_map` consists of contiguous `[source_start, source_end, destination]` windows in the declared time basis; the original curve function is evaluated after mapping. This preserves cropped power curves and repeated controls without fitting a different curve. Layer cutoff automation interpolates logarithmically in frequency.

IR schema `2.0` retains one curve object for both note-scoped performance and
layer automation:

- `target`: `pitch_cents`, `dynamic`, `cutoff_hz`, `gain_db`, `scan`, or an
  existing layer/master automation target.
- `time_basis`: `note_beats`, `note_seconds`, `layer_beats`, or
  `layer_seconds`, constrained by scope.
- Breakpoints: `points` as `[time, value]` or `[time, value, shape]`.
- Sampled encoding: `t0`, `rate_hz`, and `values`; these expand to linear
  breakpoints under the same evaluator.

Interpolation is deterministic: `linear` is the default, `hold` keeps the
previous value until the endpoint, and `pow:k` validates `k` in `[0.1, 10]`.
Before the first point the first value holds; after the last point the final
value holds; a single point is a constant curve.

`pitch_cents` is relative to the note or layer base pitch, sums in cents when
multiple in-scope pitch curves apply, and is render data. `dynamic` is
normalized `[0, 1]`; a note-scoped dynamic curve replaces the layer dynamic for
that note span. `gain_db` is additive note gain, `cutoff_hz` is a note-local
voice filter target, and `scan` is a note-local morph position legal only on
`osc: morph`. Expanded curve data is hash-included. Authored sugar such as
legacy `vibrato`, `glide_s`, and `dynamic` breakpoints may be recorded in
`_meta.semantic.authored_expression` for decompile, and that provenance remains
hash-excluded.

## Instrument Mechanics

Hash-included fretted/stringed fields remain:

- `layer.tuning`: ordered open pitch names; index 1 is the first listed string.
- `layer.max_fret`: non-negative integer, defaulted by validation to 24.
- `note.string`: 1-based integer into `layer.tuning`.
- `note.fret`: non-negative integer or `"x"` for a muted string.

When `string`/`fret` are present, validation requires a layer tuning, checks
string and fret feasibility, and rejects an explicit `note`/`freq_hz` that
disagrees with the pitch derived from tuning plus fret. The pure compiler
lowering that emits derived pitch and position timbre is staged separately in
AF-P3/P2.

Structured intent lives under `intent.structured`:

- `render_affecting`: closed enums for `density`, `contour`, and `texture`.
- `metadata`: non-render fields `affect`, `avoid`, `repair`, and `style_text`.
- `expansions`: deterministic records of the explicit IR changes produced by
  render-affecting fields.

## Validation

Use `audioforge.ir_schema.validate_ir_schema(spec)` in tests or agent tools when
the requirement is "published IR schema conformance." It checks schema-owned
metadata boundaries and delegates the render contract to
`audioforge.schema.validate_spec`.
