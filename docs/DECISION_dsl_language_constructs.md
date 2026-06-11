# Decision Record — General-Purpose Language Constructs in the `.af` DSL

**Date:** 2026-06-11
**Engine:** 2.14.0 · DSL 1.7
**Status:** Analysis / not adopted
**Question:** Should the `.af` DSL gain general-purpose **variables, control blocks
(loops/conditionals), classes, and methods** — i.e. become "musical-language-like"?

**Builds on:**
[North-Star](PROPOSAL_north_star_studio_dsl_ir.md) ·
[Smart Music DSL](PROPOSAL_smart_music_dsl.md) ·
[DSL Spec](DSL_SPEC.md) · [README](../README.md)

---

## 0. How to read this document

This is an **argument map**, not a recommendation essay. It separates:

1. **Premises** (`P#`) — load-bearing facts: either *concept commitments* (stated in
   the docs), *empirical facts* (true of the code today), or *assumptions*.
2. **Conclusions** (`C#`) — each annotated with the exact premises it **depends on**.
3. A **sensitivity matrix** — for every premise, *if it changed*, which conclusions
   flip, and what the new verdict would be.
4. A **re-analysis watchlist** — concrete, observable events that should reopen this
   decision.

The point of the structure: **no conclusion here is unconditional.** Each is only as
true as its premises. Change a premise, follow its row in §4, and re-derive.

---

## 1. Premises

Each premise has a **type**, a **source**, and a **stability** estimate (how likely
it is to change). Stability matters because low-stability premises make their
dependent conclusions fragile.

| ID | Premise | Type | Source | Stability |
|----|---------|------|--------|-----------|
| **P1** | **Determinism is the moat.** No feature may touch rendered samples unless exactly reproducible across runs/versions/platforms. | Concept commitment (non-negotiable) | North-Star §0, §8.1; README "Why deterministic" | Very high |
| **P2** | **The IR is the truth; the DSL is sugar.** Every construct must expand at compile time into explicit, inspectable IR — nothing renders from hidden state. | Concept commitment (non-negotiable) | README design rule; North-Star §8.2; DSL Spec §1 | Very high |
| **P3** | **Compile never raises; failures are structured, line-numbered diagnostics.** | Concept commitment (non-negotiable) | North-Star §8.3; README v2.14 contract | Very high |
| **P4** | **AI-readiness is emergent from a *constrained*, typed, introspectable surface**, and **grammar-constrained generation (EBNF/GBNF) is a target differentiator** — "syntactically valid `.af` by construction." | Concept commitment (roadmap Pillar A) | North-Star A1, A2 | Medium |
| **P5** | **The DSL's direction of travel is *up*: intent over assembly.** The DSL should encode musical knowledge so the author assembles *less* by hand. | Concept commitment (roadmap direction) | Smart-Music §0, §2 | Medium |
| **P6** | **IR↔DSL round-trip is a goal and partially exists.** A decompiler ships today (`decompile` CLI / `audioforge/decompile.py`); round-trip editing is a force-multiplier for AI. | Concept commitment + empirical | North-Star A5; `audioforge/decompile.py` | Medium |
| **P7** | **The desired IR is multi-altitude:** a semantic-intent layer *preserved alongside* the expanded render layer, edited at whichever altitude fits. | Concept commitment (roadmap C2) | North-Star C2 | Medium |
| **P8** | **A host-language SDK already provides arbitrary programmatic generation** of specs (Python). | Empirical | README SDK; `scripts/gen_jazz.py` | High |
| **P9** | **The compiler is a compile-time macro-expander** over a keyword-dispatched recursive-descent parser with *raw-token* property values. **There is no expression evaluator and no symbol table today.** Adding declarative *statements* is cheap; adding *expressions/scopes* is net-new machinery. | Empirical | `audioforge/dsl.py` (`Parser`, `prop_line`, `_resolve_vary`, `play_stmt`) | High |
| **P10** | **Authoring repetition is a real, demonstrated pain.** Iterating a progression and parameterizing licks today requires leaving the DSL for Python. | Empirical | `scripts/gen_jazz.py` (walking-bass loop, `LICKS`, density arrays) | High |
| **P11** | **The current DSL cannot express non-termination.** It is declarative; there is no halting concern at compile time. | Empirical | `audioforge/dsl.py` (no loops/recursion in the grammar) | High |

**Existing precedents (supporting, not premises).** Several requested constructs
already exist in partial form and stay inside P1–P3 today:
`vary(a,b,c)` ≈ a pure deterministic *expression* (`_resolve_vary`);
`play motif … invert/transpose` ≈ a *method call*;
`layer`/`bus` + `_merge_defaults` + `style:` defaults ≈ *classes with inheritance*;
`loop:`, tempo/key maps, arp/chord expansion ≈ *bounded iteration*.

---

## 2. The proposal under evaluation

> Add to `.af`: (a) **variables** with scope, (b) **control blocks** — bounded loops
> and compile-time conditionals, (c) **classes** — instantiable templates with fields
> and inheritance, (d) **methods** — parameterized, callable behavior.

Two readings are evaluated separately because they diverge sharply:

- **Proposal-G (general-purpose):** variables as scripting state, general control
  flow, OOP classes, free methods — a small programming language inside `.af`.
- **Proposal-B (bounded/declarative subset):** named musical *constants*;
  *arrangement-level* `repeat`/`section`/`for chord in progression` preserved as
  intent nodes; parameterized **motifs** (`func lick(root)`); **voice/section
  templates** via the existing merge machinery.

---

## 3. Conclusions (with explicit premise dependencies)

> Notation: **C# [depends on: P…]**. A conclusion is *live* only while every premise
> it cites holds in its current form.

**C1 — Feasible. [P9]**
Both Proposal-G and Proposal-B fit the macro-expansion architecture. Statements are
cheap; expressions/scopes are the only net-new machinery.
*Status: valid.*

**C2 — Determinism-neutral *iff* kept pure and total. [P1, P2, P11]**
If every construct is pure, side-effect-free, and **guaranteed to terminate**, full
expansion to explicit IR preserves the moat. This is conditional, not free.
*Status: valid under the totality condition; see C7.*

**C3 — Proposal-G weakens grammar-constrained generation. [P4]**
A CFG/GBNF can constrain flat declarations completely but **cannot** express
"defined before use," scope resolution, unit/type compatibility, or bounded
recursion. Correctness moves from *guaranteed by grammar* to *caught by diagnostics*
— a regression in a stated differentiator.
*Status: valid while P4 holds. Proposal-B largely avoids this (its forms are
locally CFG-expressible).*

**C4 — Proposal-G inverts the authoring altitude. [P5]**
A hand-written `for`-loop that assembles a walking bass *is the author doing* the
work the `ensemble:`/`perform:` passes are meant to do *for* them. It competes with
the north-star direction instead of reinforcing it.
*Status: valid while P5 holds.*

**C5 — Proposal-G makes AI authorship harder, not easier. [P4, P5]**
The intended AI surface is "small, reliable." Binding, scope, and evaluation order
enlarge the surface an LLM must track — the opposite of a constrained, predictable
target.
*Status: valid while P4 **and** P5 hold.*

**C6 — Proposal-G breaks clean IR↔DSL round-trip. [P6, P7]**
Once an author writes a `for`/`func`, expansion is **lossy and one-way**: a
decompiler can only re-emit the unrolled flat form. The "receive IR → edit at DSL
altitude → re-emit" loop dies for any agent that received only the IR.
*Status: valid while P6 **or** P7 holds. Proposal-B avoids this **only if** its
constructs are preserved as intent nodes (P7).*

**C7 — Proposal-G introduces a permanent compile-time totality concern. [P1, P11]**
Today non-termination is *inexpressible*. Adding control flow + methods creates the
*category* (infinite/exponential expansion). Determinism then survives only by an
**enforced, perpetual** totality boundary (bounded loops, no general recursion).
*Status: valid while P11 holds (i.e. until/unless a totality verifier is adopted).*

**C8 — The need is already served elsewhere; only a thin slice is unserved. [P8, P10]**
Arbitrary generation belongs in the SDK (P8), which already exists and is used
(P10). The genuinely unserved slice is *in-spec, round-trippable musical structure*
— which is Proposal-B, and which the roadmap already anticipates (B4 arrangement
timeline, C2 multi-altitude IR).
*Status: valid while P8 holds.*

**C9 — VERDICT. [P1, P2, P4, P5, P6, P7, P8]**
- **Proposal-G is net concept-negative.** It trades four stated differentiators
  (grammar-constrained authorship [C3], intent-up altitude [C4], clean round-trip
  [C6], no-totality-concern determinism [C7]) for sugar already available in the SDK
  [C8]. It converts *"a constrained, hashable, round-trippable spec an agent authors
  by construction"* into *"a small programming language that emits audio IR"* — a
  different product with a weaker moat.
- **Proposal-B is concept-positive** *iff* its constructs are bounded, declarative,
  and **preserved in the intent layer** (P7) so they still decompile and still
  GBNF-constrain.

**Litmus test for any future construct (derived from C3/C6/C7/C4):** *Does it still
decompile to its authored form, still GBNF-constrain, still guarantee termination,
and still raise (not lower) the altitude?* General variables/classes/methods fail;
arrangement `repeat`/`section`, parameterized motifs, and voice templates pass.

---

## 4. Sensitivity matrix — "if this premise changes, re-analyze"

Read each row as: *if the premise moves to the stated new state, then the listed
conclusions change status, and the verdict should be re-derived.*

| If premise… | …changes to | Then these flip | New effect on verdict (C9) |
|-------------|-------------|-----------------|----------------------------|
| **P1** (determinism sacred) | Relaxed (some non-reproducibility tolerated) | C2, C7 weaken as *blockers* | Moat already gone; this whole analysis is moot — determinism was the differentiator. **Re-do from scratch.** |
| **P2** (IR is truth) | Relaxed (render from hidden state allowed) | C2 voided | Inspectability gone; constructs could hide state. **Verdict no longer applies.** |
| **P3** (compile never raises) | Relaxed | C3's mitigation weakens (diagnostics matter less) | Minor; verdict unchanged. |
| **P4** (grammar-constrained gen is a goal) | **Dropped** from roadmap | **C3 void, C5 weakens** | A major cost of Proposal-G disappears. Verdict shifts toward *neutral*; Proposal-G becomes defensible if P5/P6 also move. **Re-analyze.** |
| **P5** (altitude goes up / intent-first) | **Reversed** (DSL should expose explicit low-level control) | **C4 void, C5 void** | Proposal-G stops competing with the roadmap; becomes *aligned*. Combined with P4 dropping, verdict could flip to **adopt-G**. **Re-analyze.** |
| **P6** (round-trip is a goal) | **Dropped** | **C6 void** (for the round-trip half) | One of four costs gone; verdict softens but C3/C4/C7 still stand unless they also move. |
| **P7** (multi-altitude IR ships with intent-node preservation) | **Realized** | **C6 void for intent-preserved nodes** | Makes **Proposal-B fully safe to expand**; strengthens the "adopt-B" recommendation. Does *not* rescue Proposal-G (its constructs aren't musical intent). **Re-analyze B's scope.** |
| **P8** (SDK provides generation) | **Removed / deprecated** | **C8 void** | The "use the SDK instead" escape hatch closes; pressure to put generation *in* `.af` rises. Verdict softens toward adopting at least Proposal-B, possibly more. **Re-analyze.** |
| **P9** (macro-expander, no evaluator) | Already has an expression evaluator + symbol table (e.g. shipped for another feature) | C1 strengthens (cost ↓) | Lowers implementation cost only; does **not** change concept costs (C3/C4/C6/C7). Cheaper ≠ wiser. |
| **P10** (repetition is painful) | Pain disappears (e.g. smart directives cover all real cases) | C8 strengthens | Need evaporates; **do nothing** becomes correct. |
| **P11** (non-termination inexpressible) | A **totality verifier** is adopted (proven-terminating sub-language) | **C7 mitigated** | Removes the permanent-vigilance cost. Makes bounded control flow safer; nudges toward Proposal-B, and lowers (not removes) Proposal-G's risk. |

**Compound trigger to watch for:** if **P4 *and* P5 both move** (grammar-constraint
dropped **and** altitude-direction reversed), the two largest concept costs of
Proposal-G vanish simultaneously and **the verdict can flip from reject-G to
adopt-G.** That pair is the decision's center of gravity.

---

## 5. Re-analysis watchlist (observable triggers)

Reopen this decision if any of the following becomes true:

- [ ] The roadmap **drops grammar-constrained generation (A2)** → re-evaluate C3, C5.
- [ ] The roadmap **drops or deprioritizes decompilation / round-trip (A5/C2)** →
      re-evaluate C6.
- [ ] A product decision **reverses the DSL altitude** toward explicit low-level
      control and away from smart directives → re-evaluate C4, C5, **and the verdict**.
- [ ] **Multi-altitude IR (C2)** ships with intent-node preservation → green-light
      Proposal-B's bounded constructs as intent nodes.
- [ ] A **totality-checked sub-language / verifier** lands → re-evaluate C7, and the
      acceptable scope of control flow.
- [ ] The **SDK generation path is removed or discouraged** → re-evaluate C8 and the
      pressure for in-DSL generation.
- [ ] Evidence that **smart directives (`perform/ensemble/voicing/style`) fail to
      cover real authoring needs**, forcing users back to hand-assembly → strengthens
      the case for at least Proposal-B (and possibly more).

---

## 6. Recommendation (conditional on §1 holding as written)

While P1–P11 hold in their current form:

1. **Do not adopt Proposal-G** (general variables / OOP classes / free methods /
   general control flow) in `.af`. Keep arbitrary computation in the **SDK**.
2. **Consider Proposal-B**, scoped to constructs that pass the §3 litmus test:
   - **Named musical constants** (`let swing = 0.6`) — substitution only, no scripting state.
   - **Arrangement-level `repeat` / `section` / `for chord in progression`** —
     **bounded**, and **preserved as intent nodes** (gated on P7 to keep round-trip).
   - **Parameterized motifs** (`func lick(root) { … }`) — a small generalization of
     `play … transform`.
   - **Voice / section templates** — via the existing `style:` / `_merge_defaults`
     machinery, framed as *musical* abstractions, not OOP.
3. **Sequence:** ship **C2 multi-altitude IR (P7) first**; only then expand
   Proposal-B's iteration constructs, so they decompile and GBNF-constrain by
   construction.

This recommendation is **defeasible**: it is valid exactly as long as the premises
in §1 are. If a §5 trigger fires, walk §4 and re-derive before acting.
