---
disclaimer:
  notice: >-
    No information within this document should be taken for granted. Any statement
    or premise not backed by a real logical definition or verifiable reference may
    be invalid, erroneous, or a hallucination.
  generated_by: "Claude Opus 4.8 via Claude Code"
  date: "2026-07-05"
---

# Changelog

All notable changes to AudioForge are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions track
`ENGINE_VERSION` in `audioforge/version.py` (the single source of truth).
`docs/RELEASE_NOTES.md` holds the detailed prose history; this file is the
structured, per-version summary. Version consistency across sites is gated by
`python -m audioforge.tools.bump_version --check` (AF-R09, `make version-check`).

## [Unreleased]

_Notation and interchange line (ADR-0011; `docs/evolution/roadmap-notation.xlsx`)._

### Added
- `oracles` and `engrave` extras (music21, xmlschema, LilyPond) and `make oracle-check`, which
  runs `tests/test_notation_oracles.py` against the MusicXML 3.1 XSD and music21 and skips
  loudly when the extra is absent.
- `tests/fixtures/notation`: a ten-piece notation corpus with expected structure; the MusicXML
  3.1 schema is vendored under `tests/fixtures/musicxml/xsd`.
- `tuning_not_rendered` diagnostic: a non-12-EDO `tuning:` directive compiles with a loud
  warning instead of rendering 12-TET silently.
- `audioforge.musicxml`: the MusicXML exporters and importer, re-exported by `audioforge.interop`.
- `audioforge.interop.COVERAGE` / `coverage()`: the construct × format registry that drives
  `interop_diagnostics()`, the capability manifest (`interop.coverage`, `notation.directives`)
  and the generated `docs/INTEROP.md` (`python -m audioforge.tools.gen_interop`,
  `make interop-check`). New codes: `lossy_slur`, `lossy_hold`, `lossy_polymeter`,
  `lossy_pickup`, `lossy_meter_unit`, `lossy_repeat`, `lossy_key_change`, `lossy_tuning`,
  `lossy_string_fret`, `lossy_marker`, `unsupported_layer_type`; the four legacy lossy codes
  are now registered too.
- `tests/test_notation_oracles.py` gains the chord-root parity and ambiguity-set tests
  (`docs/MIGRATION_3.md` names the 120 ambiguous collections), the Bach chorale corpus round
  trip, and a LilyPond zero-warning engraving pass over the fixture corpus.

### Changed
- The notated MusicXML export takes meter beats and unit, bar length, a global meter with `lossy_polymeter`,
  `key_map`, `tempo_map` (thinned to the quantization grid, stepped at its points) and
  `pickup` (an implicit first measure) from the spec; `export-musicxml --bars` is now an
  override that defaults to the spec meter.
- The exact-tick MusicXML export writes one part per pitched layer with `<chord/>` groups and
  `<backup>` cursor moves; the MIDI export is a format-1 file with a conductor track (time
  and key signature, every tempo point) and one track per layer on its own channel.
- `import_musicxml` reads one layer per `<part>` (named from `part-name`), follows the
  MusicXML cursor (`<chord/>`, `<backup>`, `<forward>`, voices), honours per-measure
  divisions, key, time and tempo, merges ties, and lists unrepresentable constructs under
  `_meta.import.dropped`.
- The notated MusicXML export also writes dynamics (marks and hairpins), articulations
  (staccato, spiccato, marcato, tremolo; legato as a slur; pizzicato as pizz./arco), slurs,
  tuplets (`<time-modification>`), lyrics, fermatas (from `holds`), rehearsal marks (from
  `score.sections`), repeat barlines (when the section sits on barlines) and note velocities
  (`dynamics` attribute); the importer reads all of them back. MIDI and the exact-tick export
  carry the performed form (repeats expanded) with section markers, lyric events and key
  changes.
- `audioforge score` is labelled a proof sheet, not engraving.

## [3.1.0]

_Engine 3.1.0 · DSL 2.0._


Native stereo instrument recordings retain their channels through sample
playback, velocity crossfades, loops, effects, seating and stems. Stereo layers
use balance panning with unity at center; mono layers retain constant-power pan.
Older sampled renders can change level and image and should be remastered.

Libraries can declare pinned recordings of exact note-to-note transitions,
including trim offsets, arrival lead, handover time and source provenance.
Plans expose the selected recording and its hash. Missing intervals remain
explicit approximations and fail when fallbacks are forbidden. See
[orchestral playback](docs/ORCHESTRAL_PLAYBACK.md) and
[ADR-0009](docs/adr/0009-native-stereo-recorded-transitions.md).

## [3.0.0] - 2026-09-05

_Engine 3.0.0 · DSL 2.0 · IR 2.0._ Everything since tag `engine-2.16.0` ships in this
release: the Track E engineering-discipline infrastructure landed on `main` in July and
the musical-correctness repair. Existing specs render differently by design; see the
[migration guide](docs/MIGRATION_3.md), [ADR-0007](docs/adr/0007-musical-render-semantics.md)
and the [acceptance ledger](docs/MUSICAL_CORRECTNESS.md). Delivery is governed by
[docs/evolution/harness.md](docs/evolution/harness.md); the tag is applied when its release
gate opens (the date above is the release-branch date and is confirmed at tagging).

### Fixed
- Apply instrument gain once; synth release follows note-off; filter sample transposition to suppress aliasing.
- Preserve quiet mix levels by default. Normalization is explicit and peak safety includes the delivered fade envelope.
- Execute score repeats, including following material, tempo, holds, markers and shaped automation.
- Resolve chord roots across inversions, preserve sevenths and follow modulation for extensions.
- Coordinate performance timing, retain authored phrase gates and isolate random takes from mix edits.
- Restore the Python 3.10 floor (`datetime.UTC`, `tomllib` were 3.11-only); regenerate `uv.lock`.
- `audioforge verify` accepts a single-asset `.af` source and reports non-JSON input as a structured diagnostic instead of a raw decoder error.
- `validate_spec` and the agent `validate` tool no longer rewrite the caller's spec in place; the returned IR is the expanded contract.
- The golden-audio gate is env-aware (strict exact-hash same-env, advisory cross-env) so it neither flaps on cross-platform float drift nor reddens CI.

### Added
- **Engineering-discipline infrastructure (Track E).** A composed local gate
  `make check` (AF-R02) that CI runs (AF-R01); generator + `--check` twins that
  own their committed artifacts — `docs/ir.schema.json` (AF-R05),
  `docs/capability-manifest.json` + `docs/DIAGNOSTIC_CODES.md` with a
  predicate-derived per-capability `status` (AF-R07), and the golden-audio hash
  lock `tests/golden/audio.lock.json` (AF-R06); the agent-facing `AGENTS.md`
  (AF-R03); this `CHANGELOG.md` + the version-bump tool (AF-R09); `drift_inspect`
  wired into the gate + `docs/codebase-standards.md` (AF-R13); an MCP server
  over the `agent_tools` facade (AF-R10); the mkdocs site with generated pages (AF-R11);
  the ADR set and adoption rule (AF-R12).
- Explicit fidelity diagnostics for techniques, sampled legato and section multiplication; strict routing rejects approximations.
- Context-aware audio analysis and seven measured acceptance cases with an optional before/after listening page.
- Stable performance seeds/event IDs and canonical DSL escapes for expanded event/automation IR.
- Harmony, loop-safety and analysis diagnostic codes registered in the capability manifest (38 codes) with repair hints.
- `docs/evolution/`: implementation assessment, delivery roadmap and the verification harness with `scripts/harness.sh` and committed evidence bundles.
- Resampler cost curve and rollback runbook in the migration guide; `tests/test_perf_budget.py`.

### Changed
- Randomness is rooted in `performance_hash(performance_seed, variant)`; `spec_hash` remains the render-contract identity (ADR-0001 amended, ADR-0007).
- Generated schema, capability manifest, docs and golden lock regenerated for engine 3.0.0 / DSL 2.0 / IR 2.0.

## [2.16.0]

<!-- Previous release history follows below. -->

_Engine 2.16.0 · DSL 1.9._ The published IR contract was corrected to match the
validator that actually gates rendering (audit findings F1–F7, F12); the DSL
parser was consolidated onto a single Lark grammar (F9); IR schema 1.1 added
explicit `pitch_cents` and `dynamic` curves. See `docs/RELEASE_NOTES.md` for the
detailed prose notes.
