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

Tooling note (AF-R05, 2026-07-04): `docs/ir.schema.json` is now a *generated*
artifact owned by `python -m audioforge.tools.gen_ir_schema` (`--write` to
regenerate, `--check` to fail on drift with a unified diff). The canonical
serialization is `sort_keys=True, indent=2`; `make schema-check` runs the
`--check` twin and is a `make check` prerequisite, so CI (AF-R01) fails if the
committed schema drifts from `ir_json_schema()`. This is not a runtime-contract
change and carries no version bump — the schema bytes are byte-identical; only
how they are regenerated and gated is new. Never hand-edit `docs/ir.schema.json`;
edit `audioforge/ir_schema.py` (the source of truth) and rerun `--write`.
(AI-authored: Claude Opus 4.8 via Claude Code.)

Gate note (AF-R06 / AF-R07 / AF-R03, 2026-07-04): three new gates join
`make check` (so CI runs them), each a real generator/oracle with no runtime
contract change and no version bump.
- **AF-R06 golden-audio oracle** — `tests/golden/audio/` (5 short specs) is pinned
  by `tests/golden/audio.lock.json` (SHA-256 per spec; **no WAVs committed**).
  `python -m audioforge.tools.render_golden --check` re-renders and gates drift:
  strict exact-hash when the numeric env matches the lock, advisory when it differs
  (cross-env float drift is AF-R16, not a regression), `--strict` forces failure.
  ε for cosmetic-vs-real classification is a −120 dBFS per-sample max-abs bound.
- **AF-R07 capability manifest** — `docs/capability-manifest.json` is now committed
  and owned by `python -m audioforge.tools.gen_capability` (`--write`/`--check`),
  with a predicate-derived per-capability `status` (`stable` = pure-Python;
  `experimental` = native-kernel/env-dependent). Every diagnostic code is now
  documented in the generated `docs/DIAGNOSTIC_CODES.md`, gated by the same tool.
- **AF-R03 `AGENTS.md`** — the programmatic CLI/tooling reference `CLAUDE.md`
  points to now exists; `tests/test_agents_md_sync.py` gates its verb list against
  `cli.py`.
(AI-authored: Claude Opus 4.8 via Claude Code.)

Gate + agent-surface note (AF-R09 / AF-R13 / AF-R10, 2026-07-05): two more gates
join `make check` and the agent surface gains an MCP server. No runtime-contract
change and no version bump.
- **AF-R09** — `CHANGELOG.md` (Keep-a-Changelog) plus
  `python -m audioforge.tools.bump_version` (`--check`, `<version>`, `--dry-run`):
  a coordinated bump across `version.py`/`pyproject.toml`/`README.md`/`CHANGELOG.md`
  with `make version-check` gating that every version literal equals `version.py`.
- **AF-R13** — `scripts/drift_inspect.py` (registry-drift detector, long built but
  never invoked) is now wired into `make check` as `drift-check`, and
  `docs/codebase-standards.md` records the engineering bar as an honest
  `[Enforced]`/`[Adopted]`/`[Target]` ratchet with a source-of-truth-per-topic map.
- **AF-R10** — `python -m audioforge.mcp` is a stdio MCP server exposing the nine
  `agent_tools.run_tool` ops plus `capabilities`/`verify` (pure pass-throughs);
  a `render` call emits session resources (manifest, WAV, waveform PNG) a
  vision-capable agent can read back. Pure-Python; no new dependency.
(AI-authored: Claude Opus 4.8 via Claude Code.)

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
