# AudioForge Universal Music IR Schema

`docs/ir.schema.json` is the published JSON Schema for compiled AudioForge IR
specs. The runtime source is `audioforge.ir_schema.ir_json_schema()`, and tests
fail if the checked-in JSON artifact drifts from that source.

## Versioning

- Current IR schema version: `1.1`
- Current policy: additive-compatible
- Supported from: `0.9`, `1.0`

IR schema `1.1` adds explicit performance curves for pitch and dynamics while
preserving the `1.0` shape for specs that do not use curves. Valid `1.0` specs
do not require migration.
Experimental `0.9` fixtures can be migrated with
`audioforge.ir_schema.migrate_ir_spec(spec, "0.9")`; that migration moves the
legacy provenance sidecar from `metadata` to `_meta` without changing
render-affecting fields.

## Field Ownership

The schema divides top-level fields into three ownership layers:

- Semantic intent: `intent`, `emotion`, `intensity_curve`, `score`, `key`,
  `key_map`, `tempo_map`, `groove`, `markers`, `cutdowns`, `stage`, `library`,
  `routing`.
- Expanded render data: `id`, `kind`, `duration_s`, `sample_rate`,
  `bit_depth`, `bpm`, `loop_safe`, `layers`, `buses`, `master`, `variant`,
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

IR schema `1.1` defines one curve object for both note-scoped performance and
layer automation:

- `target`: `pitch_cents`, `dynamic`, or an existing automation target.
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
normalized `[0, 1]`; a note-scoped dynamic curve replaces the layer dynamic
for that note span. Expanded curve data is hash-included. Authored sugar such
as legacy `vibrato`, `glide_s`, and `dynamic` breakpoints may be recorded in
`_meta.semantic.authored_expression` for decompile, and that provenance remains
hash-excluded.

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
