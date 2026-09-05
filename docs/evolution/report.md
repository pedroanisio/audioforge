---
disclaimer:
  notice: >-
    No information within this document should be taken for granted.
    Any statement or premise not backed by a real logical definition
    or verifiable reference may be invalid, erroneous, or a hallucination.
  generated_by: "Claude Fable 5.1 via Claude Code"
  date: "2026-09-05"
---

# Implementation Assessment and Evolution Plan: AudioForge engine 3.0 musical-correctness release

Companion artifacts: [harness.md](harness.md) (the verification contract, with the T0
baseline and an executable runner) and [roadmap.xlsx](roadmap.xlsx) (37 backlog items, 7
milestones, 34 dependency edges, 19 risks, 7 decisions). The three files share one ID space
and were cross-checked mechanically: every harness assertion is owned by at least one roadmap
item, every roadmap reference resolves to a harness assertion, and every dependency edge
names two existing items.

## 1. Executive summary

**The repair is code-complete and independently reproduced; it has not been delivered.**
That is the whole assessment in one sentence, and it corrects both descriptions currently in
circulation. The starting analysis says the twelve ledger rows are "all still open"; the
repository's own ledger (`docs/MUSICAL_CORRECTNESS.md`, untracked) says all twelve are
"Verified". Neither is right. The code exists and this assessment reproduced its claims from
a clean export of the previous engine, so the rows are not open. But nothing is committed, the
repository has never executed a CI job, the package does not import on the oldest Python it
declares, and no human has listened, so the rows are not verified in the sense the project's
own standards require (`docs/codebase-standards.md`: a rule is enforced only when a named
gate fails on violation).

**Where the system is today.** `main` sits at commit `60c0fd5` (engine 2.16.0, DSL 1.9),
equal to `origin/main`, last pushed 2026-07-05. On top of it lies an uncommitted working tree
that changes 45 files (+1 605 / −609 lines) and adds 12, bumping the engine to 3.0.0, the DSL
to 2.0 and the IR to 2.0. In the reference environment the composed gate passes (884 tests, 2
skipped), coverage is 90.96 % against a 90.1 % floor, the five golden renders reproduce
byte-for-byte, and the seven measured acceptance cases pass on 3.0.0 while all seven fail on
2.16.0. Those numbers were produced by this assessment, not copied from the ledger.

**Where it needs to go.** A tagged `engine-3.0.0` / `dsl-2.0` release on `origin/main`,
merged on remote CI evidence across Python 3.10, 3.11 and 3.12, with records (ADRs, backlog
registry, ledger, changelog, docs home page) that describe the shipped engine, a diagnostics
contract an agent can branch on without parsing prose, a documented performance cost, a
rehearsed rollback, and a recorded human listening review or an explicit, expiring waiver.

**The most important gaps, in order of consequence.**

1. The only copy of the repair is an uncommitted tree on one machine (harness `VCS-001`,
   `VCS-002`).
2. Every GitHub Actions run since 2026-07-04 (7 of 7) ended in `startup_failure` with zero
   jobs, so every gate the project calls enforced is advisory (`CI-001`). The cause could not
   be confirmed with the available token scope; the pattern (private repository, both
   workflows, valid YAML, zero seconds) points at Actions billing or a spending limit.
3. The package fails to import on Python 3.10 because a sample-catalog module uses
   `datetime.UTC` (Python 3.11+), and one test imports `tomllib`. Both predate the repair and
   were invisible because CI never ran (`PORT-001`).
4. The records contradict the code: ADR-0001 still roots randomness in the spec hash after
   ADR-0007 moved it to a performance seed; the docs home page still promises byte-identical
   audio "forever"; the backlog registry, the declared system of record, has no item for the
   largest change since 2.16.0 and marks six delivered Track E items as `ready`; the ledger's
   "Verified" rests on the author's own local run (`GOV-001…006`).
5. The repair left four contract rough edges: three new diagnostic codes are not in the
   registry that claims no code can land undocumented; validation rewrites the caller's spec
   in place; `verify` handed an `.af` file prints a raw JSON decoder error; the anti-alias
   resampler costs up to 5× more at two octaves of transposition and the migration guide does
   not say so (`CON-001…004`, `PERF-002`).
6. No listening evidence exists; the review page reports `not_reviewed` (`ACC-003`).

**The strategy.** The harness comes first and already exists: 59 assertions across 15
categories, executed against the working tree on 2026-09-05. The functional assertions pass
and were shown to fail on the previous engine, so they discriminate; the delivery assertions
fail, and that failing set is the backlog. Work is organised into five epics and six
checkpoints (T1 foundation → T6 desired state). The critical path is short and almost entirely
procedural: commit and push, fix Python 3.10, restore CI, review, merge, tag. Everything else
(governance, contract hardening, evidence tooling) runs in parallel on the branch and is
pulled onto the path only through milestone gates.

**Major risks.** Data loss before the first commit; a CI remedy that costs money or requires a
self-hosted runner; the intended audible change to existing specs; single-maintainer review
capacity; a listening review that never happens; and scope creep into the music-theory and
stochastic tracks that live in the backlog but not in this plan.

**Expected end state.** One runner invocation against the tagged commit produces an evidence
bundle in which every non-waived assertion passes, the ledger reads `released` on all twelve
rows with harness IDs beside each, `main` is green on three interpreters, and a rollback is a
`git checkout engine-2.16.0` whose own gate has been rehearsed.

## 2. Current state

### 2.1 Architecture as observed

The pipeline is unchanged in shape and changed in substance. A `.af` source is parsed by one
Lark grammar (`audioforge/lark_parser.py`), compiled by `audioforge/dsl.py` into a JSON IR in
which every smart directive has been expanded, validated and, when the score carries repeats,
rewritten into a single explicit timeline by `audioforge/arrangement.py`. The IR is hashed
(`spec_hash`, engine version folded in) and planned (`audioforge/plan.py`), then rendered
(`audioforge/render.py`) layer by layer through the sequencer, sampler and synth, mixed,
mastered (`audioforge/dynamics.py`, `audioforge/loudness.py`) and written with a manifest.
Two oracles guard the output: `audioforge verify` re-renders and compares bytes, and a
committed golden lock pins five corpus renders. Surfaces are the CLI (15 verbs), the SDK, the
in-process agent facade and a stdio MCP server that passes through to it. Generated artifacts
(IR schema, capability manifest, diagnostic-code page, docs pages, golden lock) are owned by
generators with `--check` twins composed into `make check`, which is also the CI command.

What the repair changed inside that shape, by ledger row (observed in the diff and exercised
by the new tests):

| Row | Mechanism now in the tree |
|---|---|
| A1 gain once | `render._layer_signal` no longer applies `gain_db` to instrument layers that the sampler already scaled; section players inherit one gain. |
| A2 note-off release | `synth.note_adsr` holds to gate end then releases from the current level; `sequencer.render_note_track` and `sampler.render_region` use it; sustain loops exit into the recorded tail. |
| A3 anti-alias | `sampler._sinc_read` scales the windowed-sinc cutoff and support by instantaneous playback rate, chunked to bound memory. |
| A4 mastering | `render._finish` applies fades before measurement, preserves level by default, normalises only on `normalization: peak`, and always enforces the oversampled ceiling; `dynamics.master_loudness` no longer skips limiting when the target is already met. |
| M1 harmony | `harmony.identify_chord` matches exact pitch collections across inversions, keeps sevenths, reports `ambiguous_harmony` / `unrecognized_harmony`; extensions follow the key at onset; `apply_voicing` does a bounded register search. |
| M2 phrases | `performance.conductor_spans` / `phrase_spans` prefer authored form and slurs; cadence labels require resolved roots, a declared key and a downbeat; chord tones share onset under humanisation. |
| M3 techniques | `schema.TECHNIQUES` carries `fidelity`; `technique_render` evidence survives IR and plan; `routing: fallbacks=forbid` raises on approximations; legato joins only contiguous monophonic slurs. |
| M4 arrangement | `arrangement.compile_repeats` expands sections into explicit notes, tempo, holds, markers and curve clocks; `loop_safe` measures seams and tails through SDK and facade. |
| M5 identity | `determinism.performance_hash(seed, variant)` roots all RNG; `note_seed_paths` gives events stable identities; layers are keyed by name, not index. |
| M6 analysis | `analysis.analyze_audio(…, context=…)` separates observations from recommendations and distinguishes authored rests from dead air. |
| G1 surfaces | schema, manifest, docs, versions and the golden lock regenerated; `docs/MIGRATION_3.md`, `docs/MUSICAL_CORRECTNESS.md`, ADR-0007 added. |

Package size is 21 339 lines across `audioforge/`; tests are 16 624 lines in 87 files; 886
tests collect, 67 of them in the five new suites.

### 2.2 Quality level as measured on 2026-09-05

| Measurement | Result | Harness |
|---|---|---|
| `make check`, reference env (Python 3.13.12, numpy 2.4.6, scipy 1.17.1) | exit 0; 884 passed, 2 skipped, 6 font warnings; 2 min 36 s | GATE-001, PERF-001 |
| Coverage | 90.96 % of 12 035 statements (floor 90.1 %); new modules 85–97 % | GATE-002 |
| Golden corpus | 5/5 byte-for-byte, env match true | GATE-003 |
| Acceptance corpus, current vs `60c0fd5` export | 7/7 pass on 3.0.0; 7/7 fail on 2.16.0 with the exact metrics the ledger reports; bundle reproducible across two runs | ACC-001, ACC-002, ACC-004 |
| `make check` under Python 3.12.3 (numpy 2.5.2) and 3.11.15 | exit 0; 884 passed; goldens byte-identical despite `env match: false` | PORT-002, PORT-003, PORT-004 |
| `make check` under Python 3.10.20 | fails at `manifest-check`: `ImportError: cannot import name 'UTC' from 'datetime'` | PORT-001 |
| Docs site, strict | exit 0 | GATE-004 |
| Backlog governance script | 31 items verified | GATE-005 |
| `verify` oracle | 3.0 IR vs 3.0 manifest: `REPRODUCIBLE` exit 0; 2.16 manifest under 3.0: `MISMATCH` exit 2 | MIG-001, OBS-001 |
| GitHub Actions | 7 runs, all `startup_failure`, 0 jobs | CI-001…004 |
| Rollback rehearsal: `engine-2.16.0` export, its own `scripts/run_tests.sh` | 395 passed, 2 failed, 2 skipped; both failures are the catalog-freshness guard demanding the gitignored `libraries/` tree; with it linked, one locale-dependent snapshot failure remains | RB-001, RB-002 |

### 2.3 Limitations and technical debt

The limitations fall into three groups, and the distinction matters because they need
different owners.

**Delivery debt (procedural, owner: maintainer).** Uncommitted tree; no second copy; no
review; no CI execution; no tag; `uv.lock` still says 2.16.0; the changelog files Track E
infrastructure under `[Unreleased]` and the musical fixes under `[3.0.0]` although both ship
together.

**Record debt (documentation that lies, owner: maintainer).** ADR-0001 and ADR-0007
disagree on the randomness root; ADR-0007 says "Accepted and implemented" for uncommitted
code; `docs/index.md` keeps the "every render, forever" claim the README dropped; the backlog
registry has no item for the repair and six stale `ready` statuses; the ledger's evidence
column cites `tests/test_performance_model.py`, a file the repair did not change; the
coordination pointer names a failed archived task.

**Contract debt (code, owner: maintainer with reviewer).** Diagnostic codes are prose with
embedded tokens and the registry lacks the three the repair introduced plus all analysis
codes; `validate_spec` and the agent facade's `validate` rewrite the caller's dict when repeats
are present (confirmed: duration 2.0 → 4.0 s, repeats consumed, same object returned);
`verify` with a non-JSON path emits `Error: Expecting value: line 1 column 1 (char 0)`; the
resampler's cost rises from a flat 41 ms per one-second note on 2.16.0 to 57 / 110 / 204 ms at
0 / 12 / 24 semitones on 3.0.0 and the migration guide is silent about it; the Python 3.10
floor is broken by pre-existing code.

### 2.4 Operational constraints

One maintainer; one reference machine holding the only copy; a private GitHub repository whose
Actions do not start; a docs toolchain fetched over the network by `uv`; a C compiler required
for native kernels; optional instrument libraries that are gitignored and skip two tests when
absent; and a coordination protocol (`.agent-tasks/`) that other agents on this machine use.

### 2.5 Facts, inferences, assumptions, unknowns

**Observed facts** (each backed by a command output transcribed in harness §4.3): every entry
in §2.2; the diff statistics; the seven `startup_failure` runs; the two Python 3.11-only
imports; the unregistered codes; the in-place mutation; the raw `verify` error; the benchmark
figures; the lockfile drift; the ADR and index.md text; the registry statuses; the tag dates.

**Inferred conditions.** The CI failure is account-level (billing or spending limit) rather
than a workflow defect, because both workflows fail identically at startup with valid YAML and
Actions enabled. Cross-platform determinism on x86_64 Linux is stronger than the golden gate
assumes, because the five goldens reproduced under three Python versions and two numpy/scipy
generations. The listening page is usable, because it generated and embedded seven WAVs, but
its usefulness to a listener is untested.

**Assumptions.** The maintainer is Pedro Anisio Silva and is also the repository admin.
Releases are git tags in the `engine-X.Y.Z` / `dsl-X.Y` form used for 2.16.0. The reference
machine remains available for the T1–T6 runs. Nobody else is editing the tree (the coordination
registry was empty at T0).

**Unknowns requiring validation.** The CI root cause (needs admin or a `user`-scoped token).
Whether the suite is truly offline (`SEC-001` not yet executed under isolation). Whether a
listener will judge the acceptance cases as improvements. Whether the remote ubuntu runner's
numeric environment reproduces the golden hashes (the gate is advisory there by design).

## 3. Desired state

The desired state is a released engine whose every claim has a named test and a stored piece
of evidence. Concretely, thirteen requirements, each with the assertions that decide it
(these are the rows of the roadmap's Traceability sheet):

| Req | Target capability | We know it is achieved when |
|---|---|---|
| REQ-1 | Audio semantics A1–A4 hold on the released engine | `HARNESS-AUD-001…004` and `ACC-001/002/004` pass on the tagged commit under CI |
| REQ-2 | Musical semantics M1–M6 hold | `HARNESS-MUS-001…006` pass likewise |
| REQ-3 | Every public and generated surface agrees with the code | `GATE-001…005`, `REL-001`, `MIG-001…003` pass on `main` |
| REQ-4 | The repair is committed, duplicated, reviewed and merged | `VCS-001…004` pass |
| REQ-5 | CI executes and is green on Python 3.10/3.11/3.12 | `CI-001…004`, `PORT-001…004` pass |
| REQ-6 | The release is tagged, locked and described in one changelog section | `REL-001…004` pass |
| REQ-7 | Governance and architecture records describe the shipped system | `GOV-001…008` pass |
| REQ-8 | Diagnostics carry machine-readable codes; validation never mutates its input; `verify` fails structurally | `CON-001…004` pass (CON-002 may be deferred by ADR-0008 with a waiver) |
| REQ-9 | Performance is bounded and documented | `PERF-001/002` pass |
| REQ-10 | Rollback is proven | `RB-001/002` pass |
| REQ-11 | Human listening evidence exists | `ACC-003` passes or carries an expiring waiver |
| REQ-12 | Progress is measured by execution and stored durably | `OBS-001/002` pass at every checkpoint |
| REQ-13 | The suite is offline and the tree secret-free | `SEC-001/002` pass |

Nothing in this list says "improve quality" or "modernise". Each row is decided by a command
with an exit code or by a JSON file a person produced.

## 4. Gap analysis

Each gap names its current condition, desired condition, consequence, work, prerequisites,
risks, validation and completion criterion. Roadmap and harness IDs are the cross-references.

**Gap 1: single uncommitted copy.** Current: 45 modified and 12 untracked files on one
machine; origin untouched since July. Desired: release branch on origin equal to local.
Consequence: any checkout, disk fault or careless agent erases the work and its only
evidence. Work: `RM-C-001`, then `RM-C-002` for the lockfile. Prerequisites: none.
Risks: R1, R18. Validation: `VCS-001`, `VCS-002`, `REL-004`. Complete when the T1 bundle shows
all three PASS for a named SHA.

**Gap 2: CI has never executed.** Current: 7/7 runs `startup_failure`, 0 jobs, for both
workflows; cause unconfirmed. Desired: a job runs; the matrix is green for the branch head and
for `main` after merge. Consequence: every "[Enforced]" row in `codebase-standards.md` and the
roadmap's "no longer advisory" claim are false today; merge decisions have no remote evidence.
Work: `RM-B-002` (diagnose and fix), then `RM-B-001` and `RM-B-003` so the matrix can be green.
Prerequisites: admin or billing access. Risks: R2, R10, R14. Validation: `CI-001…004`.
Complete when `CI-003` shows the merge commit green on three interpreters.

**Gap 3: Python 3.10 floor is broken.** Current: `datetime.UTC` in
`audioforge/sample_catalog/licenses.py:6` (since commit `f1c34a0`, 2026-06-13) and `tomllib` in
`tests/test_lark_parser.py:9`. Desired: `make check` passes on 3.10. Consequence:
`requires-python >= 3.10` is a false claim and the CI matrix would redden on its first run.
Work: `RM-B-001` (two-line fix), `RM-B-004` (a floor smoke in the gate). Prerequisites: none.
Risks: R3. Validation: `PORT-001`. Complete when the T1 bundle has a 3.10 exit-0 log.

**Gap 4: the audio and musical contract is unproven on a commit.** Current: all functional
assertions pass, but on a dirty tree. Desired: the same assertions pass on a commit SHA, then
on CI, then on the tag. Consequence: none for correctness, everything for trust; the ledger's
"Verified" is unfalsifiable without a SHA. Work: `RM-F-001…011` advance through the delivery
chain; no code work. Prerequisites: Gap 1. Risks: R4 (intended change). Validation:
`AUD-*`, `MUS-*`, `ACC-*`, `GATE-*`, `MIG-*`. Complete when the T6 bundle shows them PASS for
the tagged commit and the ledger rows read `released`.

**Gap 5: records contradict the code.** Current: ADR-0001 says randomness roots in the spec
hash; ADR-0007 says performance seed and calls itself implemented; `docs/index.md` promises
"forever"; the backlog has no item for the repair and six stale `ready` statuses; the ledger
uses an unqualified "Verified" and cites an unchanged test file. Desired: one determinism
story across ADRs, README and docs home; a registry item with evidence checks; a ledger whose
status vocabulary is staged and whose rows cite harness IDs. Consequence: agents that read the
records first (the project's stated consumption model) are misled about the determinism model
and about what is done. Work: `RM-D-001…006`. Prerequisites: none (sequencing after Gap 1).
Risks: R8, R11. Validation: `GOV-001…008`. Complete when all eight PASS at T3 and the ledger
advances to `released` at T6.

**Gap 6: diagnostics are prose.** Current: `Diagnostic(severity, message, path)`; codes live
inside messages; three new codes and all analysis codes are absent from the 29-entry registry.
Desired: every emitted code registered and documented; a `code` field on `Diagnostic` exposed
through the facade and MCP, or an ADR recording deferral. Consequence: an agent must
substring-match text to decide what to repair, which contradicts PURPOSE.md's "failure should
be loud and local" and `DSL_GAP_SPEC.md` §3.3. Work: `RM-E-001`, then `RM-E-002` with ADR-0008.
Prerequisites: none; `RM-E-002` depends on `RM-E-001`. Risks: R7, R13. Validation: `CON-001`,
`CON-002`. Complete when both PASS or `CON-002` carries an ADR-backed waiver.

**Gap 7: validation mutates its input.** Current: `validate_spec` returns the same object and
rewrites it when repeats exist; `run_tool("validate")` mutates the agent's request. Desired:
callers' specs are never rewritten. Consequence: an agent that validates then renders holds a
spec whose duration and event list changed underneath it; the IR it hashes is not the IR it
authored (ADR-0003 "IR is truth"). Work: `RM-E-004` (decision D2; recommended: deep-copy at the
top of `validate_spec`). Prerequisites: none. Risks: R6. Validation: `CON-004`, `GATE-003`
(goldens unchanged). Complete at T2.

**Gap 8: `verify` fails unstructurally on `.af` input.** Current: raw decoder error, exit 1.
Desired: compile-then-verify, or a diagnostic naming the expected input. Consequence: a small
but exact instance of the class of defect the project says it does not tolerate. Work:
`RM-E-003`. Prerequisites: none. Risks: none. Validation: `CON-003`. Complete at T2.

**Gap 9: performance cost is undocumented.** Current: the anti-alias kernel widens with
playback rate; measured 1.4× / 2.7× / 5.0× the 2.16.0 cost at 0 / 12 / 24 semitones; within
this plan's budget but unmentioned in `docs/MIGRATION_3.md`. Desired: documented curve and a
budget test. Consequence: users of large sampled orchestrations meet a slowdown the migration
guide did not warn about. Work: `RM-E-005`. Prerequisites: none. Risks: R5. Validation:
`PERF-002`. Complete at T5.

**Gap 10: no durable evidence or runner.** Current: T0 evidence lives in a session scratch
directory; the runner exists as a code block in harness.md and was executed once in quick
mode. Desired: `scripts/harness.sh` and `docs/evolution/evidence/<T>/`. Consequence: the
checkpoint model cannot be operated. Work: `RM-A-001`, `RM-A-002`, `RM-A-004`. Prerequisites:
none. Risks: none. Validation: `OBS-002`. Complete at T1.

**Gap 11: no listening evidence.** Current: `listening_status: not_reviewed`. Desired: a
`listening-review.json` with seven judgments citing a SHA. Consequence: the release can claim
numerical correctness only, which the ledger already states honestly; the gap is the absence
of the second kind of evidence, not a false claim. Work: `RM-A-003`. Prerequisites: Gap 1 (a
SHA). Risks: R9. Validation: `ACC-003`. Complete at T5 or waived with expiry at 3.1.0
(decision D3).

**Gap 12: rollback is a hope, not a procedure.** Current: the previous tag predates the
Makefile, its test runner hardcodes `python3`, its gate needs the gitignored `libraries/` tree
and one of its tests is locale-dependent; rehearsed by hand at T0 with 395 passing and those
two fixture failures (harness §4.4).
Desired: a documented runbook and a runner step. Consequence: an emergency rollback would
be improvised. Work: `RM-A-005`. Prerequisites: `RM-A-001`. Risks: none. Validation:
`RB-001`, `RB-002`. Complete at T5.

**Gap 13: release hygiene.** Current: changelog split across two sections; no date; lockfile
stale; tags absent. Desired: one dated `[3.0.0]`; lockfile in sync; tags on origin.
Consequence: the migration message users read first is incoherent. Work: `RM-C-002`,
`RM-C-004`, `RM-C-006`. Prerequisites: Gap 1; the M5 gate for the tag. Risks: none.
Validation: `REL-001…004`. Complete at T6.

## 5. Architecture and evolution strategy

**The evolution is a delivery, not a redesign.** The repair already replaced the four
mechanisms that were wrong (fixed-window envelopes, fixed-kernel resampling, index-keyed RNG
rooted in the spec hash, inert repeats) and the assessment found no reason to replace anything
further. The strategy therefore protects what works, changes only what the gaps name, and
introduces new components solely for evidence and contract clarity.

**Components that remain unchanged.** The Lark grammar and the IR-is-truth compilation model;
the generator-owns-artifact discipline and `make check`; the golden and `verify` oracles; the
MCP server as a pass-through over the agent facade; the synthesis, sampling and mastering
engines as repaired; the acceptance tool and its listening page.

**Components that change.** `Diagnostic` gains a `code` field (`RM-E-002`); `capabilities.py`
registers the missing codes (`RM-E-001`); `validate_spec` copies on entry (`RM-E-004`);
`cli.py verify` handles non-JSON input (`RM-E-003`); `sample_catalog/licenses.py` and
`tests/test_lark_parser.py` become 3.10-compatible (`RM-B-001`); the Makefile gains two cheap
gates (`RM-B-004`); ADR-0001, ADR-0007, `docs/index.md`, `CHANGELOG.md`, `docs/backlog.yml`,
`docs/MUSICAL_CORRECTNESS.md` and `docs/MIGRATION_3.md` are corrected (`RM-D-*`, `RM-C-004`,
`RM-E-005`, `RM-A-005`).

**Components that are replaced.** None. Stating this explicitly is the point: a reviewer who
proposes rewriting the resampler or the scheduler during this release is proposing a different
project.

**New components.** `scripts/harness.sh` and `docs/evolution/evidence/` (`RM-A-001`);
ADR-0008 for the diagnostics surface (`RM-E-002`); tests for registered codes, non-mutating
validation and the performance budget; backlog items for the release (`RM-D-001`).

**Migration boundaries.** Three boundaries move together: engine 2.16.0 → 3.0.0 (hash-breaking
by design, since `ENGINE_VERSION` folds into `spec_hash`), IR 1.2 → 2.0 (structural migration
via `migrate_ir_spec`, which flags `audio_review_required`), DSL 1.9 → 2.0 (additive syntax:
`normalize:`, `performance_seed:`, `notes_ir:` / `automation_ir:` / `clip_*` escapes).

**Compatibility requirements.** Old `.af` sources compile (verified for the repository's own
specs, `MIG-002`); old audio is intentionally not reproduced and old manifests fail `verify`
with `MISMATCH` exit 2 (`MIG-001`), which is the documented loud failure; the agent-tools
envelope stays `audioforge.agent-tools/1` if `code` is added as an optional field (decision
D1). Cross-environment reproducibility is checked, not assumed, and T0 evidence shows it
holding across three Python versions on the same architecture.

**Data migration.** No stored data belongs to the engine. Users regenerate manifests and
golden locks after reviewing renders; the tree already carries the regenerated repository
lock. Compositions under `compositions/` are gitignored and re-render on demand.

**Rollout.** Branch → PR → CI matrix → review → merge → M5 gates → tag. Consumers pin the
engine version they render with; nothing deploys anywhere else.

**Rollback.** `git checkout engine-2.16.0` (or revert the merge). The rehearsal at T0 showed four
facts the runbook must state: the tag predates the Makefile, so its gate is
`scripts/run_tests.sh`; that script hardcodes `python3`, so the reference interpreter must be
supplied through a wrapper script on `PATH` (a symlinked venv interpreter loses its
site-packages); its catalog-freshness guard fails unless the gitignored `libraries/` tree is
linked into the checkout; and even then its `current.txt` snapshot test is locale-dependent
(the repair later fixed that test with `LC_ALL=C --charset=UTF-8`), so one red test unrelated
to the engine is expected. Engine behaviour at 2.16.0 reproduced fully (395 tests). `RM-A-005`
writes this down and `RB-002` proves it each checkpoint.

## 6. Dependency analysis

**Independent work that can begin on day 1** (no prerequisites): `RM-C-001` commit and
push; `RM-B-001` Python 3.10 fix; `RM-B-002` CI diagnosis; `RM-A-001` runner; `RM-A-002`
commit the assessment; `RM-D-002`, `RM-D-003`, `RM-D-004`, `RM-D-005` record fixes;
`RM-E-001`, `RM-E-003`, `RM-E-004` contract fixes. Thirteen items, all XS or S.

**Dependent work.** `RM-C-002` needs the branch; `RM-B-003` and `RM-B-004` need the 3.10 fix
(and the lockfile for B-004); `RM-E-002` needs registered codes; `RM-A-003` needs a SHA to cite;
`RM-A-004` and `RM-A-005` need the runner; `RM-C-003` needs a PR; `RM-C-005` needs review, CI
and the M2/M3 gates; `RM-C-006` needs the merge and the M5 gates; `RM-F-*` complete only
through C-001 → C-005 → C-006.

**Enabling work** (unlocks others without being on the path): `RM-A-001` unlocks every
checkpoint decision; `RM-E-001` unlocks `RM-E-002`; `RM-B-004` prevents two findings from
recurring.

**Blocking work** (others cannot finish until it does): `RM-C-001` blocks everything;
`RM-B-002` blocks any remote evidence; `RM-C-003` blocks the merge; `RM-C-005` blocks the tag.

**Parallelizable work.** Workstreams A, D and E run concurrently with each other and with the
critical path once the branch exists; the eleven `RM-F` rows need no work, only evidence.

**Sequential work.** The critical path:
`RM-C-001` → `RM-B-001` → `RM-B-002` → (`HARNESS-CI-002` green) → `RM-C-003` → `RM-C-005` →
`RM-C-006`.

Why each edge exists: the fix must be a commit on the branch, so the branch comes first; the
matrix cannot be green on 3.10 before the fix, so the fix precedes CI; CI cannot show anything
before jobs start, so the diagnosis precedes the first green run; a reviewer should see a
green matrix, so review follows CI; merging on local logs would repeat the failure mode this
whole plan exists to end, so merge follows review and CI; a tag names a merged commit, so the
tag is last. Two gates cut across the path: M2/M3 require the record and contract fixes
(`RM-D-*`, `RM-E-001/003/004`, the `RM-E-002` decision) before merge, and M5 requires listening
evidence or a waiver, the performance note and the rollback runbook before the tag. Those
items are parallel until the gate, then blocking.

## 7. Risks and decision points

The roadmap's Risks sheet carries nineteen entries; the ones that shape the plan:

- **Architectural.** R6 mutation in validation; R7 prose diagnostics; R8 contradictory
  determinism records. All three have small fixes; the risk is shipping 3.0.0 without them and
  paying a surface change again in 3.1.
- **Implementation.** R3 further 3.10 breakage (low; the grep found only two constructs); R13
  coverage or gate-time regressions from new code (guarded every checkpoint).
- **Operational.** R2 CI remedy may cost money; R9 no listener; R12 single-maintainer review;
  R14 the governance workflow is equally broken; R16 concurrent agents.
- **Security.** R15 the offline property is inferred from mocks, not proven; no credentials or
  network are needed by the plan itself.
- **Data.** R1 the uncommitted copy; R18 a private remote behind a single account.
- **Performance.** R5 the resampler's 5× cost at large transpositions.
- **Migration.** R4 audible change for every existing spec (intended and documented; the risk
  is surprise, mitigated by the changelog consolidation); R19 the rollback target's own gate
  shows fixture failures in an isolated export (documented in the runbook).
- **External dependencies.** GitHub Actions (down), network for `uv` and wheels, a C compiler.

Unresolved decisions, with the recommendation and the alternative:

| ID | Decision | Recommended | Alternative and its cost |
|---|---|---|---|
| D1 | `Diagnostic.code` in 3.0.0 or 3.1? | Ship in 3.0.0: additive field, agents are the primary consumer, 3.0 already breaks hashes | Defer via ADR-0008 with a waiver; a second surface change later |
| D2 | Where to stop validation from mutating callers | Deep-copy at the top of `validate_spec`: one place, negligible against render cost | Copy only at the SDK/agent boundary (internal callers still bitten); or document the mutation (contradicts ADR-0003) |
| D3 | Is the listening review release-blocking? | Waivable with a recorded waiver expiring at 3.1.0; release notes say `not reviewed` | Blocking: honest but may hold a correct engine hostage to scheduling |
| D4 | How to restore CI | Confirm and fix Actions billing or spending limit | Self-hosted runner on the reference machine (fast, but the reference machine becomes infrastructure); another CI provider (new workflow, loses `test_ci_make_check_sync.py` pinning) |
| D5 | Changelog shape | One dated `[3.0.0]` containing Track E and the fixes | Two sub-sections under one header; acceptable, slightly noisier |
| D6 | Golden lock after semantic change | Accept the regenerated hashes; state that 2.16 hashes are not evidence for 3.0 sound | Keep both locks; doubles gate time for no decision value |
| D7 | Ledger status vocabulary | Five staged statuses advanced only from evidence bundles | Keep "Verified" with a footnote; repeats the ambiguity this assessment had to resolve |

## 8. Conclusion

**Recommended path.** Run the harness, then walk the critical path: commit and push today,
fix the two Python 3.10 imports as the next commit, find out why Actions do not start, and
let the first green remote matrix be the first time this repository's gate has ever run where
the maintainer did not also write the code. Review, merge, tag. In parallel, on the same
branch, make the records tell the truth and close the four contract rough edges, because 3.0.0
is the cheapest moment to change a public surface.

**Why this sequencing.** The two most consequential gaps (a single uncommitted copy; a CI that
has never executed) are also the cheapest to close, and everything else gains meaning from
them: a review needs a branch, a merge needs remote evidence, a "Verified" needs a SHA. The
functional work is finished and reproduced, so spending effort on it now would be motion, not
progress.

**What must happen first.** `RM-C-001`. Nothing else is worth doing while the only copy of the
repair can be lost by a `git checkout`.

**What can happen in parallel.** All of workstreams A (evidence), D (records) and E (contract):
thirteen day-1 items, all XS or S, none on the critical path until the M2 and M3 gates.

**What constitutes completion.** Harness §7: one runner invocation against the tagged commit
with every non-waived assertion at `PASS`, zero unexplained failures, zero blocked rows,
coverage and gate time inside their budgets, a listening review or an expiring waiver, a
rehearsed rollback, tags on `origin`, and a ledger that reads `released` with harness IDs on
all twelve rows. Roadmap items are complete under the same five-part rule; "done because the
code was written" is not a state in either artifact.

**The resulting system.** Engine 3.0.0 as it already exists in this tree, delivered: on `main`
with three green interpreters, described by records that agree with each other, emitting
diagnostics an agent can branch on, honest about its performance cost and its listening
status, and one tag away from its predecessor. The starting analysis called the state
"mid-repair"; the accurate description is "repaired, unreleased", and this plan is the
distance between the two.
