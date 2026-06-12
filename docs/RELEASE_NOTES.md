# AudioForge Release Notes

## Current Runtime Contract

- Engine 2.16.0
- DSL 1.10
- Version source of truth: `audioforge.version`

Includes note: DSL 1.10 adds content-pinned `import` directives — reusable
`motif`/`bus` fragments (`.afi`) pulled in by SHA-256 pin
(`import "lib.afi" @ sha256:…`). Resolution is pure substitution before
parsing: the pin is verified (mismatch refuses), the import graph must be
acyclic, diamonds de-duplicate, and the resolved source is what compiles — so an
imported patch is byte-identical to the same patch written inline (same
`spec_hash`, same audio). Import pins are recorded as provenance in
`_meta.imports` (hash-excluded); rendered identity comes from the expanded
events. `audioforge expand` materialises the single resolved file. Namespacing
(`import … as ns`) is a deliberate follow-up (see `docs/adr/0001-dsl-extensions.md`).
Backward compatible: no existing `.af` parses differently and every spec
re-renders byte-identically (the engine version is untouched).

Migration note: DSL 1.10 is the current documented authoring contract and is
backward compatible — every `.af` asset valid under DSL 1.8 (and 1.0-compatible)
parses to an identical AST and requires no source migration. The DSL parser was
consolidated onto a single Lark grammar (`audioforge.lark_parser.LARK_GRAMMAR`);
the legacy regex tokenizer and recursive-descent parser were removed (audit
finding F9). The published EBNF/GBNF artifacts are now derived from that one
grammar, with the GBNF `pitch` rule tightened to the real single-octave-digit
note spelling.

Contract note: Engine 2.16.0 corrects the published IR contract to match the
validator that actually gates rendering (audit findings F1–F7, F12). These are
tightenings — specs previously accepted in error may now be rejected: instrument
layers require a base `bpm` (F1); `env.sustain` is a level bounded 0–1, not a
time (F4); the published JSON Schema no longer lists `lowpass`/`highpass`/
`bandpass` as fx *types* (filters are `{"type":"filter","mode":…}`, F2); base
`bpm` is bounded 20–300 while a `tempo_map` may still reach 400 (F3); `cutoff_hz`
automation must target a real cutoff-capable fx (F12). `swing` and `groove` are
reclassified as render-affecting fields (F7).

Stereo-width note: IR schema 1.2 raises `master.stereo_width`'s ceiling from
`1.0` to `2.0`. The render path already scaled the side signal by `width`; the
schema previously clamped it to `[0, 1]`, so an author could collapse toward
mono but never widen past the as-mixed image. Widening preserves the mid (the
mono sum is unchanged) and is zero in silence (no noise-floor cost). Backward
compatible: every valid `1.0`/`1.1` spec is unchanged and re-renders
byte-identically (the engine version is untouched).

Performance-curve note: IR schema 1.1 adds explicit `pitch_cents` and
`dynamic` curves. Legacy `vibrato`, `glide_s`, and authored dynamic breakpoints
now lower to hash-included curve data before render; `_meta.semantic` keeps the
authored expression only for provenance and decompile. Synth notes and sampled
instrument notes consume these curves directly. Sampled pitch curves use a
time-varying source-read ratio with cumulative source position, including
looped sustain regions. Physical-model pitch curves still reject with
`curve_unsupported_voice` until each kernel is staged.

Render-plan note: AF-P2 adds derived `audioforge.render-plan/1` artifacts.
`audioforge plan` and `AudioAsset.plan()` expose sampled routes, synthetic
articulation fallbacks, synth/native routes, evidence, diagnostics, and
reserved cost fields before render. `routing.fallbacks` and
`routing.stretch_warn_semitones` are hash-included policy inputs. Render
manifests now stamp `plan_hash` and exports write `<id>.plan.json`; session
bundles include the plan artifact. `render --plan` recomputes and refuses stale
plans before audio computation. The first landing keeps audio behavior
unchanged while formalizing current routing decisions.

Determinism note: `ENGINE_VERSION` is folded into the `spec_hash` payload
(`audioforge.determinism`). Re-rendering an unchanged spec under Engine 2.16.0
therefore yields a different render hash than under 2.15.0 by design; provenance
consumers that pinned 2.15.0 hashes must re-pin against this engine.

## History

### Engine 2.16.0 · DSL 1.9

- DSL parser consolidated onto a single Lark grammar; the legacy regex tokenizer
  and recursive-descent parser were removed (audit finding F9). Authoring surface
  is unchanged — `.af` assets parse to identical ASTs (pinned by a golden
  snapshot regression).
- IR contract corrected to match the validator (audit findings F1–F8, F10–F14);
  see the Contract note above. The published `docs/ir.schema.json` is regenerated.
- AF-P1 performance curves are explicit IR: `pitch_cents` and `dynamic` curves
  validate under IR schema 1.1, publish support metadata in the capability
  manifest, render in synth and sampled-instrument paths, and diagnose lossy
  MIDI/MusicXML projections.
- AF-P2 render plans are first-class derived artifacts: manifests stamp
  `plan_hash`, exports and session bundles include `.plan.json`, and CLI/SDK/
  agent surfaces can generate, explain, and stale-verify plans.
- Backward compatible for authoring: no `.af` source migration required.
- Render hashes recompute under the new engine version and legacy performance
  lowering may change compiled IR for assets that use `vibrato`, `glide_s`, or
  authored dynamic breakpoints (see Determinism note).

### Engine 2.15.0 · DSL 1.8

- Engine and DSL minor version bump from Engine 2.14.0 · DSL 1.7.
- Backward compatible: no `.af` source migration required.
- Render hashes recompute under the new engine version (see Determinism note).

### Engine 2.14.0 · DSL 1.7

- Version metadata alignment; DSL 1.7 documented as the authoring contract.
- DSL 1.0-compatible assets remained valid with no source migration.
