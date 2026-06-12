# AudioForge Release Notes

## Current Runtime Contract

- Engine 2.16.0
- DSL 1.9
- Version source of truth: `audioforge.version`

Migration note: DSL 1.9 is the current documented authoring contract and is
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

AF-P3/P1 schema note: IR schema 1.2 is an additive schema/validation surface for
expressive performance techniques. It publishes note-scope timbre targets
(`cutoff_hz`, `gain_db`, `scan`), the `TECHNIQUES` registry skeleton, canonical
diagnostic codes, and fretted/stringed mechanics fields (`tuning`, `string`,
`fret`, `max_fret`). Existing valid IR 1.1 specs remain valid and no-feature
renders remain byte-identical; pure lowering and renderer timbre consumption are
staged after this schema slice.

AF-P3/P2 compiler note: expressive techniques now lower in the compiler to
explicit note data, note-scope curves, and layer fx. `palm_mute`, `dead_note`,
`let_ring`, `accent`, `tenuto`, `staccatissimo`, `harmonic`,
`sul_ponticello`, and `sul_tasto` do not create a renderer-private technique
channel. Curve escape hatches lower to `cutoff_hz`, `gain_db`, and `scan`, and
string/fret authoring resolves pitch plus synth-only position-to-timbre cutoff
curves. Renderer consumption of the new timbre curves remains the staged AF-P3/P3
hash-moving phase.

AF-P3/P3 renderer note: note-scope timbre curves are now consumed by renderers.
Synth note rendering applies absolute `cutoff_hz` lowpass envelopes, additive
`gain_db` envelopes, and per-note morph `scan` envelopes through the existing
curve evaluator. Sampled instrument rendering applies supported note
`gain_db`; sampled `cutoff_hz` and `scan` remain validation rejects because the
sampler has no per-voice filter or morph voice.

AF-P3/P4 DSL note: the authoring grammar now accepts note modifiers
`tech NAME(k=v)`, `cutoff(Nhz)`, `level(Ndb)`, `scan(N)`, `string N`, and
`fret N|x`, plus layer `tuning:` and `max_fret:`. The decompiler preserves
these authored modifiers through the semantic sidecar and suppresses their
lowered curves to avoid double-applying techniques on round-trip.

AF-P3/P5 support note: the support matrix is pinned by per-cell regressions for
note-scope curves and techniques across synth, sampled, and physical voices.
Unsupported cells reject or fall back with canonical diagnostics.

AF-P3/P6 acceptance note: `static/fixtures/expressive_techniques.af` now serves
as the end-to-end expressive-techniques fixture, covering note-scope timbre,
registered techniques, and string/fret/tuning mechanics. Sibling rejection
fixtures pin the canonical diagnostics for unsupported scan, duplicate timbre
curves, and unsupported physical-model pitch curves.

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
- AF-P3/P1 adds the additive IR schema 1.2 contract for note-scope timbre
  targets, technique registry publication, diagnostics, and string/fret/tuning
  validation. This is hash-inert for existing no-feature specs.
- AF-P3/P2 adds compiler-side pure lowering for registered techniques, curve
  escape hatches, and string/fret pitch plus synth position-timbre derivation.
  Renderer consumption of `cutoff_hz`, `gain_db`, and `scan` remains staged.
- AF-P3/P3 wires note-scope timbre curves into rendering: synth voices consume
  `cutoff_hz`, `gain_db`, and morph `scan`, while sampled instruments consume
  supported note `gain_db`.
- AF-P3/P4 adds the DSL/decompile surface for techniques, curve escape hatches,
  and string/fret/tuning mechanics.
- AF-P3/P5 adds support-matrix gating regressions for curves and techniques.
- AF-P3/P6 adds the acceptance fixture, golden IR snapshot regression, and
  rejection fixtures for the expressive-techniques contract.
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
