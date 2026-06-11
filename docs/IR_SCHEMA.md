# AudioForge Universal Music IR Schema

`docs/ir.schema.json` is the published JSON Schema for compiled AudioForge IR
specs. The runtime source is `audioforge.ir_schema.ir_json_schema()`, and tests
fail if the checked-in JSON artifact drifts from that source.

## Versioning

- Current IR schema version: `1.0`
- Current policy: additive-compatible
- Supported from: `0.9`, `1.0`

IR schema `1.0` formalizes the existing compiled spec shape. Valid current
specs do not require migration.
Experimental `0.9` fixtures can be migrated with
`audioforge.ir_schema.migrate_ir_spec(spec, "0.9")`; that migration moves the
legacy provenance sidecar from `metadata` to `_meta` without changing
render-affecting fields.

## Field Ownership

The schema divides top-level fields into three ownership layers:

- Semantic intent: `intent`, `emotion`, `intensity_curve`, `score`, `key`,
  `key_map`, `tempo_map`, `groove`, `markers`, `cutdowns`, `stage`, `library`.
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
