---
disclaimer:
  notice: >-
    No information within this document should be taken for granted.
    Any statement or premise not backed by a real logical definition
    or verifiable reference may be invalid, erroneous, or a hallucination.
  generated_by: "rendered view of docs/backlog.yml; statuses reconciled by Claude Fable 5.1 via Claude Code; revised by Claude Opus 5.5 via Claude Code"
  date: "2026-09-28"
---

# Backlog

## Disclaimer

This work is subject to the methodological caveats and commitments described in DISCLAIMER.md.
> No statement or premise not backed by a real logical definition or verifiable reference should be taken for granted.

Deferred work captured so it is not lost. Nothing here blocks current use unless a current task explicitly promotes it. Statuses were reconciled with git history on 2026-09-05 (docs/evolution/harness.md HARNESS-GOV-001/002): delivered Track E items are `done`, BL-002 is `blocked` because no Actions run has ever executed a job, and BL-032..BL-035 register the engine 3.0.0 release.

**System of record:** `docs/backlog.yml`, structured by `docs/schema/backlog.schema.json`. The YAML is canonical; this table is a rendered view. Effort is expressed as **complexity** (["XS","S","M","L","XL"]), never time. `Owner` records the provenance boundary so concurrent work stays attributable. Roadmap-item IDs (AF-*) are carried in each item's tags and trace to `docs/ROADMAP.md`.

Validate the backlog:

```bash
node scripts/check-backlog-governance.mjs
```

## Items

| ID | Roadmap | Item | Category | Type | Status | Cx | Priority | Owner | Depends on |
|----|---------|------|----------|------|--------|----|----------|-------|------------|
| BL-001 | — | Govern the backlog with schema and drift checks | docs | infra | done | S | high | shared | — |
| BL-002 | AF-R01 | CI pipeline that runs the whole gate on every push | ops | infra | blocked | M | critical | mine | BL-003 |
| BL-003 | AF-R02 | Makefile composing every gate into one make check | tooling | infra | done | S | critical | mine | — |
| BL-004 | AF-R03 | AGENTS.md programmatic CLI and tooling reference | docs | infra | done | S | critical | unassigned | BL-003 |
| BL-005 | AF-R04 | Ruff lint, format, and type-check configuration | tooling | infra | ready | S | critical | unassigned | — |
| BL-006 | AF-R05 | IR-schema generator with --check and --write | tooling | infra | done | S | critical | concurrent | BL-003 |
| BL-007 | AF-R06 | Golden-audio oracle with a committed hash lockfile | testing | infra | done | M | high | concurrent | BL-003 |
| BL-008 | AF-R07 | Persisted capability manifest with a status field and drift gate | tooling | infra | done | M | high | concurrent | BL-006 |
| BL-009 | AF-R08 | Unify the dual IR source of truth into one typed model | tooling | tech-debt | in-progress | L | high | unassigned | BL-006 |
| BL-010 | AF-R09 | CHANGELOG.md plus a version-bump tool with --check | docs | infra | done | S | high | unassigned | — |
| BL-011 | AF-R10 | MCP server over the agent_tools facade (stdio) | feature | feature | done | L | medium | unassigned | BL-008 |
| BL-012 | AF-R11 | Docs site (mkdocs-material) with generated pages and a build gate | docs | infra | done | M | medium | unassigned | BL-006, BL-008 |
| BL-013 | AF-R12 | ADR set (docs/adr/) and an adoption rule | docs | infra | done | S | medium | unassigned | — |
| BL-014 | AF-R13 | Codebase-standards ratchet and wire drift_inspect.py into the gate | tooling | infra | done | S | medium | unassigned | BL-003 |
| BL-015 | AF-R14 | src/ layout and a package-boundary AST gate | tooling | tech-debt | ready | M | low | unassigned | BL-003 |
| BL-016 | AF-R15 | Migration codemod keyed to validator rejection codes | tooling | infra | blocked | M | low | unassigned | BL-006, BL-009 |
| BL-017 | AF-R16 | Cross-platform numeric-determinism pack | testing | research | ready | L | low | unassigned | BL-007 |
| BL-018 | AF-M01 | Pitch-class-set theory core (normal/prime form, IC-vector, Tn/TnI) | feature | feature | done | M | high | mine | BL-007 |
| BL-019 | AF-M02 | Formal transformation operators and transformation networks | feature | feature | ready | M | medium | unassigned | BL-018 |
| BL-020 | AF-M03 | Neo-Riemannian triadic transformations (P/L/R, UTT) and Tonnetz | feature | feature | blocked | M | medium | unassigned | BL-018, BL-019 |
| BL-021 | AF-M04 | Scale and mode system (modes, pentatonic, octatonic, maximally-even) | feature | feature | ready | M | high | unassigned | BL-018 |
| BL-022 | AF-M05 | Tuning and temperament engine (activate the inert tuning directive) | feature | bug | ready | L | high | unassigned | BL-007 |
| BL-023 | AF-M06 | Voice-leading as optimization (minimal-displacement / VL geometry) | feature | feature | blocked | M | medium | unassigned | BL-018, BL-021 |
| BL-024 | AF-M07 | Functional-harmony grammar (roman numerals, cadences, progressions) | feature | feature | blocked | L | low | unassigned | BL-020, BL-021 |
| BL-025 | AF-R17 | Explicit filter-automation targets (auto lowpass / highpass / bandpass) | feature | feature | ready | S | medium | unassigned | — |
| BL-026 | AF-R18 | Always-on dead-air assertion in the render path | testing | feature | ready | S | medium | unassigned | BL-025 |
| BL-027 | AF-R19 | Unified render-assertion policy surface | tooling | tech-debt | blocked | M | low | unassigned | BL-025, BL-026 |
| BL-028 | AF-X01 | General sieve engine (residual-class sieves for scales and rhythm) | feature | feature | ready | M | medium | unassigned | — |
| BL-029 | AF-X02 | Seeded stochastic composition primitives | feature | feature | ready | L | high | unassigned | — |
| BL-030 | AF-X03 | Dynamic stochastic synthesis oscillator (GENDYN-style) | feature | feature | blocked | M | low | unassigned | BL-029 |
| BL-031 | AF-X04 | Positioning decision: deterministic ground truth under generative music AI | docs | research | ready | XS | low | unassigned | — |
| BL-032 | ADR-0007 | Engine 3.0.0 musical-correctness release (epic) | feature | bug | in-progress | XL | critical | mine | BL-007 |
| BL-033 | ADR-0007 | Audio semantics A1-A4: gain once, note-off release, anti-alias resampling, explicit mastering | feature | bug | in-progress | L | critical | mine | BL-032 |
| BL-034 | ADR-0007 | Musical semantics M1-M6: harmony, phrases, technique fidelity, repeats, performance identity, analysis | feature | bug | in-progress | XL | critical | mine | BL-032 |
| BL-035 | — | Release delivery for engine 3.0.0: CI executes, review, merge, consolidated changelog, tags | ops | infra | blocked | M | critical | mine | BL-002, BL-032 |
| BL-036 | ADR-0007 | Single owner for layer gain | feature | tech-debt | ready | M | medium | unassigned | BL-032 |
| BL-037 | ADR-0007 | Automation target attributes on the AUTO_TARGETS registry | tooling | tech-debt | ready | S | medium | unassigned | BL-032 |
| BL-038 | ADR-0007 | Explicit scheduling context for performance identity | feature | tech-debt | ready | M | medium | unassigned | BL-032 |
| BL-039 | ADR-0007 | Expanded parts may be silent without a fabricated note | feature | tech-debt | ready | S | medium | unassigned | BL-032 |
| BL-040 | ADR-0007 | Producers carry diagnostic codes; retire message inference | feature | tech-debt | ready | M | medium | unassigned | BL-032 |
| BL-041 | ADR-0007 | Render path cleanups from the 3.0 review | tooling | tech-debt | ready | S | medium | unassigned | BL-032 |
| BL-042 | ADR-0007 | Render-plan size and validate cost for sections and loop-safe assets | feature | tech-debt | ready | M | medium | unassigned | BL-032 |
| BL-043 | ADR-0007 | Vectorize beat-based automation and share one timeline factory | feature | tech-debt | in-progress | M | medium | unassigned | BL-032 |
| BL-044 | ADR-0007 | Decide the IR schema version format | docs | research | ready | S | medium | unassigned | BL-032 |
| BL-045 | ADR-0011 | Notation surface: semantic contract with oracle-verified interchange (epic) | feature | tech-debt | in-progress | XL | high | mine | BL-032 |
| BL-046 | ADR-0011 | Oracle toolchain: oracles extra, vendored MusicXML XSD, fixture corpus, oracle-check | testing | infra | done | M | high | mine | BL-045 |
| BL-047 | ADR-0011 | Notated and exact-tick MusicXML export derive structure from the spec | feature | bug | done | L | high | mine | BL-046 |
| BL-048 | ADR-0011 | MusicXML import keeps parts, chords, voices and attribute changes; corpus round trips | feature | bug | done | M | high | mine | BL-046 |
| BL-049 | ADR-0011 | MIDI export: one track per layer and the tempo map | feature | bug | done | S | high | mine | BL-046 |
| BL-050 | AF-M05 | Tuning directive: loud while inert, then an n-EDO resolver with FFT proof | feature | bug | done | M | high | mine | BL-022, BL-045 |
| BL-051 | ADR-0015 | Electronic-production toolkit: modulation/lo-fi effects, bus vocoder, sample editing, five demo tracks | feature | feature | done | L | high | mine | BL-045 |

See `backlog.yml` for each item's full summary, rationale, acceptance criteria, dependencies, references, and live evidence checks.
