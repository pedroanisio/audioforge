# Goal: Public-Domain SFZ/Sample Catalog Builder

## Current State

AudioForge can load pinned sample libraries and SFZ-derived regions, but it does
not yet have a safe ingestion pipeline for discovering, downloading, auditing,
normalizing, and packaging public-domain or CC0 samples into reusable
AudioForge-compatible catalogs.

The target is not a generic web scraper. The target is a source-adapter system
that uses public APIs, records license evidence, rejects unclear material, and
builds deterministic SFZ/sample-library artifacts from high-quality source
audio.

## Traceability Status

This goal is mapped to the AudioForge expressive-performance architecture
contract, because the sample-catalog builder is the library-onboarding path for
real recorded instrument coverage, especially guitar/stringed-instrument
coverage that AF-P3/G13 intentionally deferred from the renderer.

Binding source resolution for this checkout:

- Requested source:
  `docs/doc-requirements-architecture-expressive-performance-techniques-approved.md`
  is not present.
- Active source:
  `docs/doc-requirements-architecture-expressive-performance-techniques-done.md`
  is the lifecycle successor. Its metadata records operator approval and
  validated completion on 2026-06-12, so it is the binding contract for this
  map until a new `*-approved.md` file is added.
- Related architecture inputs:
  `static/refs/AF-P1-performance-curves-proposal-v2.1.md`,
  `static/refs/AF-P2-render-plan-proposal.md`, `docs/DSL_SPEC.md`,
  `docs/capability.schema.json`, and `audioforge/capabilities.py`.

The mapping is implemented in four places in this document:

- `Mapping To AudioForge Architecture Contracts` translates the governing
  architecture rules into sample-catalog boundaries.
- `Expressive-Performance Requirement Mapping` maps AF-P3/G13 requirement
  families to catalog-builder equivalents.
- `Detailed AF-P3/G13 Traceability` gives requirement-by-requirement
  implementation evidence and regression expectations.
- `Definition Of Done`, `Required Tests`, and `Coding Standards` turn the
  mapping into completion gates.

If a future `*-approved.md` requirements file appears, update all four mapping
surfaces, the implementation phase plan, and the DoD/tests/coding standards in
the same change. Do not let `docs/goal.md` point at one lifecycle document while
its traceability tables encode another.

## Source Coverage Checklist

This checklist is the direct map from the active architecture sources to this
goal. A future edit that changes one mapped source section must update the
listed goal sections and gates in the same change.

| Source section | Requirement carried into this goal | Goal sections that own it | Completion gate |
| --- | --- | --- | --- |
| `docs/doc-requirements-architecture-expressive-performance-techniques-done.md` §0 and PALS note | Treat generated/source-derived output as untrusted until verified. | `Mapping To AudioForge Architecture Contracts`; `Definition Of Done`; `Required Tests` | Evidence, analysis, SFZ, manifest, review, and approved sample bytes are rejected when hash/evidence verification fails. |
| `docs/doc-requirements-architecture-expressive-performance-techniques-done.md` §1.3 and §4.5 | True per-string multisampled timbre is a library-onboarding problem, not renderer magic. | `Traceability Status`; `Render-Plan Handoff Contract`; `Current Execution Map`; `Guitar realism` row | Guitar catalog fixtures distinguish source-proven mechanics from unavailable mechanics and never fabricate per-string coverage. |
| `docs/doc-requirements-architecture-expressive-performance-techniques-done.md` §2 FR/NFR/ER/OR | New musical surfaces must lower to explicit, deterministic, hash-owned data with named diagnostics. | `Detailed AF-P3/G13 Traceability`; `Definition Of Done`; `Coding Standards` | Region facts, fallbacks, rejections, license evidence, and loader blockers are persisted as deterministic artifact data. |
| `docs/doc-requirements-architecture-expressive-performance-techniques-done.md` §5-§7 | DoR, DoD, and tests are hard gates, not prose guidance. | `Implementation Plan`; `Definition Of Done`; `Required Tests` | No P0-P7 phase is complete without focused tests plus adjacent drift/contract validation evidence. |
| `docs/doc-requirements-architecture-expressive-performance-techniques-done.md` §8 | Reuse proven primitives and existing evaluators; add new abstractions only when necessary and testable. | `Codebase Mapping`; `Contract Decisions`; `Coding Standards` | Builder output is validated through `parse_sfz()`, `load_library()`, `_decode_wav_bytes()`, `Catalog.build()`, and existing manifest hashing. |
| `docs/doc-requirements-architecture-expressive-performance-techniques-done.md` §10 and §11 | Preserve idempotency: inspect completed work, coordinate edits, and extend validated slices. | `Current Execution Map`; `Definition Of Done`; `Coding Standards` | Agents follow `.agent-tasks`, preserve unrelated dirty work, and report fresh validation before calling a slice done. |
| `static/refs/AF-P2-render-plan-proposal.md` §1-§5.4 | Routing decisions need local coverage evidence, not assertions or renderer-private choices. | `AF-P2 Render-Plan Traceability`; `AF-P2 Proposal Section Mapping`; `Render-Plan Handoff Contract` | Approved manifests expose `library_pin`, `sample_identity`, coverage, quality, mechanics, and diagnostics without source-site access. |
| `static/refs/AF-P2-render-plan-proposal.md` §5.5-§5.7 | Policy, costs, inpaint, and planner authority belong to the render-plan bounded context, not this builder. | `Contract Decisions`; `Implementation Plan`; `Coding Standards` | Sample-catalog code produces plan-ready evidence only; it does not add planner authority, hidden route decisions, or renderer source awareness. |
| `static/refs/AF-P2-render-plan-proposal.md` §8 | Determinism, evidence integrity, policy visibility, surface drift, and session-bundle checks define the future planner gate. | `Required Tests`; `Definition Of Done` | Sample-catalog tests provide deterministic fixture evidence for catalog facts, hashes, fallback/blocker diagnostics, and public CLI/capability drift. |

## Traceability Maintenance Rules

This map is binding, not explanatory background. A goal change is incomplete if
it updates only one side of the contract.

- If the expressive-performance contract changes, update `Source Coverage
  Checklist`, `Direct AF-P3/G13 Requirements Map`, `Detailed AF-P3/G13
  Traceability`, `Definition Of Done`, `Required Tests`, and `Coding Standards`
  in the same change.
- If the sample-catalog implementation adds a source adapter, artifact schema,
  manifest field, CLI command, diagnostic, approval state, or render-plan
  handoff field, update the relevant mapping row and add or update the
  regression gate named by that row.
- A mapping row is not satisfied by prose. It is satisfied only by a local
  artifact owner plus a deterministic regression, audit, or drift test.
- Any catalog behavior must be classified as build-time source intelligence,
  persisted evidence, or runtime loader behavior. Source/API/OAuth behavior is
  allowed only in the build-time class; approved runtime loading is local,
  pinned, and source-agnostic.
- If a requirement cannot be mapped to a deterministic artifact and test, add it
  to `Open Questions` and keep it out of implementation until the missing
  contract is resolved.

## Architecture-To-Gate Index

Use this table as the shortest route from the expressive-performance contract to
the sample-catalog completion gates.

| Architecture obligation | Sample-catalog invariant | Required proof surface |
| --- | --- | --- |
| PALS/output verification | Upstream metadata, inferred analysis, generated SFZ, manifests, review state, and approved bytes are untrusted until verified. | Schema-version checks, evidence-hash checks, sample-byte hash checks, and loader/audit rejection tests. |
| Smart authoring, austere IR | Source search, license normalization, analysis, grouping, and SFZ writing happen before approval; render receives only explicit local library data. | Runtime import-boundary tests plus approved fixture loading through `load_library()` and `Catalog.build()`. |
| Determinism and hash honesty | Re-running fixture inputs produces stable evidence, analysis, SFZ, manifests, and review outputs; render-affecting data is hash-owned. | Golden/canonical-hash tests for generated artifacts and approval/audit tests for stale or forged hashes. |
| Single-source public contracts | Source IDs, accepted licenses, schema versions, diagnostics, CLI names, and supported SFZ subset have one runtime owner. | Capability/docs/CLI drift tests and schema-version rejection tests. |
| Support matrices and named fallbacks | Missing mechanics, missing articulations, unsupported formats/opcodes, candidate-only state, and loader blockers are named artifact data. | Review, manifest, SFZ, and catalog-diagnostics tests asserting exact strings. |
| R3 true multisampling deferral | Guitar realism comes from source-proven sample coverage only; absent string/fret/tuning/session data is explicit. | Guitar fixture tests for source-proven mechanics, unavailable mechanics, and no fabricated per-string coverage. |
| DoR/DoD/test discipline | No P0-P7 phase is complete from implementation presence alone. | Focused sample-catalog tests, adjacent drift/contract tests, and a reported full-suite gate before completion claims. |

## Direct AF-P3/G13 Requirements Map

The expressive-performance requirements document is complete for AF-P3/G13, but
it explicitly defers true recorded per-string multisampling to library
onboarding. This goal owns that deferred onboarding path. The map below states
how each binding AF-P3/G13 section constrains the sample-catalog builder.

| AF-P3/G13 section | Binding rule | `docs/goal.md` mapping |
| --- | --- | --- |
| §0 Meta-instructions and PALS requirement | Treat generated or model-derived output as untrusted; update lifecycle artifacts idempotently. | Source/API metadata, inferred pitch/mechanics, generated SFZ, manifests, and review state are untrusted until fixture-tested, hash-verified, and persisted as local evidence. |
| §1.1 R1/R2/R3 goal | Expressivity enters the engine as explicit, hash-owned primitives and registry-backed lowerings. | Catalog intelligence runs before approval and lowers to explicit samples, SFZ regions, manifests, evidence hashes, diagnostics, and loader-visible coverage. |
| §1.3 out-of-scope true per-string multisampled timbre | AF-P3/G13 does not record or onboard per-string sample libraries. | This builder may add real recorded guitar/string coverage only through evidence-backed catalogs; it must not fake per-string timbre, fingering, or human-performance claims. |
| §2 FR-1 to FR-16 | New musical facts must validate, fail with named diagnostics, and stay visible in IR/capability surfaces. | Catalog facts must validate through named source/license/quality/SFZ/loader diagnostics and remain visible in candidate, review, manifest, and capability surfaces. |
| §2 NFR-1 to NFR-5 | Determinism, hash honesty, backward compatibility, and build-time lowering are mandatory. | Candidate search results, downloads, analysis, grouping, SFZ, manifests, and promotion metadata must be deterministic, content-addressed, and isolated from runtime rendering. |
| §2 PR/ER/OR/AR | Authoring must be auditable, single-source, drift-tested, and coordinated. | Public sample-catalog commands, artifact schema versions, accepted licenses, source IDs, and diagnostics require shared constants plus docs/capability/CLI drift tests. |
| §3 architecture | Rich authoring compiles to explicit data; renderers consume data, not private concepts. | Source adapters, heuristics, OAuth, and network logic stay under `audioforge/sample_catalog/*`; approved catalogs load as ordinary local AudioForge libraries. |
| §4 detailed contract and diagnostics | Support matrices and canonical diagnostics are part of the contract. | Generated manifests/review artifacts must record actual coverage, unavailable mechanics, fallback/blocker strings, unsupported opcodes/formats, and candidate-only state. |
| §5 Definition of Ready | Work starts only after contracts, versions, fixtures, gates, and coordination are clear. | P0 freezes source contracts, license identifiers, evidence/candidate schemas, current loader/SFZ/catalog integration points, and task coordination. |
| §6 Definition of Done | Completion is requirement-by-requirement and validation-backed. | The sample-catalog DoD requires verified discovery, evidence, downloads, analysis, SFZ, manifests, review/promotion, loader acceptance, drift tests, and render-plan handoff facts. |
| §7 Tests | Tests are deterministic, isolated, realistic, and named by expected behavior. | All source behavior uses injected transports or recorded fixtures; generated audio fixtures replace live network or third-party corpus dependencies. |
| §8 Coding standards and DSP policy | Reuse existing primitives; add new machinery only when necessary, deterministic, and testable. | Reuse `parse_sfz()`, `load_library()`, `_decode_wav_bytes()`, `Catalog.build()`, and manifest hashing before adding new catalog abstractions. |
| §9-§11 lifecycle, ledger, and agent instructions | Do not redo validated work; update ledgers/state with evidence and follow coordination. | Future agents must inspect this goal, current sample-catalog tests/artifacts, and `.agent-tasks` before extending or declaring a phase complete. |
| §12-§16 assumptions, risks, validation evidence, and decision log | Assumptions and superseded decisions remain explicit. | Catalog assumptions, open questions, and future changes to accepted licenses, source adapters, or approval policy must stay recorded in this goal or a successor contract. |

## AF-P3/G13 Requirement Coverage Matrix

This matrix is the requirement-by-requirement map from the binding
expressive-performance contract to this sample-catalog goal. The AF-P3/G13
document owns note-scope expressivity and instrument mechanics; this goal owns
the deferred library-onboarding side needed for real recorded sample coverage.
Rows below are complete for the AF-P3/G13 FR/NFR/PR/ER/OR/AR requirement IDs.

| AF-P3/G13 ID(s) | Binding obligation | Sample-catalog obligation | Proof gate |
| --- | --- | --- | --- |
| FR-1, FR-2, FR-3 | Note-scope curve facts are explicit, validated, voice-gated, and duplicate-safe. | Generated catalog regions must expose only explicit render facts: sample path/hash, keycenter, key/velocity ranges, loop data, articulation, evidence ID, and diagnostics. No hidden analysis heuristic may affect approved rendering. | `tests/test_sample_catalog_sfz.py` and `tests/test_sample_catalog_manifest.py` assert stable region facts, supported SFZ opcodes, and manifest-owned diagnostics. |
| FR-4, FR-5, FR-6, FR-7, FR-8, FR-9, FR-10 | Techniques are registry-backed authoring constructs that lower deterministically and publish support/diagnostic data. | Source adapters, accepted licenses, artifact schemas, CLI command names, generated SFZ opcodes, review states, and diagnostics must be runtime-owned constants reflected in docs and capabilities. | `tests/test_manifest_registry_coverage.py`, `tests/test_cli_docs_sync.py`, and sample-catalog schema tests fail on registry/docs/capability drift. |
| FR-11 | Overrides and fallbacks are observable diagnostics, not silent behavior. | Missing articulation, reduced mechanics metadata, rejected candidates, withheld loops, ignored opcodes, and loader blockers must be persisted as review/manifest data. | Review and manifest tests assert stable warning, fallback, rejection, and blocker strings. |
| FR-12, FR-13, FR-14, FR-15, FR-16 | String/fret/tuning are first-class musical facts; true per-string timbre is deferred to library onboarding unless source-proven. | Guitar/string catalogs may preserve source-proven string, fret, tuning, position, pack, and session data, but must mark missing mechanics explicitly and must not infer fingering or per-string sample coverage from generic pitch samples. | Guitar fixture coverage in sample-catalog analysis/manifest tests distinguishes source-proven mechanics from `unavailable` mechanics. |
| NFR-1 | Identical inputs produce deterministic artifacts. | Search fixtures, downloads, evidence JSON, analysis summaries, SFZ, manifests, review reports, and promotion outputs must serialize stably and avoid wall-clock data in hash-owned artifacts. | Golden/canonical-hash tests regenerate fixture artifacts and compare byte output or canonical hashes. |
| NFR-2 | Render-affecting data is hash-owned; provenance-only metadata is hash-excluded. | Sample bytes, evidence records, license bundles, manifests, approved state, and review metadata used for loader acceptance must be hash-verified. Review prose that does not affect loading must not change render pins. | Audit, promotion, and loader tests reject forged evidence hashes, stale bundle hashes, sample-byte mutation, and candidate-only catalogs. |
| NFR-3 | Existing IR/library behavior remains backward compatible. | Existing `ingest`, `libgen`, SFZ parsing, `load_library()`, and normal rendering must keep working; catalog fields are additive or gated. | Existing sampler/library/CLI tests run with sample-catalog fixture tests. |
| NFR-4, NFR-5 | Expressive lowering is pure and does not tax the runtime fast path. | Source search, license normalization, audio analysis, grouping, and SFZ generation stay build-time. Runtime library loading remains local, offline, and source-agnostic. | Import-boundary and loader tests prove source adapters, OAuth, HTTP clients, and downloader code are not required by render/library paths. |
| PR-1, PR-2 | Authoring should expose usable musical outcomes, not require hand-built primitives. | Review reports must give a normal AudioForge audition/render path, and approved fixture catalogs must be consumable through `library: "name@manifest_sha256"` references. | Review tests assert audition snippets; fixture tests load or render approved catalogs through public library APIs. |
| PR-3, PR-4 | Public musical names are conventional and future extension is registry-driven. | Instrument/source/license/articulation names must be stable, lowercase where applicable, and extended through adapter/constant registries rather than ad hoc strings. | Registry drift tests and CLI choices fail when public names diverge from runtime constants. |
| ER-1, ER-2, ER-3 | Single-source registries and existing primitives must be reused. | Reuse `parse_sfz()`, `load_library()`, `_decode_wav_bytes()`, `Catalog.build()`, manifest hashing, and structured sample-catalog constants before adding new abstractions. | Focused tests exercise those existing APIs on generated fixtures instead of testing private builder internals only. |
| ER-4 | Grammar/docs artifacts must move together when public syntax changes. | New sample-catalog CLI commands, source names, and generated-library examples must update `docs/DSL_SPEC.md`, `docs/goal.md`, capability output, and parser choices together. | CLI/docs sync tests cover command families and sample-catalog subcommands. |
| ER-5 | Generated schemas and capability docs must equal runtime sources. | Artifact schema IDs, accepted licenses, source adapters, command names, diagnostics, and SFZ subset must stay in runtime/docs/capability lockstep. | Capability schema and goal-map regressions assert exact literals from runtime registries. |
| OR-1 | Every change must leave the gate green. | A sample-catalog phase is incomplete without focused tests plus adjacent drift/contract validation; completion reports must name fresh commands. | Phase completion requires focused sample-catalog tests, doc/capability drift tests, and a reported full-suite gate where feasible. |
| OR-2 | Hash-moving changes are isolated and documented. | Promotion, manifest-hash, sample-hash, or license-bundle changes must be explicit version/pin moves and must not silently mutate approved catalogs. | Promotion/audit tests detect stale pins and require synchronized review metadata. |
| OR-3, OR-4 | Fallbacks and support problems are observable user-facing diagnostics. | Unsupported licenses/sources/formats/opcodes, missing evidence, candidate-only state, missing samples, and unrenderable SFZ must surface as structured diagnostics or typed CLI errors. | CLI, review, manifest, and loader tests assert exact diagnostic strings instead of tracebacks. |
| AR-1, AR-2, AR-3 | Agents must inspect the ledger, satisfy readiness, and execute in order. | Future work starts from this goal, existing tests/artifacts, and P0-P7 phase order; no validated slice should be restarted without operator rework. | Final reports cite the active phase, changed files, and fresh validation evidence. |
| AR-4 | State and lifecycle artifacts stay synchronized. | Any change that alters source adapters, license policy, schemas, commands, diagnostics, phase state, or DoD/test gates updates this map and related sections in the same change. | Goal-map regression fails if public runtime contract literals disappear from `docs/goal.md`. |
| AR-5 | Scope must not widen to deferred or forbidden work. | Do not implement arbitrary crawling, unclear-license ingestion, synthetic/AI samples, fingering inference, renderer-private sample behavior, or fabricated per-string claims. | Non-goal rows plus hardening tests quarantine unsupported sources/licenses and prove runtime remains source-agnostic. |
| AR-6 | Editing is coordinated and collision-aware. | Agents use `.agent-tasks`, inspect dirty state, preserve unrelated work, and release locks when done. | Process evidence in final reports; coordination state is not a replacement for automated artifact tests. |

## Research Basis

Use these source policies and APIs as the initial implementation basis:

- Creative Commons CC0 deed:
  `https://creativecommons.org/publicdomain/zero/1.0/`
  - CC0 allows copy, modification, distribution, performance, and commercial use
    without permission.
  - CC still disclaims warranty over copyright status, so AudioForge must retain
    provenance and review evidence.
- Creative Commons Public Domain Mark:
  `https://creativecommons.org/public-domain/pdm/`
  - PDM identifies works free of known copyright restrictions.
  - CC warns against using PDM for works with limited or hybrid public-domain
    status; the builder must quarantine uncertain jurisdictional cases.
- Freesound API:
  `https://freesound.org/docs/api/resources_apiv2.html`
  - Provides search, filters, pagination, fields selection, tags, type filters,
    pitch/note descriptors, ratings, and download resources.
  - Downloads require OAuth2.
- Internet Archive metadata:
  `https://archive.org/developers/metadata-schema/index.html`
  - Provides item metadata and file metadata, including license/right fields
    when present.
- Wikimedia Commons imageinfo API:
  `https://www.mediawiki.org/wiki/API:Imageinfo`
  - Provides file URL, SHA-1, MIME type, media type, and selected metadata.
- Openverse:
  `https://api.openverse.engineering`
  - Useful for discovery across CC/public-domain sources.
  - Canonical download and license verification must still happen against the
    upstream source.
- SFZ format:
  `https://sfzformat.com/` and `https://www.linuxsampler.org/sfz/`
  - Plain-text region mapping format for sample-based instruments.

## Objective

Build an AudioForge catalog builder that can:

1. Discover high-quality public-domain or CC0 instrument samples from supported
   public sources.
2. Download only license-approved candidates.
3. Store samples content-addressably with provenance and license evidence.
4. Analyze audio quality and musical metadata.
5. Group samples into playable instrument libraries.
6. Emit conservative SFZ mappings plus AudioForge `library.manifest.json` files.
7. Require human review before a generated library becomes an approved catalog.

## Non-Goals

- Do not crawl arbitrary websites.
- Do not ingest "royalty-free", "free download", `CC-BY`, `CC-BY-SA`,
  `CC-BY-NC`, or unclear-license assets by default.
- Do not bypass source APIs, authentication requirements, rate limits, or terms.
- Do not treat Openverse search results as license proof; they are discovery
  leads only.
- Do not infer public-domain status from age, filename, uploader text, or search
  snippets alone.
- Do not generate synthetic samples or AI-resynthesized instruments in this
  goal.
- Do not create an opaque binary catalog format. Generated artifacts must remain
  diffable and auditable.

## License Policy

The default accepted license set is intentionally narrow:

- `CC0-1.0`
- Creative Commons Public Domain Mark / no-known-copyright status
- Explicit source metadata stating public domain with a stable source URL and
  no contradictory license fields

Everything else is quarantined.

Each accepted sample must carry a license evidence record:

```json
{
  "source": "freesound|internet_archive|wikimedia_commons|openverse_discovery",
  "source_id": "stable upstream id",
  "source_url": "canonical source page",
  "download_url": "canonical file URL used",
  "license_name": "CC0-1.0",
  "license_url": "https://creativecommons.org/publicdomain/zero/1.0/",
  "rights_text": "raw source rights field when available",
  "creator": "uploader or creator when available",
  "fetched_at": "ISO-8601 UTC",
  "evidence_hash": "sha256 of normalized evidence JSON"
}
```

The builder must preserve this evidence in every downstream artifact. A library
without complete evidence is invalid.

## Architecture

### Components

- `audioforge/sample_catalog/sources.py`
  - Source adapter interfaces.
  - Implementations for Freesound, Internet Archive, Wikimedia Commons, and
    Openverse discovery.
- `audioforge/sample_catalog/licenses.py`
  - License normalization and allow/quarantine decisions.
  - Public-domain evidence model.
- `audioforge/sample_catalog/download.py`
  - Rate-limited, resumable downloader.
  - Hash verification and content-addressed storage.
- `audioforge/sample_catalog/analyze.py`
  - Audio decoding and quality analysis.
  - Pitch, duration, level, silence, clipping, transient, channel, and loop
    candidate extraction.
- `audioforge/sample_catalog/group.py`
  - Instrument grouping, pitch mapping, velocity grouping, articulation mapping,
    and pack/session preference.
- `audioforge/sample_catalog/sfz.py`
  - Conservative SFZ writer.
  - Region generation from analyzed candidates.
- `audioforge/sample_catalog/manifest.py`
  - AudioForge `library.manifest.json` emission and validation.
- `audioforge/sample_catalog/review.py`
  - Candidate review reports, playable examples, and promotion gates.
- CLI integration under `audioforge sample-catalog ...`.

### Codebase Mapping

This goal must build on the current AudioForge sample-library surfaces instead
of introducing a parallel catalog format.

| Existing surface | Current role | Required mapping |
| --- | --- | --- |
| `audioforge/library.py` | Owns `library.manifest.json`, manifest hashing, `add_library_path()`, `load_library()`, byte verification, SFZ region loading, and sample decoding. | Generated catalogs must emit manifests that `load_library()` can resolve and verify. Any manifest schema extension must be additive or isolated in sidecars until the loader is intentionally upgraded. |
| `audioforge/sampler.py` | Owns the executable SFZ subset through `parse_sfz()`. Runtime regions support key ranges, velocity ranges, ADSR, loop fields, transpose/tune, volume, and round-robin opcodes. | Generated SFZ must target this subset only. Unsupported opcodes, `#include`, `$define`, and speculative format features are invalid for generated approved catalogs. |
| `audioforge/catalog.py` | Owns the queryable instrument catalog and renderability verdicts. `Catalog.build()` scans SFZ libraries, registers the root with `add_library_path()`, reports ignored opcodes, missing samples, unsupported formats, key ranges, velocity layers, and round-robin counts. | Every generated candidate must be validated with `Catalog.build(candidate_root)` before review. Approved catalogs must appear renderable through this catalog surface. |
| `audioforge/_sndfile.py` and `audioforge/library._decode_wav_bytes()` | Define the supported decode path: WAV always, FLAC/Ogg/MP3/AIFF only when libsndfile is available. | Audio analysis and quality gates should reuse the same decode capabilities or record stricter analysis-only dependencies explicitly. A sample accepted by analysis must also be decodable by the runtime loader. |
| `audioforge/cli.py` | Owns top-level CLI commands. Existing library commands are `ingest` for local sample snippets and `libgen` for manifest generation. | Add `sample-catalog` as a grouped command family without changing `ingest` or `libgen` semantics. `sample-catalog build-sfz` may call the same manifest generation contract instead of duplicating it. |
| `scripts/catalog_instruments.py` | Thin script over `audioforge.catalog.Catalog`. | Treat this as a legacy/export example. New builder logic belongs under `audioforge/sample_catalog/`; script-level wrappers may be added later if needed. |
| `libraries/` | Current default library search root. | Generated/downloaded assets stay outside git under `_catalog/`. Reviewed catalogs may be exposed through `add_library_path("_catalog/approved")` and scanned via `Catalog.build("_catalog/approved")`. |

### Public Runtime Contract Constants

These literals are part of the public sample-catalog contract and must stay
synchronized with runtime constants, CLI choices, the capability manifest, and
tests:

- Builder version: `audioforge.sample-catalog/1`.
- Artifact schemas:
  - `audioforge.sample-catalog.analysis/1`
  - `audioforge.sample-catalog.candidate/1`
  - `audioforge.sample-catalog.evidence/1`
  - `audioforge.sample-catalog.licenses/1`
- Accepted license identifiers:
  - `CC0-1.0`
  - `PDM`
  - `PUBLIC-DOMAIN`
- Source adapter IDs:
  - `freesound`
  - `internet_archive`
  - `wikimedia_commons`
  - `openverse_discovery`
- CLI source names:
  - `freesound`
  - `internet-archive`
  - `wikimedia-commons`
  - `openverse`
- Sample-catalog CLI commands:
  - `search`
  - `resolve-openverse`
  - `download`
  - `analyze`
  - `build-sfz`
  - `audit-license`
  - `review`
- Generated SFZ opcode subset validated by
  `audioforge.sampler.parse_sfz`:
  - `ampeg_attack`
  - `ampeg_release`
  - `hikey`
  - `hivel`
  - `lokey`
  - `lovel`
  - `pitch_keycenter`
  - `sample`
  - `seq_length`
  - `seq_position`
- Review gate literals:
  - `candidate`
  - `approved`
  - `LICENSES.json`
  - `license_evidence_hash`
  - `review.status=approved`
  - `review.reviewer`
  - `manifest_sha256`
- Manifest diagnostics fields:
  - `catalog_diagnostics`
  - `render_blockers`
  - `ignored_opcodes`
  - `missing_samples`

### Mapping To AudioForge Architecture Contracts

This goal is a catalog-build pipeline, not a new render engine. It must follow
the same architectural discipline used by the completed expressive-performance
work and the AF-P2 render-plan proposal: authoring/build-time intelligence is
allowed; runtime execution stays explicit, pinned, deterministic, and
auditable.

Requirement source resolution:

- The requested source document name
  `docs/doc-requirements-architecture-expressive-performance-techniques-approved.md`
  is not present in this checkout.
- The present lifecycle successor is
  `docs/doc-requirements-architecture-expressive-performance-techniques-done.md`.
  Its metadata records operator approval and validated completion on 2026-06-12,
  so this goal treats it as the binding approved contract until a new
  `*-approved.md` requirements file is added.
- Any future replacement of that source must update this mapping, the phase
  plan, required tests, and coding standards in the same change.

| Governing contract | Architectural rule | Mapping for this goal |
| --- | --- | --- |
| `docs/doc-requirements-architecture-expressive-performance-techniques-done.md` PALS requirement | LLM/source-derived output is untrusted until explicitly verified; missing output verification is a design defect. | Source metadata, license claims, pitch/mechanics inference, generated SFZ, manifests, review state, and approved sample bytes are all untrusted until fixture-tested and artifact-verified. The builder must reject or quarantine unverifiable facts instead of letting them become render inputs. |
| `docs/doc-requirements-architecture-expressive-performance-techniques-done.md` | Smart musical constructs lower to explicit IR or explicit library/capability data. Renderer-private behavior is forbidden. | Sample discovery, license interpretation, quality analysis, pitch inference, grouping, and SFZ generation are build-time/compiler-side operations. The runtime receives only approved local library manifests, pinned sample bytes, and SFZ opcodes already supported by `audioforge.sampler`. |
| `docs/doc-requirements-architecture-expressive-performance-techniques-done.md` §2 FR/NFR | Every new expressive surface has explicit validation, hash honesty, deterministic lowering, and manifest-matching diagnostics. | Every sample-catalog surface must produce explicit accepted/quarantined records, stable artifact hashes, and named rejection reasons. License, source, quality, and loader failures are data in candidate/review artifacts, not warnings hidden in logs. |
| `docs/doc-requirements-architecture-expressive-performance-techniques-done.md` §4.1/§4.3 | Support matrices distinguish what each voice can actually render; unsupported combinations fail or produce manifest-recorded fallbacks. | Catalog manifests must distinguish actual sample coverage from authoring intent: key ranges, velocity layers, round-robin depth, articulations, string/fret provenance, loop support, and any missing/fallback articulation must be recorded before render. |
| `docs/doc-requirements-architecture-expressive-performance-techniques-done.md` §4.5 | String/fret/tuning are first-class, hash-included musical facts; true per-string multisampling is deferred to library onboarding. | Guitar catalogs must preserve string/fret/tuning/session evidence when known, but must not pretend to have per-string timbre unless source samples actually provide it. When metadata is absent, the builder records absence instead of synthesizing provenance. |
| `docs/doc-requirements-architecture-expressive-performance-techniques-done.md` §5 | Definition of Ready is a hard preflight gate before implementation starts. | P0 requires source contracts, accepted license identifiers, candidate/evidence schemas, and current AudioForge integration contracts before source adapters or downloads are expanded. |
| `docs/doc-requirements-architecture-expressive-performance-techniques-done.md` §6 | Definition of Done is requirement-by-requirement and validation-backed. | The catalog builder is done only when discovery, evidence, download, analysis, SFZ, manifest, review, approval, loader, capability, docs, and drift requirements all have tests and fresh gate evidence. |
| `docs/doc-requirements-architecture-expressive-performance-techniques-done.md` §7 | Tests must be deterministic, isolated, realistic, and named after expected behavior. | All source/API behavior is covered by recorded fixtures or injected transports; no sample-catalog regression depends on the public network, source availability, wall-clock, or a downloaded corpus. |
| `docs/doc-requirements-architecture-expressive-performance-techniques-done.md` §8 | Proven primitives and existing evaluators are reused; new kernels or abstractions are allowed only when necessary, deterministic, and testable. | The builder must reuse `parse_sfz()`, `load_library()`, `_decode_wav_bytes()`, `Catalog.build()`, and existing manifest hashing. New analysis helpers are allowed only when their outputs are deterministic, fixture-tested, and persisted as auditable data. |
| `docs/doc-requirements-architecture-expressive-performance-techniques-done.md` §8 coding standards | Public names, diagnostics, typed errors, and single-source constants must remain synchronized. | Source IDs, accepted license names, artifact schema versions, quarantine reasons, and CLI command names must be defined once and checked by docs/capability/CLI drift tests. |
| `docs/doc-requirements-architecture-expressive-performance-techniques-done.md` §10 | Idempotent phase ledger prevents redoing `done-validated` work and ties progress to validation evidence. | This goal's P0-P7 phases are execution checkpoints. A phase is complete only when its listed artifacts and tests pass; future agents must inspect existing sample-catalog tests/artifacts before reimplementing a completed slice. |
| `static/refs/AF-P1-performance-curves-proposal-v2.1.md` | Expressive macro layers may be rich, but lowered artifacts must be dense, diffable, bounded-error, and hash-owned. | Catalog analysis may use richer heuristics, but outputs must be concrete JSON/SFZ/manifest artifacts with stable ordering, content hashes, evidence hashes, and explicit rejection reasons. No hidden heuristic may affect rendering after approval. |
| `static/refs/AF-P2-render-plan-proposal.md` | Routing decisions should be derived from catalog evidence and exposed before render. A plan entry without evidence is only an assertion. | Generated catalogs must produce the evidence a render plan needs: key ranges, keycenters, velocity layers, round-robin depth, articulation availability, sample hashes, library pin, and diagnostics. `Catalog.build(candidate_root)` is the pre-review evidence surface until a first-class render plan consumes it. |
| `docs/DSL_SPEC.md` §14 | Instrument libraries are byte-pinned directories of samples, SFZ files, and `library.manifest.json`; unsupported SFZ opcodes are reported, never silently honored. | The builder must emit only the documented SFZ subset and must validate generated libraries through `parse_sfz()`, `load_library()`, and `Catalog.build()`. Approved catalogs are referenced by manifest pin, not by mutable source URLs. |
| `docs/DSL_SPEC.md` §17 | Render determinism is proven by hashes and verification, not assumed. | License evidence, analysis summaries, generated SFZ, manifests, review state, and approved sample bytes must be hashable and reproducible. Any mutation to approved render-affecting bytes requires a new version or manifest hash. |
| `docs/capability.schema.json` and `audioforge/capabilities.py` | Public capabilities must advertise supported surfaces and stay in sync with runtime behavior. | The CLI/capability surface must advertise `sample-catalog` operations, accepted licenses, source adapters, generated-artifact schema versions, and the supported SFZ subset. Drift tests must fail when docs, capabilities, and CLI behavior diverge. |

The builder therefore has three strict boundaries:

- **Discovery boundary:** public APIs and source metadata may be queried only
  during `sample-catalog search/download`; network and OAuth logic must never
  enter render or library loading.
- **Evidence boundary:** a candidate sample is not a region until license
  evidence, source bytes, analysis, and rejection/acceptance state are persisted
  in deterministic artifacts.
- **Runtime boundary:** approved catalogs are ordinary AudioForge libraries.
  Rendering must not know whether a sample came from Freesound, IA, Commons, or
  a local fixture; it knows only the pinned manifest, SFZ map, and verified
  sample bytes.

### Expressive-Performance Requirement Mapping

The AF-P3/G13 done/validated document is the binding style guide for how this
goal enters AudioForge. The sample-catalog builder maps to it as follows:

| AF-P3/G13 requirement family | Sample-catalog equivalent | Required consequence |
| --- | --- | --- |
| R1: explicit note-scope primitives | Explicit catalog artifacts: `LICENSES.json`, analysis records, SFZ regions, `library.manifest.json`, review metadata | No render-affecting fact may live only in prose, stdout, source-site metadata, or an unpinned cache. |
| R2: technique registry as single source | License policy, source adapter registry, artifact schema version, and generated SFZ subset as single sources | Docs, capability manifest, CLI help, and tests must read from or assert against the same constants. |
| R3: string/fret/tuning as hash-included musical facts | Instrument-mechanics metadata in analysis/manifest when source evidence supports it | Guitar catalogs must retain source-proven string/fret/tuning/position/session data and reject or mark missing mechanics explicitly. |
| FR diagnostics | Named quarantine/rejection reasons | Every rejected or quarantined candidate must carry a stable reason such as `unsupported_license`, `missing_download_url`, `decode_failed`, `quality_gate_failed`, `missing_license_evidence`, or `unrenderable_sfz`. |
| NFR determinism/hash honesty | Content-addressed samples and deterministic JSON/SFZ output | Re-running the same fixture input must produce byte-identical evidence, analysis, SFZ, manifest, and review artifacts. |
| PR authoring ergonomics and audibility | Reviewable audition snippets and renderable approved fixture catalogs | Generated review reports must show how to audition the candidate through normal AudioForge library references; approved fixtures must be renderable through existing `library: "name@manifest_sha256"` flows. |
| ER single-source/drift discipline | Runtime/docs/capability/test synchronization | Adding a source adapter, license state, CLI command, manifest field, or SFZ opcode requires matching tests and capability/docs updates in the same change. |
| OR full-gate discipline | Focused sample-catalog tests plus repo gate before completion claims | A phase cannot be called done from implementation presence alone; it needs fresh validation evidence. |
| AR coordination/idempotency | Inspect existing ledger/tests/artifacts before editing | Future agents must extend the current implementation and preserve unrelated work instead of restarting the builder. |

### Detailed AF-P3/G13 Traceability

This table is the execution map from the AF-P3/G13 requirements document to this
catalog-builder goal. A sample-catalog phase is incomplete if its mapped row has
no implementation artifact and no regression test.

| AF-P3/G13 requirement | Catalog-builder mapping | Required implementation evidence | Required regression coverage |
| --- | --- | --- | --- |
| FR-1 to FR-3: explicit note-scope curves and duplicate/voice validation | Generated catalogs must expose only explicit, loader-visible render facts: regions, sample hashes, key/velocity ranges, loop fields, and evidence IDs. No hidden heuristic may affect audio after approval. | `library.manifest.json`, SFZ regions, `LICENSES.json`, and analysis/review sidecars contain all render-affecting catalog facts. | Manifest/SFZ tests prove generated regions are explicit, stable, parseable, and hash-covered. |
| FR-4 to FR-10: registry single source, deterministic lowering, capability publication, named unsupported diagnostics | License states, source adapters, schema versions, CLI command names, and generated SFZ opcode subset must be runtime constants or generated from runtime constants. Unsupported licenses, sources, formats, opcodes, and catalog states fail with named diagnostics. | `audioforge/sample_catalog/constants.py`, `audioforge/capabilities.py`, CLI parser choices, and docs agree on accepted licenses, adapters, artifact schemas, and commands. | Drift tests fail when capability output, CLI help, docs, or runtime constants diverge. |
| FR-11: override/fallback diagnostics | Any catalog fallback, omitted articulation, missing loop, missing mechanics metadata, or rejected candidate must be visible as data, not a log-only warning. | Candidate/review artifacts include structured `warnings`, `fallbacks`, or `rejection_reasons`. | Review and manifest tests assert named warnings/rejections for fixture failures. |
| FR-12 to FR-16: tuning, string, fret, and position facts | Guitar catalogs must preserve source-proven string/fret/tuning/position/session metadata when present and explicitly mark it unavailable when absent. The builder must not infer fingering or claim per-string sample coverage from generic pitch samples. | Analysis records and manifest region summaries carry source mechanics metadata or an explicit unavailable marker. | Guitar fixture tests cover both source-proven mechanics and absent-mechanics cases. |
| NFR-1: deterministic output | Re-running the same fixture input must produce byte-identical evidence, analysis, SFZ, manifest, and review artifacts. | Deterministic JSON serialization, stable SFZ ordering, content-addressed sample paths, and no wall-clock in hash-owned artifacts except recorded fetch evidence. | Golden or round-trip tests compare regenerated fixture artifacts byte-for-byte or by canonical hash. |
| NFR-2: hash honesty | Every render-affecting catalog decision must be hash-owned: sample bytes, evidence bundles, manifest summaries, approved state, and review gate. Hash-excluded prose must not affect loading. | Evidence hashes, license bundle hash, sample byte hashes, manifest hash, and review/promotion metadata are verified before approved loading. | Loader/audit tests reject forged evidence hashes, stale bundle hashes, sample-byte mismatches, and candidate-only catalogs. |
| NFR-3: backward compatibility | Existing library manifests, `ingest`, `libgen`, SFZ parsing, and normal render/library loading must continue to work. Catalog fields must be additive or explicitly gated. | Existing loader paths accept old fixtures; sample-catalog additions are isolated from runtime network/source code. | Existing sampler/interop/library tests plus sample-catalog fixture tests run together. |
| NFR-4 to NFR-5: performance and pure lowering | Source search, license interpretation, quality analysis, grouping, and SFZ generation are build-time operations. Runtime loading should only verify local files and manifests. | No network/OAuth/source adapter imports are reachable from render paths; pure helper functions handle decisions and generation. | Import-boundary or loader tests prove `load_library()` works offline and rejects invalid approved catalogs deterministically. |
| PR-1 to PR-2: authoring surface and audible acceptance | Catalog output must not be a private build artifact only; reviewers need a normal AudioForge audition path before approval. | `review.md` includes a minimal `.af` audition snippet that references the candidate by library manifest pin once promotion is possible. | Review tests assert audition guidance, and fixture tests render or load the approved catalog through public library APIs. |
| ER-1 to ER-5: single-source and drift discipline | Public catalog constants must have one owner and every public schema/docs/capability surface must track it. Generated schema artifacts must stay synchronized with runtime generators. | Runtime constants feed or are asserted by capability output, CLI help, docs, and schema/version tests. | `tests/test_manifest_registry_coverage.py`, `tests/test_cli_docs_sync.py`, and sample-catalog schema tests are mandatory gates. |
| OR-1 to OR-4: gate discipline and observable fallbacks | A phase cannot be marked complete until focused sample-catalog tests and the adjacent repo gate pass. Fallbacks and unsupported states must be manifest/review data. | Phase notes and Definition of Done entries cite fresh validation commands and named fallback fields. | Focused sample-catalog test suite plus `./scripts/run_tests.sh` before completion or commit claims. |
| AR-1 to AR-6: idempotent agent execution | Future agents must inspect existing docs/tests/artifacts first, open coordination tasks before edits, and extend the current implementation rather than restarting it. | `.agent-tasks` protocol followed during edits; `docs/goal.md` remains the phase ledger for pending catalog-builder work. | No automated test for coordination is required, but final work reports must state changed files and validation evidence. |

### AF-P2 Render-Plan Traceability

The AF-P2 proposal is not itself a sample-catalog feature, but it defines the
evidence shape the catalog builder must produce so a future render plan can make
routing decisions without re-inspecting source websites, caches, or private
heuristics.

| AF-P2 rule | Catalog-builder obligation | Artifact owner | Regression gate |
| --- | --- | --- | --- |
| Plan entries cite coverage evidence; a decision without evidence is only an assertion. | Every generated region must point to sample hash, keycenter, key range, velocity range, round-robin group, articulation, evidence ID, and library pin. | `library.manifest.json`, generated SFZ, `LICENSES.json`, analysis/review sidecars | Manifest/SFZ tests reject regions that lack hashes, evidence IDs, or loader-visible coverage facts. |
| Routing decisions are derived from pinned catalog facts, not renderer-private behavior. | Search, license normalization, analysis, grouping, and SFZ generation happen before approval; runtime loading sees only pinned local library data. | `audioforge/sample_catalog/*`; runtime boundary remains `audioforge/library.py`, `audioforge/sampler.py`, and `audioforge/catalog.py` | Runtime import-boundary tests and loader tests prove source adapters/network code are not required to load approved catalogs. |
| Fallbacks and unsupported states are inspectable before render. | Missing articulation, missing mechanics metadata, rejected license, unsupported format, decode failure, loop omission, and candidate-only state are named artifact fields. | Candidate analysis records, review reports, manifest diagnostics | Review/manifest tests assert stable rejection and fallback reason strings. |
| Whole-timeline planning needs catalog facts for route selection. | Approved catalogs must be discoverable through `Catalog.build()` with renderability, key ranges, velocity layers, round-robin depth, articulation availability, and blocker diagnostics intact. | `audioforge/catalog.py` output over `_catalog/approved` and fixture catalogs | Fixture tests build the catalog and assert generated approved libraries are renderable or blocked for named reasons. |
| Plan/apply style requires staleness detection from hashes and pins. | Promotion must move candidate state to approved state by updating review metadata, license bundle hash, sample byte hashes, and manifest hash together. | `review.py`, `manifest.py`, approved catalog layout | Promotion/audit tests reject stale bundle hashes, forged evidence hashes, sample-byte mismatches, and manual candidate copies. |
| Reserved cost/inpaint fields depend on reliable source capability data later. | Catalog output must not overclaim sample coverage. Guitar string/fret/tuning/session data is recorded only when source-proven; absence is explicit. | Analysis records and manifest region summaries | Guitar fixture tests cover both source-proven mechanics metadata and explicit unavailable mechanics metadata. |

### AF-P2 Proposal Section Mapping

This goal maps the AF-P2 render-plan proposal as a producer-side contract. The
sample-catalog builder does not implement `audioforge.render-plan/1`; it
produces the pinned coverage evidence that the planner needs to make decisions
without source-site access or renderer-private heuristics.

| AF-P2 section | Render-plan requirement | Sample-catalog mapping | Completion gate |
| --- | --- | --- | --- |
| §1 Summary | The plan records route, coverage evidence, policy, diagnostics, and cost placeholders per segment. | Approved catalog artifacts must expose route-relevant facts: instrument name, articulation, key range, keycenter, pitch offset, velocity layer, round-robin group, sample hash, evidence ID, library pin, and named blockers. | Manifest/SFZ/catalog fixture tests assert all plan-relevant fields are present and loader-visible before approval. |
| §2 Problem statement | Catalog coverage already exists, but routing needs a first-class consumer. | Candidate and approved catalogs must be consumable by `Catalog.build()` without network access and must preserve blocker diagnostics rather than only review prose. | `Catalog.build(candidate_root)` and approved fixture tests check renderable and blocked cases with stable diagnostics. |
| §4 P1/P2 | Plans are derived artifacts and render-from-plan recomputes hashes to reject stale inputs. | Catalog promotion must synchronize sample bytes, evidence hashes, license bundle hash, review metadata, manifest hash, and builder version so future plans can detect stale catalog inputs. | Audit/promotion tests reject stale hashes, stale builder versions, forged evidence, and sample-byte mutation. |
| §4 P4 | Decisions carry evidence; an entry without evidence is only an assertion. | No generated region may omit the source evidence ID or sample byte hash; Openverse-only evidence remains quarantined. | Manifest tests reject missing evidence IDs and Openverse final-evidence cases. |
| §5.1 Artifact | Plan segments cite `sample_sha256`, keycenter, velocity layer, round robin, articulation resolution, and diagnostics. | Manifest region summaries and generated SFZ must carry or derive the same values in stable order. | SFZ and manifest golden tests cover stable ordering and explicit region facts. |
| §5.2 Pipeline placement | Planning happens after validation/resource binding and before render. | `sample-catalog build-sfz`, audit, review, and promotion happen before render; runtime library loading remains local and deterministic. | Import-boundary tests prove source adapters/downloader code are not imported by loader/render paths. |
| §5.3 Recompute-verify | Planning is pure over spec, library pins, catalog pin, and engine version. | Approved catalogs must make their effective catalog pin reproducible from manifest and sidecar hashes. | Fixture tests recompute audit outputs from disk and compare canonical hashes. |
| §5.4 Decision model | The planner formalizes sampler choices: region candidates, velocity layer, round robin, pitch offset, articulation resolution. | Catalog builder must not invent runtime choices after approval; all candidate grouping and fallback decisions become explicit catalog data. | Grouping/SFZ tests assert deterministic key, velocity, articulation, and round-robin assignments. |
| §5.5 Policy | Fallback policy changes validation/planning outcomes before audio is computed. | Sample-catalog artifacts must distinguish supported articulation coverage from fallback or unavailable articulation data so a future `fallbacks: forbid` policy can fail early. | Review/manifest tests assert missing articulation and fallback reason fields. |
| §5.6 Phasing | Phase 1 formalizes existing behavior; later phases transfer authority and add intelligence. | This goal must stay producer-side: it may add plan-ready evidence, but must not add planner authority or renderer route decisions. | Docs/capability tests fail if sample-catalog code starts advertising a render-plan implementation it does not own. |
| §8 Test plan | Determinism, evidence integrity, policy, CLI/agent surface, and session-bundle checks are mandatory for the planner. | Sample-catalog tests must provide deterministic fixture evidence for the subset they own: catalog facts, hashes, fallback/blocker diagnostics, and public CLI/capability drift. | Required Tests below include sample-catalog gates that feed the future AF-P2 planner gates. |

### Render-Plan Handoff Contract

An approved sample catalog is render-plan-ready only if these facts are
available from local artifacts, without reading source-site metadata:

- `library_pin`: manifest hash and builder version for the approved library.
- `sample_identity`: stable relative sample path, byte size, `sample_sha256`,
  source evidence ID, and license bundle hash.
- `coverage`: instrument, articulation, keycenter MIDI, key range, velocity
  range, round-robin group/index, loop status, and any loop candidate withheld
  from SFZ emission.
- `quality`: analysis schema version, quality score, pitch confidence, and
  named rejection or warning reasons.
- `mechanics`: string, fret, tuning, position, pack/session, and unavailable
  markers when source evidence does not provide those facts.
- `diagnostics`: unsupported license/source/format/opcode, missing evidence,
  missing articulation, missing mechanics metadata, candidate-only state, and
  loader/catalog blockers as stable strings.

The handoff is intentionally one-way: source adapters and heuristics may create
or refine candidate facts before review, but once a catalog is approved the
planner and renderer consume only these pinned local facts.

### Current Execution Map

This goal is intentionally broader than the slices already implemented. Treat
the table below as the live handoff map: a row is not complete merely because a
module exists; completion requires the listed artifact and regression evidence.

| Goal area | Governing source | Target state in this goal | Current completion rule |
| --- | --- | --- | --- |
| Architecture boundary | AF-P3/G13 FR/NFR/ER/OR + AF-P2 P1-P4 | Build-time intelligence only; runtime sees explicit approved libraries. | Passing boundary tests plus no source-adapter imports from loader/render paths. |
| License policy | CC0/PDM/public-domain policy + AF-P3 named diagnostics | Narrow accepted set, explicit quarantine for everything else, evidence hashes preserved. | License tests cover accepted, quarantined, forged, and unknown-schema cases. |
| Source adapters | Source API docs + adapter registry discipline | Freesound first; IA, Commons, and Openverse only through adapters and fixtures. | Adapter tests use injected transports/recorded fixtures and no public network. |
| Downloads and evidence | AF-P2 hash/pin discipline | Content-addressed downloads, resumable writes, evidence sidecars, no downloaded corpus in git. | Downloader tests cover resume, retry, hash mismatch, and missing download URLs. |
| Analysis and grouping | AF-P3 explicit artifact rule | Deterministic quality facts, pitch/keycenter facts, rejection reasons, grouping facts. | Analysis/grouping tests use generated audio fixtures and stable canonical JSON. |
| SFZ and manifest emission | `docs/DSL_SPEC.md` sample-library contract | Conservative SFZ subset and additive manifest data that existing loaders can verify. | SFZ parses without ignored opcodes; `load_library()` and `Catalog.build()` validate fixtures. |
| Review and promotion | AF-P2 plan/apply and AF-P3 DoD discipline | Candidate catalogs cannot become approved without reviewer metadata and synchronized hashes. | Promotion tests reject bypasses and stale/forged review or evidence data. |
| Render-plan readiness | AF-P2 §1-§8 | Approved catalogs expose local, hash-owned coverage facts and diagnostics sufficient for future `audioforge.render-plan/1` segments. | Manifest, SFZ, catalog, and fixture tests assert plan-relevant fields and stable blocker/fallback strings. |
| Public surface drift | Capability schema, CLI help, docs | CLI commands, accepted licenses, source adapters, schema versions, and docs stay synchronized. | `tests/test_cli_docs_sync.py`, `tests/test_manifest_registry_coverage.py`, and sample-catalog schema tests pass together. |
| Guitar realism | AF-P3 R3 and current guitar-solo feedback | Real sample coverage and source-proven mechanics only; no fabricated per-string or human-performance claims. | Guitar fixture tests distinguish known mechanics, absent mechanics, and unsupported per-string coverage. |

### Contract Decisions

- Keep `library.manifest.json` as the loader contract. The first
  implementation may store license evidence, analysis, and review state in
  sidecars such as `LICENSES.json`, `analysis.json`, and `review.md` while the
  runtime loader still understands the current manifest core.
- If `library.manifest.json` gains fields such as `catalog_state`,
  `license_evidence`, or `builder_version`, update `_canonical_manifest_hash()`
  intentionally and add compatibility tests. Do not let review or license state
  drift outside the pin if the loader uses it for acceptance.
- Treat `manifest_sha256` as render-affecting. It currently covers name,
  version, license, files, and instruments. Any change that can affect rendered
  audio must remain inside that hash.
- Treat `audioforge.sampler.parse_sfz()` as the approved IR boundary for SFZ.
  Generated SFZ is acceptable only when it parses with no ignored opcodes and
  `Catalog.build()` marks it renderable.
- Do not add network, OAuth, or external-source logic to the render path.
  Discovery, download, evidence capture, and review are compiler/build-time
  concerns. Runtime loading stays pinned, local, deterministic, and auditable.
- Treat candidate promotion as a hash-moving review event. Promotion to
  `_catalog/approved/<instrument>/<version>/` must update review metadata,
  catalog state, license bundle hash, and manifest hash together.
- Treat `Openverse` as an index, not a provenance authority. Every accepted
  Openverse lead must resolve to an upstream adapter or remain quarantined.
- Treat generated sample catalogs as library onboarding, not expressivity
  lowering. They may satisfy AF-P3/R3's deferred per-string multisampling need,
  but only through real recorded sample coverage and explicit manifest evidence.

### Data Flow

```text
search query
  -> source adapter candidates
  -> license normalization
  -> candidate quarantine or approval
  -> download
  -> content hash
  -> audio analysis
  -> grouping and region inference
  -> SFZ + manifest generation
  -> review report
  -> candidate|approved catalog state
```

## Source Adapters

### Freesound Adapter

Use Freesound as the first implementation target because it has the strongest
sample-oriented API surface.

Required behavior:

- Search with explicit fields to avoid per-result metadata fetches where
  possible.
- Filter by license, file type, duration, quality descriptors, tags, rating, and
  pitch/note confidence where available.
- Prefer `wav`, `aiff`, and `flac`.
- Use OAuth2 for downloads.
- Respect page size limits and rate limits.
- Store Freesound sound ID, pack ID, uploader, license URL, tags, and descriptors.

Example discovery constraints:

- License: CC0 only.
- Types: `wav OR aiff OR flac`.
- Instrument tags: `piano`, `guitar`, `violin`, `cello`, `flute`, `drum`.
- Reject obvious loops, beats, songs, speech, field recordings, and mixes when
  building pitched instruments.

### Internet Archive Adapter

Use IA as a second-stage source because metadata is broader and less normalized.

Required behavior:

- Search only `mediatype:audio`.
- Fetch item metadata before downloading files.
- Accept only recognized public-domain/CC0 license evidence.
- Prefer archive items that are clearly sample packs, isolated notes, or
  institutional audio collections.
- Quarantine items with ambiguous rights text.

### Wikimedia Commons Adapter

Use Commons for provenance-heavy audio and public-domain institutional media.

Required behavior:

- Use MediaWiki APIs, not HTML scraping.
- Fetch `imageinfo` with URL, SHA-1, MIME/media type, and selected license
  metadata.
- Accept only CC0/PDM/no-known-copyright evidence.
- Store the Commons file page as canonical provenance.

### Openverse Discovery Adapter

Use Openverse only as a discovery index.

Required behavior:

- Search for audio candidates with public-domain/CC0-like filters.
- Record Openverse result metadata.
- Resolve each candidate back to the canonical upstream adapter before download.
- Do not accept an Openverse result as final license evidence.

## Storage Layout

Generated/downloaded assets should live outside tracked source by default:

```text
_catalog/
  cache/
    downloads/<sha256[0:2]>/<sha256>.<ext>
    evidence/<sha256>.json
    analysis/<sha256>.json
  candidates/
    <instrument>/<candidate-id>/
      samples/
      instrument.sfz
      library.manifest.json
      review.md
  approved/
    <instrument>/<version>/
      samples/
      instrument.sfz
      library.manifest.json
      LICENSES.json
```

Tracked tests must use tiny synthetic fixtures, not downloaded corpora.

## Audio Quality Gates

Each downloaded file must be decoded and analyzed before it can become a region.

Reject or quarantine files with:

- Unsupported format.
- Decode failure.
- Clipping above configured threshold.
- Silence or near-silence.
- Excessive noise floor.
- Duration too short or too long for the target instrument class.
- Multiple unrelated events when building one-shot note regions.
- Speech, full songs, backing tracks, beats, or mixed performances for pitched
  instrument catalogs.
- Pitch confidence below threshold for pitched instruments.
- Sample rate or bit depth below configured minimum unless explicitly allowed.

Extract and store:

- SHA-256 and source byte size.
- Format, sample rate, bit depth, channels, duration.
- Peak, RMS, LUFS approximation if available.
- Estimated pitch, MIDI note, cents offset, pitch confidence.
- Attack time, decay/release envelope, transient count.
- Spectral centroid and bandwidth.
- Loop candidate spans and loop confidence.
- Quality score and rejection reasons.

## Instrument Grouping Rules

The builder should prefer coherent instruments over random individual samples.

Grouping priority:

1. Same source pack/session/institution.
2. Same uploader/creator and consistent recording metadata.
3. Same instrument tag and similar timbre descriptors.
4. Same license and compatible provenance.

Mapping rules:

- Filename and metadata pitch labels are hints.
- Audio pitch analysis verifies or corrects pitch labels.
- `pitch_keycenter` is mandatory for pitched SFZ regions.
- `lokey`/`hikey` ranges are derived from neighboring keycenters.
- Velocity layers require explicit metadata or strong filename evidence.
- Articulations require explicit metadata/tag support.
- Round-robin requires same pitch/articulation/velocity class and compatible
  timbre.

## Generated SFZ Rules

Emit conservative SFZ only:

```sfz
<group>
ampeg_attack=0
ampeg_release=0.1

<region>
sample=samples/C4_rr1.wav
pitch_keycenter=60
lokey=59
hikey=61
lovel=1
hivel=127
```

Rules:

- Do not emit speculative filters, EQ, modulation, or envelopes.
- Emit loop opcodes only when loop analysis passes and review confirms.
- Normalize paths to repo-portable relative paths.
- Keep generated SFZ stable and sorted by pitch, velocity, articulation, then
  round-robin index.

## AudioForge Manifest Rules

Emit `library.manifest.json` with:

- Library name, version, builder version.
- Instrument names and articulations.
- Region list with key ranges, velocity ranges, sample path, sample hash,
  keycenter, loop info, and source evidence ID.
- License evidence bundle hash.
- Analysis summary and quality score.
- Catalog state: `candidate` or `approved`.
- Review status and reviewer metadata.

The existing AudioForge library loader must reject:

- Missing sample file.
- Sample hash mismatch.
- Missing license evidence.
- Unsupported or unclear license.
- Candidate catalogs when an approved catalog is required.

## CLI Surface

Add commands:

```bash
audioforge sample-catalog search \
  --source freesound \
  --license cc0 \
  --instrument guitar \
  --limit 200 \
  --out _catalog/search/guitar-cc0.json

audioforge sample-catalog search \
  --source openverse \
  --license cc0 \
  --instrument guitar \
  --limit 50 \
  --out _catalog/search/openverse-guitar-cc0.json

audioforge sample-catalog resolve-openverse \
  --candidates _catalog/search/openverse-guitar-cc0.json \
  --out _catalog/search/openverse-guitar-resolved.json

audioforge sample-catalog download \
  --candidates _catalog/search/guitar-cc0.json \
  --out _catalog/cache \
  --retries 3 \
  --retry-sleep 1.0

audioforge sample-catalog analyze \
  --downloads _catalog/cache/downloads \
  --out _catalog/cache/analysis

audioforge sample-catalog build-sfz \
  --instrument guitar \
  --analysis _catalog/cache/analysis \
  --out _catalog/candidates/guitar/public-domain-guitar-v0

audioforge sample-catalog audit-license \
  _catalog/candidates/guitar/public-domain-guitar-v0

audioforge sample-catalog review \
  _catalog/candidates/guitar/public-domain-guitar-v0

audioforge sample-catalog review \
  _catalog/candidates/guitar/public-domain-guitar-v0 \
  --reviewer qa \
  --reviewed-at 2026-06-12T15:00:00+00:00 \
  --approve-to _catalog/approved
```

## Implementation Plan

### P0: Source Contract And Safety Gates

- Add this goal to `docs/goal.md`.
- Add `_catalog/` to `.gitignore`.
- Freeze integration contracts against `audioforge/library.py`,
  `audioforge/sampler.py`, `audioforge/catalog.py`, and `audioforge/cli.py`.
- Map the goal to the current AudioForge architecture contracts:
  expressive-performance lowering discipline, AF-P2 evidence/routing needs,
  DSL sample-library semantics, deterministic manifests, and capability drift
  gates.
- Map AF-P2 proposal sections to sample-catalog producer obligations and
  define the local render-plan handoff facts that approved catalogs must carry.
- Define the AF-P3/G13-derived execution rules for this goal: build-time
  intelligence only, explicit artifacts only, named diagnostics, hash-owned
  render inputs, and no renderer-private catalog behavior.
- Define accepted license identifiers and quarantine states.
- Define source evidence schema and candidate schema.
- Add tests for license normalization and evidence hashing.

### P1: Freesound Discovery MVP

- Implement Freesound source adapter.
- Support search with explicit fields, pagination, filters, and OAuth2 download
  URL resolution.
- Accept only CC0 results.
- Add recorded API fixtures for tests.
- Add CLI `sample-catalog search --source freesound`.

### P2: Downloader And Evidence Store

- Implement rate-limited downloads.
- Store files by SHA-256.
- Store normalized evidence JSON by evidence hash.
- Add resumable download behavior and bounded retry for transient transport
  failures.
- Add tests with local HTTP fixtures or mocked transport.

### P3: Audio Analysis And Quality Gates

- Decode supported files.
- Extract format, pitch, level, duration, transient, silence, clipping, and
  quality metadata.
- Reject or quarantine low-quality samples.
- Add deterministic generated WAV fixtures for tests.

### P4: SFZ And Manifest Generation

- Group samples into instrument candidates.
- Generate stable SFZ.
- Generate AudioForge `library.manifest.json`.
- Validate generated SFZ through `audioforge.sampler.parse_sfz()`.
- Validate generated manifests through `audioforge.library.load_library()`.
- Validate generated library directories through `audioforge.catalog.Catalog`.
- Emit region summaries that are sufficient for future render-plan evidence:
  sample hash, evidence ID, keycenter, key range, velocity range, articulation,
  round-robin group/index, loop status, and named fallback/blocker diagnostics.
- Add golden tests for SFZ and manifest output.

### P5: Review And Promotion

- Generate `review.md` with source links, license evidence, pitch map, quality
  warnings, and suggested audition commands.
- Add `candidate` versus `approved` catalog state.
- Require explicit reviewer and reviewed-at metadata before promotion to
  approved; promotion must not inject wall-clock time into the manifest hash.
- Ensure approved manifests are immutable unless version changes.

### P6: Additional Sources

- Add Internet Archive adapter.
- Add Wikimedia Commons adapter.
- Add Openverse discovery adapter.
- Keep stricter review requirements for IA and Commons until enough fixtures
  prove metadata reliability.

### P7: AudioForge Integration

- Add library search-path helpers for `_catalog/approved`.
- Add docs showing how to render with generated libraries.
- Add a small committed synthetic fixture catalog for tests only.
- Ensure approved catalogs are discoverable through
  `Catalog.build("_catalog/approved")` and renderable through existing
  `library: "name@manifest_sha256"` references.
- Ensure approved catalogs expose all AF-P2 render-plan handoff facts from
  local manifest/SFZ/sidecar data, without source adapter or network access.
- Ensure guitar catalogs can expose string/fret/tuning/session evidence when
  available without changing the renderer contract.
- Do not commit downloaded public samples to the repo.

## Definition Of Done

- License policy accepts CC0/PDM/no-known-copyright and quarantines unclear or
  attribution/non-commercial licenses by default.
- Freesound CC0 discovery, download, evidence storage, and analysis work through
  CLI and tests.
- Downloaded samples are content-addressed and hash-verified.
- Every accepted sample has complete provenance and license evidence.
- Low-quality, ambiguous, or unsuitable audio is rejected or quarantined with a
  clear reason.
- The builder emits deterministic SFZ files and AudioForge manifests.
- Generated manifests load through the existing sample-library code.
- Candidate catalogs cannot be treated as approved without review metadata.
- No downloaded third-party samples are committed to the repo.
- Tests cover license normalization, source adapters, downloader behavior,
  analysis gates, SFZ generation, manifest generation, and loader integration.
- The architecture mapping remains true in code: all source/network work stays
  in build-time commands, all approved catalogs load through existing
  `library.manifest.json` and SFZ surfaces, and capability/docs drift tests cover
  the public `sample-catalog` surface.
- AF-P3/G13 mapping remains true in code: no network or source-adapter logic is
  reachable from render/library loading, no accepted sample lacks persisted
  evidence, no generated region lacks a sample hash and evidence ID, and every
  fallback/rejection has a named diagnostic.
- AI-agent execution mapping remains true in process: agents inspect the current
  execution map and existing tests before extending the builder, use the
  repository coordination task protocol before edits, preserve unrelated dirty
  work, and report fresh validation evidence before calling a phase complete.
- Generated guitar catalogs preserve source-proven string/fret/tuning/session
  metadata when present and explicitly record when that metadata is unavailable;
  the builder must not fabricate per-string sample coverage.
- Capability manifest, CLI help, docs, and runtime constants agree on source
  adapters, accepted licenses, command names, artifact schema versions, and the
  supported SFZ subset.
- Promotion to approved is reproducible: re-auditing an approved fixture verifies
  license bundle hash, manifest hash, sample byte hashes, review metadata, and
  loader acceptance.
- Approved catalogs are render-plan-ready: local artifacts expose library pin,
  sample identity, coverage, quality, mechanics, and diagnostics sufficient for
  future `audioforge.render-plan/1` route evidence, without source-site access.
- The architecture mapping remains bidirectional: every implemented
  sample-catalog public surface is represented in the traceability tables, and
  every binding architecture row has an artifact owner plus a deterministic
  regression, audit, or drift gate.

## Required Tests

- `tests/test_manifest_registry_coverage.py` and `tests/test_cli_docs_sync.py`
  - Capability manifest advertises `sample-catalog` only when the CLI implements
    it.
  - CLI documentation lists the same public command family as runtime help.
  - Capability output publishes the sample-catalog artifact schema versions for
    candidates, analysis records, license evidence, license bundles, and manifest
    builder output.
  - CLI and loader paths reject unknown sample-catalog artifact schema versions
    with stable diagnostics instead of accepting drifted records silently.
- `tests/test_sample_catalog_license.py`
  - CC0 accepted.
  - PDM/no-known-copyright accepted only with source evidence.
  - CC-BY, CC-BY-SA, CC-BY-NC, missing license, and unclear rights quarantined.
- `tests/test_sample_catalog_freesound.py`
  - Search request construction.
  - Pagination.
  - CC0-only filtering.
  - File-type, duration, rating, tag, unsuitable-content, and pitch/note
    confidence gates for pitched instruments.
  - OAuth-required download handoff.
- `tests/test_sample_catalog_download.py`
  - Content-addressed writes.
  - Resume/retry behavior.
  - Hash mismatch rejection.
- `tests/test_sample_catalog_analysis.py`
  - Silence rejection.
  - Clipping rejection.
  - Pitch detection on generated sine fixtures.
  - Duration and sample-rate gates.
- `tests/test_sample_catalog_sfz.py`
  - Stable region ordering.
  - Correct `sample`, `pitch_keycenter`, `lokey`, `hikey`, velocity ranges.
  - Round-robin, articulation, loop, and sample-hash facts remain explicit and
    stable enough to feed render-plan evidence.
  - Generated SFZ parses with `audioforge.sampler.parse_sfz()` and reports no
    ignored opcodes.
- `tests/test_sample_catalog_manifest.py`
  - Manifest includes hashes, evidence IDs, license bundle, and catalog state.
  - Manifest region summaries include the AF-P2 handoff fields: library pin,
    sample identity, keycenter, key/velocity ranges, articulation,
    round-robin group/index, loop status, mechanics availability, quality
    summary, and named diagnostics.
  - Existing AudioForge loader accepts approved generated fixtures through
    `load_library()`.
  - Existing AudioForge loader rejects missing evidence, candidate-only
    catalogs when approval is required, and hash mismatches.
  - `Catalog.build()` reports generated approved fixtures as renderable.
- `tests/test_sample_catalog_hardening.py`
  - Accepted candidates require non-empty download URLs and supported audio
    extensions.
  - Openverse results remain discovery leads until upstream evidence is
    verified.
  - Unsupported formats, missing evidence, and ambiguous rights produce named
    quarantine reasons.
  - Runtime loader/render imports stay free of source adapters, downloader
    clients, OAuth, and network-only dependencies.
- `tests/test_sample_catalog_fixture.py`
  - The committed synthetic approved fixture loads through the approved catalog
    path and validates the `_catalog/approved/<instrument>/<version>` layout.
  - Approved fixture manifests include sample hashes, source evidence IDs,
    license bundle hash, and review state.
- `tests/test_sample_catalog_review.py`
  - Candidate promotion rewrites catalog state, records reviewer metadata, and
    preserves hash/evidence integrity.
  - Candidate catalogs cannot bypass review by being copied into the approved
    root manually.
- `tests/test_sample_catalog_cli.py`
  - CLI smoke for search, analyze, build-sfz, audit-license, and review.
  - Existing `ingest` and `libgen` CLI behavior remains unchanged.
- All sample-catalog tests must be deterministic and network-free. Public API
  behavior is tested through recorded fixtures or injected transports only.
- Completion reports must name the focused test command, adjacent drift/contract
  command, and any full-suite command used for the phase; coordination protocol
  compliance is process evidence, not a substitute for automated regression
  coverage.
- Goal-map regression must fail if public sample-catalog artifact schema
  versions, CLI command names, accepted license identifiers, source adapter IDs,
  or manifest diagnostics drift away from the traceability map in this document.

## Coding Standards

- Use source adapters, not ad hoc scrapers.
- Keep HTTP clients injectable so tests never require network access.
- Persist raw upstream metadata and normalized evidence.
- Use deterministic JSON serialization for evidence, analysis, and manifests.
- Treat render-plan handoff fields as compatibility data: add fields
  additively, keep names stable, and test any rename or removal as a schema
  migration.
- Keep generated review artifacts path-portable; do not embed local checkout,
  cache, or temporary directory paths in `review.md`.
- Hash source bytes and generated artifacts.
- Never infer license approval from text snippets alone.
- Do not silently downgrade license failures into warnings.
- Keep generated SFZ stable, sorted, and minimal.
- Keep sample-analysis thresholds configurable but default-strict.
- Keep downloaded corpora out of git.
- Prefer pure functions for license decisions, grouping, SFZ generation, and
  manifest generation.
- Keep build-time and runtime modules separate. `audioforge/sample_catalog/*`
  may know about public APIs, OAuth, rate limits, and source metadata;
  `audioforge/library.py`, `audioforge/sampler.py`, and render paths must not.
- Use typed exceptions or structured result objects for user-facing failures;
  do not leak raw transport, decode, JSON, or filesystem exceptions from CLI
  commands.
- Add or change public constants in one place, then update docs, capability
  output, and tests in the same change.
- Do not add speculative SFZ opcodes, source adapters, manifest fields, or DSP
  behavior without a deterministic fixture and a validation path.
- Treat all LLM- or heuristic-produced classification as untrusted until it is
  reduced to deterministic evidence and review artifacts.
- Do not add planner authority, hidden route decisions, or source-aware behavior
  to the renderer while implementing this goal; sample-catalog code produces
  evidence, and the AF-P2 planner consumes evidence in its own bounded context.
- Before editing, inspect the current execution map, existing sample-catalog
  tests, and coordination locks; extend validated slices instead of restarting
  or overwriting unrelated work.
- Do not add a sample-catalog feature unless its architecture class is explicit:
  build-time source intelligence, persisted catalog evidence, or runtime loader
  verification. Runtime loader verification must remain offline and must not
  import source adapters, download clients, OAuth helpers, or network-only
  dependencies.
- Keep traceability edits paired with implementation edits. A code change that
  changes public catalog behavior but leaves this map stale is a defect; a map
  change without an artifact owner and regression gate is also a defect.

## Open Questions

- Which Freesound OAuth flow should be supported first for local CLI use?
- Should reviewed catalogs live under `_catalog/approved` only, or also support
  an external shared cache path?
- What minimum audio standard should be required for "high quality" in v1:
  44.1 kHz/16-bit, 48 kHz/24-bit preferred, or source-preserving?
- Should CC-BY be supported later with automatic attribution bundles, or remain
  out of scope for this public-domain-only goal?
