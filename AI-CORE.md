---
disclaimer:
  notice: >-
    No information within this document should be taken for granted.
    Any statement or premise not backed by a real logical definition
    or verifiable reference may be invalid, erroneous, or a hallucination.
  generated_by: "Claude Opus 4.8 (1M context) via Claude Code; revised by Claude Opus 5.5 via Claude Code"
  date: "2026-09-28"
---

# AI Core Concepts

The concepts an agent must hold to author, inspect, and repair AudioForge
assets. They are not peers: one is the **premise** that frames the rest, one is
a **constraint** every concept obeys, one is the **thesis** the project asserts,
and the remainder are the **pillars** that make that thesis defensible. Each
links to its authoritative definition in
[docs/DSL_GAP_SPEC.md](docs/DSL_GAP_SPEC.md).

---

## 0. Premise — the consumption model

AudioForge is reached through three paths, and they do not enter through the
same door:

```
HUMAN ──▶ UI ──▶ Engine ──▶ AF          (direct: human drives the tooling)
HUMAN ──▶ AI ──▶ AF IR                  (mediated: human prompts an agent)
AI ──────────────▶ AF ──▶ Engine ──▶ Compiler   (native: agent authors directly)
```

- **Agentic AI as a first-class consumer** — the human can reach the artifact
  through a UI and the engine, *or* prompt an AI that interacts with the AF IR
  on the human's behalf; the AI also authors the `.af` surface directly and
  drives it down through the engine and compiler. On both AI paths there is no
  UI to absorb ambiguity or repair malformed input — the agent reads and writes
  the IR itself. Every concept below exists because those paths must be safe,
  inspectable, and verifiable without a human watching each step.

## 1. Foundational constraint

Everything below rests on this; nothing may contradict it.

- **The IR Is Truth** — the DSL is the authoring surface; the JSON IR is the
  render contract. Smart syntax, macros, style packs, and agent intent are
  permitted only when their output is explicit and diffable in IR. This is what
  lets an agent read exactly what will render.
  See [DSL_GAP_SPEC.md §3.2](docs/DSL_GAP_SPEC.md).

## 2. Thesis

The claim the constraint above is meant to support.

- **Universal Expression Claim** — AudioForge expresses composed, produced, and
  hybrid music workflows; its Smart DSL is universal *in principle* because it
  unifies symbolic structure, parametric synthesis, performance semantics,
  production automation, interop, and content-addressed audio. The remaining
  work is coverage, ergonomics, and verification — not a theoretical
  expressiveness gap. See [DSL_GAP_SPEC.md §2](docs/DSL_GAP_SPEC.md).

## 3. Pillars (gap contracts delivered; strong universality still pending)

The capabilities that move the thesis from "universal in principle" to
"universal without qualification". Each pillar's initial contract is now closed
in [DSL_GAP_SPEC.md](docs/DSL_GAP_SPEC.md); the strong-universality acceptance
criteria in [§5](docs/DSL_GAP_SPEC.md) remain the open work.

- **Formal Universal Music IR Schema** — a versioned, published schema that
  separates semantic intent, expanded render data, and provenance, so the IR is
  a checkable contract rather than implicit dictionaries. Delivered:
  `audioforge/ir_schema.py` → `docs/ir.schema.json` (G2 closed).
  See [DSL_GAP_SPEC.md G2](docs/DSL_GAP_SPEC.md).
- **Semantic Round-Trip Preservation** — `DSL → IR → DSL → IR` that preserves
  authored *altitude* (smart directives, motifs, intent), not just
  render-equivalent output, so an agent reads back what it wrote. Delivered:
  `_meta.semantic` capture plus `decompile` round-trip diagnostics (G4 closed).
  See [DSL_GAP_SPEC.md G4](docs/DSL_GAP_SPEC.md).
- **Library-Aware Orchestration** — orchestration that chooses playable
  instruments from a catalog, enforces comfortable/hard ranges, selects
  articulations by technique, and forms divisi from real instrument
  capabilities. Delivered: `catalog.DEFAULT_INSTRUMENT_CAPABILITIES` enforced by
  validation (G5 closed). See [DSL_GAP_SPEC.md G5](docs/DSL_GAP_SPEC.md).
- **Interop Depth** — documented MIDI/MusicXML subsets, real-world fixture
  coverage, session/stems bundle export, and structured lossy-conversion
  diagnostics. Delivered: `docs/INTEROP.md` coverage matrix and
  `interop_diagnostics()` (G8 initial contract closed).
  See [DSL_GAP_SPEC.md G8](docs/DSL_GAP_SPEC.md).
