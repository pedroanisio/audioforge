---
disclaimer:
  notice: >-
    No information within this document should be taken for granted.
    Any statement or premise not backed by a real logical definition
    or verifiable reference may be invalid, erroneous, or a hallucination.
  generated_by: "Claude Fable 5.1 via Claude Code"
  date: "2026-09-05"
---

# Evolution and Verification Harness — Engine 3.0 musical-correctness release

Companion artifacts: [report.md](report.md) (analysis) and [roadmap.xlsx](roadmap.xlsx) (backlog).
The three files share one ID space: roadmap items are `RM-<ws>-<nnn>`, harness tests are
`HARNESS-<cat>-<nnn>`, checkpoints are `T0`…`T6`. The repository's own ledger rows
(`docs/MUSICAL_CORRECTNESS.md`: A1–A4, M1–M6, G1) are referenced by their existing IDs.

## 0. What the baseline says in one paragraph

At T0 (2026-09-05, working tree on top of commit `60c0fd5`) the harness has 59 assertions.
Thirty pass: every assertion that tests what the engine *does* (audio, musical, acceptance,
gate, migration, manifest identity) plus the Python 3.11 and 3.12 portability legs, and the
acceptance corpus was shown to fail on the previous engine (`HARNESS-ACC-002`), so these are
not tests that merely mirror current behaviour. Twenty-four that test whether the work has
been *delivered* fail: nothing is committed, the repository has never executed a CI job, the
package does not import on Python 3.10, the release is untagged, the governance registry does
not know the work exists, and no human has listened to the result. Four are partial (ledger
citations, resampler documentation, durable evidence, and the rollback rehearsal, whose
2.16.0 gate needs gitignored fixtures the tag does not carry) and one is blocked. That split
is the transformation backlog: the code is done, the release is not.

## 1. Core principle

The desired state is encoded as assertions first. A roadmap item is complete only when
(1) implementation exists, (2) its harness tests execute, (3) they pass, (4) the evidence
named in this file is produced, and (5) the milestone gate in §6 accepts it. "Verified"
without a harness ID and an evidence path is not a status this project recognises. This
replaces the single-word `Verified` column currently used in `docs/MUSICAL_CORRECTNESS.md`
(see `HARNESS-GOV-003`).

Result vocabulary, used everywhere in this file, in the roadmap `Status` column and in the
ledger:

| Result | Meaning |
|---|---|
| `PASS` | Procedure executed, pass criteria met, evidence stored. |
| `PARTIAL` | Some pass criteria met; the row names exactly which are missing. |
| `FAIL` | Procedure executed, criteria not met. At T0 this is the expected state for undelivered capabilities. |
| `BLOCKED` | Procedure cannot execute because a precondition is missing; the row names the precondition and the roadmap item that supplies it. |
| `N/A` | Not applicable to this system; the row says why. |
| `WAIVED` | Failing but accepted with a recorded waiver (§6.3). Counts as a failure in the totals. |

## 2. Harness architecture

### 2.1 Layers

| Layer | What it proves | Tools | Where it runs |
|---|---|---|---|
| L0 Static / contract | Generated artifacts match their generators; registries agree; docs claims match code; lockfile matches manifest | `make schema-check manifest-check drift-check version-check docs-gen-check`, `uv lock --check`, `node scripts/check-backlog-governance.mjs`, `grep` | local, CI |
| L1 Semantic unit | Compiler and validator produce the specified IR (harmony, phrases, repeats, IDs, diagnostics) | `pytest` on `tests/test_musical_correctness.py`, `tests/test_arrangement_correctness.py`, `tests/test_score_timing_validation.py` | local, matrix venvs, CI |
| L2 Audio measurement | Rendered buffers have the specified level, spectrum, timing and reproducibility | `pytest` on `tests/test_audio_correctness.py`; `python -m audioforge.tools.musical_acceptance`; `python -m audioforge.tools.render_golden --check`; `audioforge verify` | local, matrix venvs, CI |
| L3 Delivery | The work is committed, reviewed, CI-executed, tagged, governed | `git`, `gh`, `jq`, `make check` under Python 3.10/3.11/3.12 | local + GitHub |
| L4 Human | A listener judged the acceptance corpus | the generated listening page (`index.html`) and its exported `listening-review.json` | a person with monitoring |

### 2.2 Categories and their IDs

`AUD` audio semantics (ledger A1–A4) · `MUS` musical semantics (M1–M6) · `ACC` acceptance
corpus and listening · `GATE` composed gate and generated artifacts · `PORT` interpreter
portability · `CI` continuous integration · `VCS` version control and data safety · `REL`
release hygiene · `GOV` governance and architecture records · `CON` contract hardening ·
`PERF` performance · `MIG` migration and backward compatibility · `RB` rollback · `OBS`
observability and evidence · `SEC` security.

Categories the user template lists that are intentionally thin here: *scalability* is not a
property of this system (an offline, single-process renderer with an opt-in thread pool), so
the relevant dimension is render wall time and it lives in `PERF`; *permissions* reduce to
GitHub repository and Actions permissions and live in `CI`; *deployment* is a git tag and
lives in `REL`; *infrastructure* is interpreters, compilers and GitHub Actions and lives in
`PORT` and `CI`.

### 2.3 Execution environments

| Name | Definition | Used by |
|---|---|---|
| Reference | This machine at T0: Linux 7.0.11 x86_64, 12 cores, `./.venv` Python 3.13.12, numpy 2.4.6, scipy 1.17.1, C compiler present, `tree`, `node` 24.14, `uv` 0.10.9, `gh` authenticated as `pedroanisio` | every automated check; golden lock `numeric_env` matches this environment |
| Matrix venvs | `uv venv --python 3.10|3.11|3.12` + `uv pip install -e '.[dev]'`, in a scratch directory | `PORT-*` |
| Baseline export | `git archive <ref> \| tar -x -C <dir>`; run with `PYTHONPATH=<dir>` and `cwd=<dir>` so the export shadows the editable install | `ACC-002`, `MIG-001`, `RB-*` |
| GitHub Actions | `.github/workflows/ci.yml` (`ubuntu-latest`, Python 3.10/3.11/3.12, `make check`) | `CI-*` |

### 2.4 Fixtures and test data

All audio is synthesized inside the tests: sine and noise layers, and a self-built two-file
SFZ library (18 kHz tone for aliasing, 261.63 Hz tone for gain) generated by
`audioforge.tools.musical_acceptance._library`. The golden corpus is
`tests/golden/audio/*.af` (5 specs) pinned by `tests/golden/audio.lock.json`. The optional
instrument libraries under `libraries/` (gitignored) add two tests that skip when absent. No
network and no credentials are needed for L0–L2; L3 needs `git` push access and a `gh` token
with `repo` scope; billing diagnosis (`RM-B-002`) needs repository-admin access.

### 2.5 Evidence and reporting

Every check writes `<evidence>/<checkpoint>/<HARNESS-ID>.log` and one line to
`<evidence>/<checkpoint>/summary.tsv`; heavy artifacts (WAVs, exports, the built site) go under
`<evidence>/<checkpoint>/work/`, which is gitignored (`id`, `result`, `description`, `seconds`, `log`). The
evidence root is `docs/evolution/evidence/` once `RM-A-001` lands; WAV files stay out of git
(`*.wav` ignored under that path), JSON manifests and logs are committed. Until then, the T0
evidence lives in this session's scratch directory and its load-bearing lines are copied into
§4 verbatim. Render manifests are evidence in themselves: they carry `spec_hash`,
`performance_hash`, `performance_seed`, `engine_version`, `output_sha256` and `plan_hash`
(`HARNESS-OBS-001`).

### 2.6 CI, local, staging, production-safe

`make check` already is the CI job (`tests/test_ci_make_check_sync.py` pins that). The
runner in §8 adds the delivery-layer checks; `RM-B-004` wires the cheap ones (`uv lock
--check`, a Python-floor import smoke) into `make check`, and the roadmap proposes a second
workflow job that runs `scripts/harness.sh <checkpoint>` on pull requests. "Staging" for this
project is the matrix venvs. The only production-safe assertion is `audioforge verify
<ir.json> <manifest.json>`: it re-renders and compares bytes without writing to the delivered
asset, so it may be run against shipped manifests at any time (`HARNESS-MIG-001` shows the
expected loud `MISMATCH`, exit 2, when the manifest came from the old engine).

## 3. Test registry

Shared preconditions unless a row says otherwise: reference environment (§2.3); repository
root as working directory; the tree under test is either the working tree (T0) or a named
commit (T1 onward, recorded in the evidence summary). `Mode` is `A` automated, `M` manual,
`A+M` automated with a human step. `T0` is the recorded baseline result; `Target` is the
desired-state result. `Green by` names the checkpoint at which the test must be `PASS` for
the gate in §6 to open.

### 3.1 AUD — audio semantics (ledger A1–A4)

Failure meaning for this whole category: the engine produces audio that contradicts the
documented contract in `docs/MIGRATION_3.md` and ADR-0007; the release must not ship.
Evidence: pytest log; for `ACC` cross-reference, the acceptance manifest metrics.

| ID | Requirement | Procedure | Pass criteria | Mode | T0 | Target | Roadmap | Green by |
|---|---|---|---|---|---|---|---|---|
| HARNESS-AUD-001 | A1: instrument layer gain is applied once, including virtual sections, measured through the full renderer on a pinned sample library | `pytest -q tests/test_audio_correctness.py -k gain_is_applied_once` (2 parametrisations) | both pass; stem RMS changes by −6 dB ± 0.03 for a −6 dB edit | A | PASS | PASS | RM-F-001, RM-C-005 | T2 (branch), T3 (CI) |
| HARNESS-AUD-002 | A2: note duration is gate time; release starts at note-off for synth and sampler, including note-off during attack and sustain-loop exit into the recorded tail | `pytest -q tests/test_audio_correctness.py -k "release_starts_at_note_off or during_attack or sustain_loop_exits"` | 3 pass; last non-zero sample at 0.70 s ± 2 ms for a 0.5 s gate + 0.2 s release | A | PASS | PASS | RM-F-002, RM-C-005 | T2, T3 |
| HARNESS-AUD-003 | A3: transposition and rate conversion suppress out-of-band content, preserve in-band pitch and level, including variable-rate glides | `pytest -q tests/test_audio_correctness.py -k "out_of_band or in_band_tone or aliases_during_glide"` (5 cases) | all pass; interior RMS of folded content < 0.001; in-band level 2^-0.5 ± 0.002 and peak bin exactly 4000 Hz | A | PASS | PASS | RM-F-003, RM-C-005 | T2, T3 |
| HARNESS-AUD-004 | A4: default mastering preserves absolute level below the ceiling; `normalize: peak` is explicit and round-trips; ceiling includes intersample peaks and delivered fades; LUFS path never skips peak safety | `pytest -q tests/test_audio_correctness.py -k "preserves_absolute_level or explicit_request or normalization_dsl_roundtrip or intersample or does_not_skip_peak_safety"` | 5 pass | A | PASS | PASS | RM-F-004, RM-C-005 | T2, T3 |

### 3.2 MUS — musical semantics (ledger M1–M6)

Failure meaning: the compiler or planner asserts musical meaning it cannot support
(invented roots, fabricated cadences, silent approximations, reseeded takes), which is the
class of defect the September review found. Evidence: pytest logs.

| ID | Requirement | Procedure | Pass criteria | Mode | T0 | Target | Roadmap | Green by |
|---|---|---|---|---|---|---|---|---|
| HARNESS-MUS-001 | M1: chord root and quality resolve across inversions; sevenths preserved; ambiguous (C6/Am7) and unrecognised clusters are preserved and reported; extensions follow key at onset; voice leading preserves chord tones; emotion tags report production scope | `pytest -q tests/test_musical_correctness.py -k "chord_extensions or explicit_chord_quality or ambiguous_harmony or unknown_cluster or modulation or voice_leading_preserves or emotion_reports"` (11 cases) | all pass; diagnostics contain `ambiguous_harmony` / `unrecognized_harmony` where specified | A | PASS | PASS | RM-F-005, RM-E-001 | T2, T3 |
| HARNESS-MUS-002 | M2: phrases use authored form and slurs; no fabricated cadence or pitch peak; cadence candidates need resolved roots, declared key and a downbeat; chord tones share onset under humanize; parts share a conductor clock without becoming identical | `pytest -q tests/test_musical_correctness.py -k "fabricate or polyphonic_gates or coordinated or cadence_candidates or share_timing_motion"` and `pytest -q tests/test_ai_agent_dsl.py -k "phrase or voicing_directive"` | all pass; cadence candidate exactly `{beat 4.0, dominant_to_tonic, candidate, [resolved_chord_roots, declared_key, local_downbeat]}` | A | PASS | PASS | RM-F-006 | T2, T3 |
| HARNESS-MUS-003 | M3: technique fidelity is explicit (`technique_render.fidelity`), survives IR and plan, and `routing: fallbacks=forbid` rejects approximations; legato joins only contiguous monophonic slurs; planner and runtime consume the same schedule and RNG stream | `pytest -q tests/test_musical_correctness.py -k "technique_approximation or legato_requires"`; `pytest -q tests/test_render_plan.py -k plan_authority_matches_performance_rng_stream` (5 parametrisations); `pytest -q tests/test_expressive_techniques_lowering.py tests/test_performance_model.py` | all pass; harmonic partial 3 lowers to 1200·log2(3) cents | A | PASS | PASS | RM-F-007 | T2, T3 |
| HARNESS-MUS-004 | M4: `repeat` executes in the render contract (notes, duration, continuation, tempo, holds, markers, shaped automation, unique IDs, decompile round trip); meter/pickup define groove phase; loop safety measures real seams and tails through SDK and agent facade | `pytest -q tests/test_arrangement_correctness.py` (17) and `pytest -q tests/test_audio_correctness.py -k "loop_safe or loop_check or render_ready_validation"` (4) | all 21 pass; `verse x2` yields 3.0 s and onsets `[0, 2, 4]` | A | PASS | PASS | RM-F-008 | T2, T3 |
| HARNESS-MUS-005 | M5: gain, pan, metadata and reordering edits leave unrelated stems byte-identical; explicit `performance_seed` changes the take reproducibly; inserting an earlier note preserves later notes; full uint64 seed round-trips through the DSL; expanded repeats keep IDs unique | `pytest -q tests/test_audio_correctness.py -k "mix_edits_preserve or explicit_performance_seed or inserting_an_earlier_note"` (6); `pytest -q tests/test_musical_correctness.py -k uint64_seed`; `pytest -q tests/test_arrangement_correctness.py -k event_ids_unique` | all pass; `np.array_equal` on stems | A | PASS | PASS | RM-F-009 | T2, T3 |
| HARNESS-MUS-006 | M6: analysis reports observations always and recommendations only under declared expectations; authored rests are not dead air | `pytest -q tests/test_musical_correctness.py -k "analysis_observations or authored_rests"`; `pytest -q tests/test_ai_agent_dsl.py -k analysis_returns_actionable` | 3 pass | A | PASS | PASS | RM-F-010, RM-E-001 | T2, T3 |

### 3.3 ACC — acceptance corpus and listening

Evidence: `manifest.json` (`audioforge.musical-acceptance/1`) with per-case metrics and
`output_sha256`; `index.html` with embedded WAVs; `listening-review.json`
(`audioforge.listening-review/1`) for the human step.

| ID | Requirement | Procedure | Pass criteria | Mode | T0 | Target | Roadmap | Green by |
|---|---|---|---|---|---|---|---|---|
| HARNESS-ACC-001 | The seven measured acceptance cases (seventh, phrase, repeat, release, quiet, alias, sample_gain) pass on the tree under test | `python -m audioforge.tools.musical_acceptance --out <ev>/acceptance` | exit 0; `manifest.json` `passed: true`; 7 cases | A | PASS (11.2 s) | PASS | RM-F-001…010 | T2, T3 |
| HARNESS-ACC-002 | The same cases expose the targeted defect on the previous engine, proving the assertions discriminate | export `engine-2.16.0` (or HEAD `60c0fd5`), then `--baseline-root <export>`; assert every `revisions.baseline.passed == false` | 7/7 baseline `false`, 7/7 current `true` | A | PASS | PASS | RM-A-001 | T2 |
| HARNESS-ACC-003 | A human listening review of the corpus is recorded and cited by the ledger; `listening_status` is no longer `not_reviewed` | open `index.html` at matched playback level, judge all 7 cases blind, `Download listening notes`, commit the JSON under `docs/evolution/evidence/<checkpoint>/listening-review.json` with the reviewed `spec_hash`es and commit SHA; update the ledger row | 7 non-null judgments; JSON schema `audioforge.listening-review/1`; ledger cites the file and the commit | M | FAIL (no listener yet; page generated, status `not_reviewed`) | PASS | RM-A-003, RM-D-003 | T5 (waivable, §6.3) |
| HARNESS-ACC-004 | The acceptance bundle is itself reproducible | run `ACC-001` twice into different directories; compare `output_sha256` per case | identical hashes for all 7 | A | PASS | PASS | RM-A-004 | T2 |

### 3.4 GATE — composed gate and generated artifacts (ledger G1)

Failure meaning: a generated artifact, registry, version literal or golden hash disagrees with
the code; the contract is not inspectable. Evidence: `make check` log; `coverage report`;
`mkdocs` log; governance script output.

| ID | Requirement | Procedure | Pass criteria | Mode | T0 | Target | Roadmap | Green by |
|---|---|---|---|---|---|---|---|---|
| HARNESS-GATE-001 | The composed local gate passes in the reference environment | `make check` | exit 0; pytest summary has 0 failed | A | PASS: 884 passed, 2 skipped, 6 warnings; 2 min 36 s wall | PASS | RM-F-011 | T2, and at every later checkpoint |
| HARNESS-GATE-002 | Statement coverage meets the repository threshold | `coverage run -m pytest -q && coverage report` (`fail_under = 90.1`) | exit 0 | A | PASS: 90.96 % (12 035 statements, 1 088 missed); new modules: arrangement 85.1 %, harmony 97.0 %, performance 96.3 %, musical_acceptance 85.6 % | PASS | RM-F-011 | T2 |
| HARNESS-GATE-003 | Golden corpus reproduces byte-for-byte in the lock's numeric environment | `python -m audioforge.tools.render_golden --check` (inside `make check`) | "all 5 golden specs reproduce byte-for-byte (env match: True)" | A | PASS | PASS | RM-F-011 | T2 |
| HARNESS-GATE-004 | The documentation site builds strictly with the new pages in nav | `uv run --with mkdocs-material mkdocs build --strict --site-dir <ev>/site` | exit 0; no WARNING | A | PASS (exit 0, 0.25 s) | PASS | RM-F-011 | T2 |
| HARNESS-GATE-005 | The backlog registry validates | `node scripts/check-backlog-governance.mjs` | exit 0 | A | PASS: "31 item(s) verified" | PASS | RM-D-001 | T2 |
| HARNESS-GATE-006 | No whitespace errors in the diff | `git diff --check` | exit 0 | A | PASS | PASS | RM-A-001 | T1 |

### 3.5 PORT — interpreter portability

Preconditions: matrix venvs (§2.3), network to fetch interpreters and wheels once. Failure
meaning: the declared `requires-python >= 3.10` and the CI matrix are false claims.

| ID | Requirement | Procedure | Pass criteria | Mode | T0 | Target | Roadmap | Green by |
|---|---|---|---|---|---|---|---|---|
| HARNESS-PORT-001 | `make check` passes under Python 3.10 | `make check PYTHON=<py310 venv>/bin/python` | exit 0 | A | FAIL: `manifest-check` aborts, `ImportError: cannot import name 'UTC' from 'datetime'` in `audioforge/sample_catalog/licenses.py:6` (pre-existing since commit `f1c34a0`); `tests/test_lark_parser.py:9` also imports `tomllib` (3.11+) | PASS | RM-B-001 | T1 |
| HARNESS-PORT-002 | `make check` passes under Python 3.11 | `make check PYTHON=<py311 venv>/bin/python` | exit 0 | A | PASS: 884 passed, 2 skipped, 1 min 46 s; numpy 2.4.6, scipy 1.17.1; goldens 5/5 with `env match: False` | PASS | RM-B-003 | T2 |
| HARNESS-PORT-003 | `make check` passes under Python 3.12 | `make check PYTHON=<py312 venv>/bin/python` | exit 0 | A | PASS: 884 passed, 2 skipped, 2 min 55 s; numpy 2.5.2, scipy 1.18.1 | PASS | RM-B-003 | T2 |
| HARNESS-PORT-004 | Cross-environment golden behaviour is the documented one: advisory when `numeric_env` differs, strict when it matches | inspect `golden-check` line in PORT-002/003 logs and in GATE-001 | "env match: False" reported without reddening the gate; hashes compared | A | PASS: under numpy 2.5.2 the 5 goldens still reproduced byte-for-byte with `env match: False` | PASS | RM-B-003 | T2 |

### 3.6 CI — continuous integration

Preconditions: `gh` authenticated with `repo` scope; for `CI-001` diagnosis, repository-admin
and billing visibility. Failure meaning: every contract gate in this repository is advisory,
which contradicts `docs/ROADMAP.md` ("the discipline is no longer advisory") and
`docs/codebase-standards.md` (`[Enforced]` rows).

| ID | Requirement | Procedure | Pass criteria | Mode | T0 | Target | Roadmap | Green by |
|---|---|---|---|---|---|---|---|---|
| HARNESS-CI-001 | A GitHub Actions run for this repository executes at least one job | `gh run list -L 1 --json databaseId` then `gh api repos/pedroanisio/audioforge/actions/runs/<id>/jobs --jq .total_count` | `total_count ≥ 1` and conclusion ≠ `startup_failure` | A | FAIL: 7 of 7 runs since 2026-07-04 are `startup_failure`, 0 jobs, 0 s; both workflow YAML files parse; Actions enabled (`allowed_actions: all`); repo private; billing endpoint needs the `user` token scope, so the root cause is unconfirmed | PASS | RM-B-002 | T1 diagnosed, T3 PASS |
| HARNESS-CI-002 | The `ci` workflow is green on the release branch head for Python 3.10, 3.11 and 3.12 | `gh run list --branch <branch> --workflow ci --json conclusion,headSha` | latest run for the head SHA `success`, 3 jobs | A | FAIL (no run has ever executed) | PASS | RM-B-001, RM-B-002, RM-C-001 | T3 |
| HARNESS-CI-003 | The `ci` workflow is green on `main` after the merge | same, `--branch main` | `success` for the merge commit | A | FAIL | PASS | RM-C-005 | T4 |
| HARNESS-CI-004 | The `backlog-governance` workflow is green | `gh run list --workflow backlog-governance` | latest `success` | A | FAIL (`startup_failure`) | PASS | RM-B-002, RM-D-001 | T3 |

### 3.7 VCS — version control and data safety

Failure meaning: the repair exists as one uncommitted copy on one machine; a disk fault or a
`git checkout` erases four hours of engine work and the only evidence of it.

| ID | Requirement | Procedure | Pass criteria | Mode | T0 | Target | Roadmap | Green by |
|---|---|---|---|---|---|---|---|---|
| HARNESS-VCS-001 | The repair is committed; the tree under test is clean | `git status --porcelain` | empty output | A | FAIL: 45 modified (+1 605/−609) and 12 untracked files | PASS | RM-C-001 | T1 |
| HARNESS-VCS-002 | A second copy exists: the tree is clean and the release branch is pushed and equals local | `test -z "$(git status --porcelain)" && git fetch -q origin && test "$(git rev-parse HEAD)" = "$(git rev-parse origin/$(git branch --show-current))"` | equal SHAs | A | FAIL: `origin` last pushed 2026-07-05; local `main` = `origin/main` = `60c0fd5`, so the repair has never left this machine | PASS | RM-C-001 | T1 |
| HARNESS-VCS-003 | The repair was reviewed by someone other than its author and findings were closed | PR exists; `gh pr view --json reviews` shows ≥ 1 `APPROVED`; review notes (including `/code-review` output) attached | approval present; every finding marked fixed or explicitly declined with reason | A+M | FAIL (no branch, no PR) | PASS | RM-C-003 | T3 |
| HARNESS-VCS-004 | The tree is clean and the release commit is an ancestor of `origin/main` | `test -z "$(git status --porcelain)" && git merge-base --is-ancestor <release-sha> origin/main` | exit 0 | A | FAIL | PASS | RM-C-005 | T4 |

### 3.8 REL — release hygiene

| ID | Requirement | Procedure | Pass criteria | Mode | T0 | Target | Roadmap | Green by |
|---|---|---|---|---|---|---|---|---|
| HARNESS-REL-001 | Every version literal equals `audioforge/version.py` | `python -m audioforge.tools.bump_version --check` (inside `make check`) | exit 0 | A | PASS (3.0.0 / DSL 2.0 everywhere the tool manages) | PASS | RM-F-011 | T1 |
| HARNESS-REL-002 | `CHANGELOG.md` describes one release: the `[3.0.0]` section carries a date and contains both the Track E infrastructure (AF-R01…R13, committed since 2.16.0) and the musical fixes; `[Unreleased]` holds only post-3.0 work | `awk '/^## \[Unreleased\]/,/^## \[3.0.0\]/' CHANGELOG.md \| grep -c 'Track E'` must be 0; `grep -E '^## \[3.0.0\] - 20[0-9]{2}-' CHANGELOG.md` | both criteria | A | FAIL: Track E sits under `[Unreleased]` while `[3.0.0]` lists only the fixes; no date | PASS | RM-C-004 | T4 |
| HARNESS-REL-003 | Tags `engine-3.0.0` and `dsl-2.0` exist on `origin` and point at an ancestor of `main` | `git ls-remote --tags origin \| grep -E 'refs/tags/(engine-3\.0\.0\|dsl-2\.0)$'` (2 lines); `git merge-base --is-ancestor engine-3.0.0 origin/main` | both | A | FAIL (latest tags: `engine-2.16.0`, `dsl-1.9` at `282756e`, 2026-06-12) | PASS | RM-C-006 | T6 |
| HARNESS-REL-004 | The `uv` lockfile matches `pyproject.toml` | `uv lock --check` | exit 0 | A | FAIL: "The lockfile at `uv.lock` needs to be updated" (still records `audioforge 2.16.0`) | PASS | RM-C-002, RM-B-004 | T1 |

### 3.9 GOV — governance and architecture records

Failure meaning: the project's declared system of record (`docs/backlog.yml`) and its
decision records (`docs/adr/`) describe a different system from the one in the tree; agents
reading them are misled.

| ID | Requirement | Procedure | Pass criteria | Mode | T0 | Target | Roadmap | Green by |
|---|---|---|---|---|---|---|---|---|
| HARNESS-GOV-001 | The musical-correctness work is registered in the backlog system of record with evidence checks | `grep -c 'ADR-0007' docs/backlog.yml` ≥ 1; `node scripts/check-backlog-governance.mjs` exit 0; `docs/BACKLOG.md` re-rendered | item(s) present with `evidence_checks` pointing at the new tests and docs | A | FAIL: no item mentions the repair, ADR-0007, 3.0.0 or any ledger row | PASS | RM-D-001 | T3 |
| HARNESS-GOV-002 | Registry status agrees with git history for Track E | for BL-004, BL-010, BL-011, BL-012, BL-013, BL-014 assert `status: "done"` with evidence checks | 6/6 | A | FAIL: all six are `ready` although AF-R03, R09, R10, R11, R12, R13 are in `git log` | PASS | RM-D-002 | T3 |
| HARNESS-GOV-003 | The ledger uses the staged status vocabulary and cites harness IDs; no row says `Verified` for uncommitted or un-CI'd work | `grep -c '\| Verified \|' docs/MUSICAL_CORRECTNESS.md` = 0; `grep -c 'HARNESS-' docs/MUSICAL_CORRECTNESS.md` ≥ 12 | both | A | FAIL: 12 rows read `Verified` on self-reported local evidence | PASS | RM-D-003 | T3 (statuses advance at each later checkpoint) |
| HARNESS-GOV-004 | ADR-0001 no longer states that randomness is rooted in the spec hash without pointing to ADR-0007 | `grep -c 'ADR-0007' docs/adr/0001-determinism-oracle.md` ≥ 1 | ≥ 1 | A | FAIL: ADR-0001 says "All randomness derives from per-component seeds rooted in the spec hash"; the code now roots it in `performance_hash(seed, variant)` | PASS | RM-D-004 | T2 |
| HARNESS-GOV-005 | The docs-site home page makes the same determinism claim as README and ADR-0007 | `grep -c 'every render, forever' docs/index.md` = 0 | 0 | A | FAIL: `docs/index.md:14` still promises "byte-identical audio, every render, forever" | PASS | RM-D-005 | T2 |
| HARNESS-GOV-006 | ADR-0007 status reflects delivery state: "Implemented" only when `HARNESS-VCS-004` and `HARNESS-CI-003` pass | if VCS-004 fails, `grep -c 'implemented' docs/adr/0007-musical-render-semantics.md` (status line) must be 0 | consistent | A | FAIL: status reads "Accepted and implemented" for uncommitted code | PASS | RM-D-004 | T2 (wording), T4 (final) |
| HARNESS-GOV-007 | The coordination pointer `.agent-tasks/.current_task` names an active task or is absent | `[ ! -f .agent-tasks/.current_task ] \|\| jq -e --arg t "$(cat .agent-tasks/.current_task)" 'any(.task_id==$t)' .agent-tasks/registry.json` | exit 0 | A | FAIL: points at `task-1783257140897-7b8a`, archived with status `failed` | PASS | RM-D-006 | T2 (non-blocking) |
| HARNESS-GOV-008 | Ledger evidence citations are accurate: every cited test file was changed by the repair or is labelled a pre-existing regression guard | diff the cited files against `git diff --stat` and the untracked list | 0 unlabelled pre-existing citations | M | PARTIAL: `tests/test_performance_model.py` is cited for M2, M3 and A2 but is unchanged (its five tests are regression guards, not new assertions) | PASS | RM-D-003 | T3 (non-blocking) |

### 3.10 CON — contract hardening

Failure meaning: agents must parse prose to learn what failed, or receive mutated input
back from a validation call; both violate PURPOSE.md ("failure should be loud and local",
"the contract must be inspectable") and `DSL_GAP_SPEC.md` §3.3.

| ID | Requirement | Procedure | Pass criteria | Mode | T0 | Target | Roadmap | Green by |
|---|---|---|---|---|---|---|---|---|
| HARNESS-CON-001 | Every diagnostic code the engine emits is in `capability_manifest()["diagnostic_codes"]` and therefore in `docs/DIAGNOSTIC_CODES.md` | python: assert `{ambiguous_harmony, unrecognized_harmony, loop_boundary_tail, render_plan_approximation, dead_air, mono_image, low_foundation_weak, very_bright}` ⊆ manifest codes | subset holds | A | FAIL: registry has 29 codes; `ambiguous_harmony`, `unrecognized_harmony`, `loop_boundary_tail` and all analysis codes are absent (`render_plan_approximation` is present) | PASS | RM-E-001 | T2 |
| HARNESS-CON-002 | `Diagnostic` carries a machine-readable `code`, exposed through `agent_tools` and MCP envelopes | python: `'code' in {f.name for f in dataclasses.fields(audioforge.sdk.Diagnostic)}`; `tests/test_mcp_contract.py` asserts the field | field present, envelope documented | A | FAIL: `Diagnostic(severity, message, path)`; codes are embedded in message text | PASS | RM-E-002 (ADR-0008) | T3 |
| HARNESS-CON-003 | `audioforge verify` given a non-JSON spec returns a structured diagnostic, not a raw decoder error | `python -m audioforge.cli verify tests/golden/audio/synth_voice.af <manifest>`; stderr must not contain `Expecting value` | criterion holds; documented exit code | A | FAIL: prints `Error: Expecting value: line 1 column 1 (char 0)`, exit 1 | PASS | RM-E-003 | T2 |
| HARNESS-CON-004 | `validate_spec` and `run_tool("validate", …)` do not mutate the caller's spec | python: deep-copy a spec with `score.repeats`, validate, compare | caller object unchanged (`==` to the copy) | A | FAIL: `validate_spec` returns the same object and rewrites it in place (duration 2.0 → 4.0, repeats consumed); `run_tool("validate")` mutates the caller's dict too | PASS | RM-E-004 | T2 |

### 3.11 PERF — performance

Preconditions: reference machine, otherwise scale thresholds by a documented factor.

| ID | Requirement | Procedure | Pass criteria | Mode | T0 | Target | Roadmap | Green by |
|---|---|---|---|---|---|---|---|---|
| HARNESS-PERF-001 | The composed gate stays inside a five-minute budget | wall time of `GATE-001` | ≤ 300 s | A | PASS: 156 s | PASS | RM-A-001 | every checkpoint |
| HARNESS-PERF-002 | The anti-alias resampler's cost is bounded and documented | render a 1 s note from a 2 s 48 kHz source at +0, +12, +24 semitones with `render_region`; `grep -Ei 'resampl.*(cost\|slower\|time)' docs/MIGRATION_3.md` | ≤ 130 ms at +12, ≤ 250 ms at +24 on the reference machine; migration guide states the cost curve | A | PARTIAL: measured 57 / 110 / 204 ms (engine 2.16.0: 41 / 42 / 41 ms, so up to 5× at two octaves up); the cost is undocumented | PASS | RM-E-005 | T5 |

### 3.12 MIG — migration and backward compatibility

| ID | Requirement | Procedure | Pass criteria | Mode | T0 | Target | Roadmap | Green by |
|---|---|---|---|---|---|---|---|---|
| HARNESS-MIG-001 | A 2.16.0 manifest verified by 3.0.0 fails loudly and non-zero, as ADR-0007 intends | render `synth_voice.af` in the baseline export, then `audioforge verify <2.16 ir.json> <2.16 manifest>` with the current engine | output `MISMATCH`, exit 2 | A | PASS | PASS | RM-F-011 | T2 |
| HARNESS-MIG-002 | Every `.af` in the repository compiles and renders under 3.0.0 without error diagnostics | compile `static/samples/*.af` and `tests/golden/audio/*.af`; `render_golden --check` | 0 errors | A | PASS (1 sample + 5 goldens) | PASS | RM-F-011 | T2 |
| HARNESS-MIG-003 | Structural IR migration flags that audio review is required | `migrate_ir_spec({'id':'x'}, '1.2')['_meta']['migration']` | `{'from': '1.2', 'to': '2.0', 'audio_review_required': True}` | A | PASS | PASS | RM-F-011 | T2 |

### 3.13 RB — rollback

| ID | Requirement | Procedure | Pass criteria | Mode | T0 | Target | Roadmap | Green by |
|---|---|---|---|---|---|---|---|---|
| HARNESS-RB-001 | A rollback anchor exists and is runnable: the previous release tag exports and renders the acceptance corpus with its documented behaviour | `git rev-parse engine-2.16.0`; `ACC-002` baseline leg | tag resolves; 7 baseline renders produced | A | PASS (`282756e`; baseline metrics recorded in §4) | PASS | RM-A-005 | T2 |
| HARNESS-RB-002 | Rollback rehearsal: the previous release's own gate passes in an isolated export with the current toolchain | `git archive engine-2.16.0 \| tar -x -C <dir>`; `cd <dir> && PATH=<shim with python3 → ref venv>:$PATH PYTHONPATH=$PWD sh scripts/run_tests.sh` (the tag predates the Makefile and its runner hardcodes `python3`; use `make check` for tags that have it); link the gitignored `libraries/` into the export first | exit 0 | A | PARTIAL: 395 passed, 2 failed, 2 skipped; both failures are `tests/test_catalog_freshness.py` asserting that gitignored `libraries/` exists; with `libraries/` linked one remains (`test_current_txt_matches_fresh_tree_snapshot`: the 2.16.0 test compares against `tree -a` without the `LC_ALL=C --charset=UTF-8` the repair later added, and `libraries/current.txt` is working-tree state, not tag state) | PASS | RM-A-005 | T5 |

### 3.14 OBS — observability and evidence

| ID | Requirement | Procedure | Pass criteria | Mode | T0 | Target | Roadmap | Green by |
|---|---|---|---|---|---|---|---|---|
| HARNESS-OBS-001 | Render manifests identify both the contract and the take | render a golden spec via CLI; read keys | contains `spec_hash`, `performance_hash`, `performance_seed`, `engine_version`, `output_sha256`, `plan_hash` | A | PASS | PASS | RM-F-009 | T2 |
| HARNESS-OBS-002 | Each checkpoint leaves a durable evidence bundle in the repository | `ls docs/evolution/evidence/<checkpoint>/summary.tsv`; `git ls-files docs/evolution/evidence/<checkpoint>` non-empty | both | A | PARTIAL: T0 evidence exists only in the session scratch directory; load-bearing lines are transcribed in §4 | PASS | RM-A-001, RM-A-002 | T1 |

### 3.15 SEC — security

| ID | Requirement | Procedure | Pass criteria | Mode | T0 | Target | Roadmap | Green by |
|---|---|---|---|---|---|---|---|---|
| HARNESS-SEC-001 | The test suite and the acceptance tool run without network access | `unshare -rn make test` (or an equivalent egress block) | exit 0 | A | BLOCKED: not executed at T0 (needs an isolation run; sample-catalog network paths are mocked in tests, but that is inferred, not proven) | PASS | RM-A-001 | T5 (non-blocking) |
| HARNESS-SEC-002 | No credentials in tracked files | `git grep -nE 'ghp_[A-Za-z0-9]{20,}\|AKIA[0-9A-Z]{16}\|-----BEGIN (RSA\|OPENSSH\|EC) PRIVATE KEY\|xox[baprs]-'` | 0 matches | A | PASS (0) | PASS | RM-A-001 | T1 |

## 4. Baseline run — T0

**Tree under test.** `main` at `60c0fd5637f75744250a82ec7d98e9f7d8f167e3` (= `origin/main`,
engine 2.16.0) plus the uncommitted repair: 45 modified files (+1 605 / −609), 12 untracked
(`audioforge/{arrangement,harmony,performance}.py`, `audioforge/tools/musical_acceptance.py`,
five test files, `docs/MIGRATION_3.md`, `docs/MUSICAL_CORRECTNESS.md`,
`docs/adr/0007-musical-render-semantics.md`), bumping to engine 3.0.0 / DSL 2.0 / IR 2.0.
Reference environment per §2.3. Date 2026-09-05.

### 4.1 Totals

| Count | Value |
|---|---|
| Total assertions | 59 |
| PASS | 30 (AUD 4, MUS 6, ACC 3, GATE 6, PORT 3, REL 1, PERF 1, MIG 3, RB 1, OBS 1, SEC 1) |
| FAIL | 24 (ACC-003, PORT-001, CI 4, VCS 4, REL 3, GOV 7, CON 4) |
| PARTIAL | 4 (GOV-008, PERF-002, OBS-002, RB-002) |
| BLOCKED | 1 (SEC-001) |
| N/A | 0 |
| Completed after the main run | 2 (PORT-002, RB-002; §4.4) |

Failures at T0 are not harness defects. Every FAIL row names the missing capability and the
roadmap item that supplies it.

### 4.2 Coverage by target capability

| Capability (report §Desired state) | Harness IDs | T0 |
|---|---|---|
| Audio semantics A1–A4 hold | AUD-001…004, ACC-001/002/004 | PASS |
| Musical semantics M1–M6 hold | MUS-001…006 | PASS |
| Surfaces agree (G1) | GATE-001…005, REL-001, MIG-001…003, OBS-001 | PASS |
| Listening evidence exists | ACC-003 | FAIL (human) |
| Portable to the declared interpreters | PORT-001…004 | FAIL (3.10), PASS (3.11, 3.12, cross-env) |
| CI executes and is green | CI-001…004 | FAIL |
| Committed, duplicated, reviewed, merged | VCS-001…004 | FAIL |
| Released and locked | REL-002…004 | FAIL |
| Governed and coherent records | GOV-001…008 | FAIL / PARTIAL |
| Structured, non-mutating contract | CON-001…004 | FAIL |
| Performance bounded and documented | PERF-001/002 | PASS / PARTIAL |
| Rollback proven | RB-001/002 | PASS / PARTIAL |
| Durable evidence | OBS-002 | PARTIAL |
| Offline and secret-free | SEC-001/002 | BLOCKED / PASS |

### 4.3 Load-bearing evidence lines (verbatim from the T0 logs)

```
make check (reference env)        : 884 passed, 2 skipped, 6 warnings in 95.77s ; total 2:35.83 ; MAKE_CHECK_EXIT=0
golden-check                      : all 5 golden specs reproduce byte-for-byte (env match: True)
coverage report                   : TOTAL 12035 1088 90.96% ; COVERAGE_EXIT=0
pytest --collect-only             : 886 tests collected ; new suites 25 + 21 + 17 + 1 + 3 = 67
musical_acceptance (current)      : {"passed": true, "cases": 7} ; 11.2 s ; listening_status not_reviewed
musical_acceptance (baseline)     : seventh [0,4,7,10,11]→FAIL | phrase gates_preserved=false | repeat 2.0 s | release last_active 0.4979 s | quiet Δ≈0 dB | alias interior_rms 0.007886 | sample_gain −12.0 dB  (7/7 FAIL on 2.16.0)
acceptance reproducibility        : identical current hashes across runs: True (7 cases)
verify (3.0 IR vs 3.0 manifest)   : REPRODUCIBLE ; exit 0
verify (2.16 IR vs 2.16 manifest) : MISMATCH — output drifted ; exit 2
verify (.af input)                : Error: Expecting value: line 1 column 1 (char 0) ; exit 1
mkdocs build --strict             : Documentation built in 0.25 seconds ; MKDOCS_EXIT=0
backlog governance                : backlog-governance: 31 item(s) verified
make check (Python 3.12.3)        : 884 passed, 2 skipped in 110.02s ; golden env match: False, 5/5 byte-for-byte ; EXIT=0 ; numpy 2.5.2 scipy 1.18.1
make check (Python 3.11.15)       : 884 passed, 2 skipped in 106.47s ; golden env match: False, 5/5 byte-for-byte ; EXIT=0 ; numpy 2.4.6 scipy 1.17.1
rollback gate (engine-2.16.0 export, scripts/run_tests.sh via python3 wrapper shim) : 2 failed, 395 passed, 2 skipped in 63.41s ; EXIT=1 ; both failures assert libraries/ exists ; with libraries/ linked: 1 failed (current.txt tree snapshot, locale/charset), 1 passed
make check (Python 3.10.20)       : ImportError: cannot import name 'UTC' from 'datetime' (audioforge/sample_catalog/licenses.py:6) ; make: *** [Makefile:41: manifest-check] Error 1 ; EXIT=2
gh run list                       : 7 runs 2026-07-04..07-05, all startup_failure, jobs total_count 0 ; workflows active ; YAML parses ; repo private
git                               : 45 M + 12 ?? ; HEAD 60c0fd5 == origin/main ; origin pushed_at 2026-07-05T13:06:27Z ; tags engine-2.16.0 dsl-1.9 @ 282756e
uv lock --check                   : The lockfile at `uv.lock` needs to be updated
resampler cost (1 s note, 48 kHz) : 2.16.0 → 40.9 / 41.8 / 41.1 ms ; 3.0.0 → 57.1 / 110.0 / 204.1 ms at +0 / +12 / +24 semitones
validate_spec mutation            : returned same object: True ; caller dict mutated: True (2.0→4.0 s) ; run_tool validate mutated caller: True
diagnostic registry               : 29 codes ; ambiguous_harmony 0 ; unrecognized_harmony 0 ; loop_boundary_tail 0 ; render_plan_approximation 1
```

### 4.4 Rows completed after the main run

| ID | Result | Detail |
|---|---|---|
| HARNESS-PORT-002 | PASS | Python 3.11.15, numpy 2.4.6, scipy 1.17.1: `make check` exit 0, 884 passed, 2 skipped, 1 min 46 s; goldens 5/5 byte-for-byte with `env match: False`. Together with PORT-003 (numpy 2.5.2) this shows the golden hashes are stable across Python 3.11–3.13 and two numpy/scipy generations on x86_64 Linux. |
| HARNESS-RB-002 | PARTIAL | `git archive engine-2.16.0` export, `scripts/run_tests.sh` with a `python3` wrapper to the reference venv (a symlink loses site-packages): 395 passed, 2 failed, 2 skipped, exit 1. Both failures are `tests/test_catalog_freshness.py` requiring the gitignored `libraries/` tree. With `libraries/` linked in, the catalog rescan passes and one failure remains: the 2.16.0 `current.txt` snapshot test runs `tree -a` without `LC_ALL=C --charset=UTF-8` (added by the repair) and compares against a working-tree file the tag does not own. Engine behaviour at 2.16.0 reproduces fully (all 16 script suites and the rest of pytest pass); the rollback runbook (`RM-A-005`) must state the fixture precondition and this known snapshot failure. |

## 5. Progress model — checkpoints T0…T6

Progress is reported on two axes and both must be shown together: **delivery progress**
(roadmap items complete under the five-part definition in §1) and **verified target-state
coverage** (share of the 59 assertions at `PASS`). A roadmap item cannot be marked complete
because code was written; its harness rows must be green in the evidence bundle for the
checkpoint.

| Checkpoint | Name | Must be PASS to leave the checkpoint | Expected to flip at this checkpoint | Roadmap milestone |
|---|---|---|---|---|
| T0 | Current-state baseline | — (recorded in §4) | — | M0 |
| T1 | Foundation | VCS-001, VCS-002, REL-004, PORT-001, OBS-002, GATE-006, SEC-002 | CI-001 diagnosed (root cause and owner recorded; PASS if the fix lands) | M1 |
| T2 | Core capabilities on the committed branch | AUD-001…004, MUS-001…006, ACC-001/002/004, GATE-001…005, PORT-002…004, MIG-001…003, RB-001, OBS-001, PERF-001, CON-001, CON-003, CON-004, GOV-004, GOV-005, GOV-006 (wording), GOV-007 | all functional rows re-run against a commit SHA rather than a dirty tree | M2 |
| T3 | Integration | CI-001, CI-002, CI-004, VCS-003, GOV-001, GOV-002, GOV-003, GOV-008, CON-002 | first remote job ever executed; review closed; registry knows the work | M3 |
| T4 | Migration (merge and consolidate) | VCS-004, CI-003, REL-002, GATE-001…005 re-run on `main` | ADR-0007 status may now say implemented | M4 |
| T5 | Hardening | ACC-003 (or a §6.3 waiver), PERF-002, RB-002, SEC-001 | human listening evidence; cost documented; rollback rehearsed | M5 |
| T6 | Desired state | REL-003, REL-001 on the tag, and every non-waived row PASS; final evidence bundle committed | release tags pushed | M6 |

Verified target-state coverage at T0: 30 / 59 PASS = 51 %, all of it in the code layer.
Delivery progress at T0: 0 of 37 roadmap items complete (11 are *implemented* and
independently reproduced, which the roadmap records as 70 % on the staged scale:
implemented 40, locally verified 60, independently reproduced 70, CI-verified 90,
released 100).

## 6. Quality gates

### 6.1 Gate definitions

| Gate | Opens checkpoint | Blocking rows | Rationale |
|---|---|---|---|
| Data-safety gate | T1 → T2 | VCS-001, VCS-002 | Nothing else is worth doing while the only copy of the repair is an uncommitted tree. |
| Portability gate | T1 → T2 | PORT-001 | The declared Python floor is a public contract (`requires-python`, CI matrix). |
| Contract gate | T2 → T3 | GATE-003…005, CON-001, CON-003, CON-004, GOV-004…006 | Generated artifacts, registries and ADRs must describe the code that ships. |
| Test gate | T2 → T3 and every later transition | GATE-001, GATE-002, AUD-*, MUS-*, ACC-001/002/004 | The composed gate and the correctness suites are the definition of "works". |
| Architecture gate | T3 → T4 | CON-002 with ADR-0008 accepted (or ADR-0008 accepted as an explicit deferral to 3.1 plus a §6.3 waiver), GOV-006 | A public-surface change (`Diagnostic.code`) ships with an ADR either way (AF-R12 adoption rule); the decision, not the code, is what the gate requires. |
| CI gate | T3 → T4 | CI-001, CI-002, CI-004 | Merge only on remote evidence, never on local logs. |
| Review gate | T3 → T4 | VCS-003 | The author verified their own work; an independent reader has not. |
| Migration gate | T4 → T5 | VCS-004, CI-003, REL-002, MIG-001…003 | `main` is the migration target; the changelog is the migration message. |
| Performance gate | T5 → T6 | PERF-001, PERF-002 | Bounded and documented, not merely "fast enough today". |
| Observability gate | every transition | OBS-002 | A checkpoint without a committed evidence bundle did not happen. |
| Security gate | T5 → T6 | SEC-002 blocking; SEC-001 non-blocking | Offline operation is a stated property; secrets in tree are a release stopper. |
| Release gate | T6 | REL-001, REL-003, ACC-003 or waiver, zero unexplained FAIL, zero open BLOCKED | Completion is demonstrated by the harness, not declared. |

### 6.2 Classification of failures

| Class | Rows | Effect |
|---|---|---|
| Blocking | every row not listed below | Gate stays closed. |
| Non-blocking | GOV-007, GOV-008, SEC-001 | Recorded; gate may open; must be PASS by T6 or waived. |
| Accepted temporarily | ACC-003 between T2 and T5 | The release may be prepared while a listener is scheduled; T5 requires PASS or an explicit waiver. |
| Explicitly waivable | ACC-003, SEC-001, PERF-002, CON-002 (only with ADR-0008 recording the deferral) | See §6.3. No other row may be waived. |

### 6.3 Waivers

A waiver is a row in `docs/evolution/evidence/waivers.tsv` with: harness ID, reason, owner
(a person, not a role), expiry condition (a checkpoint or a date), remediation roadmap
item. A waived row still counts as a failure in §4-style totals and is listed in the
release notes. Example that would be acceptable at T6 if no listener is available:

```
HARNESS-ACC-003	no listener with monitoring available before tag	Pedro Anisio Silva	expires at engine 3.1.0 tag	RM-A-003
```

## 7. Final harness state (definition of complete)

The transformation is complete when a single run of the runner (§8) against the tagged
release commit produces an evidence bundle in which:

1. every row in §3 is `PASS`, except rows carrying a live waiver per §6.3;
2. there are zero `FAIL` rows without a waiver and zero `BLOCKED` rows;
3. `GATE-002` reports ≥ 90.1 % and `PERF-001` ≤ 300 s;
4. `ACC-003` cites a `listening-review.json` whose `spec_hash`es match the acceptance
   manifest of the tagged commit (or a waiver exists);
5. `RB-002` shows the previous release's gate green in an isolated export, so a rollback
   is a `git checkout engine-2.16.0` away;
6. `REL-003` shows `engine-3.0.0` and `dsl-2.0` on `origin`, and `CI-003` shows the
   merge commit green on the three-interpreter matrix;
7. the roadmap workbook's `Status` column shows every item complete with an evidence path,
   and the ledger's `Status` column reads `released` with harness IDs on all 12 rows.

Until all seven hold, the honest sentence remains the one this file opened with: the code
is done, the release is not.

## 8. Runner

`RM-A-001` materialises this as `scripts/harness.sh`. It is deliberately plain shell: each
assertion is one command whose exit code is the verdict; heavy checks are skipped under
`HARNESS_QUICK=1`; interpreter venvs and the release SHA come from the environment.

```bash
#!/usr/bin/env bash
# scripts/harness.sh — run the automated assertions of docs/evolution/harness.md
# usage: scripts/harness.sh <checkpoint e.g. T1> [evidence-root]
# env:   PYTHON (default ./.venv/bin/python)  PY310 PY311 PY312 (matrix interpreters)
#        RELEASE_SHA (default HEAD)  HARNESS_QUICK=1 (skip long checks)
set -u
CP=${1:?checkpoint label}; EV=${2:-docs/evolution/evidence}/$CP; W="$EV/work"; mkdir -p "$W"   # work/ holds WAVs, exports, sites: gitignored
PY=${PYTHON:-./.venv/bin/python}; SHA=${RELEASE_SHA:-$(git rev-parse HEAD)}
SUM="$EV/summary.tsv"; printf 'id\tresult\tdescription\tseconds\tlog\n' > "$SUM"
{ echo "checkpoint=$CP"; echo "sha=$SHA"; echo "date=$(date -u +%FT%TZ)"; git status --porcelain | wc -l | sed 's/^/dirty_paths=/'; } > "$EV/context.txt"

run() { local id=$1 desc=$2; shift 2; local log="$EV/$id.log" t0=$SECONDS r
  if "$@" >"$log" 2>&1; then r=PASS; else r=FAIL; fi
  printf '%s\t%s\t%s\t%s\t%s\n' "$id" "$r" "$desc" "$((SECONDS-t0))" "$log" | tee -a "$SUM"; }
heavy() { if [ "${HARNESS_QUICK:-0}" = 1 ]; then printf '%s\tSKIPPED\t%s\t0\t-\n' "$1" "$2" | tee -a "$SUM"; else run "$@"; fi; }
manual() { printf '%s\tMANUAL\t%s\t0\t-\n' "$1" "$2" | tee -a "$SUM"; }
py() { "$PY" - "$@"; }   # read a python program from stdin

# --- AUD / MUS ------------------------------------------------------------
run HARNESS-AUD-001 "A1 gain once"            "$PY" -m pytest -q -p no:cacheprovider tests/test_audio_correctness.py -k gain_is_applied_once
run HARNESS-AUD-002 "A2 release at note-off"  "$PY" -m pytest -q -p no:cacheprovider tests/test_audio_correctness.py -k "release_starts_at_note_off or during_attack or sustain_loop_exits"
run HARNESS-AUD-003 "A3 anti-alias"           "$PY" -m pytest -q -p no:cacheprovider tests/test_audio_correctness.py -k "out_of_band or in_band_tone or aliases_during_glide"
run HARNESS-AUD-004 "A4 mastering"            "$PY" -m pytest -q -p no:cacheprovider tests/test_audio_correctness.py -k "preserves_absolute_level or explicit_request or normalization_dsl_roundtrip or intersample or does_not_skip_peak_safety"
run HARNESS-MUS-001 "M1 harmony"              "$PY" -m pytest -q -p no:cacheprovider tests/test_musical_correctness.py -k "chord_extensions or explicit_chord_quality or ambiguous_harmony or unknown_cluster or modulation or voice_leading_preserves or emotion_reports"
run HARNESS-MUS-002 "M2 phrase evidence"      "$PY" -m pytest -q -p no:cacheprovider tests/test_musical_correctness.py tests/test_ai_agent_dsl.py -k "fabricate or polyphonic_gates or coordinated or cadence_candidates or share_timing_motion or phrase or voicing_directive"
run HARNESS-MUS-003 "M3 technique fidelity"   "$PY" -m pytest -q -p no:cacheprovider tests/test_musical_correctness.py tests/test_render_plan.py tests/test_expressive_techniques_lowering.py tests/test_performance_model.py -k "technique_approximation or legato_requires or plan_authority_matches_performance_rng_stream or lower_technique or legato or section or phrasing or slur"
run HARNESS-MUS-004 "M4 arrangement + loops"  "$PY" -m pytest -q -p no:cacheprovider tests/test_arrangement_correctness.py tests/test_audio_correctness.py -k "repeat or clip or meter or curve or event_ids or loop_safe or loop_check or render_ready_validation"
run HARNESS-MUS-005 "M5 performance identity" "$PY" -m pytest -q -p no:cacheprovider tests/test_audio_correctness.py tests/test_musical_correctness.py tests/test_arrangement_correctness.py -k "mix_edits_preserve or explicit_performance_seed or inserting_an_earlier_note or uint64_seed or event_ids_unique"
run HARNESS-MUS-006 "M6 analysis context"     "$PY" -m pytest -q -p no:cacheprovider tests/test_musical_correctness.py tests/test_ai_agent_dsl.py -k "analysis_observations or authored_rests or analysis_returns_actionable"

# --- ACC ------------------------------------------------------------------
heavy HARNESS-ACC-001 "acceptance cases pass"  "$PY" -m audioforge.tools.musical_acceptance --out "$W/acceptance"
[ -f "$W/acceptance/manifest.json" ] && cp "$W/acceptance/manifest.json" "$EV/acceptance-manifest.json"
acc002() { local b="$W/baseline-2.16.0"; mkdir -p "$b" && git archive engine-2.16.0 | tar -x -C "$b" \
  && "$PY" -m audioforge.tools.musical_acceptance --out "$W/acceptance_ab" --baseline-root "$b" >/dev/null \
  && py "$W/acceptance_ab/manifest.json" <<'PYEOF'
import json,sys; m=json.load(open(sys.argv[1])); c=m["cases"]
ok=all(not x["revisions"]["baseline"]["passed"] and x["revisions"]["current"]["passed"] for x in c)
print({x["id"]:(x["revisions"]["baseline"]["passed"],x["revisions"]["current"]["passed"]) for x in c}); sys.exit(0 if ok and len(c)==7 else 1)
PYEOF
}
heavy HARNESS-ACC-002 "baseline fails, current passes" acc002
manual HARNESS-ACC-003 "listening review recorded (see harness.md 3.3)"
acc004() { "$PY" -m audioforge.tools.musical_acceptance --out "$W/acceptance_b" >/dev/null && py "$W/acceptance/manifest.json" "$W/acceptance_b/manifest.json" <<'PYEOF'
import json,sys; a,b=[json.load(open(p)) for p in sys.argv[1:3]]
h=lambda m:{c["id"]:c["revisions"]["current"]["output_sha256"] for c in m["cases"]}; sys.exit(0 if h(a)==h(b) else 1)
PYEOF
}
heavy HARNESS-ACC-004 "acceptance bundle reproducible" acc004

# --- GATE -----------------------------------------------------------------
heavy HARNESS-GATE-001 "make check"            timeout 300 make check PYTHON="$PY"
heavy HARNESS-GATE-002 "coverage >= 90.1"      bash -c "$PY -m coverage run -m pytest -q -p no:cacheprovider && $PY -m coverage report"
run   HARNESS-GATE-003 "golden strict same-env" "$PY" -m audioforge.tools.render_golden --check
heavy HARNESS-GATE-004 "mkdocs strict"          uv run --with mkdocs-material mkdocs build --strict --site-dir "$W/site"
run   HARNESS-GATE-005 "backlog governance"     node scripts/check-backlog-governance.mjs
run   HARNESS-GATE-006 "git diff --check"       git diff --check

# --- PORT -----------------------------------------------------------------
for v in 310 311 312; do var=PY$v; if [ -n "${!var:-}" ]; then heavy HARNESS-PORT-00$(( v==310?1:(v==311?2:3) )) "make check py3.${v#3}" make check PYTHON="${!var}"; else printf 'HARNESS-PORT-00%s\tBLOCKED\tno %s interpreter\t0\t-\n' "$(( v==310?1:(v==311?2:3) ))" "$var" | tee -a "$SUM"; fi; done
if ls "$EV"/HARNESS-PORT-00*.log >/dev/null 2>&1; then run HARNESS-PORT-004 "cross-env golden advisory" bash -c "grep -h 'golden-check' $EV/HARNESS-PORT-00*.log | grep -q 'reproduce byte-for-byte'"; else printf 'HARNESS-PORT-004\tSKIPPED\tcross-env golden advisory (no PORT logs)\t0\t-\n' | tee -a "$SUM"; fi

# --- CI -------------------------------------------------------------------
ci001() { local id; id=$(gh run list -L 1 --json databaseId --jq '.[0].databaseId') && [ "$(gh api "repos/{owner}/{repo}/actions/runs/$id/jobs" --jq .total_count)" -ge 1 ]; }
run HARNESS-CI-001 "a CI job executed" ci001
run HARNESS-CI-002 "ci green on branch head" bash -c "gh run list --workflow ci --branch \"\$(git branch --show-current)\" -L 1 --json conclusion,headSha --jq '.[0] | select(.conclusion==\"success\" and .headSha==\"$SHA\")' | grep -q success"
run HARNESS-CI-003 "ci green on main"        bash -c "gh run list --workflow ci --branch main -L 1 --json conclusion --jq '.[0].conclusion' | grep -qx success"
run HARNESS-CI-004 "backlog-governance green" bash -c "gh run list --workflow backlog-governance -L 1 --json conclusion --jq '.[0].conclusion' | grep -qx success"

# --- VCS / REL ------------------------------------------------------------
run HARNESS-VCS-001 "tree clean"             bash -c 'test -z "$(git status --porcelain)"'
run HARNESS-VCS-002 "branch pushed == local" bash -c 'test -z "$(git status --porcelain)" && git fetch -q origin && test "$(git rev-parse HEAD)" = "$(git rev-parse origin/$(git branch --show-current))"'
run HARNESS-VCS-003 "PR approved"            bash -c 'gh pr view --json reviews --jq ".reviews[].state" | grep -q APPROVED'
run HARNESS-VCS-004 "merged into origin/main" bash -c "test -z \"\$(git status --porcelain)\" && git merge-base --is-ancestor $SHA origin/main"
run HARNESS-REL-001 "version literals"       "$PY" -m audioforge.tools.bump_version --check
run HARNESS-REL-002 "changelog consolidated" bash -c "! awk '/^## \[Unreleased\]/,/^## \[3.0.0\]/' CHANGELOG.md | grep -q 'Track E' && grep -Eq '^## \[3.0.0\] - 20[0-9]{2}-' CHANGELOG.md"
run HARNESS-REL-003 "release tags on origin" bash -c "test \"\$(git ls-remote --tags origin | grep -cE 'refs/tags/(engine-3\.0\.0|dsl-2\.0)$')\" = 2 && git merge-base --is-ancestor engine-3.0.0 origin/main"
run HARNESS-REL-004 "uv lock in sync"        uv lock --check

# --- GOV ------------------------------------------------------------------
run HARNESS-GOV-001 "backlog knows the repair" bash -c "grep -q 'ADR-0007' docs/backlog.yml && node scripts/check-backlog-governance.mjs >/dev/null"
run HARNESS-GOV-002 "Track E statuses done"    py <<'PYEOF'
import re,sys; y=open("docs/backlog.yml").read(); bad=[]
for i in ("BL-004","BL-010","BL-011","BL-012","BL-013","BL-014"):
    m=re.search(rf"id: {i}\n(.*?)(?=\n  - id: |\Z)", y, re.S); st=re.search(r'status: "(\w[\w-]*)"', m.group(1)).group(1) if m else "missing"
    if st!="done": bad.append((i,st))
print(bad); sys.exit(1 if bad else 0)
PYEOF
run HARNESS-GOV-003 "ledger vocabulary + harness ids" bash -c "! grep -q '| Verified |' docs/MUSICAL_CORRECTNESS.md && test \"\$(grep -c 'HARNESS-' docs/MUSICAL_CORRECTNESS.md)\" -ge 12"
run HARNESS-GOV-004 "ADR-0001 points to ADR-0007"  grep -q 'ADR-0007' docs/adr/0001-determinism-oracle.md
run HARNESS-GOV-005 "index.md claim corrected"     bash -c "! grep -q 'every render, forever' docs/index.md"
run HARNESS-GOV-006 "ADR-0007 status honest"       bash -c "(test -z \"\$(git status --porcelain)\" && git merge-base --is-ancestor $SHA origin/main 2>/dev/null) || ! grep -Eiq 'Status:\*\* .*implemented' docs/adr/0007-musical-render-semantics.md"
run HARNESS-GOV-007 "agent-task pointer valid"     bash -c '[ ! -f .agent-tasks/.current_task ] || jq -e --arg t "$(cat .agent-tasks/.current_task)" "any(.task_id==\$t)" .agent-tasks/registry.json >/dev/null'
manual HARNESS-GOV-008 "ledger citations accurate (see harness.md 3.9)"

# --- CON ------------------------------------------------------------------
run HARNESS-CON-001 "emitted codes registered" py <<'PYEOF'
import sys; from audioforge.capabilities import capability_manifest
codes=set(capability_manifest()["diagnostic_codes"]); need={"ambiguous_harmony","unrecognized_harmony","loop_boundary_tail","render_plan_approximation","dead_air","mono_image","low_foundation_weak","very_bright"}
print("missing:", sorted(need-codes)); sys.exit(0 if need<=codes else 1)
PYEOF
run HARNESS-CON-002 "Diagnostic has code field" py <<'PYEOF'
import dataclasses,sys; from audioforge.sdk import Diagnostic; f={x.name for x in dataclasses.fields(Diagnostic)}; print(f); sys.exit(0 if "code" in f else 1)
PYEOF
run HARNESS-CON-003 "verify .af gives structured error" bash -c "! ($PY -m audioforge.cli verify tests/golden/audio/synth_voice.af /dev/null 2>&1 | grep -q 'Expecting value')"
run HARNESS-CON-004 "validate does not mutate caller" py <<'PYEOF'
import copy,sys; from audioforge.schema import validate_spec; from audioforge.agent_tools import run_tool
raw={"id":"r","kind":"cue","duration_s":2.0,"sample_rate":48000,"bpm":120,"score":{"sections":[{"name":"verse","start_beat":0,"dur_beats":4}],"repeats":[{"section":"verse","count":2}]},"layers":[{"name":"m","type":"notes","osc":"sine","notes":[{"note":"C4","start_beat":0,"dur_beats":0.5}]}],"master":{"target_peak_dbfs":-1}}
a=copy.deepcopy(raw); validate_spec(a); b=copy.deepcopy(raw); run_tool("validate",{"spec":b})
print("validate_spec mutated:", a!=raw, "run_tool mutated:", b!=raw); sys.exit(0 if a==raw and b==raw else 1)
PYEOF

# --- PERF / MIG / RB / OBS / SEC -------------------------------------------
if grep -q $'^HARNESS-GATE-001\tSKIPPED' "$SUM"; then printf 'HARNESS-PERF-001\tSKIPPED\tmake check <= 300 s\t0\t-\n' | tee -a "$SUM"; else run HARNESS-PERF-001 "make check <= 300 s" bash -c "awk -F'\t' '\$1==\"HARNESS-GATE-001\"{exit !(\$2==\"PASS\" && \$4<=300)}' $SUM"; fi
run HARNESS-PERF-002 "resampler cost bounded + documented" bash -c "$PY - <<'PYEOF' && grep -Eiq 'resampl.*(cost|slower|time)' docs/MIGRATION_3.md
import time,sys,numpy as np; from audioforge.sampler import Region,render_region
SR=48000; src=np.sin(2*np.pi*440*np.arange(SR*2)/SR); out={}
for s,lim in ((12,.130),(24,.250)):
    r=Region(pitch_keycenter=60,ampeg_attack=.001,ampeg_release=.1); best=min((lambda t0:(render_region(r,src,SR,60+s,SR,SR),time.perf_counter()-t0)[1])(time.perf_counter()) for _ in range(3)); out[s]=(best,lim)
print(out); sys.exit(0 if all(b<=l for b,l in out.values()) else 1)
PYEOF"
mig001() { local b="$W/baseline-2.16.0"; [ -d "$b" ] || { mkdir -p "$b" && git archive engine-2.16.0 | tar -x -C "$b"; }
  (cd "$b" && PYTHONPATH="$b" "$PY" -m audioforge.cli render tests/golden/audio/synth_voice.af -o "$W/mig" >/dev/null && PYTHONPATH="$b" "$PY" -m audioforge.cli compile tests/golden/audio/synth_voice.af > "$W/mig/legacy.ir.json")
  "$PY" -m audioforge.cli verify "$W/mig/legacy.ir.json" "$W/mig/synth_voice.manifest.json"; [ $? -eq 2 ]; }
heavy HARNESS-MIG-001 "legacy manifest -> MISMATCH exit 2" mig001
run   HARNESS-MIG-002 "repo .af specs compile+render" py <<'PYEOF'
import sys; from pathlib import Path; from audioforge import AudioForge
bad=[p.name for p in list(Path("static/samples").glob("*.af"))+list(Path("tests/golden/audio").glob("*.af")) if not AudioForge().compile(p.read_text()).ok]
print("failed:", bad); sys.exit(1 if bad else 0)
PYEOF
run   HARNESS-MIG-003 "migration flags audio review" py <<'PYEOF'
import sys; from audioforge.ir_schema import migrate_ir_spec; m=migrate_ir_spec({"id":"x"},"1.2")["_meta"]["migration"]; print(m); sys.exit(0 if m.get("audio_review_required") is True and m.get("to")=="2.0" else 1)
PYEOF
run   HARNESS-RB-001 "rollback anchor resolves"  git rev-parse --verify engine-2.16.0
rb002() { local d="$W/rollback-2.16.0" p shim="$W/shim"; p="$(readlink -f "$PY")"; mkdir -p "$d" "$shim"
  printf '#!/bin/sh\nexec %s "$@"\n' "$p" > "$shim/python3"; cp "$shim/python3" "$shim/python"; chmod +x "$shim/python3" "$shim/python"  # wrapper, not symlink: a venv python reached via an outside symlink loses its site-packages
  git archive engine-2.16.0 | tar -x -C "$d" && ln -sfn "$PWD/libraries" "$d/libraries" && (cd "$d" && export PATH="$shim:$PATH" PYTHONPATH="$d" PYTHON="$p"
  if [ -f Makefile ]; then make check PYTHON="$p"; else sh scripts/run_tests.sh; fi); }  # 2.16.0 predates the Makefile and its runner hardcodes python3
heavy HARNESS-RB-002 "previous release gate green in export" rb002
run   HARNESS-OBS-001 "manifest carries identities" bash -c "$PY -m audioforge.cli render tests/golden/audio/synth_voice.af -o $W/obs >/dev/null && $PY -c \"import json,sys; m=json.load(open('$W/obs/synth_voice.manifest.json')); need={'spec_hash','performance_hash','performance_seed','engine_version','output_sha256','plan_hash'}; print(sorted(need-set(m))); sys.exit(0 if need<=set(m) else 1)\""
run   HARNESS-OBS-002 "evidence bundle tracked"     bash -c "test -s $SUM && git ls-files --error-unmatch docs/evolution/evidence >/dev/null 2>&1"
if command -v unshare >/dev/null && unshare -rn true 2>/dev/null; then heavy HARNESS-SEC-001 "suite offline" unshare -rn make test PYTHON="$PY"; else printf 'HARNESS-SEC-001\tBLOCKED\tno unprivileged network namespace\t0\t-\n' | tee -a "$SUM"; fi
run   HARNESS-SEC-002 "no secrets tracked"          bash -c "test \"\$(git grep -nE 'ghp_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|-----BEGIN (RSA|OPENSSH|EC) PRIVATE KEY|xox[baprs]-' -- . ':!uv.lock' | wc -l)\" = 0"

echo; awk -F'\t' 'NR>1{n[$2]++} END{for(k in n) printf "%s=%d ", k, n[k]; print ""}' "$SUM"
```

Reading the summary: `PASS`/`FAIL` are verdicts; `SKIPPED` means `HARNESS_QUICK=1` was set
and the row must be re-run before a gate decision; `MANUAL` rows are completed by a person
who appends a `PASS`/`FAIL` line with the evidence path; `BLOCKED` names the missing
precondition. The T0 values in §3 and §4 were obtained by running these same commands by
hand in the reference environment before the script existed.
