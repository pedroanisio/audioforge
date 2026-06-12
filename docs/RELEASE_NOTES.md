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
