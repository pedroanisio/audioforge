# AudioForge — North-Star Proposal: Complete Studio · Best AI-Ready DSL · Most Advanced IR

**Date:** 2026-06-10
**Engine:** 2.13.0 · DSL 1.6
**Builds on:**
[Issues & Proposals](REVIEW_2026-06-10_issues_and_proposals.md) ·
[Complementary Libraries](REVIEW_2026-06-10_complementary_libraries.md)

---

## 0. Thesis

The three goals — a **complete music studio**, the **best AI-ready DSL**, and the
**most advanced IR** — are not three projects. They are **one architecture with the
IR at its center of gravity**:

```
        capability surface                  human/AI-writable sugar
   ┌─────────────────────────┐         ┌──────────────────────────┐
   │   STUDIO  (what can be   │         │   DSL  (.af — constrained │
   │   expressed & rendered)  │         │   generation, round-trip) │
   └─────────────┬───────────┘         └─────────────┬────────────┘
                 │                                    │
                 ▼                                    ▼
        ┌───────────────────────────────────────────────────┐
        │   IR  (typed · hashed · introspectable · the truth)│   ← center of gravity
        │   semantic-intent layer  +  expanded render layer  │
        └───────────────────────────────────────────────────┘
                 │                                    │
                 ▼                                    ▼
        deterministic render                analysis / feedback / interop
        (the moat: byte-identical)          (closes the AI loop)
```

**AI-readiness is an *emergent property* of a typed, introspectable, closed-loop
IR — not a feature bolted on.** And **determinism is the moat**: byte-identical,
verifiable, diffable output is what makes AudioForge fundamentally different from a
DAW-scripting layer. Every initiative below is gated by the rule: *never trade
determinism for capability.*

---

## 1. Scorecard — where you are today

| Pillar | Strong already | Missing for the goal |
|--------|----------------|----------------------|
| **Studio** | synth voices, FX, buses, sidechain, EQ, dynamics, BS.1770 loudness + limiter, SFZ-subset sampler, stage/spatial, stems, export presets, packs/campaigns/cutdowns, foley, granular, convolution IR, motifs/transforms, arp/euclid, chord symbols, tempo/key maps | **score/MIDI import**, **recorded-audio tracking**, deep modulation (LFO/mod-matrix), sends/returns, arrangement timeline, fast interactive preview |
| **AI-ready DSL** | deterministic + hashable, "compile never raises", schema-checked `set()` mutation, versioned grammar | **the validate≠render contract is broken** (see Issues P0), no machine-readable capability manifest, no grammar-constrained generation, no closed-loop analysis, no tool/MCP surface, no IR→DSL round-trip |
| **Advanced IR** | "DSL is sugar, IR is truth", emotion/intensity/motifs expand to explicit params, content-addressed provenance (engine version + spec/library/sample/IR hashes in manifest) | **formal typed schema** (validation is hand-rolled), no stable multi-altitude layering contract, no analysis write-back, no interop exports (MIDI/MusicXML), no published schema |

The codebase is deliberately hand-rolled and tiny (numpy/scipy only). The synthesis
and determinism core is **sound**; the gaps are at the *authoring, introspection,
and interop* boundaries.

---

## 2. Foundation (Phase 0 — nothing else ships first)

The single prerequisite for all three pillars is **making the IR contract solid**.
A studio that crashes on real input, a DSL an AI can't trust, and an IR that isn't
formally typed are the same problem. From the Issues doc:

- **P0 — resolve pass + structured, line-numbered diagnostics.** `validate` must
  mean "will render." Resource binding (libraries, samples, IRs, kernels) and
  render-time invariants become `Diagnostic`s, never tracebacks.
- **P1 — validate/render parity**, locked by a property test: *if `render()` raises
  a `SpecError`, `validate()` must already have reported it.*
- **Formal typed IR schema** (pydantic v2 or jsonschema) — replaces the hand-rolled
  `schema.py`, gives structured error *paths*, and is **publishable** (the first
  artifact an AI consumes).

Without Phase 0, "AI-ready" is aspirational: the documented compile→validate→render
loop silently breaks at the resource boundary.

---

## 3. Pillar A — the BEST AI-ready DSL

What makes a DSL *best-in-class* for AI authorship, in priority order:

### A1 · Machine-readable capability manifest
Today the registries (`OSCILLATORS`, FX, drum voices, exporters, validators) are
internal dicts; the spec lives in prose (`DSL_SPEC.md`). Ship a **generated,
versioned JSON capability descriptor**: every voice, FX, articulation, layer type,
and parameter — with **types, ranges, defaults, units, and enums**. This is the
context an AI reads to author correctly on the first try, and it stays in sync
because it's *derived from the registries*, not written by hand.

### A2 · Grammar-constrained generation
Ship the DSL grammar as **EBNF + GBNF** from the executable `lark` grammar in
`audioforge.lark_parser`. This lets LLM toolchains do *grammar-constrained
decoding* — guaranteeing **syntactically valid `.af` by construction** for the
published syntax surface and shrinking parse-error round-trips (Issues I-4/I-5).
Few DSLs ship this; it is a genuine differentiator.

### A3 · Closed-loop analysis feedback
Today the only feedback is loudness/gain-reduction in the manifest. Add an
**analysis pass** (outside the render path, determinism-safe) that annotates a
render with structured features — per-section loudness, spectral balance, stereo
width, transient density, masking hot-spots. This closes the agent loop:
**author → render → analyze → structured critique → mutate**. `pyloudnorm` and a
small feature set (centroid/rolloff/crest) power this in *tests and analysis*, never
in the engine.

### A4 · Tool surface / MCP server
Expose the SDK (`compile / validate / resolve / render / mutate / analyze / export`)
as a **typed tool surface** — and as an **MCP server** so any agent can drive the
studio directly. The structured `Diagnostic` and analysis outputs are the return
payloads. This turns AudioForge from "a library an AI can call" into "a studio an
agent operates."

### A5 · Validated corpus + bidirectional DSL↔IR
- A curated, **always-valid** few-shot corpus of `.af` files (the current
  `static/fixtures/*.af` are authored against a wrong mental model and don't
  render — they should become *passing* examples or labeled diagnostic fixtures).
- **IR → DSL decompilation** (none exists today): lets an agent receive an IR, edit
  at the DSL altitude, and re-emit — and lets the engine pretty-print canonical
  `.af` from any IR. Round-trip is a force-multiplier for AI editing.

---

## 4. Pillar B — the complete studio

Capability breadth, ordered by leverage for the stated goal:

### B1 · Score & MIDI interop  *(highest-demand gap)*
There is **no MIDI or MusicXML import** today — the `static/fixtures` motets/fugues
were transcribed *by hand*, which is exactly why they're full of placeholders. A
**MusicXML/MIDI → IR importer** turns real scores into renderable specs and is the
bridge from "type notes by hand" to "ingest the repertoire." MIDI **export** (from
the IR's explicit events) is comparatively trivial and immediately useful for DAW
interop.

### B2 · Recorded-audio / sample-first tracking
The README's one explicit "not implemented": *"recorded material would enter
cleanly as a content-addressed sample layer."* Make it real — sample-first layers
with time/pitch handling — so the studio covers *captured* as well as *synthesized*
sound. Content-addressing keeps it deterministic and hash-tracked.

### B3 · Modulation & routing depth
A complete studio needs more than per-parameter `auto` curves: **LFOs, envelope
followers, a modulation matrix**, and **aux sends/returns** (parallel compression,
shared reverb buses with independent send levels). All of it compiles to explicit
IR events — no hidden state, determinism preserved.

### B4 · Arrangement timeline
Campaigns/cutdowns exist, but a first-class **song-form / arrangement layer**
(sections, repeats, transitions across assets) would let the studio express whole
pieces, not just cues — and gives the AI a high-altitude structural handle.

### B5 · Fast interactive preview
Render is offline (tens of seconds for cinematic masters). A **low-latency preview
path** (already hinted by `web_preview`) — partial/region renders, cached tails —
makes iterative AI *and* human auditioning practical.

---

## 5. Pillar C — the most advanced IR

Make the IR the hub everything orbits:

### C1 · Formal, typed, published schema
Replace hand-rolled validation with a declarative typed schema (Phase 0). Publish
it. A versioned IR schema is the contract the DSL, the studio, the AI, and external
tools all bind to.

### C2 · Multi-altitude IR (stable layering contract)
Today emotion/intensity/motifs expand to explicit params (good). Formalize **two
co-resident layers with a stable contract**: a **semantic-intent layer** (emotion,
markers, sections, motif identity, dynamics marks) *preserved alongside* the
**expanded render layer** (explicit events/params). An AI then reasons and edits at
whichever altitude fits — and edits at one layer re-expand deterministically.

### C3 · Full provenance / bill-of-materials
Extend the already-good content-addressing into a complete **provenance graph** in
every manifest: engine version, every plugin, every sample/IR/library hash, the
exact grammar version, and the analysis snapshot — a verifiable BOM for any
delivered asset. This is what makes renders auditable and reproducible in
regulated/branded contexts.

### C4 · Analysis write-back
Persist the A3 analysis features **back into the IR/manifest** as annotations, so a
render carries its own measured description — the substrate for AI critique, A/B
diffing, and regression detection.

### C5 · Interop exports (IR as a standards hub)
The IR already exports stems + markers + EDL. Extend to **MIDI, MusicXML, and a
session/stems bundle**, so AudioForge interoperates with the wider studio world
*from the IR outward*. Combined with B1's import, the IR becomes a
**bidirectional interchange format**, not a dead end.

---

## 6. How the pillars reinforce

- A **typed, published IR schema** (C1) is simultaneously the AI's contract (A1),
  the validator (Phase 0), and the interop anchor (C5).
- **Grammar-constrained generation** (A2) and **structured diagnostics** (Phase 0)
  are the same investment in `lark` viewed from two sides.
- **Closed-loop analysis** (A3) + **analysis write-back** (C4) are one feature
  serving both AI feedback and IR richness.
- **Score/MIDI interop** (B1) feeds the **validated corpus** (A5) with real
  repertoire and exercises the **multi-altitude IR** (C2).

One architecture, mutually reinforcing — provided determinism is never sacrificed.

---

## 7. Phased roadmap

| Phase | Theme | Initiatives | Powered by |
|-------|-------|-------------|------------|
| **0 — Foundation** | Make the contract solid | Resolve pass + line-numbered diagnostics (P0); validate/render parity + property test (P1); formal typed IR schema | pydantic/jsonschema, hypothesis, threadpoolctl, `pyproject.toml` |
| **1 — Close the AI loop** | DSL the AI can trust & drive | Capability manifest (A1); Lark-backed EBNF/GBNF grammar artifacts (A2); analysis pass + write-back (A3/C4); MCP/tool surface (A4) | lark, pyloudnorm |
| **2 — Studio breadth** | From cues to complete works | Modulation/routing depth (B3); arrangement timeline (B4); recorded-audio layers (B2); fast preview (B5) | soundfile (I/O) |
| **3 — Interop hub** | IR ↔ the world | MusicXML/MIDI import (B1); MIDI/MusicXML/session export (C5); IR→DSL round-trip (A5); validated corpus | mido/music21 (import-only, determinism-fenced) |

Each phase is independently shippable and independently valuable. Phase 0 is
strictly first.

---

## 8. Non-negotiables (the moat)

1. **Determinism is sacred.** No dependency or feature may touch rendered samples
   unless it is exactly reproducible across runs, versions, and platforms. Importers
   and analyzers live *outside* the render path. (See the libraries doc's avoid-list:
   librosa/numba/pydub/torch are determinism-hostile.)
2. **The IR is the truth.** Every sugar (emotion, motif, score import, AI mutation)
   must expand to explicit, inspectable IR — nothing renders from hidden state.
3. **Compile never raises; the studio never tracebacks.** Every failure is a
   structured, line-numbered diagnostic an agent can act on.

These three rules are what make "complete studio + best AI-ready DSL + most advanced
IR" a single defensible product rather than a feature pile. Hold them, and the
roadmap above is additive; break them, and the moat is gone.
