---
disclaimer:
  notice: >-
    No information within this document should be taken for granted.
    Any statement or premise not backed by a real logical definition
    or verifiable reference may be invalid, erroneous, or a hallucination.
  generated_by: "Claude Opus 4.8 (1M context) via Claude Code"
  date: "2026-07-04"
---

# AudioForge — Canonical Roadmap

> **This is the single, canonical roadmap for the AudioForge codebase.** It
> supersedes any narrower planning document. It is organized into three tracks
> that advance in parallel:
>
> - **Track E — Engineering discipline & contract infrastructure** (`AF-R01`…`AF-R19`).
>   The meta-infrastructure that makes a contract-first, agent-facing,
>   reproducibility-driven project *trustworthy*. Sourced from a direct read of
>   the sibling FrameForge project (`../frameforge`, FrameGraph v2).
> - **Track M — Music-theory & compositional capability** (`AF-M01`…`AF-M07`).
>   The music-theoretic depth that makes AudioForge *musically expressive* rather
>   than a 12-TET note-stamping engine. Sourced from the research corpus —
>   principally Julian Hook, *Exploring Musical Spaces* (Oxford, 2022) — cross-
>   referenced against the codebase's actual capability surface.
> - **Track X — Algorithmic & stochastic composition** (`AF-X01`…`AF-X04`).
>   The *computer-music* lineage: sieves, seeded stochastic processes, and dynamic
>   stochastic synthesis. Sourced from Iannis Xenakis, *Formalized Music*
>   (Pendragon, 1992), cross-referenced against the codebase. Where Track M builds
>   the transformational/common-practice tradition, Track X builds the
>   algorithmic one — the tradition whose "mechanizable functions" ideal the
>   engine's seeded determinism is already built to realize.
>
> Every item is an actionable work unit with a Definition of Ready (DoR), a
> Definition of Done (DoD), and a full spec. The two tracks are not independent:
> Track M changes render-output bytes, so every Track-M item MUST land behind the
> golden-audio gate (`AF-R06`) that Track E builds — capability work and
> determinism discipline are co-dependent.
>
> **Source basis.** Track E is grounded in a direct read of both repositories on
> 2026-07-04. Track M is grounded in machine-verified sentence retrieval from the
> research corpus (GraphQL endpoint; see Appendix §7) plus canonical music-theory
> literature cited with DOI/ISBN. FrameForge paths are relative to `../frameforge`;
> AudioForge paths are relative to this repository root. Where a claim could not
> be verified against a file or a source, it is marked. Per PALS's LAW, treat
> unverified assertions here as untrusted until checked against the references.
>
> **Relationship to the governed registry.** This document is the **human
> specification** — the full spec / DoR / DoD / risks per item. The
> machine-checked **status registry** is [`docs/backlog.yml`](./backlog.yml)
> (system of record for status, ownership, dependencies, and live evidence;
> rendered to [`docs/BACKLOG.md`](./BACKLOG.md); gated by
> `scripts/check-backlog-governance.mjs`). Every `AF-*` item here maps 1:1 to a
> `BL-*` item there (the mapping is carried in each registry item's `tags` and
> `references`). **Rule:** item *status* is owned by `backlog.yml`; item *design*
> is owned by this file. When they disagree, the registry wins on status and this
> file wins on specification — reconcile, do not let them drift.

---

## 0. Executive summary

FrameForge and AudioForge are siblings with the same north star: **a hashed,
inspectable contract is the ground truth, and every derived artifact is either
generated from it or gated against it.** AudioForge already has *unusually
strong runtime-contract drift discipline* — version, schema-JSON, CLI-name,
registry, and grammar-token drift are all guarded by pytest, and a SHA-256
determinism oracle backs `verify`. That is real and it is good.

The gap is **not** the discipline. The gap is that **almost none of it runs
automatically, none of it is composed into a single local gate, and the
agent-facing surface FrameForge treats as a first-class product barely exists
in AudioForge.** FrameForge's transferable idea, stated once and applied
everywhere, is:

> **One source of truth + a `--check` twin for every derived artifact + a test
> that pins the gate itself + a single command (`make check`) that runs them
> all + CI that runs that command.**

AudioForge has the first two-thirds of that sentence and none of the last
third. The highest-leverage work is therefore *cheap*: wire the discipline you
already have into an enforced pipeline. The expensive work — unifying the dual
IR source of truth, a real MCP server, a typed model layer — is genuine but
secondary, and this roadmap is honest about which is which. That
cheap-versus-expensive split governs Track E; **Track M (music-theory
capability, §3) is a parallel workstream** justified on its own merit and gated
behind the same golden oracle (`AF-R06`).

### The single most important Track-E finding — ✅ RESOLVED (2026-07-04)

**Original finding.** AudioForge had no code-gate CI: every drift gate,
determinism test, and regression fixture passed locally via
`scripts/run_tests.sh`, but nothing forced them to run before a merge, so the
entire contract-discipline investment was **advisory.** (A narrow
`backlog-governance.yml` workflow existed, but it gated only the backlog
registry — not the test/drift suite.)

**Resolution.** `AF-R02` (root `Makefile` composing `make check`) and `AF-R01`
(`.github/workflows/ci.yml` running that same `make check` on push/PR across
Python 3.10–3.12) are **implemented and verified** — `make check` runs green
locally (704 passed, 3 skipped) and the gate is now pinned by two regression
tests (`tests/test_makefile_targets.py`, `tests/test_ci_make_check_sync.py`) so
it cannot silently weaken. The discipline is no longer advisory. See the AF-R02
and AF-R01 items for the delivered artifacts.

### Track M — the capability gap, in one sentence

AudioForge's synthesis engine is deep and physically grounded (waveguides,
tension-modulated Karplus-Strong, coupled sympathetic strings, Moog ladder,
Dattorro plate, LUFS mastering) but its **music-theory layer stops at 12-TET
major/minor with literal chord spelling.** The concepts that let a system *reason* about harmony — formal
pitch-class-set operations, `Tn`/`TnI`, neo-Riemannian triadic transformations,
modes beyond major/minor, real tunings and temperaments, functional-harmony
grammar, and minimal-displacement voice leading — are **absent** (verified by a
package-wide read of `theory.py`, `dsl.py`, `grammar.py`, `compose.py`,
`interop.py`). The corpus text *Exploring Musical Spaces* is the canonical formal
reference for exactly these, and Track M ports them.

### The single most important Track-M finding

**The `tuning: edo divisions=N base=A4 hz=440` DSL directive is inert.** It parses
and is stored in `spec["notation"]["tuning"]`, but **no renderer reads it** — every
pitch→frequency conversion in the engine is hardcoded 12-TET (`440 * 2**(x/12)` in
`dsl.note_to_freq`, and `2**(st/12)` resample ratios in `library.py`/`plan.py`).
The DSL therefore *advertises microtuning it does not deliver.* By PALS's LAW this
is not a missing feature; it is an **unverified claim shipped as a capability** —
a correctness defect. `AF-M05` closes it. This is the highest-leverage Track-M item.

### Honest caveats (Rule 1 — unbiased over flattering)

- **Not every FrameForge practice should be copied.** FrameForge's grammar
  ⇄ model gate exists because its EBNF is a hand-maintained *view* of Pydantic
  models. AudioForge's grammar is a real Lark file that is *executed*, so the
  drift surface is different and smaller. Copy the *principle* (gate the mirror),
  not the mechanism.
- **The Pydantic migration (AF-R08) is the one item where "the current approach
  is not broken" is a legitimate argument against.** It is included because it
  removes a real HIGH-severity coupling (two hand-synced IR sources), but it is
  L-effort and is explicitly *not* P0. Do the cheap enforcement wins first;
  they de-risk everything else.
- **Some FrameForge infra does not map.** The font-determinism toolchain
  (`fg-font`) solves "measure-time font ≠ render-time font." AudioForge's analog
  is cross-platform float/BLAS determinism (AF-R16), which is a different and
  harder problem. Do not cargo-cult the font pack; solve the actual problem.

---

## 1. Prioritization

Priority is assigned by **leverage = impact ÷ effort**, with a tie-break toward
items that *unblock* other items or that convert existing-but-dormant work into
enforced work. Complexity uses the mandated XS/S/M/L/XL scale (no time
estimates). Impact and effort are 1–5 (5 = highest).

### Track E — engineering discipline & contract infrastructure

| ID | Item | Priority | Complexity | Impact | Effort | Leverage | Depends on |
|----|------|:--------:|:----------:|:------:|:------:|:--------:|------------|
| **AF-R01** | CI pipeline (`.github/workflows`) | **P0** | S–M | 5 | 2 | ★★★★★ | AF-R02 |
| **AF-R02** | `Makefile` with composed `make check` | **P0** | S | 5 | 1 | ★★★★★ | — |
| **AF-R03** | `AGENTS.md` programmatic reference | **P0** | S | 4 | 2 | ★★★★☆ | AF-R02 |
| **AF-R04** | Ruff + format + type-check config | **P0** | XS–S | 3 | 1 | ★★★★☆ | — |
| **AF-R05** | IR-schema generator with `--check`/`--write` | **P0** | S | 4 | 2 | ★★★★☆ | AF-R02 |
| **AF-R06** | Golden-audio oracle + hash lockfile | **P1** | M | 5 | 3 | ★★★★☆ | AF-R02 |
| **AF-R07** | Persisted capability manifest + status field | **P1** | S–M | 4 | 2 | ★★★★☆ | AF-R05 |
| **AF-R08** | Unify the dual IR source of truth (typed model) | **P1** | L | 5 | 5 | ★★★☆☆ | AF-R05 |
| **AF-R09** | `CHANGELOG.md` + version-bump tool `--check` | **P1** | S | 3 | 1 | ★★★★☆ | — |
| **AF-R10** | MCP server over `agent_tools` (stdio) | **P2** | M–L | 4 | 4 | ★★★☆☆ | AF-R07 |
| **AF-R11** | Docs site (mkdocs-material) + doc-build gate | **P2** | M | 3 | 3 | ★★★☆☆ | AF-R05, AF-R07 |
| **AF-R12** | ADR set (`docs/adr/`) + adoption rule | **P2** | S | 3 | 1 | ★★★★☆ | — |
| **AF-R13** | `codebase-standards.md` ratchet + wire `drift_inspect.py` | **P2** | S | 3 | 2 | ★★★☆☆ | AF-R02 |
| **AF-R14** | `src/` layout + package-boundary AST gate | **P3** | M | 2 | 3 | ★★☆☆☆ | AF-R02 |
| **AF-R15** | Migration codemod keyed to validator codes | **P3** | M | 3 | 3 | ★★★☆☆ | AF-R05, AF-R08 |
| **AF-R16** | Cross-platform numeric-determinism pack | **P3** | L | 4 | 5 | ★★☆☆☆ | AF-R06 |
| **AF-R17** | Explicit filter-automation targets (`auto lowpass/highpass`) | **P1** | S | 4 | 1 | ★★★★☆ | — |
| **AF-R18** | Always-on dead-air render assertion (loud-by-default) | **P1** | S | 4 | 2 | ★★★★☆ | AF-R17 |
| **AF-R19** | Unified render-assertion policy surface | **P2** | M | 3 | 3 | ★★★☆☆ | AF-R17, AF-R18 |

### Track M — music-theory & compositional capability

| ID | Item | Priority | Complexity | Impact | Effort | Leverage | Depends on |
|----|------|:--------:|:----------:|:------:|:------:|:--------:|------------|
| **AF-M01** | Pitch-class-set theory core (normal/prime form, IC-vector, `Tn`/`TnI`) | **P1** | M | 4 | 3 | ★★★★☆ | AF-R06 |
| **AF-M05** | Tuning & temperament engine (activate the inert `tuning:` directive) | **P1** | M–L | 5 | 4 | ★★★★☆ | AF-R06 |
| **AF-M04** | Scale & mode system (modes, pentatonic, octatonic, maximally-even) | **P1** | S–M | 4 | 2 | ★★★★☆ | AF-M01 |
| **AF-M02** | Formal transformation operators + transformation networks | **P2** | M | 3 | 3 | ★★★☆☆ | AF-M01 |
| **AF-M03** | Neo-Riemannian triadic transformations (P/L/R, UTT) + Tonnetz | **P2** | M | 4 | 3 | ★★★★☆ | AF-M01, AF-M02 |
| **AF-M06** | Voice-leading as optimization (minimal-displacement / VL geometry) | **P2** | M | 3 | 3 | ★★★☆☆ | AF-M01, AF-M04 |
| **AF-M07** | Functional-harmony grammar (roman numerals, cadences, progressions) | **P3** | L | 3 | 4 | ★★★☆☆ | AF-M03, AF-M04 |

### Track X — algorithmic & stochastic composition

| ID | Item | Priority | Complexity | Impact | Effort | Leverage | Depends on |
|----|------|:--------:|:----------:|:------:|:------:|:--------:|------------|
| **AF-X02** | Seeded stochastic composition primitives (distributions, Markov, walks) | **P1** | L | 5 | 4 | ★★★★☆ | — |
| **AF-X01** | General sieve engine (residual-class sieves → scales & rhythm) | **P2** | M | 4 | 3 | ★★★★☆ | — |
| **AF-X04** | Positioning ADR — deterministic ground truth under generative music AI | **P2** | XS | 3 | 1 | ★★★☆☆ | — |
| **AF-X03** | Dynamic stochastic synthesis oscillator (GENDYN-style) | **P3** | M | 3 | 3 | ★★★☆☆ | AF-X02 |

### Waves (execution order)

```
Wave 0 — Enforcement Foundation (P0):  make the discipline you already have RUN
         AF-R02 → AF-R04 → AF-R05 → AF-R03 → AF-R01
         (Makefile first so CI just calls it; then the gates it composes; CI last.)

Wave 1 — Contract & Verification Hardening (P1)
         AF-R09, AF-R07 → AF-R06 → AF-R08
         (Cheap wins first; the L-effort IR unification last and optional.)

Wave 2 — Agent & Docs Surface (P2)
         AF-R12 → AF-R13 → AF-R11 → AF-R10

Wave 3 — Structural / Architectural (P3)
         AF-R14, AF-R15, AF-R16  (opportunistic; none blocks a release)

Track M — Music-theory capability (runs AFTER AF-R06 golden gate exists)
  M-Wave 1:  AF-M01 (pc-set core) → AF-M04 (scales/modes) ; AF-M05 (tuning engine)
             (AF-M01 and AF-M05 are independent and can run in parallel.)
  M-Wave 2:  AF-M02 (formal operators) → AF-M03 (neo-Riemannian) ; AF-M06 (voice leading)
  M-Wave 3:  AF-M07 (functional-harmony grammar)
```

**Cross-track gate.** No Track-M item merges before `AF-R06` (golden-audio
oracle) exists: every one of them alters pitch/frequency math and therefore
render bytes, and without the golden gate those changes are unverifiable per
PALS's LAW. `AF-R06` is thus the pivot that unblocks the entire capability track.

### Dependency graph

```
AF-R02 (Makefile) ──┬─▶ AF-R01 (CI)
                    ├─▶ AF-R03 (AGENTS.md)
                    ├─▶ AF-R05 (schema gen) ──┬─▶ AF-R07 (manifest) ──▶ AF-R10 (MCP)
                    │                         └─▶ AF-R08 (typed model) ──▶ AF-R15 (codemod)
                    ├─▶ AF-R06 (golden audio) ──▶ AF-R16 (numeric pack)
                    ├─▶ AF-R13 (standards ratchet)
                    └─▶ AF-R14 (src/ layout)
AF-R05 + AF-R07 ────▶ AF-R11 (docs site)
(independent): AF-R04, AF-R09, AF-R12

AF-R06 (golden gate) ─▶ [unblocks all of Track M]
AF-M01 (pc-set core) ─┬─▶ AF-M02 (operators) ──▶ AF-M03 (neo-Riemannian)
                      ├─▶ AF-M04 (scales) ─────▶ AF-M06 (voice leading)
                      └─▶ AF-M06
AF-M03 + AF-M04 ──────▶ AF-M07 (functional-harmony grammar)
AF-M05 (tuning engine) — independent of AF-M01; needs only AF-R06
```

---

## 2. Track E items — engineering discipline & contract infrastructure

Each item is self-contained: **FrameForge reference → AudioForge gap → Full
spec → DoR → DoD → Risks.** DoR is the gate to *start*; DoD is the gate to
*call it done*.

---

### AF-R01 — CI pipeline that runs the whole gate on every push

- **Priority:** P0 · **Wave:** 0 · **Complexity:** S–M · **Depends on:** AF-R02
- **Status:** ✅ **Implemented (2026-07-04)** — `.github/workflows/ci.yml` runs
  `make check` on push/PR across Python 3.10–3.12; `tests/test_ci_make_check_sync.py`
  pins the CI↔gate binding. *Caveat:* a live GitHub Actions run has not yet been
  observed from this environment; the workflow and its sync test are green, but
  first-run validation (and asset-availability `skipif` for `libraries/`-dependent
  tests) remains to confirm on the runner. The `determinism-cross-os`,
  `native-kernels`, and `lint` jobs from the full spec are **not** yet split out.

**FrameForge reference.** `.github/workflows/ci.yml` runs five jobs; the primary
`python` job *is* `make check` — the exact same composed gate a developer runs
locally. A meta-test (`tests/test_ci_make_check_sync.py`) asserts CI literally
invokes `make check`, so the workflow can never silently drop a gate by
hand-mirroring the target list.

**AudioForge gap.** No `.github/` directory exists. Every drift gate,
determinism test, and regression fixture (`tests/test_ir_schema.py`,
`test_docs_regression.py`, `test_determinism.py`, `test_contract.py`, the 16
script-style suites in `scripts/run_tests.sh`, …) passes locally and runs
*only* when a human remembers to. The contract discipline is unenforced.

**Full spec.**

1. Create `.github/workflows/ci.yml` with jobs:
   - `test` — the primary gate: `make check` (AF-R02). Matrix over
     `python-version: ["3.10", "3.11", "3.12"]` on `ubuntu-latest`. Install via
     `uv sync` (a `uv.lock` already exists) or `pip install -e ".[dev]"`.
   - `determinism-cross-os` (non-blocking initially, then blocking) — runs the
     determinism + `verify` suite on `macos-latest` and `windows-latest` to
     surface cross-platform float drift the README admits is only "checked, not
     assumed." Feeds AF-R16.
   - `lint` — `ruff check` + `ruff format --check` (AF-R04).
   - `native-kernels` — builds the `audioforge/native/*.c` kernels and runs the
     tests that exercise them (bowed/blown/plate-mod), since a C compiler is a
     real runtime dependency that can break silently.
2. Add `tests/test_ci_make_check_sync.py` (port of FrameForge's): parse
   `.github/workflows/ci.yml`, assert the `test` job's run-step invokes
   `make check`, and assert every target composed into `check` (AF-R02) is
   present — so CI and the local gate cannot diverge.
3. Cache: `~/.cache/uv` (or pip) and the compiled native kernels keyed on the
   `.c` file hashes.
4. Trigger on `push` and `pull_request` to `main`.
5. Add a status badge to `README.md`.

**DoR (ready to start when all true):**
- [ ] AF-R02 merged (there is a `make check` to call).
- [ ] `scripts/run_tests.sh` passes on a clean checkout of `main` (baseline green).
- [ ] Decision recorded: `uv sync` vs `pip install -e` as the CI install path.
- [ ] Known-flaky or environment-dependent tests are catalogued (e.g. tests
      needing large `libraries/` assets) and either marked `skipif` or a
      fixture-provisioning step is specified.

**DoD (done when all true):**
- [ ] `.github/workflows/ci.yml` exists; a PR that breaks any existing gate
      (e.g. edits `docs/ir.schema.json` to drift from `ir_json_schema()`) fails CI.
- [ ] The `test` job is green on `main` across the 3.10–3.12 matrix.
- [ ] `tests/test_ci_make_check_sync.py` passes and fails loudly if a target is
      removed from `make check` but left in the workflow (or vice-versa).
- [ ] CI run URL for a green `main` build is recorded in the PR.
- [ ] README shows a passing CI badge.
- [ ] `RELEASE_NOTES.md` (or `CHANGELOG.md` after AF-R09) records the addition.

**Risks.** Large vendored `libraries/` assets may not be present in CI →
guard asset-dependent tests behind a fixture-availability `skipif` rather than
committing gigabytes. Cross-OS float drift is *expected* to fail first; keep
that job non-blocking until AF-R16, but surface it.

---

### AF-R02 — `Makefile` composing every gate into one `make check`

- **Priority:** P0 · **Wave:** 0 · **Complexity:** S · **Depends on:** —
- **Status:** ✅ **Implemented (2026-07-04)** — root `Makefile` with self-documenting
  `make help`; `check: native-check test` composes only *real* gates (`test`
  wraps `scripts/run_tests.sh`, `native-check` asserts a C compiler for the
  deterministic kernels) — no stub gates, honoring the no-placeholder rule. Real
  discrete fast-gates (`schema-check`, `docs-check`, `version-check`) are provided
  for iteration but kept out of `check` to avoid double-running the suite. Pinned
  by `tests/test_makefile_targets.py`. `make check` verified green (704 passed,
  3 skipped, ~88 s). As `AF-R04` (lint) and `AF-R05` (schema `--check`) land, add
  them as `check` prerequisites — the regression test will require them documented.

**FrameForge reference.** `Makefile:64`:
`check: schema-check grammar-check spec-check a11y-check status-check test validate overflow golden-check docs-check docs-linkcheck disclaimer-check`.
One target composes twelve gates; every gate is a `--check`-mode generator or a
test. Developers and CI run the identical command. `make help` is authoritative.

**AudioForge gap.** No `Makefile`. The only orchestration is
`scripts/run_tests.sh`, which runs 16 script-style suites then `pytest -q`. It
is a test runner, not a composed *gate*: it does not include schema regen-check,
lint, doc-build, or a manifest-freshness check as discrete, named targets, and
there is no `make help` surface an agent can introspect.

**Full spec.**

1. Create a root `Makefile` with named, single-purpose targets, each mapping to
   an existing or new check:
   ```makefile
   help:            ## list targets (self-documenting, grep the ## comments)
   test:            ## scripts/run_tests.sh (the 16 suites + pytest)
   schema-check:    ## python -m audioforge.tools.gen_ir_schema --check   (AF-R05)
   manifest-check:  ## python -m audioforge.tools.gen_capability --check   (AF-R07)
   docs-check:      ## pytest tests/test_docs_regression.py tests/test_cli_docs_sync.py ...
   lint:            ## ruff check .                                        (AF-R04)
   format-check:    ## ruff format --check .                              (AF-R04)
   drift-check:     ## python scripts/drift_inspect.py --check            (AF-R13)
   verify-samples:  ## re-render the tracked corpus and compare SHA-256   (AF-R06 seed)
   native:          ## build audioforge/native/*.c kernels
   check: lint format-check schema-check manifest-check docs-check drift-check test
   ```
2. Each `*-check` target must exit non-zero on drift and write nothing (the
   FrameForge "generate-then-`--check`" contract).
3. `make help` parses `##` trailing comments into a target list (standard
   self-documenting-Makefile idiom).
4. Add `tests/test_makefile_targets.py`: assert every target referenced by
   `check:` exists and that `make help` lists it — so the gate list cannot rot.
5. Keep `scripts/run_tests.sh` as the `test` target's implementation (do not
   duplicate the suite list); the Makefile *wraps* it, does not replace it.

**DoR:**
- [ ] AF-R04 and AF-R05 target commands are specified (they can be stubbed to
      `true` initially and filled in as those items land, but the target names
      are fixed now so CI/AGENTS.md reference stable names).
- [ ] Confirm the environment has `make` (POSIX) available in CI images.

**DoD:**
- [ ] `make check` runs on a clean checkout and is green on `main`.
- [ ] `make help` lists every target with a one-line description.
- [ ] Each `*-check` target returns non-zero when its source is drifted
      (demonstrated by a deliberate local drift for at least `schema-check`).
- [ ] `tests/test_makefile_targets.py` passes.
- [ ] `scripts/run_tests.sh` is invoked *by* the Makefile, not forked.

**Risks.** Low. The main trap is duplicating the suite list between the Makefile
and `run_tests.sh` and letting them drift — the `test` target must shell out to
the script, not re-enumerate suites.

---

### AF-R03 — `AGENTS.md` programmatic CLI/tooling reference

- **Priority:** P0 · **Wave:** 0 · **Complexity:** S · **Depends on:** AF-R02

**FrameForge reference.** `AGENTS.md` is a single agent-facing map from intent
to exact command: tables for the runtime rule, every dependency group, every
`make` target, every `tooling/<script>.py` with flags and exit-code contract,
the test bootstrap rule, and the generated-artifact policy ("never hand-edit
generated outputs; edit the source or generator and rerun the paired target").
It is explicitly "derived from the live Makefile, pyproject.toml, and argparse
surfaces; when in doubt, `make help` and `<script> --help` are authoritative."

**AudioForge gap.** `CLAUDE.md` puts `AGENTS.md` at position #2 in the priority
reading order and calls it the "programmatic CLI/tooling reference (when
present)" — **but the file does not exist.** That pointer is dead. The nearest
substitutes are `docs/AGENT_TOOLS.md` (the in-process facade only) and
`AI-CORE.md` (concepts, not commands). An agent has no single command map.

**Full spec.**

1. Create root `AGENTS.md` with the mandated disclaimer frontmatter (Rule 5),
   structured as tables:
   - **Runtime** — Python 3.10+, `numpy`/`scipy`/`lark`/`matplotlib`, the C
     compiler requirement for native kernels, `uv`/venv bootstrap.
   - **CLI verbs** — every `audioforge` subcommand (verified present:
     `render, plan, pack, libgen, ingest, campaign, compile, decompile, repair,
     capabilities, grammar, score, batch, validate, verify`) with its arguments,
     what it emits, and its exit-code contract (e.g. `verify` → `0` reproducible
     / `2` mismatch).
   - **Make targets** — mirror of `make help` (AF-R02).
   - **Scripts** — the build/generation scripts in `scripts/` that are meant to
     be run (distinguish the intended-entrypoint ones from `_`-prefixed internal
     ones).
   - **Agent surface** — `audioforge.agent_tools.run_tool` ops and the
     `agent-tools/1` envelope; after AF-R10, the MCP entrypoint.
   - **Generated-artifact policy** — list every generated file
     (`docs/ir.schema.json`, the capability manifest artifact from AF-R07, any
     mkdocs pages from AF-R11) and the "edit source + rerun target" rule.
2. Add `tests/test_agents_md_sync.py`: assert every CLI verb parsed from
   `cli.py` appears in `AGENTS.md` and vice-versa (the FrameForge "AGENTS.md is
   a hand mirror → gate it" lesson — the drift map already rates such mirrors as
   HIGH risk).
3. Update `CLAUDE.md`'s dead pointer only if needed (it already references the
   file; creating it revives the pointer).

**DoR:**
- [ ] AF-R02 merged so `make` targets are stable names to document.
- [ ] The list of "public" vs internal `scripts/` entrypoints is agreed (the
      `_`-prefix convention suggests internal; confirm).

**DoD:**
- [ ] `AGENTS.md` exists at root with disclaimer frontmatter and all six sections.
- [ ] Every `cli.py` subcommand is documented; `tests/test_agents_md_sync.py`
      fails if a verb is added to `cli.py` without an `AGENTS.md` entry.
- [ ] `CLAUDE.md`'s reading-order reference now resolves to a real file.
- [ ] No command in `AGENTS.md` is stale (spot-checked by running three of them).

**Risks.** It is a hand-maintained mirror and will drift — which is exactly why
the sync test in step 2 is part of the DoD, not optional.

---

### AF-R04 — Ruff lint + format + type-check configuration

- **Priority:** P0 · **Wave:** 0 · **Complexity:** XS–S · **Depends on:** —

**FrameForge reference.** FrameForge carries `.ruff_cache/` and runs lint/format
as part of its bar; `docs/codebase-standards.md` tags each rule
`Enforced`/`Adopted`/`Target`. The point is a machine-enforced style floor.

**AudioForge gap.** The root `pyproject.toml` has **no linter, formatter, or
type-checker configuration** — no ruff, black, or mypy. (The *nested*
`shadowmd/` sub-project has its own ruff/mypy config, but the AudioForge package
has none.) Style and basic correctness (unused imports, undefined names) are
unchecked.

**Full spec.**

1. Add `[tool.ruff]` to root `pyproject.toml`: `target-version = "py310"`,
   `line-length = 100` (or match existing code — measure, do not impose), select
   at minimum `E,F,I,UP,B` (pyflakes, import sort, pyupgrade, bugbear). Add
   per-file ignores for the C-binding shims and the large generated/`_`-prefixed
   scripts if needed.
2. Add `ruff format` as the formatter. Run it once as a dedicated,
   review-labeled "format-only, no logic change" commit so the diff is
   reviewable and the following functional commits stay clean.
3. Optionally add `[tool.mypy]` in *non-strict* mode scoped to the contract
   modules first (`schema.py`, `ir_schema.py`, `version.py`, `capabilities.py`)
   — the modules where a type error is a contract error. Do **not** attempt
   repo-wide strict typing in one shot; that is a separate L effort.
4. Wire `lint` and `format-check` targets into `make check` (AF-R02) and CI
   (AF-R01).

**DoR:**
- [ ] Baseline `ruff check .` output captured so the initial noise is known and
      a "fix vs ignore" decision is made per rule (Rule 8: ship, then adjust —
      do not stall on style).
- [ ] Agreement to land the `ruff format` pass as its own isolated commit.

**DoD:**
- [ ] `ruff check .` and `ruff format --check .` both pass on `main`.
- [ ] Config lives in root `pyproject.toml`.
- [ ] `make lint` and `make format-check` exist and are in `make check`.
- [ ] The format-only commit is separate from any logic commit.

**Risks.** A repo-wide format churns the diff once; isolate it. Over-selecting
ruff rules creates noise that stalls the item — start minimal (`E,F,I`) and
ratchet up later under AF-R13.

---

### AF-R05 — IR-schema generator with `--check` / `--write` (kill the hand-regen)

- **Priority:** P0 · **Wave:** 0 · **Complexity:** S · **Depends on:** AF-R02

**FrameForge reference.** `docs/schema/build_schema.py` generates the JSON
Schema from the Pydantic models and, in `--check` mode, exits non-zero if the
committed `framegraph-v2.schema.json` differs from a fresh build. The committed
file *cannot silently drift* because a generator owns it and a gate re-runs the
generator.

**AudioForge gap.** `audioforge/ir_schema.py::ir_json_schema()` builds the JSON
Schema in code, and `docs/ir.schema.json` is the published copy — but **nothing
writes `docs/ir.schema.json`.** It is regenerated by hand. The only protection
is `tests/test_ir_schema.py::test_published_ir_schema_matches_runtime_source`,
which catches drift *after the fact* but offers no `--write` to fix it. There is
no generator command and no `--check` twin owned by that command; a contributor
who changes the schema has no blessed way to regenerate the artifact.

**Full spec.**

1. Create `audioforge/tools/` (a real, importable tools subpackage — the
   AudioForge analog of FrameForge `tooling/`) and add `gen_ir_schema.py`:
   - `--write` (default): `json.dump(ir_json_schema(), docs/ir.schema.json)` with
     a stable key order and trailing newline (byte-stable output).
   - `--check`: build fresh, compare to the committed file, exit `0` if equal,
     non-zero with a unified diff if not. Write nothing.
2. Keep the existing `test_ir_schema.py` equality test — but retarget it to call
   the new generator so there is one canonical serialization (kill the risk of
   the test and the generator disagreeing on formatting).
3. Add `make schema-check` → `python -m audioforge.tools.gen_ir_schema --check`
   into `make check` (AF-R02) and CI (AF-R01).
4. Document in `AGENTS.md` (AF-R03): "`docs/ir.schema.json` is generated; never
   hand-edit — run `python -m audioforge.tools.gen_ir_schema --write`."
5. Apply the same pattern to `docs/capability.schema.json` if it too is
   hand-maintained (verify; if generated from `capability_manifest_schema()`,
   add a `--check`).

**DoR:**
- [ ] `ir_json_schema()` output is confirmed deterministic (stable dict order;
      no set iteration leaking into key order). If not, fix ordering first — a
      generator must be byte-stable or `--check` will flap.
- [ ] AF-R02 exists so the `schema-check` target has a home.

**DoD:**
- [x] `python -m audioforge.tools.gen_ir_schema --write` reproduces
      `docs/ir.schema.json` byte-for-byte on a clean tree.
- [x] `--check` exits non-zero on a deliberately drifted schema and prints a diff.
- [x] `make schema-check` is in `make check` and CI.
- [x] `test_ir_schema.py` uses the generator's serializer (single source of
      formatting).
- [x] `IR_SCHEMA_VERSION` bump procedure is documented next to the generator.

**Delivered (2026-07-04, Claude Opus 4.8 via Claude Code).** `audioforge/tools/`
package + `gen_ir_schema.py` (`--write`/`--check`, canonical
`sort_keys=True, indent=2` serialization); `tests/test_gen_ir_schema.py` (11
tests); `tests/test_ir_schema.py` retargeted to `render_schema()` for byte-parity;
`Makefile` `schema-check` repurposed to the generator `--check` and promoted to a
`make check` prerequisite (so CI runs it via AF-R01). **Scope boundary:** step 5
(`docs/capability.schema.json` `--check`) is out of scope here because it *is*
**AF-R07**'s deliverable (persisted capability manifest + drift gate); building it
here would duplicate that item's generation seam. `ir.schema.json` — this item's
own subject — is fully delivered.

**Risks.** If `ir_json_schema()` is not order-stable, `--check` will produce
false failures — the DoR guards this. Low overall risk; this is the cheapest
structural win and it directly hardens the existing `test_ir_schema.py`.

---

### AF-R06 — Golden-audio oracle with a committed hash lockfile

- **Priority:** P1 · **Wave:** 1 · **Complexity:** M · **Depends on:** AF-R02

**FrameForge reference.** `tools/render_golden.py` + `tests/golden/`: a compact
per-page **SHA-256 hash lock** (`oracle.lock.json`, "a tiny diffable file") is
the primary gate; on a hash mismatch it falls back to a **numeric tolerance
compare** against full reference renders and *classifies* the diff as
**cosmetic** (skeleton identical, every number within ±ε → reported, not failed)
vs **real drift** (fail). Determinism guards (pinned env vars) keep the hash
host-independent. `--update`/`make golden` re-pins.

**AudioForge gap.** AudioForge's reproducibility oracle is `verify`: re-render a
spec and compare `output_sha256` against the value stored in a *manifest that
travels with the render output* (`renders/*.manifest.json`). There is exactly
**one committed golden** (`tests/golden/dsl_ast.json`, the parser AST) and **no
golden audio corpus and no committed hash lockfile.** Regression protection for
rendered audio depends on a human having kept a manifest around; there is no
`tests/`-resident lock a fresh clone can gate against, and no
cosmetic-vs-real-drift distinction (a hash either matches or it doesn't, which
for float audio across environments is brittle).

**Full spec.**

1. Curate a **small, fast** golden corpus under `tests/golden/audio/`: 5–10 `.af`
   specs covering the render surface (synth voice, sampler, fx chain, loudness
   limiter, stage/room convolution, a `pack` variant, a groove/humanize path).
   Keep them short (≤ a few seconds) so re-rendering in CI is cheap.
2. Create `tests/golden/audio.lock.json`: `{spec_stem: {spec_hash, output_sha256,
   sr, channels, frames}}` — the compact primary lock. Commit it; **do not commit
   the WAVs** (regenerate them).
3. Create `audioforge/tools/render_golden.py`:
   - default/`--check`: for each corpus spec, re-render into a tempdir and
     compare `output_sha256` to the lock. On mismatch, fall back to a **numeric
     tolerance compare**: load both waveforms, compute per-sample max-abs
     difference and an RMS/`ULP`-style tolerance; classify **cosmetic**
     (max-abs ≤ ε, e.g. below −120 dBFS, or within N ULP) vs **real drift**
     (audible/structural). Cosmetic → warn and pass; real → fail with the offending
     spec, the dB delta, and the first divergent sample index.
   - `--update`: re-pin `audio.lock.json` (the AudioForge `make golden`).
   - `--strict`: treat cosmetic as failure (for the same-OS CI lane).
4. Pin determinism-affecting state the way FrameForge pins env vars: assert
   single-threaded BLAS or a fixed thread count during golden render (float
   reduction order depends on it), and record the numeric environment in the
   lock (`numpy`/`scipy` version, BLAS name) so a mismatch is explainable.
5. Add `make golden-check` into `make check` and a **same-OS** golden lane in CI
   (`--strict`) plus a **cross-OS** lane (non-strict, cosmetic-tolerant → feeds
   AF-R16).

**DoR:**
- [ ] The determinism knobs that affect float reduction order are identified
      (BLAS threading, `numpy` reduction order, FFT backend) and a pinning
      strategy is chosen — otherwise the "cosmetic vs real" threshold ε cannot
      be set defensibly.
- [ ] Corpus specs selected and confirmed to render in < ~10 s total.
- [ ] ε defined with a rationale (e.g. "cosmetic = max-abs < −120 dBFS", cite the
      reasoning, not a magic number — Rule 2: formalization means research).

**DoD:**
- [ ] `tests/golden/audio.lock.json` committed; WAVs are **not** committed.
- [ ] `render_golden.py --check` passes on `main` same-OS and fails on a
      deliberate render change (proven by flipping a coefficient).
- [ ] The cosmetic/real classification is exercised by a test that injects a
      sub-ε perturbation (→ cosmetic/pass) and a supra-ε one (→ real/fail).
- [ ] `--update` re-pins reproducibly.
- [ ] `make golden-check` is in `make check`; CI has strict same-OS + tolerant
      cross-OS lanes.
- [ ] The ε threshold and its justification are documented next to the tool.

**Risks.** Cross-platform float drift is real and *expected* — that is the whole
reason for the cosmetic tolerance and the reason the cross-OS lane starts
non-blocking. Setting ε too loose hides real regressions; too tight makes the
gate flap. This is the crux and the DoR forces it to be decided with evidence,
not guessed.

---

### AF-R07 — Persisted capability manifest with a feature-status field + drift gate

- **Priority:** P1 · **Wave:** 1 · **Complexity:** S–M · **Depends on:** AF-R05

**FrameForge reference.** `docs/capability-manifest.json` is a **committed**,
machine-readable tri-state map (`core`/`sdk`/`mcp` booleans per capability),
generated purely by introspection (`gen_capability_manifest.py`), gated by
`manifest-check` and a test that asserts it is introspected-not-hardcoded — and
cross-checked so every validator finding code is documented in
`docs/error-codes.md`.

**AudioForge gap.** `audioforge/capabilities.py::capability_manifest()` returns
a rich dict at runtime and is exposed via `audioforge capabilities`, and
`tests/test_manifest_registry_coverage.py` guards it against the real registries
— genuinely good. But: (a) there is **no committed on-disk artifact** — an agent
or a diff reviewer must *run the CLI* to see the surface; there is no file to
`git diff`; and (b) it is a **capability surface, not a feature-status
tracker** — no per-feature `status: done|planned|wip|deprecated` field. Feature
status lives in prose (`docs/DSL_GAP_SPEC.md` G-numbers, `docs/goal.md`), which
cannot be queried or drift-gated.

**Full spec.**

1. Add `audioforge/tools/gen_capability.py`:
   - `--write`: serialize `capability_manifest()` to committed
     `docs/capability-manifest.json` (byte-stable).
   - `--check`: fail on drift (the AF-R05 pattern).
2. Extend the manifest schema (`capability_manifest_schema()` /
   `docs/capability.schema.json`) with a per-capability `status` enum
   (`stable | experimental | planned | deprecated`) and an optional `since`
   (engine version) and `gap_ref` (link to a `DSL_GAP_SPEC.md` G-number). Derive
   `status` from a single declared registry, not by hand per entry — e.g. a
   capability is `stable` iff it is reachable *and* covered by a test, else
   `experimental`; `planned` entries come from the gap spec. Introspect, do not
   hand-list (the FrameForge invariant).
3. Cross-check: add a test that every `diagnostic_codes` entry in the manifest is
   documented (AudioForge's analog of `error-codes.md`). If no such doc exists,
   create `docs/DIAGNOSTIC_CODES.md` and gate it.
4. Add `make manifest-check` into `make check` and CI.

**DoR:**
- [ ] The definition of each `status` value is written down with the *derivable*
      predicate (what makes something `stable` vs `experimental`) — no per-item
      hand-labeling (Rule 2).
- [ ] AF-R05 merged so the `--write`/`--check` generator pattern is established.

**DoD:**
- [ ] `docs/capability-manifest.json` is committed and regenerated byte-stably
      by `gen_capability.py --write`.
- [ ] Each capability carries a `status` derived by predicate, not hardcoded;
      a test asserts the derivation (add a new voice → it appears as
      `experimental` until tested, then `stable`).
- [ ] `make manifest-check` is in `make check` and CI; a drifted committed
      manifest fails.
- [ ] Every diagnostic code in the manifest is documented and gated.

**Risks.** The `status` derivation predicate is where honesty lives — if it is
"whatever the author typed," it rots. The DoD requires it be derivable. Low
overall risk; mostly additive.

---

### AF-R08 — Unify the dual IR source of truth into one typed model

- **Priority:** P1 · **Wave:** 1 · **Complexity:** L · **Depends on:** AF-R05

**FrameForge reference.** *One* module (`docs/models/framegraph.py`, Pydantic
v2) is the source of truth; the JSON Schema, the validator's type sets, the
grammar view, and the docs are all generated from or gated against it.
`tests/test_validate_type_sets_sync.py` asserts the validator's hand-maintained
`CORE_OBJECT_TYPES` etc. equal the live model unions — so "the validator
silently under-validates a new type" becomes a loud failure.

**AudioForge gap.** AudioForge has **two** hand-synced IR sources that must
agree: `audioforge/schema.py` (the `KINDS`/`LAYER_TYPES`/`OSC_SHAPES`/`FX_TYPES`/
`AUTO_TARGETS` Python `set`/`dict` literals + imperative `validate_spec()`) **and**
`audioforge/ir_schema.py` (a JSON Schema `dict` hand-built in code +
`validate_ir_schema()`). The same facts (which osc shapes exist, which fx types
are legal) are encoded twice. The repo's own `drift-risk-map.md` rates the
registry-coupling here as **HIGH**, and `scripts/drift_inspect.py` exists to
detect it but is **not wired into `run_tests.sh`** (AF-R13). This is the largest
genuine structural weakness FrameForge's practice would fix.

**Full spec (incremental — do not big-bang this).**

1. **Phase A (no behavior change):** designate `schema.py`'s Python registries
   as the *single* source and make `ir_schema.py` *derive* its JSON Schema
   `enum`/`type` lists from those registries by import, rather than restating
   them. Delete every duplicated literal in `ir_schema.py` that can be computed
   from `schema.py`. Add `tests/test_schema_sources_sync.py` (the AudioForge
   `test_validate_type_sets_sync.py`) asserting the JSON Schema's enumerations
   equal `schema.py`'s registries — converting the HIGH coupling into a gated
   invariant even before any typed model exists.
2. **Phase B (optional, typed model):** introduce a typed IR model — **evaluate
   Pydantic v2 vs `@dataclass` + `TypedDict`** honestly. Pydantic buys
   `model_json_schema()` (free, in-sync JSON Schema — exactly AF-R05's dream) and
   validation, at the cost of a new runtime dependency and a rewrite of
   `validate_spec()`. Dataclasses/TypedDict avoid the dependency but do not
   generate a schema for free. **Recommendation:** if AF-R05 is already the
   generation seam, Pydantic v2 removes the most code and best matches PURPOSE's
   "the contract must be inspectable." If a new runtime dep is unacceptable,
   stop at Phase A — it captures ~70% of the value at ~20% of the cost.
3. If Phase B proceeds: the typed model generates `docs/ir.schema.json`
   (subsumes AF-R05's generator), and `validate_spec()` becomes model validation
   plus the semantic rules that a schema cannot express (binding, resource
   resolution, loop-safety) layered on top — mirroring FrameForge's
   "structural (models) + static rules (validator)" split.

**DoR:**
- [ ] `drift-risk-map.md` coupling #(the registry HIGH one) is re-read and the
      exact duplicated literals between `schema.py` and `ir_schema.py` are
      enumerated (the concrete drift surface).
- [ ] Explicit decision recorded: **Phase A only**, or **Phase A + B**, with the
      Pydantic-vs-dataclass tradeoff written as an ADR (AF-R12). This item MUST
      NOT start without that decision — it is the one place where "current
      approach is not broken" is a valid stop.
- [ ] AF-R05 merged (the generation seam exists).

**DoD (Phase A):**
- [ ] No IR fact (osc shape, fx type, layer type, auto target, kind) is stated in
      more than one module; `ir_schema.py` derives from `schema.py`.
- [ ] `tests/test_schema_sources_sync.py` passes and fails if a new osc shape is
      added to `schema.py` but not reflected in the generated JSON Schema.
- [ ] `drift_inspect.py` reports the HIGH registry coupling as resolved (and is
      wired into the gate per AF-R13).
- [ ] All existing determinism/contract tests still green (byte-identical
      renders — this is a refactor, not a behavior change).

**DoD (Phase B, if chosen):**
- [ ] A single typed model generates `docs/ir.schema.json` (AF-R05's generator
      now delegates to it).
- [ ] `validate_spec()` is model validation + explicitly-listed semantic rules;
      every render-time `SpecError` is still pre-reported by `validate` (the
      existing v2.14 contract property test still passes).
- [ ] The ADR recording the Pydantic/dataclass decision is merged.

**Risks.** **This is the highest-effort item and the one most able to introduce
regressions.** Phase A is safe and high-value; Phase B is a genuine refactor of
the validator and IR — do it behind the golden-audio gate (AF-R06) so any
byte-level behavior change is caught. If time is constrained, **ship Phase A and
stop** — that alone closes the HIGH coupling.

---

### AF-R09 — `CHANGELOG.md` + a version-bump tool with `--check`

- **Priority:** P1 · **Wave:** 1 · **Complexity:** S · **Depends on:** —

**FrameForge reference.** A 61 KB structured `CHANGELOG.md`
(`## <type>(<scope>): <summary> (<date>)`), entries annotate schema-vs-non-schema
changes and cite the gates/tests they add. `tooling/bump_version.py` moves *one
logical version* across all its hand-edited literal sites atomically and
`--check` asserts they agree; `test_docs_in_sync.py` fails on any half-bump.

**AudioForge gap.** **No `CHANGELOG.md`.** The human changelog surrogate is
`docs/RELEASE_NOTES.md` (prose, no machine-readable per-version diff). Version
consistency across `audioforge/version.py` (the SoT: `ENGINE_VERSION`,
`DSL_VERSION`), `pyproject.toml`, README, and docs *is* guarded by
`tests/test_version_sources.py` and `test_docs_regression.py` — good — but there
is no *tool* that performs a coordinated bump, so bumping is manual and
error-prone, and there is no Keep-a-Changelog history.

**Full spec.**

1. Create `CHANGELOG.md` following Keep-a-Changelog + the existing
   conventional-commit style (`feat:`/`fix:`/`chore(release):` already in git
   history). Seed it from `RELEASE_NOTES.md` by folding the release notes into
   dated, versioned sections; keep `RELEASE_NOTES.md` as a pointer or retire it
   (decide — do not maintain both silently).
2. Add `audioforge/tools/bump_version.py`:
   - `bump_version.py <new_engine_version> [--dsl <v>]`: rewrites `version.py`,
     `pyproject.toml`, and any README/doc version banner atomically, and inserts
     a new `CHANGELOG.md` section skeleton.
   - `--check`: assert all version sites agree (subsumes part of
     `test_version_sources.py`; keep the test too).
3. Add `make version-check` → `bump_version.py --check` into `make check`.
4. Adopt a CHANGELOG-entry expectation in the contribution flow: a PR that
   changes the engine or DSL updates `CHANGELOG.md` (optionally gate with a soft
   CI check that flags a version bump without a changelog edit).

**DoR:**
- [ ] The exhaustive list of files carrying a version literal is captured (grep
      `2.16.0` / `ENGINE_VERSION` / `DSL_VERSION`).
- [ ] Decision: fold `RELEASE_NOTES.md` into `CHANGELOG.md` or keep both with a
      clear division of labor.

**DoD:**
- [ ] `CHANGELOG.md` exists, seeded from history, with the current version at top.
- [ ] `bump_version.py <v>` performs an atomic multi-file bump and a dry-run
      shows every site updated.
- [ ] `bump_version.py --check` fails on a deliberately half-bumped tree; wired
      into `make check` and CI.
- [ ] No version literal exists that the tool does not manage (proven by the
      `--check`).

**Risks.** Low. The only trap is maintaining `RELEASE_NOTES.md` *and*
`CHANGELOG.md` in parallel — the DoR forces a single-owner decision.

---

### AF-R10 — MCP server over the `agent_tools` facade (stdio)

- **Priority:** P2 · **Wave:** 2 · **Complexity:** M–L · **Depends on:** AF-R07

**FrameForge reference.** `src/framegraph/mcp/` exposes 25 tools over the Model
Context Protocol — a closed author→validate→render→*see* loop, with session
resources (`framegraph://session/{id}/…` YAML/SVG/PNG/diagnostics) the model
reads back, and a local `live/` web UI that *reuses the same functions* rather
than forking a second render path. It is wired into any consumer via
`docker/mcp.docker.json`.

**AudioForge gap.** AudioForge's PURPOSE and `AI-CORE.md` make "AI agents as
first-class consumers" a central thesis — yet there is **no MCP server.** The
agent surface is an *in-process* Python facade only:
`audioforge/agent_tools.py::run_tool(operation, request)` over 9 ops
(`compile, validate, plan, render, analyze, decompile, import, export, repair`)
with a typed `agent-tools/1` envelope. An external agent cannot reach it over a
protocol — it must import Python. (The `import` op even returns "use the CLI".)
The facade is a *good foundation*; it just is not exposed.

**Full spec.**

1. Add an optional `mcp` dependency group and `audioforge/mcp/` (a real
   subpackage). Implement a stdio MCP server whose tools are thin wrappers over
   the *existing* `agent_tools.run_tool` ops — do **not** fork a second logic
   path (the FrameForge "reuse the same functions" discipline). Map each op to a
   `@server.tool()`.
2. Expose **session resources** the agent can read back — the audio analog of
   FrameForge's SVG/PNG/diagnostics:
   `audioforge://session/{id}/{spec.ir.json, manifest.json, diagnostics.json,
   render.wav, waveform.png, spectrogram.png, markers.json}`. Rendering a
   waveform/spectrogram PNG lets a *vision-capable* agent visually verify the
   output the way FrameForge rasterizes SVG for a VLM.
3. Tool surface (minimum): `compile`, `validate`, `plan`, `render`, `analyze`,
   `repair`, `decompile`, `capabilities` (returns AF-R07's manifest), `verify`
   (the reproducibility gate), plus `describe_capabilities` and a `guide` prompt.
4. Server entrypoint: `python -m audioforge.mcp`; document it in `AGENTS.md`
   (AF-R03) and provide a `mcp.json` client-wiring snippet.
5. Contract test: `tests/test_mcp_contract.py` asserts every `agent_tools` op is
   reachable as an MCP tool and the response envelope matches `agent-tools/1`
   (the FrameForge capability-manifest-via-recording-stub idea: enumerate the
   *real* registered tool surface, do not hand-list it).

**DoR:**
- [ ] AF-R07 merged so `capabilities` returns a stable, versioned manifest the
      MCP `describe_capabilities` tool can serve.
- [ ] MCP SDK/transport choice made (official `mcp` Python package vs a minimal
      stdio JSON-RPC shim) with the dependency cost recorded.
- [ ] Decision on whether `render`/`verify` (potentially slow, filesystem-heavy)
      run in-process or are bounded (timeouts, tempdir sandboxing) — a render can
      take "tens of seconds" per the README.

**DoD:**
- [ ] `python -m audioforge.mcp` starts a stdio MCP server exposing all 9 ops +
      `verify` + `capabilities`.
- [ ] A round-trip test drives compile→validate→render→read-resource and reads
      back the manifest + waveform PNG.
- [ ] `tests/test_mcp_contract.py` fails if an `agent_tools` op is added without
      an MCP tool (no hand-maintained parallel list).
- [ ] Server reuses `run_tool` — no duplicated render/validate path (verified by
      grep/AST test that `mcp/` imports the facade and does not re-implement it).
- [ ] `AGENTS.md` documents the entrypoint and client wiring.

**Risks.** Scope creep toward FrameForge's 25-tool vision/measurement lane — that
is out of scope; AudioForge's value is the compile/render/verify loop, not image
reconstruction. Long renders over stdio need timeouts. Keep the first cut to the
9 ops + resources.

---

### AF-R11 — Docs site (mkdocs-material) with generated pages + a build gate

- **Priority:** P2 · **Wave:** 2 · **Complexity:** M · **Depends on:** AF-R05, AF-R07

**FrameForge reference.** A MkDocs-Material site where only `index.md` is
hand-written; SDK API pages are committed generated snapshots; reference/grammar/
spec/fixtures/changelog pages are transient generated build artifacts.
`make docs` runs `gen_docs.py` then `mkdocs build --strict`; a CI `docs` job
gates it; `docs-linkcheck` gates every relative link; `test_docs_in_sync.py`
gates the hand-written numbers against reality.

**AudioForge gap.** **No `mkdocs.yml`, no docs site, no generated API docs.**
Documentation is a set of hand-written Markdown files in `docs/` (`DSL_SPEC.md`
42 KB, `DSL_GAP_SPEC.md`, `IR_SCHEMA.md`, `goal.md` 83 KB, …). Drift *is* tested
(`test_cli_docs_sync.py`, `test_docs_regression.py`, `test_schema_docs_coverage.py`)
— strong — but there is no browsable site, no generated reference from the schema
or capability manifest, and no `--strict` build that fails on a broken link.

**Full spec.**

1. Add `mkdocs.yml` (Material theme, fetched ephemerally like FrameForge to keep
   it out of runtime deps). Nav: hand-written `index.md`; `DSL_SPEC.md`,
   `IR_SCHEMA.md`, `INTEROP.md`, `AGENT_TOOLS.md` as authored pages; a
   **generated** `reference.md` from `docs/ir.schema.json` (AF-R05) and a
   **generated** `capabilities.md` from `docs/capability-manifest.json` (AF-R07).
2. Add `audioforge/tools/gen_docs.py`: renders the generated pages from the
   committed schema + manifest artifacts; `--check` mode asserts every
   `mkdocs.yml` nav entry resolves after regen (the FrameForge `docs-check`).
3. Add `make docs` (`gen_docs` + `mkdocs build --strict`) and `make docs-serve`;
   add a `docs` CI job. Add a link-check step (`docs-linkcheck` analog).
4. Do not fight the existing drift tests — the generated `reference.md` replaces
   the *manual* parts of `IR_SCHEMA.md`; keep the prose nuance that a schema
   cannot express and gate it as before.

**DoR:**
- [ ] AF-R05 and AF-R07 merged (there are committed schema + manifest artifacts
      to generate pages from — otherwise the site restates hand-written facts and
      inherits the drift it is meant to kill).
- [ ] Decision on hosting (GitHub Pages via CI `docs-deploy`, or local-only
      build gate first). Local build gate is sufficient for P2.

**DoD:**
- [ ] `make docs` builds the site with `--strict` (zero warnings) on `main`.
- [ ] `reference.md` and `capabilities.md` are generated from the committed
      artifacts, not hand-written.
- [ ] `gen_docs.py --check` fails if a nav page is missing or a generated page is
      stale; wired into `make check` and CI.
- [ ] A broken relative link fails the build (demonstrated).

**Risks.** A docs site can become a second place that restates facts — the DoR
prevents that by requiring the generated pages derive from AF-R05/AF-R07
artifacts. Hosting/deploy is deliberately deferred; the *gate* is the value.

---

### AF-R12 — ADR set (`docs/adr/`) and an adoption rule for future decisions

- **Priority:** P2 · **Wave:** 2 · **Complexity:** S · **Depends on:** —

**FrameForge reference.** Four numbered ADRs (`docs/adr-000N-*.md`), each a
short, dated decision record with context/decision/consequences, in the docs
nav under "Design records" — e.g. ADR-0002 "the SDK is a downstream consumer of
core and may lag," which the capability manifest then *tracks*. Decisions are
first-class, discoverable, and referenced by the code that implements them.

**AudioForge gap.** **No ADRs.** Architectural rationale is scattered as long
code comments (`# audit finding F3/F6/F9`), in `docs/RELEASE_NOTES.md`, and in
`docs/goal.md` (83 KB). The *reasons* behind decisions like "flat package, not
`src/`", "hand-built JSON Schema instead of Pydantic", "in-process facade
instead of MCP", "SHA-256 re-render as the verify oracle" are not recorded where
a new contributor or agent can find them — they must be reverse-engineered.

**Full spec.**

1. Create `docs/adr/` with a template (`adr-template.md`: Status, Context,
   Decision, Consequences, disclaimer frontmatter per Rule 5).
2. Backfill the load-bearing decisions already made (retroactive ADRs, clearly
   marked as recording an existing decision):
   - ADR-0001: Determinism model — SHA-256 over `ENGINE_VERSION + canonical_json`
     as the reproducibility contract; `verify` = re-render + compare.
   - ADR-0002: Non-vocal scope (from PURPOSE — record it as a decision with
     consequences for the roadmap).
   - ADR-0003: The IR-is-truth / DSL-is-sugar split.
   - ADR-0004: Native C kernels that "fail loudly" vs pure-Python fallbacks.
   - ADR-0005 (forward): the AF-R08 Pydantic-vs-dataclass decision (this ADR is a
     *DoR* for AF-R08).
3. Add an adoption rule to `CLAUDE.md`/`AGENTS.md`: any change that alters the
   IR contract, the determinism model, or a public surface ships with an ADR.
4. Link ADRs from the docs nav (AF-R11) and reference them from the code they
   govern (the FrameForge practice of citing the decision in the source).

**DoR:**
- [ ] ADR template agreed (MADR-style is fine).
- [ ] The 4–5 highest-value existing decisions to backfill are listed.

**DoD:**
- [ ] `docs/adr/` exists with a template and ≥4 backfilled ADRs.
- [ ] Each backfilled ADR states Context/Decision/Consequences and carries the
      disclaimer frontmatter.
- [ ] The adoption rule is written into `CLAUDE.md` and/or `AGENTS.md`.
- [ ] At least one ADR is referenced from the code it governs.

**Risks.** ADRs rot if writing them is not part of the change flow — the
adoption rule in step 3 is what keeps them alive. Very low technical risk.

---

### AF-R13 — `codebase-standards.md` tri-state ratchet + wire `drift_inspect.py` into the gate

- **Priority:** P2 · **Wave:** 2 · **Complexity:** S · **Depends on:** AF-R02

**FrameForge reference.** `docs/codebase-standards.md` is a self-honest standards
doc where every rule is tagged `[Enforced]` (fails `make check`, with the gate
cited), `[Adopted]` (upheld by reviewers), or `[Target]` (committed but not yet
gated, with §16 tracking the gap). The drift-risk map is *wired into the code*:
findings are numbered and referenced back in source comments, and freshness is
verified live by running the gates at generation time.

**AudioForge gap.** No standards ratchet doc. And critically:
`scripts/drift_inspect.py` **exists** — it reimplements registry-drift detection
— but is **not wired into `scripts/run_tests.sh`**, so it never runs in the
canonical suite (the repo's own `drift-risk-map.md` flags this as MODERATE). A
built drift detector that nothing invokes is exactly the "advisory discipline"
failure this whole roadmap targets.

**Full spec.**

1. Wire `scripts/drift_inspect.py` into the gate: give it a `--check` mode
   (exit non-zero on detected drift), add `make drift-check`, and include it in
   `make check` (AF-R02) and CI (AF-R01). This is the highest-value 30% of this
   item — do it first.
2. Create `docs/codebase-standards.md` with the tri-state tagging. Seed it from
   the existing implicit standards: determinism (`[Enforced]` via
   `test_determinism.py`), version consistency (`[Enforced]`), schema drift
   (`[Enforced]` after AF-R05), lint (`[Enforced]` after AF-R04), typed IR model
   (`[Target]` — AF-R08), MCP surface (`[Target]` — AF-R10), 90.1% coverage
   floor (`[Enforced]` via `fail_under`).
3. Add a "Source of truth per topic" table (version → `version.py`; IR contract
   → `schema.py`; capabilities → `capabilities.py`; …) so there is one place that
   answers "who owns this fact."
4. Keep `drift-risk-map.md` generation in the loop (it already regenerates); add
   the FrameForge practice of numbering findings and citing them in source
   comments where fixed.

**DoR:**
- [ ] AF-R02 exists (`make check` to add `drift-check` to).
- [ ] `drift_inspect.py`'s current detection scope is read and confirmed to be
      the registry HIGH coupling (so wiring it actually gates the right thing).

**DoD:**
- [ ] `drift_inspect.py --check` runs in `make check` and CI and fails on
      injected registry drift.
- [ ] `docs/codebase-standards.md` exists with every rule tagged
      Enforced/Adopted/Target and the enforcing gate cited for each `[Enforced]`.
- [ ] A "source of truth per topic" table exists.
- [ ] `drift-risk-map.md` no longer lists "`drift_inspect.py` not wired in" as an
      open MODERATE finding (it is resolved).

**Risks.** Low. The standards doc is only worth maintaining if the `[Enforced]`
tags are true — the DoD requires a cited gate per enforced rule so the doc
cannot lie.

---

### AF-R14 — `src/` layout + package-boundary AST gate

- **Priority:** P3 · **Wave:** 3 · **Complexity:** M · **Depends on:** AF-R02

**FrameForge reference.** `src/framegraph/` layout with a package-boundary test
(`test_package_boundary.py`) that AST-scans to forbid the package importing
`tooling` (which would break in a wheel). The `src/` layout prevents "works
because the repo root is on `sys.path`" import accidents.

**AudioForge gap.** Flat package layout: `audioforge/` sits at repo root as a
flat module directory (~40 `.py` files, only two real subpackages). There is no
`src/` boundary, so tests and tooling can import the package by virtue of the
repo root being importable, which masks packaging errors. There is no gate
preventing the package from importing test-only or script-only code.

**Full spec.**

1. **Evaluate honestly first** — this is P3 for a reason. A flat layout is not
   wrong; the `src/` move is churn (every import, `pyproject.toml`
   `packages`/`package-dir`, `egg-info`, coverage `source`). The value is
   real but modest for a single-package project. **Only proceed if AF-R05/AF-R08
   introduce a `audioforge/tools/` package that must not leak into the shipped
   wheel** — that is the concrete trigger.
2. If proceeding: move `audioforge/` → `src/audioforge/`, keep `audioforge/tools/`
   *out* of the wheel (or in a separate top-level `tools/` like FrameForge),
   update `pyproject.toml` build config, coverage source, and imports.
3. Add `tests/test_package_boundary.py` (AST scan): the shipped package must not
   import `tests`, `scripts`, or `audioforge.tools` — so a wheel install works.
4. Verify with an actual `pip install .` into a clean venv + import smoke test in
   CI (the real proof the boundary holds).

**DoR:**
- [ ] A concrete trigger exists (a `tools/` package that must not ship, from
      AF-R05/AF-R08). Absent that, **do not do this** — record the decision to
      defer as an ADR.
- [ ] A clean `pip install .` + import smoke currently passes (baseline).

**DoD:**
- [ ] Package builds and installs as a wheel; `import audioforge` works from an
      install with the repo root *not* on `sys.path`.
- [ ] `test_package_boundary.py` fails if the package imports `tests`/`scripts`/
      `tools`.
- [ ] All existing tests green after the move; coverage config updated.

**Risks.** Pure churn with regression potential and low direct user value —
hence P3 and a hard DoR trigger. If the trigger never materializes, the correct
outcome is a "deferred, here's why" ADR, not the move.

---

### AF-R15 — Migration codemod keyed to validator rejection codes

- **Priority:** P3 · **Wave:** 3 · **Complexity:** M · **Depends on:** AF-R05, AF-R08

**FrameForge reference.** `tooling/codemod.py` mechanically migrates legacy
documents to HEAD, and **each migration corresponds to a specific validator
rejection code** documented in `error-codes.md` (e.g. code `stroke-single-form`
↔ "codemod migrates this automatically"). A breaking change ships with a
rejection code *and* an auto-fixer keyed to that code, so old corpora convert
deterministically instead of being stranded.

**AudioForge gap.** `audioforge/ir_schema.py::migrate_ir_spec()` exists and
`repair.py` performs fixes — but migrations are **not systematically keyed to
validator diagnostic codes.** When the IR contract changes, there is no
guaranteed pairing "diagnostic D means old form → run migration M." Old `.af`/IR
corpora in `compositions/` and `renders/` can silently strand on a schema bump.

**Full spec.**

1. After AF-R07's diagnostic-code catalog exists, establish the invariant: every
   *breaking* IR change adds (a) a validator diagnostic code that rejects the old
   form with a clear message, and (b) a `migrate_ir_spec()` branch keyed to that
   code that fixes it.
2. Add `audioforge migrate <spec>` CLI (or extend `repair`) that runs the
   keyed migrations and re-validates, exit-code-contracted like FrameForge's
   codemod.
3. Add `tests/test_migration_codes.py`: for every "breaking" diagnostic code,
   assert a migration exists that turns a rejected fixture into a passing one
   (the FrameForge codemod↔validator tie, tested).
4. Maintain a small corpus of pre-bump fixtures under `tests/fixtures/legacy/`
   that must migrate cleanly (AudioForge's `b1/`-style oracle for migration).

**DoR:**
- [ ] AF-R05 (schema generator) and ideally AF-R08 Phase A (single registry) are
      merged — migrations key off a stable, single-sourced contract.
- [ ] The set of "breaking" vs "additive" IR changes is defined (a bump policy).

**DoD:**
- [ ] Every breaking diagnostic code has a keyed migration and a fixture proving
      the migration fixes it.
- [ ] `audioforge migrate` (or `repair --migrate`) exists with an exit-code
      contract.
- [ ] `tests/test_migration_codes.py` passes and fails if a breaking code lands
      without a migration.
- [ ] `tests/fixtures/legacy/` corpus migrates cleanly and is gated.

**Risks.** Only valuable once the IR actually versions its breaking changes;
premature if the contract is stable. P3 accordingly. Low technical risk built on
existing `migrate_ir_spec()`.

---

### AF-R16 — Cross-platform numeric-determinism pack

- **Priority:** P3 · **Wave:** 3 · **Complexity:** L · **Depends on:** AF-R06

**FrameForge reference.** The `fg-font` toolchain solves "measure-time font ≠
render-time font": a `.fp` pack bundles the exact TTFs + a sha256 manifest so
`measure == render` on any host, and silent font substitution is *banned*
(emits a warning to diagnostics and stderr). The transferable principle:
**pin the environmental inputs that determinism secretly depends on, and make
substitution loud, not silent.**

**AudioForge gap.** AudioForge's README is explicit: "Determinism is guaranteed
within an environment; cross-platform float reproducibility is *checked* by the
`verify` gate rather than assumed." The environmental inputs that float audio
determinism depends on — BLAS implementation and threading, `numpy`/`scipy`
version, FFT backend, the native-kernel compiler and flags, denormal/FTZ CPU
flags — are **not pinned or recorded**, and a mismatch produces different audio
*silently* (only a later `verify` catches it, and only if someone runs it on the
other platform). This is the exact failure `fg-font` bans for fonts.

**Full spec.**

1. Define a **numeric environment descriptor** recorded in every render manifest:
   `{numpy_version, scipy_version, blas: {name, threads}, fft_backend,
   native_kernel_hashes, cpu_flags: {ftz, daz}, python_version}`. This is the
   audio analog of the font pack's sha256 manifest.
2. Make substitution **loud**: at render start, if the current numeric
   environment differs from the one recorded in a spec/manifest being verified,
   emit a `numeric_environment_drift` diagnostic to the manifest *and* stderr
   (the `font_substitution` analog). Never silently produce different audio.
3. Pin what can be pinned: force single-thread (or a fixed thread count) BLAS
   during deterministic renders (reduction order depends on it); pin the FFT
   backend; record native-kernel compiler + flags in the kernel hash.
4. Extend AF-R06's golden lane: the **same-numeric-environment** lane is strict
   (exact hash); the **cross-environment** lane uses the cosmetic tolerance and
   *attributes* any diff to the recorded environment delta, so a failure says
   "differs because BLAS was OpenBLAS-8-thread here vs reference MKL-1-thread,"
   not just "hash mismatch."
5. Optionally provide a container image (the FrameForge Docker-runtime analog)
   that pins the numeric environment so `verify` is byte-exact inside it — the
   audio equivalent of the font-rich image.

**DoR:**
- [ ] AF-R06 merged (there is a golden oracle and a defined ε to build the
      cross-environment tolerance on).
- [ ] Empirical study done: *which* inputs actually change AudioForge's output
      bytes (BLAS threads? FFT backend? kernel flags?) — measured, not assumed
      (Rule 2). This study is the real work; the plumbing is easy.

**DoD:**
- [ ] Every render manifest records the numeric environment descriptor.
- [ ] A render whose numeric environment differs from a verified reference emits
      a loud `numeric_environment_drift` diagnostic (to manifest + stderr) — never
      silent.
- [ ] BLAS threading / FFT backend are pinned during deterministic renders and
      the pin is asserted at render time.
- [ ] The cross-environment golden lane attributes hash diffs to specific
      environment deltas.
- [ ] (If containerized) `verify` is byte-exact inside the pinned image on ≥2
      host OSes.

**Risks.** **Highest-uncertainty item.** Full cross-platform bit-exact float
audio may be *unachievable* without pinning to one BLAS/compiler — and that is a
legitimate finding, not a failure. The honest DoD target is "drift is *recorded
and loud*, and byte-exact *within a pinned environment*," not "byte-exact
everywhere." Do the measurement study (DoR) before committing to any bit-exact
promise. This is where Rule 2 (formalization = research, mark uncertainty) binds
hardest.

---

### AF-R17 — Explicit filter-automation targets (`auto lowpass` / `auto highpass` / `auto bandpass`)

- **Priority:** P1 · **Wave:** 1 · **Complexity:** S · **Depends on:** —

**Context.** `auto cutoff:` binds automation to *the first filter in the fx
chain* (documented in `docs/DSL_SPEC.md` §10). With more than one filter, chain
order silently decides which corner moves. A `highpass(28hz), lowpass(19000hz)`
master chain automated with lowpass-shaped values swept the *highpass* toward
Nyquist and rendered a ten-minute track to near-silence — a valid WAV, no
diagnostic — a silent failure of the "loud and local" contract.

**Mitigation shipped.** A compile-time warning now fires when `auto cutoff`
targets a highpass (`audioforge/sdk.py` `_cutoff_target_warnings`,
`tests/test_render_guardrails.py`). That flags the trap; it does not remove it.

**Full spec.**
1. Add `auto lowpass:`, `auto highpass:`, `auto bandpass:` targets that bind to
   the named filter kind regardless of chain position, lowering to the same
   `cutoff_hz` curve on that filter.
2. Keep `auto cutoff:` as a first-filter alias for compatibility, retaining the
   highpass-target warning.
3. Document the targets in `docs/DSL_SPEC.md` §10 and expose them in
   `audioforge capabilities`.

**DoR:**
- [ ] The automatable filter kinds and their IR targets are enumerated.
- [ ] Decision: `auto <kind>:` binds to the first filter of that kind, or errors
      when a chain holds several of one kind.

**DoD:**
- [ ] A highpass-first chain with `auto lowpass:` renders with the low band
      intact (regression test).
- [ ] `auto cutoff:` behavior and its warning are unchanged.
- [ ] The new targets appear in the capability manifest and grammar artifacts,
      guarded by the existing docs/grammar sync tests.

**Risks.** Low. Additive DSL surface; the alias preserves existing specs.

---

### AF-R18 — Always-on dead-air render assertion (loud-by-default)

- **Priority:** P1 · **Wave:** 1 · **Complexity:** S · **Depends on:** AF-R17

**Context.** The dead-air detector (`audioforge/analysis.py` `_silence_metrics`,
`tests/test_render_guardrails.py`) computes `silence_share` and
`longest_silence_s` and raises a `dead_air` recommendation — but only under
`render --analyze`. A default `render`/`verify` still passes a mostly-silent
output, so the guardrail that catches the AF-R17 class is opt-in.

**Full spec.**
1. Run the windowed silence scan in the render path (it is cheap) and record
   `silence_share` / `longest_silence_s` in every manifest.
2. Add a `routing.dead_air: allow|warn|forbid` policy (default `warn`) mirroring
   the sustain-gap policy (`audioforge/plan.py`): `warn` surfaces and records the
   diagnostic; `forbid` refuses to write output.
3. Surface the diagnostic the way plan diagnostics already surface, and document
   the policy in `docs/DSL_SPEC.md`.

**DoR:**
- [ ] The audibility floor and run-length thresholds are pinned as documented
      constants (already prototyped in `analysis.py`).
- [ ] Decision: default policy `warn` vs `allow` for the first release.

**DoD:**
- [ ] A muted-lane spec surfaces `dead_air` in the manifest without `--analyze`.
- [ ] `forbid` refuses the render; `allow` opts out; all three covered by tests.
- [ ] An intentionally sparse-but-audible reference spec does not false-positive.

**Risks.** Low–medium. False positives on deliberately sparse cues; mitigated by
conservative thresholds and the `allow` opt-out.

---

### AF-R19 — Unified render-assertion policy surface

- **Priority:** P2 · **Wave:** 2 · **Complexity:** M · **Depends on:** AF-R17, AF-R18

**Context.** Loud-failure checks have accrued independently: sustain-gap,
articulation-fallback, and stretch policies live in the render plan
(`audioforge/plan.py`); the cutoff-target warning in SDK validation
(`audioforge/sdk.py`); dead-air in analysis (`audioforge/analysis.py`). Different
homes and inconsistent `allow|warn|forbid` handling make the verification stance
real but scattered and hard to discover.

**Full spec.**
1. Define one render-assertion registry: each check declares a code, a default
   severity, and a policy key under `routing`.
2. Normalize every existing check onto that registry without changing default
   behavior.
3. Emit one `assertions` block in the manifest enumerating every check, its
   inputs, and its verdict, so an agent reads one place to judge a render.
4. Document the registry in `docs/DSL_SPEC.md` and expose it via
   `audioforge capabilities`.

**DoR:**
- [ ] The full inventory of current render-time checks and their homes is
      captured.
- [ ] Decision: one flat `routing` namespace vs a nested `routing.assertions`.

**DoD:**
- [ ] Every listed check is registered and policy-gated through one path.
- [ ] The manifest carries a single assertions report; existing sustain-gap and
      fallback tests pass unchanged.
- [ ] `audioforge capabilities` lists the assertion codes and their policies.

**Risks.** Medium. A refactor across three modules; guarded by keeping default
behavior identical and by the existing per-check tests.

---

## 3. Track M items — music-theory & compositional capability

Each item is self-contained: **Corpus/source reference → AudioForge gap → Full
spec → DoR → DoD → Risks.** Sources are cited with DOI/ISBN; sentence anchors
(`§`, `#nnnn`) are machine-verified retrievals from *Exploring Musical Spaces*
(Hook 2022, ISBN 978-0-19-024601-3, DOI [10.1093/oso/9780190246013.001.0001](https://doi.org/10.1093/oso/9780190246013.001.0001))
against the corpus GraphQL endpoint (Appendix §7). Where the corpus does **not**
attest a concept, the canonical external source is cited instead and the gap in
corpus coverage is marked — no citation is fabricated (Rule 2).

> **Shared invariant for all Track-M items (PALS's LAW).** Every new theory
> operation is LLM-adjacent surface an agent will call; each MUST ship with an
> exhaustive property test against a *closed, enumerable* ground truth (e.g. the
> 224 Tn/TnI set-classes, the 24 major/minor triads, the 12 transpositions) — not
> spot-checks. A music-theory function that is "probably right" is unverified
> output, and unverified output is a design defect, not a runtime bug.

---

### AF-M01 — Pitch-class-set theory core (normal form, prime form, IC-vector, formal `Tn`/`TnI`)

- **Priority:** P1 · **Wave:** M1 · **Complexity:** M · **Depends on:** AF-R06
- **Status:** ✅ **Implemented (2026-07-05)** — `audioforge/theory_pcset.py`
  (`normal_form`, `prime_form` (Rahn), `interval_class_vector`, `Tn`/`TnI`,
  `invert`, `complement`, symmetry degrees). Pinned by `tests/test_theory_pcset.py`,
  which verifies **exhaustively** that `prime_form` partitions all 2¹² subsets into
  the **224** Tn/TnI set-classes (correct count per cardinality) — plus the group
  axioms and the corpus-attested `{0,4,7}`≡`{0,3,7}`→`(0,3,7)`. The ad-hoc `{s%12}`
  pc-set construction in `dsl.py` now routes through `pcset()`; renders verified
  byte-identical via `make golden-check`. (Set-class identity is the derivable
  `(cardinality, prime_form)`; Forte ordinal numbers are intentionally not
  fabricated — Rule 2.) *Correction:* an earlier draft of this roadmap said "220
  set classes"; the Tn/TnI count is **224** (Burnside on D₁₂).

**Source reference.** Hook, *Exploring Musical Spaces*, §1.2 "Pitch-class spaces";
pc-set prime form is attested directly — "major and minor triads … share the
prime form 037, and all 24 sets of that prime form …" (verified #625). Canonical
external algorithm sources: Forte, *The Structure of Atonal Music* (Yale Univ.
Press, 1973, ISBN 978-0-300-02120-2) — set-class catalog and the
interval-class vector; Rahn, *Basic Atonal Theory* (Longman, 1980) — the standard
normal-form/prime-form selection algorithm. **Corpus-coverage note:** the term
"interval vector" returned *no* hit in the corpus; the IC-vector is therefore
grounded on Forte 1973, not on *Exploring Musical Spaces*.

**AudioForge gap.** Pitch classes exist only as ad-hoc `{s % 12}` sets in
`dsl.py` (used for out-of-scale checks and common-tone retention). There is **no**
normal form, prime form, interval-class vector, set-class / Forte-number lookup,
or formal `Tn`/`TnI` operator anywhere (verified: package-wide read of
`theory.py`, `dsl.py`). `theory.invert` is a concrete chromatic mirror over note
events, not an inversion operator on pc-sets.

**Full spec.**

1. New module `audioforge/theory_pcset.py` (pure, dependency-free):
   - `normal_form(pcs) -> tuple`, `prime_form(pcs) -> tuple` (Rahn algorithm),
     `interval_class_vector(pcs) -> tuple[6]`, `forte_number(pcs) -> str`,
     `set_class(pcs)` returning the derivable (cardinality, prime-form) identity — no hand-typed catalogue (Rule 2).
   - Operators: `Tn(pcs, n)`, `TnI(pcs, n)`, `invert(pcs, axis)`,
     `complement(pcs)`, `transpositional/inversional symmetry` degree.
2. Refactor the existing ad-hoc `{s % 12}` sites in `dsl.py` to call this module
   (single source for pc arithmetic) — no behavior change to render output.
3. Expose read-only analysis via `analysis.py` / `agent_tools` (`analyze` op):
   report set-class labels for the chords a spec uses.

**DoR:**
- [ ] AF-R06 golden oracle exists (any incidental render change is caught).
- [ ] The Forte set-class table is sourced from a single authoritative reference
      and its provenance recorded (no hand-typed catalog without a citation).

**DoD:**
- [ ] `prime_form` and `interval_class_vector` are validated **exhaustively**
      against all 224 Tn/TnI set-classes (property test), not sampled.
- [ ] `Tn`/`TnI` satisfy the group axioms under test (e.g. `TnI ∘ TnI = identity`,
      `Tm ∘ Tn = T(m+n)`) over all 12 (or 24) elements.
- [ ] The `{s % 12}` duplication in `dsl.py` is gone; renders are byte-identical
      (golden gate green).
- [ ] `analyze` returns a set-class label for a known chord (037 → "major/minor
      triad, prime form (0,3,7)").

**Risks.** Low. Self-contained, closed ground truth, no render-path change. The
only trap is an off-by-one in the Rahn "most-packed-to-the-left" tie-break — the
exhaustive test against all 224 Tn/TnI classes is precisely what catches it.

---

### AF-M02 — Formal transformation operators + transformation networks

- **Priority:** P2 · **Wave:** M2 · **Complexity:** M · **Depends on:** AF-M01

**Source reference.** Lewin, *Generalized Musical Intervals and Transformations*
(Yale Univ. Press, 1987; Oxford reissue 2007, ISBN 978-0-19-531713-8) — the GIS
formalism and transformation graphs/networks. Attested in the corpus: Hook Ch. 9
"Transformations II: Transformation Graphs and Networks; Serial Transformations"
(verified #16).

**AudioForge gap.** The DSL `play … {transform}` surface offers `transpose`,
`diatonic`, `invert`, `retrograde`, `stretch` as *concrete note-event edits*
(`theory.py`), not as composable algebraic operators, and there is no notion of a
transformation *network* (a labeled graph of operators applied across a passage).

**Full spec.**

1. Layer the DSL transforms onto AF-M01's `Tn`/`TnI` so `invert`/`transpose`
   are the pc-set operators applied to events, not bespoke arithmetic.
2. Add a small transformation-network evaluator: a spec may declare a sequence /
   graph of named operators (`T5`, `I`, `R`, a UTT from AF-M03) and apply it to a
   motif or chord stream deterministically.
3. Grammar (`grammar.py`) + GBNF productions for the operator sequence so an LLM
   samples only well-formed networks.

**DoR:**
- [ ] AF-M01 merged (operators exist to compose).
- [ ] Decision: how far to go toward full Lewinian networks vs a linear operator
      pipeline (recommend: linear pipeline first; graph later only if a use case
      demands it — Rule 8, do not gold-plate).

**DoD:**
- [ ] `play motif {ops: T5 I R}` produces the operator-composed result and a test
      asserts associativity/round-trips against AF-M01's algebra.
- [ ] Grammar accepts valid operator sequences and rejects malformed ones
      (`test_grammar_token_sync.py` extended).
- [ ] Renders byte-stable under the golden gate.

**Risks.** Scope creep toward the full apparatus of *GMIT*. Keep the first cut to
composable `Tn`/`TnI`/`R` pipelines; a general graph evaluator is optional.

---

### AF-M03 — Neo-Riemannian triadic transformations (P/L/R, UTT) + Tonnetz

- **Priority:** P2 · **Wave:** M2 · **Complexity:** M · **Depends on:** AF-M01, AF-M02

**Source reference.** Hook, *Exploring Musical Spaces*: §1.4 "Tonnetz" (verified
#8, in the chapter "Spaces generated by fifths and thirds"); Ch. 8 "Transformations
I: Triadic — 8.1 Uniform triadic transformations, 8.2 Riemannian UTTs and
neo-Riemannian analysis" (verified #15). Hook's UTT formalism originates in Hook,
"Uniform Triadic Transformations," *Journal of Music Theory* 46 (2002),
DOI [10.1215/00222909-2005-002](https://doi.org/10.1215/00222909-2005-002).
Neo-Riemannian voice-leading context: Cohn, *Audacious Euphony* (Oxford, 2012,
ISBN 978-0-19-977269-8).

**AudioForge gap.** No `P`, `L`, `R`, no UTT, no `Tonnetz` (verified: grep of the
package returns none). AudioForge cannot express the smooth chromatic
third-relations (e.g. `C major → E minor` by a single `L`) that are the core of
19th-century and film-score harmony — directly relevant to the orchestral
`renders/` the project already produces.

**Full spec.**

1. In `audioforge/theory_triads.py`: represent a consonant triad as
   `(root_pc, mode ∈ {major, minor})`; implement `P`, `L`, `R` and their
   compositions (the neo-Riemannian PLR group, order 24), plus the general UTT
   `⟨sign, t+, t−⟩` representation with composition.
2. `tonnetz_neighbors(triad)` returns the P/L/R-adjacent triads (the Tonnetz
   edges), enabling shortest-path chromatic progressions between two triads.
3. DSL surface: `play <triad> {plr: L R P}` and/or a `progression via tonnetz
   from Cmaj to Abmaj` sugar that emits the minimal P/L/R path; compiles to the
   existing literal-chord event stream (no new render primitive).

**DoR:**
- [ ] AF-M01 (pc-sets) and AF-M02 (operator plumbing) merged.
- [ ] Triad representation reconciled with `theory.parse_chord` so P/L/R output
      round-trips to existing chord symbols.

**DoD:**
- [ ] `P`, `L`, `R` verified against their definitions on **all 24** triads
      (`P(C major)=C minor`, `L(C major)=E minor`, `R(C major)=A minor`), exhaustively.
- [ ] The generated PLR group has order 24 (test), and UTT composition is
      associative (test).
- [ ] A Tonnetz shortest-path progression renders and is byte-stable.
- [ ] `AGENTS.md` / DSL spec document the new directive.

**Risks.** Low-to-moderate. The math is closed and testable. Main design choice
is how much sugar to expose; keep the primitive (P/L/R on triads) minimal and let
progressions compose from it.

---

### AF-M04 — Scale & mode system (modes, pentatonic, octatonic, maximally-even)

- **Priority:** P1 · **Wave:** M1 · **Complexity:** S–M · **Depends on:** AF-M01

**Source reference.** Hook, *Exploring Musical Spaces*: diatonic collections
`dpc(n)` and the Dorian-on-D centering (verified #532); "pentatonic pitch spaces,
whole-tone pitch spaces, and octatonic pitch [spaces]" (verified #364);
"maximally even sets" treated in Ch. 14 (verified #6609). Canonical external
sources for the generators: Clough & Douthett, "Maximally Even Sets," *Journal of
Music Theory* 35 (1991), DOI [10.2307/843811](https://doi.org/10.2307/843811);
Carey & Clampitt, "Aspects of Well-Formed Scales," *Music Theory Spectrum* 11
(1989), DOI [10.2307/745935](https://doi.org/10.2307/745935). **Corpus-coverage
note:** "well-formed" returned no corpus hit; well-formed/generated-scale theory
is grounded on Carey–Clampitt, not on *Exploring Musical Spaces*.

**AudioForge gap.** `dsl.py` defines only `MAJOR` and `MINOR` interval lists, and
`_scale_pitch_classes` handles only those two. `theory.diatonic_transpose` accepts
an arbitrary interval list but **no caller ever supplies one** other than
major/minor. There are no church modes, pentatonic, harmonic/melodic minor,
whole-tone, or octatonic collections, and the out-of-scale advisory checks only
major/minor.

**Full spec.**

1. `audioforge/theory_scales.py`: a registry of named collections — the 7
   diatonic modes, harmonic & melodic minor, major/minor pentatonic, whole-tone,
   octatonic (both), chromatic — each as an interval list plus its pc-set (via
   AF-M01), with a `maximally_even(n, c)` generator (Clough–Douthett) so
   arbitrary even collections are derivable, not hand-listed.
2. Wire `dsl._scale_pitch_classes`, `theory.diatonic_transpose`, and the
   out-of-scale diagnostic to consume the registry; add a DSL `scale: <name>`
   directive (grammar + GBNF).
3. `analyze` reports best-fit scale/collection for a passage's pc content.

**DoR:**
- [ ] AF-M01 merged (pc-set machinery for membership/normalization).
- [ ] The `maximally_even` generator's output for the diatonic (7-in-12) and
      octatonic (8-in-12) cases is checked against the known collections before
      it is trusted as a generator (Rule 2 — derive, then verify).

**DoD:**
- [ ] Every registered collection has a test pinning its pcs; the
      `maximally_even` generator reproduces the diatonic, pentatonic, and
      octatonic sets exactly.
- [ ] `scale: dorian` (and friends) drives `diatonic_transpose` and the
      out-of-scale diagnostic; a passage in D-Dorian raises no false out-of-scale
      warnings.
- [ ] Renders byte-stable under the golden gate.

**Risks.** Low. Additive and closed-form. The maximally-even generator is the one
place to verify against known sets rather than assume.

---

### AF-M05 — Tuning & temperament engine (activate the inert `tuning:` directive)

- **Priority:** P1 · **Wave:** M1 · **Complexity:** M–L · **Depends on:** AF-R06

**Source reference.** Hook, *Exploring Musical Spaces*, §1.1 "Pitch spaces":
continuous pitch space `cpitch` identified with the rationals/reals — "continuous
pitch space cpitch may be identified [with] … ℚ≠0 = {all rational numbers except
0}" (verified #1057); "Just Intonation." (verified #15617); semitone metric —
"pitch numbers … measured in semitones above or below middle C" (verified #227),
equal-semitone piano idealization (verified #259). Historical temperament grounding
from the sibling corpus text: Braguinski, *Mathematical Music: From Antiquity to
Music AI* — well-temperament and Grell's just-intonation systems ("Drawing on this
'just intonation' idea that small-integer ratios have special aesthetic qualities …",
verified #506, #508). Canonical external: Barbour, *Tuning and Temperament: A
Historical Survey* (Michigan State Univ. Press, 1951; Dover reprint
ISBN 978-0-486-43406-3); the Scala scale-file format (`.scl`/`.kbm`, Manuel Op de
Coul) as the interchange standard.

**AudioForge gap (a real correctness defect, not a missing feature).** The DSL
directive `tuning: edo divisions=N base=A4 hz=440` is parsed (`dsl.py`) and stored
in `spec["notation"]["tuning"]`, but **no code reads it** — every pitch→frequency
conversion is hardcoded 12-TET: `dsl.note_to_freq` uses `440 * 2**(semis/12)`, and
`library.py`/`plan.py` resample with `2**(st/12)`. The engine therefore *accepts a
microtuning instruction and silently renders 12-TET.* By PALS's LAW this is an
unverified capability claim shipped to users.

**Full spec.**

1. `audioforge/tuning.py`: a `Tuning` resolver `pitch → frequency_hz` supporting:
   - **n-EDO** (the directive that already parses): `base_hz * 2**(steps/N)`.
   - **Just intonation**: rational ratio tables (e.g. 5-limit) relative to a tonic.
   - **Historical temperaments**: quarter-comma meantone, a well-temperament
     (e.g. Werckmeister III), each defined by cents offsets per pc — cite Barbour.
   - **Scala `.scl`** import (arbitrary scales) with optional `.kbm` keyboard map.
   - Output resolvable in **cents** for exactness and for interop.
2. Thread the resolver through the *entire* pitch→frequency path — replacing the
   hardcoded `2**(x/12)` in `dsl.note_to_freq`, the sampler resample ratio in
   `library.py`, and `plan.py` — gated on `spec["notation"]["tuning"]`; default
   remains 12-TET so existing renders are byte-identical.
3. Interop (`interop.py`): non-12-EDO pitches export as MIDI **pitch-bend**
   (the existing `pitch_cents` → bend path already exists) or MPE, and MusicXML
   microtonal accidentals where representable; document the lossy cases.
4. **Verification (mandatory):** render a pure tone at a non-12-EDO scale degree
   and assert via `analysis.py` FFT that the fundamental lands at the specified
   cents (± the analysis bin tolerance). This is the test that proves the
   directive is no longer inert.

**DoR:**
- [ ] AF-R06 golden oracle exists (12-TET renders must be provably unchanged).
- [ ] The default-path guarantee is specified: `tuning` absent ⇒ byte-identical
      to today (the resolver is a no-op that returns `440*2**(x/12)`).
- [ ] Reference values for at least one JI table and one historical temperament
      are sourced from Barbour (cents per degree) — no hand-invented ratios.

**DoD:**
- [ ] A 19-EDO (or 31-EDO) render places partials at the tuning's cents, proven
      by the FFT assertion — the directive **demonstrably drives the render.**
- [ ] With no `tuning` directive, all existing golden renders are byte-identical.
- [ ] `.scl` import round-trips a known scale (e.g. Pythagorean) to the correct
      cents.
- [ ] JI and meantone tables match Barbour's published cents (test).
- [ ] `DSL_SPEC.md` marks `tuning:` as *active*, not notational; `AGENTS.md`
      documents the supported tuning systems.

**Risks.** Moderate–high, and the most valuable Track-M item precisely because it
fixes a live defect. Threading a new resolver through the pitch path risks
perturbing 12-TET output — the default-no-op guarantee plus the golden gate are
what make that safe. Interop of arbitrary microtuning to MIDI/MusicXML is
inherently lossy; document the boundaries rather than over-promise (Rule 1).

---

### AF-M06 — Voice-leading as optimization (minimal-displacement / VL geometry)

- **Priority:** P2 · **Wave:** M2 · **Complexity:** M · **Depends on:** AF-M01, AF-M04

**Source reference.** Hook, *Exploring Musical Spaces*, Ch. 10 "Spaces III:
Introduction to Voice-Leading Spaces" — "10.1 The hexatonic triad graph as a
continuous voice-leading space" (verified #17). Canonical external: Tymoczko,
*A Geometry of Music* (Oxford, 2011, ISBN 978-0-19-533667-2) — the OPTIC
voice-leading spaces and minimal (efficient) voice leading.

**AudioForge gap.** The voice-leading logic in `dsl.py` (≈ L1030–1106) is a fixed
*ornament-insertion heuristic* — it adds passing tones, suspensions,
anticipations, and retains common tones by pc-set intersection. It is **not**
minimal-displacement voice leading: it does not compute the bijection between two
chords' voices that minimizes total semitone motion.

**Full spec.**

1. `audioforge/voice_leading.py`: given two pitch-class sets / voicings, compute
   the minimal-displacement bijective voice leading (sum of absolute semitone
   motion), with options for T-related and inversional voice leadings; support
   crossing-free constraints.
2. Add a DSL voicing mode: `voicing: smooth` (minimal displacement, new) vs the
   existing behavior renamed `voicing: ornamented` (the current L1030 heuristic),
   preserving backward compatibility (unspecified ⇒ current default).
3. Integrate with AF-M03: neo-Riemannian P/L/R progressions request `smooth`
   voice leading to realize the parsimonious motion those transformations model.

**DoR:**
- [ ] AF-M01 (pc-sets) and AF-M04 (scales, for scale-aware passing tones) merged.
- [ ] The objective is pinned precisely (minimize summed |Δsemitone| over a
      bijection; tie-break rule stated) so the result is deterministic.

**DoD:**
- [ ] For known cases the algorithm returns the textbook minimal voice leading
      (e.g. `C major → G major` moves 2 voices by 1–2 semitones, not a leap),
      verified by test.
- [ ] `voicing: ornamented` reproduces today's output byte-for-byte (the current
      heuristic is unchanged, only renamed/defaulted).
- [ ] `voicing: smooth` renders and is byte-stable under the golden gate.

**Risks.** Moderate. Minimal voice leading over a voicing *space* (with octave
and cardinality freedom) can be combinatorial; bound it to reasonable voice counts
and state the tie-break so output is deterministic (determinism is the product).

---

### AF-M07 — Functional-harmony grammar (roman numerals, cadences, progressions)

- **Priority:** P3 · **Wave:** M3 · **Complexity:** L · **Depends on:** AF-M03, AF-M04

**Source reference.** This item is grounded primarily in the codebase gap and in
standard functional-harmony pedagogy rather than in a single corpus citation;
*Exploring Musical Spaces* is deliberately *transformational* rather than
functional, so it is cited here as the complement AudioForge also lacks, not as
the source of Roman-numeral practice. **Marked accordingly:** the theory here is
common-practice consensus, not a novel formal claim — no fabricated citation.

**AudioForge gap.** `grammar.py` expresses harmony only as literal `PITCH = note |
chord` (e.g. `C3min7`) plus voicing directives. There are **no** Roman numerals,
chord-function labels (T/S/D), cadence types, or progression templates. A user
must spell every chord literally; the DSL cannot say "a ii–V–I in F" or "a
deceptive cadence."

**Full spec.**

1. A compile-time expansion layer in `dsl.py`: given a `key:` context, expand a
   Roman-numeral progression (`I vi IV V`, `ii7 V7 I`, secondary dominants
   `V/V`, borrowed chords) into the concrete chord symbols the engine already
   renders — reusing AF-M04's scale system for diatonic chord construction and
   AF-M03 for chromatic/functional substitutions.
2. Cadence templates (authentic, plagal, half, deceptive) as named sugar.
3. Grammar + GBNF productions for the Roman-numeral surface so constrained LLM
   sampling emits valid functional progressions.

**DoR:**
- [ ] AF-M03 and AF-M04 merged (chromatic transforms + scale/chord construction
      the expansion relies on).
- [ ] The dialect is fixed (which Roman-numeral conventions: figured-bass
      inversions? applied chords? mode mixture?) — scope it explicitly to avoid an
      open-ended grammar.

**DoD:**
- [ ] `key: F; prog: ii V I` expands to the correct literal chords (Gm–C–F) and
      renders byte-stable.
- [ ] Each cadence template produces the textbook chord succession (test).
- [ ] Grammar accepts valid progressions and rejects malformed numerals
      (`test_grammar_token_sync.py` extended).

**Risks.** Moderate. Functional harmony has many dialects; an unbounded grammar
rots. Pin a documented subset first (diatonic triads/sevenths + secondary
dominants) and extend deliberately. Lowest-priority Track-M item because it is
sugar over capabilities the other items provide.

---

## 4. Track X items — algorithmic & stochastic composition

Sourced from Iannis Xenakis, *Formalized Music* (Pendragon, 1992), and grounded
in a deep-dive of the codebase against the formalized-music corpus (corpus
document `48190286-Xenakis-Formalized-Music`, retrieved via the GraphQL endpoint,
Appendix §7). This track builds the *algorithmic* tradition — the one whose
"logical (hence mechanizable) functions" ideal the engine's seeded determinism
already realizes — where Track M builds the transformational/common-practice one.
Every Track-X item lands behind the golden-audio gate (`AF-R06`); each maps 1:1
to a `BL-*` item in [`docs/backlog.yml`](./backlog.yml).

### AF-X02 — Seeded stochastic composition primitives

- **Priority:** P1 · **Wave:** 2 · **Complexity:** L · **Depends on:** AF-R06

**Corpus reference.** Xenakis, *Formalized Music* — *Free Stochastic Music*,
*Markovian Stochastic Music (Theory / Applications)*. The corpus's computer-music
core is overwhelmingly stochastic (58 of 60 "stochastic" sentence hits resolve to
this document).

**AudioForge gap.** The engine exposes **no compositional stochastic primitives**.
`np.random` appears only for DSP noise/dither (`synth.py`, `fx.py`); `compose.py`
and `theory.py` have none. Yet the determinism substrate (`determinism.py`) roots
every random path in the spec hash — the exact machinery to make stochastic
composition *reproducible*, which was Xenakis's unrealized aim on 1960s hardware.

**Full spec.**
1. Add seeded generators that expand at compile time into explicit IR note/rhythm
   events: probability distributions (uniform, Gaussian, exponential, Poisson,
   Cauchy — Xenakis's set), first- and higher-order Markov chains, and bounded
   random walks for contours.
2. Root them in the existing seed lineage so the IR stays the complete ground
   truth and a variant tag re-realizes all choices coherently.
3. Document under the DSL spec and the capability manifest; gate with `AF-R06`.

**DoR:**
- [ ] The distribution set and their IR lowering are enumerated.
- [ ] Decision: distributions as note-generators only, or also as parameter
      modulators (velocity, timing, density).

**DoD:**
- [ ] A stochastic passage expands to explicit IR events and renders
      byte-identically for a fixed spec+variant.
- [ ] A new variant re-realizes the seeded choices; both are golden-locked.
- [ ] Primitives appear in `audioforge capabilities`.

**Risks.** Medium. Scope creep across distribution families; mitigate by shipping
the core set first and treating the rest as follow-ups.

---

### AF-X01 — General sieve engine (residual-class sieves → scales & rhythm)

- **Priority:** P2 · **Wave:** 2 · **Complexity:** M · **Depends on:** —

**Corpus reference.** Xenakis sieve theory: *"an axiomatization for the totally
ordered structure of the tempered chromatic scale … express any scale in terms of
logical (hence mechanizable) functions."*

**AudioForge gap.** Sieves exist only as **Euclidean rhythm** (`theory.py`
`bjorklund`, `dsl.py` `euclid()`) — one degenerate case, rhythm-only. There is no
general residual-class sieve (unions/intersections of classes mod *m*) and no
sieve→scale path. Over the tempered chromatic (mod 12) this needs no new tuning
support, so it is buildable now and generalizes once `AF-M05` lands.

**Full spec.**
1. Implement a `sieve(...)` primitive over residual classes with union,
   intersection, and complement, producing both a pitch-class set (mod 12) and a
   rhythm pattern.
2. Make `euclid` a special case (or reduce it to a sieve) with byte-identical
   output.
3. Couple to `AF-M04` (scale system) and, when available, `AF-M05` (tuning) so
   sieves generate scales over non-12 moduli.

**DoR:**
- [ ] Sieve syntax and IR representation are specified (period, residues, ops).
- [ ] Decision: sieve output as first-class IR objects vs. expanded to explicit
      pitch/rhythm only.

**DoD:**
- [ ] A sieve produces a pitch-class set and a rhythm pattern; `euclid` reduces
      to it and renders unchanged.
- [ ] Sieve output is explicit in the IR and golden-locked.

**Risks.** Low. Additive, self-contained, and maps cleanly onto the deterministic
compile-time model.

---

### AF-X04 — Positioning ADR: deterministic ground truth under generative music AI

- **Priority:** P2 · **Wave:** 1 · **Complexity:** XS · **Depends on:** —

**Context.** The corpus survey *Mathematical Music: From Antiquity to Music AI*
frames the frontier as learning-based generation. The engine deliberately does
not occupy it: it is a deterministic renderer and verifier whose operating law
treats model output as *untrusted*. That is arguably the ideal **ground-truth /
verification substrate** *under* generative music AI — a complement, not a
competitor — but the stance is unrecorded, so product direction can drift.

**Full spec.**
1. Write an ADR (`docs/adr/`, per `AF-R12`) fixing the position: deterministic,
   verifiable render/ground-truth layer beneath generative music AI, versus
   adding generation.
2. Reconcile with `PURPOSE.md` and the untrusted-output law in `CLAUDE.md`.
3. Reference the ADR from this roadmap so downstream items inherit the stance.

**DoR:**
- [ ] The alternatives and their consequences are drafted.

**DoD:**
- [ ] The ADR is committed and linked from the roadmap; no roadmap item
      contradicts it.

**Risks.** Low. A decision record, not code.

---

### AF-X03 — Dynamic stochastic synthesis oscillator (GENDYN-style)

- **Priority:** P3 · **Wave:** 3 · **Complexity:** M · **Depends on:** AF-X02

**Corpus reference.** Xenakis's dynamic stochastic synthesis — sound generated by
stochastic walks over the waveform itself, *"free of the … tradition of
electronic, concrete, and instrumental music."*

**AudioForge gap.** The synthesis palette (`synth.py`) has exact-Fourier
wavetables, PADsynth, and granular voices, but no stochastic-waveform voice.

**Full spec.**
1. Add an oscillator whose breakpoint amplitudes and durations evolve by seeded,
   bounded stochastic walks (reflecting/elastic barriers), reproducible from the
   per-note seed.
2. Expose it as a synth (or native) voice with explicit IR parameters; verify
   determinism.
3. Reuse the `AF-X02` distribution primitives for the walk laws.

**DoR:**
- [ ] The walk laws and barrier model are specified.
- [ ] Decision: pure-Python voice vs. a native kernel (perf).

**DoD:**
- [ ] The voice is byte-reproducible and golden-locked.
- [ ] Parameters appear in `audioforge capabilities`.

**Risks.** Low–medium. Potential CPU cost at audio-rate walks; mitigate with a
native kernel if needed (fails loud, per the engine's kernel policy).

---

## 5. Cross-cutting principles to adopt (the meta-lesson)

Beyond the individual items, these FrameForge *habits* are what make the whole
system trustworthy. Adopt them as review defaults, not as separate tickets:

1. **Every generated artifact has a `--check` twin owned by its generator.**
   Never a committed file that a human regenerates by hand (AF-R05, AF-R07,
   AF-R09, AF-R11 all instantiate this).
2. **Gate the gate.** Add a test that the *gate itself* cannot silently weaken —
   CI-runs-`make check` (AF-R01), the Makefile-target test (AF-R02), the
   AGENTS.md/CLI sync test (AF-R03). A gate nothing checks is a gate that rots.
3. **Every hand-maintained mirror is a HIGH drift risk — so gate it or delete
   it.** AudioForge's own `drift-risk-map.md` already thinks this way; the work
   is to *wire the detector in* (AF-R13), not to invent the philosophy.
4. **Make substitution loud.** Silent fallback (a missing font, a different BLAS,
   an un-migrated legacy spec) is the enemy of a reproducibility product
   (AF-R15, AF-R16). Emit a diagnostic to the manifest *and* stderr.
5. **The agent surface is a product, not an afterthought.** FrameForge treats the
   MCP loop as first-class; AudioForge's PURPOSE claims the same thesis but
   under-delivers on it (AF-R10). Close the gap between the stated thesis and the
   shipped surface.
6. **Be honest about status in-band.** The `Enforced/Adopted/Target` ratchet
   (AF-R13) and the capability `status` field (AF-R07) turn "we intend to" from
   prose into a queryable, drift-gated fact.
7. **Music theory is verified against closed ground truth, or it is not shipped**
   (Track M). Every theory operation has an enumerable correctness oracle — the
   224 Tn/TnI set-classes, the 24 triads, the 12 transpositions, published temperament
   cents. Test against the *whole* set, not samples. A "probably correct"
   transformation is exactly the unverified LLM-adjacent output PALS's LAW
   forbids. This is why every Track-M item sits behind the AF-R06 golden gate and
   carries an exhaustive property test in its DoD.

---

## 6. What NOT to copy (Rule 1 — unbiased)

To keep this roadmap honest, the following FrameForge features are **deliberately
excluded** because they do not serve AudioForge's PURPOSE:

- **The vision / raster→vector reconstruction MCP lane** (`measure_image`,
  `vectorize_image`, `score_reconstruction`, the Vector Construction Coach).
  These are graphics-domain; AudioForge has no analog need. AF-R10 takes the MCP
  *loop*, not this toolset.
- **The grammar ⇄ model EBNF gate.** AudioForge's grammar is an *executed* Lark
  file, not a hand-maintained view of models; the existing
  `test_grammar_token_sync.py` already covers the smaller real drift surface.
  Copy the principle, not the machinery.
- **Font-determinism packs verbatim.** The *problem* (pin the hidden
  determinism inputs) transfers; the *solution* (TTF bundles) does not — AF-R16
  solves the actual audio problem (BLAS/FFT/kernel), which is harder and must be
  measured, not assumed.
- **A full versioned docs deployment (`mike`) up front.** AF-R11 delivers the
  build *gate*; public hosting is deferred until there is an audience for it.

**Track-M scope discipline (Rule 8 — no gold-plating).** The corpus is a
600-page research monograph; AudioForge is not a music-theory analysis suite.
Port the operations that make *synthesis and composition* more expressive
(pc-sets, transformations, real tunings, modes, voice leading) — **not** the
book's analytical apparatus for its own sake. Specifically excluded until a
concrete render use-case demands them: generalized interval systems over
arbitrary GISes, filtered point-symmetry / David-Lewin network isographies,
and continuous *n*-dimensional voice-leading orbifold visualizations. Build the
operator; skip the treatise.

---

## 7. Appendix — evidence table (verified 2026-07-04)

| Claim | Evidence (path) | Verified |
|-------|-----------------|:--------:|
| ~~AudioForge has no `.github/` / CI~~ → **RESOLVED**: gate CI added (`.github/workflows/ci.yml`) | AF-R01; prior `.github/` held only `backlog-governance.yml`, not a code gate | ✅ |
| ~~No `Makefile`~~ → **RESOLVED**: root `Makefile` composes `make check` | AF-R02; `make check` green (704 passed) | ✅ |
| `AGENTS.md` referenced by `CLAUDE.md` but absent | `CLAUDE.md` reading-order §; root listing | ✅ |
| No ruff/black/mypy in root `pyproject.toml` | `pyproject.toml` (deps: lark, matplotlib, numpy, scipy) | ✅ |
| `docs/ir.schema.json` regenerated by hand; only test guards it | `tests/test_ir_schema.py`; no writer found | ✅ |
| Dual IR source: `schema.py` + `ir_schema.py` | both files present; registries duplicated | ✅ |
| Capability manifest is runtime-only, no on-disk artifact, no status field | `capabilities.py`; `audioforge capabilities` | ✅ |
| One golden (`dsl_ast.json`), no golden-audio corpus/lock | `tests/golden/` listing | ✅ |
| `verify` = re-render + SHA-256 compare | `cli.py` `verify`; `determinism.py` | ✅ |
| No MCP server; in-process `agent_tools.run_tool` only | `agent_tools.py`; `grep -ri mcp` empty | ✅ |
| No `CHANGELOG.md`; `RELEASE_NOTES.md` surrogate | `docs/` listing | ✅ |
| `scripts/drift_inspect.py` exists but not in `run_tests.sh` | `scripts/`; `run_tests.sh` suite list | ✅ |
| No ADRs | `docs/` listing (no `adr/`) | ✅ |
| Flat package layout (no `src/`) | repo root; `audioforge/` at root | ✅ |
| CLI verbs enumerated | `cli.py` `add_parser(...)` grep | ✅ |
| FrameForge `make check` composes 12 gates | `../frameforge/Makefile:64` | ✅ |
| FrameForge capability-manifest introspected, drift-gated | `../frameforge/tooling/gen_capability_manifest.py` | ✅ |
| FrameForge golden = hash lock + tolerance classification | `../frameforge/tooling/render_golden.py` | ✅ |
| FrameForge MCP = 25 tools, session resources | `../frameforge/src/framegraph/mcp/` | ✅ |

### Track-M evidence — codebase gaps (verified by package read 2026-07-04)

| Claim | Evidence (path) | Verified |
|-------|-----------------|:--------:|
| Pitch classes only as ad-hoc `{s % 12}`; no normal/prime form, IC-vector, Forte # | `dsl.py` (`_note_pc`, `pcs={s%12}`); `theory.py` | ✅ |
| `tuning: edo …` directive parses but is **inert** (no renderer reads it) | `dsl.py` (parse → `spec["notation"]["tuning"]`); `note_to_freq` = `440*2**(x/12)`; `library.py`/`plan.py` = `2**(st/12)` | ✅ |
| Only `MAJOR`/`MINOR` scales; `diatonic_transpose` never fed other modes | `dsl.py` (`MAJOR`,`MINOR`,`_scale_pitch_classes`); `theory.diatonic_transpose` | ✅ |
| No P/L/R, no UTT, no Tonnetz | grep of `audioforge/` — none | ✅ |
| Voice leading is a fixed ornament heuristic, not minimal-displacement | `dsl.py` ≈ L1030–1106 (passing tones/suspensions/anticipations) | ✅ |
| Grammar has no Roman-numeral / functional-harmony productions | `grammar.py` (`PITCH = note \| chord`) | ✅ |

### Track-M evidence — corpus source anchors (machine-verified retrieval 2026-07-04)

Retrieved from *Exploring Musical Spaces* (doc `b36afe03-…-e1e33b659a0`) via the
corpus GraphQL endpoint `http://192.168.199.25:8000/graphql` (API v1.3.0), using
`searchSentences(term, documentId)`. `#nnnn` is the sentence ordinal.

| Concept | Corpus anchor (verbatim fragment) | Sentence | Verified |
|---------|-----------------------------------|:--------:|:--------:|
| Book identity | ISBN 978-0-19-024601-3, DOI 10.1093/oso/9780190246013.001.0001 | #7 | ✅ |
| Tonnetz / fifths–thirds spaces | "1.3 Spaces generated by fifths and thirds … 1.4 Tonnetz" | #8 | ✅ |
| Prime form (pc-sets) | "major and minor triads … share the prime form 037" | #625 | ✅ |
| Triadic / neo-Riemannian | "8.1 Uniform triadic transformations … 8.2 Riemannian UTTs and neo-Riemannian analysis" | #15 | ✅ |
| Transformation networks | "Transformations II: Transformation Graphs and Networks" | #16 | ✅ |
| Voice-leading spaces | "10.1 The hexatonic triad graph as a continuous voice-leading space" | #17 | ✅ |
| Modes / diatonic collections | "white-note diatonic collection, called dpc(0) … centered on D" | #532 | ✅ |
| Non-heptatonic collections | "pentatonic … whole-tone … and octatonic pitch [spaces]" | #364 | ✅ |
| Maximally even sets | "our study of maximally even sets in Chapter 14" | #6609 | ✅ |
| Continuous pitch / JI | "continuous pitch space cpitch may be identified [with ℚ≠0]"; "Just Intonation." | #1057, #15617 | ✅ |
| Semitone metric | "pitch numbers … measured in semitones above or below middle C" | #227, #259 | ✅ |
| **Not attested in corpus** | "interval vector", "well-formed", "meantone" → **no hit** (grounded on external canon instead) | — | ⚠ |

> Per PALS's LAW and Rule 2: every item above should be re-verified against the
> cited file or source before acting on it. This roadmap is LLM-generated planning
> output — untrusted until checked. Corpus retrieval is subject to OCR/segmentation
> error in the source PDF; sentence fragments are quoted as returned. The corpus
> `entities`/`lexemes` GraphQL resolvers returned HTTP 500 for this 542k-token
> document, so the full entity/lexeme graph could **not** be extracted — Track-M
> grounding rests on targeted `searchSentences` retrieval, which succeeded.
