---
disclaimer:
  notice: >-
    No information within this document should be taken for granted. Claims
    require the implementation and verification evidence recorded below.
  generated_by: "GPT-6 via Codex; revised by Claude Opus 5.5 via Claude Code"
  date: "2026-09-28"
---

# Audio and music correctness acceptance ledger

The objective is to fix **all** findings from the September 5 codebase review.
Passing a subset does not close this work. `docs/goal.md` governs a separate
sample-catalog effort and is not replaced by this ledger.

## Status vocabulary

Statuses advance only from evidence bundles under `docs/evolution/evidence/<checkpoint>/`
produced by `scripts/harness.sh`; the assertion IDs (`HARNESS-…`) are defined in
[docs/evolution/harness.md](evolution/harness.md).

| Status | Meaning |
|---|---|
| `implemented` | Code and tests exist in a working tree. |
| `locally-verified` | The author's own gate run passed. |
| `independently-reproduced` | A second run, from a clean checkout or export, reproduced the claim (T0, 2026-09-05). |
| `ci-verified` | The `ci` workflow is green for the commit on Python 3.10/3.11/3.12 (`HARNESS-CI-002/003`). |
| `released` | The commit is tagged `engine-3.0.0` / `dsl-2.0` on origin (`HARNESS-REL-003`). |

No row may read `released` while `HARNESS-VCS-004` or `HARNESS-CI-003` fail, and no
row may read `ci-verified` on the strength of a local run.

## Requirements and completion evidence

| ID | Required behavior | Evidence required | Status |
|---|---|---|---|
| M1 | Recognize chord roots and quality across inversions; preserve existing sevenths and avoid ungrounded added notes. Emotion controls must expose their actual musical/production effects and limitations. | HARNESS-MUS-001; `tests/test_musical_correctness.py`: inversion/quality, existing sevenths, ambiguous harmony, modulation, voice-leading invariants and explicit emotion scope. | independently-reproduced |
| M2 | Phrase and performance decisions use authored structure, meter, harmonic context and coordinated timing; cadence and peak labels must not be fabricated from list position/pitch alone. | HARNESS-MUS-002; `tests/test_musical_correctness.py`, `tests/test_ai_agent_dsl.py`, `tests/test_performance_model.py`: authored gates/slurs, evidence-based cadence candidates, conductor rubato and correlated part timing. (`tests/test_performance_model.py` is a pre-existing regression guard, unchanged by the repair) | independently-reproduced |
| M3 | Instrument techniques resolve to actual supported behavior, with explicit approximate routes and rejection when fidelity is required; legato and section controls must not silently imply physical realism. | HARNESS-MUS-003; `tests/test_performance_model.py`, `tests/test_expressive_techniques_lowering.py`, `tests/test_render_plan.py`: acoustic transitions, partial tuning, every section player and strict fidelity routing. (`tests/test_performance_model.py` is a pre-existing regression guard, unchanged by the repair) | independently-reproduced |
| M4 | Repeats execute in the render contract; meter/polymeter/pickup have defined operational or notation semantics. Loop safety checks actual boundaries and tails. | HARNESS-MUS-004; `tests/test_arrangement_correctness.py`, `tests/test_audio_correctness.py`: repeated notes/continuous sounds, continuation, tempo/holds, shaped/offset controls, terminal fermatas, unique IDs, meter phase and measured seams. | independently-reproduced |
| M5 | Editing gain, pan, metadata, or another part preserves unrelated performance randomness; explicit seed/variation changes are reproducible. | HARNESS-MUS-005; `tests/test_audio_correctness.py`, `tests/test_render_plan.py`, `tests/test_musical_correctness.py`: unchanged unrelated stems under edits/reordering/insertion, reproducible seeds and planner/runtime sample parity. | independently-reproduced |
| M6 | Analysis respects declared intent and evaluates musical behavior separately from reproducibility. | HARNESS-MUS-006, HARNESS-ACC-001/002/004; `tests/test_musical_correctness.py`, `tests/test_musical_acceptance.py`: context-aware recommendations, authored rests, all seven numerical acceptance cases, embedded WAV hashes and an unreviewed listening form. | independently-reproduced |
| A1 | Instrument gain is applied exactly once, including sections. | HARNESS-AUD-001, HARNESS-ACC-001; `tests/test_audio_correctness.py`: real pinned sample stems change exactly -6 dB for a -6 dB edit, including sections. | independently-reproduced |
| A2 | Note duration denotes gate time; release follows note-off for synths and samples, including short notes and transitions. | HARNESS-AUD-002; `tests/test_audio_correctness.py`, `tests/test_performance_model.py`: post-gate releases, early note-off and recorded sustain-loop exits. (`tests/test_performance_model.py` is a pre-existing regression guard, unchanged by the repair) | independently-reproduced |
| A3 | Sample transposition/rate conversion suppresses aliasing while preserving in-band pitch and amplitude. | HARNESS-AUD-003; `tests/test_audio_correctness.py`, `tests/test_sampler.py`: in-band pitch/level, octave/fractional/rate-conversion alias rejection and variable-rate glide. | independently-reproduced |
| A4 | Default mastering preserves deliberate quiet levels; normalization is explicit and peak safety remains enforced. | HARNESS-AUD-004; `tests/test_audio_correctness.py`, `tests/test_dynamics.py`, `tests/test_sdk_edges.py`: quiet-level preservation, explicit normalization, LUFS, intersample ceiling and final fades. | independently-reproduced |
| G1 | Public contracts, SDK, CLI/MCP, generated schema/capabilities/docs, examples, versions and golden audio agree with the final behavior. | HARNESS-GATE-001…005, HARNESS-REL-001, HARNESS-MIG-001…003; `make check` with coverage on the pytest phase: generated schema/capabilities/docs, five exact golden renders, registry/version checks, 16 script suites and the full pytest suite. ADR-0007 and migration guide delivered. | independently-reproduced |
| L1 | A human listening review of the seven acceptance cases is recorded and cited here; `listening_status` is no longer `not_reviewed`. | HARNESS-ACC-003; `docs/evolution/evidence/<checkpoint>/listening-review.json` (schema `audioforge.listening-review/1`) with 7 judgments, the reviewed commit SHA and acceptance `spec_hash`es. | not-started |

> **Engine 3.2.0 note (2026-09-28).** The golden hashes behind G1 and the records
> below were produced by engine 3.0/3.1. Engine 3.2.0 re-pinned all five golden specs
> after bounded numeric drift (at most −131 dBFS over the example corpus; see
> "Engine 3.2: render cost and numeric drift" in [MIGRATION_3.md](MIGRATION_3.md) and
> [ADR-0012](adr/0012-native-dsp-kernels-bounded-drift.md)). The records remain dated
> evidence of what was reproduced then; `make golden-check` is today's gate.

## Verification discipline

Each behavioral fix starts with a failing regression that reaches the relevant
public boundary or measures actual audio. Run focused and adjacent tests after
each change. Golden hashes establish reproducibility, not musical merit.
Listening results may only be reported if a listener actually provided them.
Automated acceptance cases and review artifacts must remain useful without
inventing subjective ratings or requiring network resources.

## Execution order

1. Correct gain, note lifecycle, resampling and mastering.
2. Separate performance identity from render identity and verify planner parity.
3. Execute arrangement semantics and correct harmony/phrase/performance rules.
4. Enforce instrument technique fidelity and contextual quality feedback.
5. Deliver the musical acceptance/listening corpus and synchronize all surfaces.
6. Run the composed gate and audit every row against fresh evidence.

## Verification record (2026-09-05, author's local run)

- Final composed gate: **881 passed, 2 skipped, 6 warnings in 152.37s (0:02:32)**. All 16 script suites also passed, and all five golden specs reproduced byte-for-byte in the matching numerical environment.
- Coverage: **90.96%**, above the repository's 90.1% statement threshold. Coverage was collected on the pytest phase through a temporary interpreter wrapper; the same `make check` targets and script runner executed. No gate was removed or weakened.
- The two optional corpus skips are retained; no missing external library or cinematic example is claimed as verified. Six score-PDF warnings concern missing Noto Music glyphs for `l` and `p`; audio regressions passed.
- `git diff --check` passed. Evidence is local; this work does not claim a commit, publication, or remote CI run.
- Reproduce coverage with `coverage run -m pytest -q && coverage report`. Reproduce the numerical/listening bundle with the command in [MIGRATION_3.md](MIGRATION_3.md).

## Independent reproduction (2026-09-05, T0)

A second agent reproduced the claims above from a clean `git archive` export of
commit `60c0fd5` (engine 2.16.0) against the working tree: `make check` 884 passed;
coverage 90.96 %; all seven acceptance cases fail on 2.16.0 and pass on 3.0.0; the
five goldens reproduce byte-for-byte under Python 3.11, 3.12 and 3.13. Logs:
`docs/evolution/evidence/T0/`. The same run found the delivery gaps recorded in
[docs/evolution/report.md](evolution/report.md): no commit, no CI execution, Python
3.10 import failure, unregistered diagnostic codes, mutating validation.

## Before/after numerical acceptance

The comparison used engine 2.16.0 from baseline commit
`60c0fd5637f75744250a82ec7d98e9f7d8f167e3` and the corrected engine 3.0.0.
All seven current cases pass; all seven baseline cases expose their targeted
failure. The generated manifest records the per-render spec/output hashes.

| Case | Baseline | Corrected |
|---|---|---|
| Authored C major seventh | Adds B-flat to C/E/G/B | Preserves C/E/G/B |
| Phrase gates/slurs | Changes authored gates/groups | Preserves the authored gates and unslurred chord voices |
| Verse repeated twice, then ending | 2 seconds; repeat inert | 3 seconds; continuation follows both passes |
| 0.5 s gate + 0.2 s release | Last measured activity 0.498 s | Last measured activity 0.697 s |
| Layer raised by 20 dB below ceiling | Output change approximately 0 dB | Output change 20 dB |
| 18 kHz sample up an octave | Interior stem RMS 0.007886 | Interior stem RMS 0.0000002292 |
| Instrument gain lowered by 6 dB | Stem changes -12 dB | Stem changes -6 dB |

The standalone review page and JSON manifest were generated under
`/tmp/audioforge-musical-review/`. WAVs are embedded in the HTML and remain
outside Git. **Listening status: not reviewed.** Numerical correctness and
reproducibility are verified; no subjective musical-merit or realism rating is
claimed. Approximate techniques, stationary-sample legato and multiplied sections
remain explicitly labelled and are rejected by strict routing.
