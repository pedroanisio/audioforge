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

## [2.16.0]

_Engine 2.16.0 · DSL 1.9._ The published IR contract was corrected to match the
validator that actually gates rendering (audit findings F1–F7, F12); the DSL
parser was consolidated onto a single Lark grammar (F9); IR schema 1.1 added
explicit `pitch_cents` and `dynamic` curves. See `docs/RELEASE_NOTES.md` for the
detailed prose notes.
