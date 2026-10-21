---
disclaimer:
  notice: >-
    No information within this document should be taken for granted. Claims
    require verification against the implementation and its acceptance tests.
  generated_by: "GPT-6 via Codex; revised by Claude Opus 5.5 via Claude Code"
  date: "2026-09-28"
---

# AudioForge Release Notes

## Current Runtime Contract

- Engine 3.3.0
- DSL 2.0
- IR schema 2.1
- Version source of truth: `audioforge.version`

Engine 3.3.0 is the first release published as installable artifacts (GitHub Release
`engine-3.3.0`: wheel, sdist, `SHA256SUMS`). Earlier distributions built from this
repository omitted the C kernel sources that every render compiles
([ADR-0012](adr/0012-native-dsp-kernels-bounded-drift.md)) and the bundled samples, so an
installed engine could not render. Both now ship as package data, the bundled samples and
impulse responses resolve from any working directory (`./samples` still takes precedence),
and `make package-check` installs the built wheel into a clean environment and renders
from outside the repository before anything is published. The release also carries the
integrated feature work recorded in `CHANGELOG.md` under 3.3.0: physical-voice pitch
curves by varispeed, rendered layer pitch rides, multi-oscillator notes layers, the video
cue library and scene resolver, n-EDO tuning that renders, LilyPond engraving, the
electronic-production effects, content-pinned `.af` includes, sound match and the
render-quality A/B tooling. Spec hashes include the engine version, so every 3.2.0 spec
hash changes; regenerate manifests with this engine. DSL 2.0 sources remain valid.

Engine 3.2.0 renders with about 4.4x less CPU over the example corpus (short CLI renders
~7.5x less) by moving streaming DSP to native kernels, batching FFT convolution and
parsing with LALR. Output is not bit-identical to 3.1.0: every example stays within
-131 dBFS of it (sources and sizes in the migration guide's "Engine 3.2: render cost
and numeric drift"); regenerate manifests and golden hashes with this engine. Renders
now always require a C compiler ([ADR-0012](adr/0012-native-dsp-kernels-bounded-drift.md)),
so the capability `status` now separates core-engine capabilities (`stable`) from those
that also need a dedicated physical-model or effect kernel (`experimental`) rather than
pure Python from native. The same release ships the notation and interchange line
([ADR-0011](adr/0011-notation-interchange-oracles.md)): structure-preserving MusicXML and
MIDI export/import, the construct × format coverage matrix in [INTEROP.md](INTEROP.md),
and the optional `oracles`/`engrave` extras. DSL 2.0 authoring is unchanged.

Engine 3.1.0 preserves native stereo instrument recordings and adds explicitly
mapped recorded note transitions. Stereo mixes change level and image; review
their balance and regenerate manifests with this engine. DSL 2.0 authoring
remains compatible. The [playback guide](ORCHESTRAL_PLAYBACK.md) describes the
library mapping, evidence and limits; [ADR-0009](adr/0009-native-stereo-recorded-transitions.md)
records the decision. The revised First Light demonstration retains the original
audio for comparison and validates the complete 300-second delivery.

Migration is required for audio expectations: corrected gain, note gates,
resampling, mastering, repeats and performance identity intentionally change
renders. Review the [engine 3 migration guide](MIGRATION_3.md) and regenerate
manifests after review. [ADR-0007](adr/0007-musical-render-semantics.md) records
the decision; the [acceptance ledger](MUSICAL_CORRECTNESS.md) tracks proof.

## Unreleased on main

Integrated 2026-10-10 from `feat/notation-interchange`, `feat/electronic-production` and
`claude/render-quality-comparison-5krec4`; see the `[Unreleased]` section of the changelog.

- n-EDO tuning renders ([ADR-0014](adr/0014-n-edo-tuning-resolution.md)); the default
  12-TET path is unchanged. `audioforge score --engrave` engraves through LilyPond.
- Electronic production effects ([ADR-0015](adr/0015-electronic-production-effects.md)):
  `phaser`, `flanger`, `chorus`, `bitcrush`, bus `vocoder:`, sample `offset`/`length`/
  `reverse`/`stretch`/`slices`.
- Content-pinned `import` directives ([ADR-0016](adr/0016-dsl-extensions.md)), resolved by
  pure substitution before parsing; `audioforge expand` writes the resolved file.
- IR schema 2.1 raises `master.stereo_width`'s ceiling from 1.0 to 2.0 (M/S widening; the
  mid is preserved, so the mono sum is unchanged). 2.0 specs are unaffected.
- Sound match (`audioforge.match`) and the render-quality A/B (`audioforge.quality`,
  [RENDER_QUALITY_COMPARISON.md](RENDER_QUALITY_COMPARISON.md)).

## Engine 2.16.0 and DSL 1.9 history

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

Decisions + docs note (AF-R12 / AF-R08 / AF-R11, 2026-07-05): no runtime-contract
change and no version bump.
- **AF-R12** — `docs/adr/` holds a template plus six backfilled architecture
  decision records (determinism oracle, non-vocal scope, IR-is-truth, native
  kernels fail-loud, IR source-of-truth, generator-owns-artifact). AGENTS.md §7
  records the adoption rule: IR-contract / determinism / public-surface changes
  ship with an ADR.
- **AF-R08 Phase A** — the generated JSON Schema already derived its enums from
  `schema.py`; the last duplicated literal (filter modes) is now a single
  `FILTER_MODES` registry, and `tests/test_schema_sources_sync.py` gates that every
  generated enum equals its registry. Schema bytes unchanged. **Phase B** (a typed
  Pydantic model) is deferred to the operator (ADR-0005).
- **AF-R11** — `mkdocs.yml` + `python -m audioforge.tools.gen_docs` generate
  `docs/reference.md` (from `ir.schema.json`) and `docs/capabilities.md` (from
  `capability-manifest.json`); `make docs-gen-check` gates them in `make check`,
  and `make docs` runs `mkdocs build --strict`.
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
