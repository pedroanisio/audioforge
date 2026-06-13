---
disclaimer:
  notice: >-
    No information within this document should be taken for granted.
    Any statement or premise not backed by a real logical definition
    or verifiable reference may be invalid, erroneous, or a hallucination.
  generated_by: "Claude Opus 4.8 (1M context) via Claude Code"
  date: "2026-06-13"
---

# AudioForge Roadmap

## Disclaimer

This work is subject to the methodological caveats and commitments described in [@DISCLAIMER.md](../DISCLAIMER.md).
> No statement or premise not backed by a real logical definition or verifiable reference should be taken for granted.

This is the synthesis view. **Why** lives in [PURPOSE.md](../PURPOSE.md), the
agent-facing **concepts** in [AI-CORE.md](../AI-CORE.md), gap-level **detail** in
[DSL_GAP_SPEC.md](DSL_GAP_SPEC.md) (`G1`–`G13`), and **decisions** in
[adr/](adr/). Where this document and a gap entry disagree, the gap entry's
normative contract wins and this page is updated in the same change.

## Current contract

| Surface | Version | Source of truth |
|---|---|---|
| Engine | **2.16.0** | `audioforge.version.ENGINE_VERSION` (folded into every `spec_hash`) |
| DSL | **1.10** | `audioforge.version.DSL_VERSION` |
| IR schema | **1.3** | `audioforge.ir_schema.IR_SCHEMA_VERSION` (published `docs/ir.schema.json`) |
| Capability manifest | `audioforge.capabilities/1` | `audioforge.capabilities.capability_manifest()` |
| Render plan | `audioforge.render-plan/1` | `audioforge.plan` |

## Governing invariants (every item below obeys these)

1. **Reproducibility is a feature.** Same spec + same engine version → byte-identical audio, verified by the `verify` gate. The hash is computed on the fully-resolved IR.
2. **The IR is truth.** The DSL is sugar; everything expressive expands at compile time into explicit, diffable IR. User files stay inert, substitution-only data.
3. **Computation lives behind a versioned, hash-covered boundary** — engine, plugin, or `gen`/library generator — never in user files (ADR 0001).
4. **Inference output is untrusted by default (PALS's Law).** Anything inferred (a matched patch, a learned proposal) is re-verified by re-render before it is trusted.
5. **Agent-first, non-vocal, synthesis-first.** The surfaces are built for agents authoring/inspecting IR without a UI; recorded material enters only as content-addressed samples.

## Recently shipped (this cycle)

**Engine / authoring (from `main`):**
- **G13 — Expressive performance techniques** (IR schema 1.2): `tech NAME(…)`, note-scope `cutoff_hz`/`gain_db`/`scan` curves, fretted/stringed mechanics (`tuning`/`string`/`fret`/`max_fret`); all lower to explicit IR.
- **G12 — First-class render plans** (Phase 1 + verification entry): derived `*.plan.json`, `plan_hash` in manifests, stale-plan refusal.
- **G11 — Continuous performance curves** (IR schema 1.1): explicit `pitch_cents`/`dynamic` note curves.
- **G8 — Interop depth (progress):** channel-aware, multi-track MIDI import.
- **Public-domain sample-catalog builder** (`audioforge sample-catalog`): license-audited, content-addressed SFZ library generation. Spec: [goal.md](goal.md).

**This branch (`render-quality-comparison`):**
- **Render-quality A/B** vs a professional renderer + a produced render that wins delivery/dynamics/DC/width and matches spectral balance ([RENDER_QUALITY_COMPARISON.md](RENDER_QUALITY_COMPARISON.md)); engine fix: `master.stereo_width` widening to 2.0 (**IR schema 1.3**).
- **Sound match** (`audioforge.match`): audio → editable `.af` patch by offline analysis-by-synthesis, with re-render verification ([SOUND_MATCH.md](SOUND_MATCH.md)).
- **Content-pinned includes** (**DSL 1.10**): SHA-256-pinned `import` of `motif`/`bus` fragments, `expand` to materialize ([ADR 0001](adr/0001-dsl-extensions.md)).

## Near-term (next slices)

- **DSL 1.11 — derivation + namespacing** (ADR 0001 slice 2): `import … as ns` with `ns.name` references, and single-hop `bus x : preset { … }` / `archetype` derivation-with-override (replace-by-default collection merge, `expand --flatten`). One grammar change covers both.
- **DSL 1.11 — G11 curve-sugar authoring surface** (re-reserved from 1.10, which includes took).
- **Constraint formalization** (the type-system half of "classes"): stable `L2xx` diagnostic codes and declared strictness over the *already-shipping* key/scale advisories; range/playability lints belong with G5 (catalog-dependent, not free event analysis).
- **G12 Phase 2:** byte-identical plan-consuming sampler path, then retire the legacy derivation path.
- **Sound-match depth:** local refine / CMA-ES after the grid; a learned proposal model (CLAP/DDSP-style) that only *suggests* starting patches and never bypasses the re-render verification or the render path.

## Open universality pillars (AI-CORE)

These move the universality thesis from "in principle" to "without qualification" (acceptance criteria in [DSL_GAP_SPEC.md](DSL_GAP_SPEC.md)):

- **G2 — Formal Universal Music IR Schema:** keep the versioned, published schema separating semantic intent / expanded render data / provenance as the checkable contract (IR schema is now at 1.3; continue hardening).
- **G4 — Semantic Round-Trip Preservation:** `DSL → IR → DSL → IR` preserving authored *altitude* (smart directives, motifs, intent), not just render-equivalent output. (The tone-layer pitch round-trip fix in `decompile` is one step.)
- **G5 — Library-Aware Orchestration:** choose playable instruments from a catalog, enforce comfortable/hard ranges, select articulations by technique, form divisi from real capabilities.
- **G8 — Interop Depth:** documented MIDI/MusicXML subsets, real-world fixtures, session/stems bundles, structured lossy-conversion diagnostics. (Advanced this cycle via channel-aware MIDI import.)

## Horizon — hybrid authoring intelligence

The defensible long bet (reviewed in-session): a **hybrid neural + symbolic** authoring stack where learning lives in an **offline front-end that emits explicit, verified IR**, while the render path stays deterministic DSP. The bright line: **no neural model in the render path** — it would break byte-determinism, hash-verification, and IR-is-truth (and violate PALS's Law, since a black box that *is* the audio cannot be verified). Sound match is the first instance; natural extensions are semantic timbre search (reference/prompt → ranked `.af` candidates), offline DDSP/FM/physical-model parameter fitting to a target, and a generative modulation graph that expands to explicit automation IR. All of these are reproducible because the artifact is an inspectable patch, not a model output.

## Version sequencing

- **Engine** bumps on any render-affecting change (folds into `spec_hash`); additive validation/authoring surface does not require it.
- **DSL** minor per new authoring surface: `1.10` = includes; `1.11` reserved for derivation/namespacing + G11 curve-sugar.
- **IR schema** is additive-compatible; `supported_from` lists `0.9, 1.0, 1.1, 1.2`; current `1.3`.

---

[← back to README](../README.md)
