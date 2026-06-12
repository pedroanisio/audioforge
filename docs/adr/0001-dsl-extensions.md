---
disclaimer:
  notice: >-
    No information within this document should be taken for granted.
    Any statement or premise not backed by a real logical definition
    or verifiable reference may be invalid, erroneous, or a hallucination.
  generated_by: "Claude Opus 4.8 (1M context) via Claude Code"
  date: "2026-06-12"
---

# ADR 0001 — DSL extensions: includes, templates, functions, classes

## Disclaimer

This work is subject to the methodological caveats and commitments described in [@DISCLAIMER.md](../../DISCLAIMER.md).
> No statement or premise not backed by a real logical definition or verifiable reference should be taken for granted.

**Status:** accepted · includes implemented (DSL 1.10) · remainder sequenced.

## Context

A proposal asked whether the `.af` DSL should gain includes, templates,
functions, and classes. Grounding the question in the actual DSL (1.9) corrected
three premises:

- The DSL is **not** zero-abstraction: `motif`s are already pure macros that
  expand to inert events (`Motifs are pure macros — the IR contains only
  expanded notes`), alongside chord voicings, transforms, `arp`, euclid, and
  emotion macros. "Templates over events" already ship.
- **Key/scale constraint linting already exists** as an advisory diagnostic
  (`dsl.py` `_scale_pitch_classes` → out-of-scale warning, tagged "intentional
  chromaticism is fine").
- The **versioned-generator escape valve already exists**: `gen voice_leading /
  passing_tone / suspension` plus the five-point plugin system (names folded
  into the spec hash).

## Decision — the governing invariant (corrected)

The proposal's slogan "substitution is safe, computation is not" is imprecise:
the trusted compiler *already* computes heavily (emotion expansion, analytic
beat→second tempo integration, Bjorklund, voicing/voice-leading,
`perform: rubato`). The real invariant is:

> **All computation lives behind a versioned, hash-covered boundary (engine,
> plugin, or `gen` library). User-authored files stay inert, substitution-only,
> statically-bounded data — and the spec hash is computed on the fully-resolved
> form, so two surface spellings of the same music hash identically.**

Every item below is judged against that line.

## Resolutions

### Includes — **accepted, implemented (DSL 1.10).**
Content-pinned `import "frag.afi" @ sha256:…` for reusable `motif`/`bus`
fragments. Pure pre-parse substitution (`audioforge/includes.py`):

- pinned by SHA-256 (mismatch refuses); **content-address, not a re-pointable
  version tag** — version tags would need a committed lockfile mapping
  versions→hashes and are deferred;
- acyclic graph (cycles refuse); diamonds de-duplicate;
- flat names with collision detection (duplicate name refuses);
- the **resolved source is what compiles**, so an imported patch is
  byte-identical to the inline form (same `spec_hash`, same audio — locked by
  test). Pins recorded as hash-excluded `_meta.imports` provenance;
- `audioforge expand` materialises the single resolved file.

### Templates — **mostly already present; derivation-with-override deferred.**
Parametric templates over events *are* `motif`s. The remaining sense — a
skeleton with overridable holes — is **derivation-with-override** (`bus x :
presets.y { gain: -2db }`), deferred to the next slice with one hard
requirement the proposal omitted: **specify collection-merge semantics**. Scalar
override is trivial; the load-bearing question is list/dict fields (when a
parent sets `fx: [...]` and the child also sets `fx:`, replace or append?).
Decision: **replace by default**, with an explicit `extend(...)` if append is
ever needed, and `expand --flatten` must show the resolved chain. Implicit merge
is the hidden state we are avoiding.

### Functions — **refused.**
User-defined computation would break decidable validation, statically-bounded
expansion, and — the agent-specific killer — turn local literal bugs into
non-local logic bugs an agent cannot hear. Demand for power routes into
versioned `gen` generators and plugins, which already exist. Documented as a
non-goal.

### Classes — **split.**
1. *Archetypes* (instrument+FX+section+bus bundle a layer instantiates):
   accepted in principle as **single-level derivation-with-override, one hop, no
   hierarchies**, `expand --flatten` mandatory. Same mechanism and the same
   merge-semantics requirement as templates above. Deferred with derivation.
2. *Constraint classes* (key/scale/range as a musical type system): the
   **key/scale half already ships** as advisory diagnostics; the work is to
   *formalise* it — stable error codes (`L2xx`) and a declared strictness
   (**advisory by default**; music breaks the scale on purpose; strict opt-in).
   **Range/playability is not pure event analysis** — it needs the instrument
   catalog (`catalog.py` `lokey/hikey`, surfaced in `plan.py`), i.e. the
   Library-Aware Orchestration pillar (G5), not a free lint. Sequenced there.

## Sequencing

1. **Includes** — done (this ADR's implementation, DSL 1.10).
2. **Derivation-with-override / archetypes** — one hop, *specified* collection
   merge, `expand --flatten`. Needs a grammar change (dotted refs / `as ns`
   namespacing rides along here).
3. **Formalise constraint diagnostics** — codes + strictness for key/scale now;
   range under G5.
4. **Functions** — closed; documented non-goal with `gen`/plugins as the
   sanctioned escape.

## Consequences

- Includes cut context spent re-emitting boilerplate without weakening any
  validation or reproducibility property.
- The DSL stays inert data; power continues to grow only behind versioned,
  hash-covered boundaries.
- Namespacing's absence means flat-name collisions are possible across large
  import sets until slice 2; collision detection makes that loud, not silent.

---

[← back to README](../../README.md)
