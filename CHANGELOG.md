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


### Added
- **Engineering-discipline infrastructure (Track E).** A composed local gate
  `make check` (AF-R02) that CI runs (AF-R01); generator + `--check` twins that
  own their committed artifacts — `docs/ir.schema.json` (AF-R05),
  `docs/capability-manifest.json` + `docs/DIAGNOSTIC_CODES.md` with a
  predicate-derived per-capability `status` (AF-R07), and the golden-audio hash
  lock `tests/golden/audio.lock.json` (AF-R06); the agent-facing `AGENTS.md`
  (AF-R03); this `CHANGELOG.md` + the version-bump tool (AF-R09); `drift_inspect`
  wired into the gate + `docs/codebase-standards.md` (AF-R13); and an MCP server
  over the `agent_tools` facade (AF-R10).

### Changed
- Nothing yet.

### Fixed
- The golden-audio gate is env-aware (strict exact-hash same-env, advisory
  cross-env) so it neither flaps on cross-platform float drift nor reddens CI.

## [3.0.0]

_Engine 3.0.0 · DSL 2.0 · IR 2.0._ See [migration guidance](docs/MIGRATION_3.md).

### Fixed
- Apply instrument gain once; synth release follows note-off; filter sample transposition to suppress aliasing.
- Preserve quiet mix levels by default. Normalization is explicit and peak safety includes the delivered fade envelope.
- Execute score repeats, including following material, tempo, holds, markers and shaped automation.
- Resolve chord roots across inversions, preserve sevenths and follow modulation for extensions.
- Coordinate performance timing, retain authored phrase gates and isolate random takes from mix edits.

### Added
- Explicit fidelity diagnostics for techniques, sampled legato and section multiplication; strict routing rejects approximations.
- Context-aware audio analysis and seven measured acceptance cases with an optional before/after listening page.
- Stable performance seeds/event IDs and canonical DSL escapes for expanded event/automation IR.

## [2.16.0]

<!-- Previous release history follows below. -->

_Engine 2.16.0 · DSL 1.9._ The published IR contract was corrected to match the
validator that actually gates rendering (audit findings F1–F7, F12); the DSL
parser was consolidated onto a single Lark grammar (F9); IR schema 1.1 added
explicit `pitch_cents` and `dynamic` curves. See `docs/RELEASE_NOTES.md` for the
detailed prose notes.
