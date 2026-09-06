---
disclaimer:
  notice: >-
    No information within this document should be taken for granted.
    Any statement or premise not backed by a real logical definition
    or verifiable reference may be invalid, erroneous, or a hallucination.
  generated_by: "Claude Fable 5.1 via Claude Code"
  date: "2026-09-06"
---

# Evolution and Verification Harness — notation, interchange and musical analysis

Companion artifacts: [report-notation.md](report-notation.md) (analysis) and
[roadmap-notation.xlsx](roadmap-notation.xlsx) (backlog). Shared ID space: roadmap items
`RN-<ws>-<nnn>`, assertions `HARNESS-N<CAT>-<nnn>`, checkpoints `T0`…`T6`, report requirements
`NREQ-n`. The release harness ([harness.md](harness.md)) governs engine 3.0.0; this one governs
the notation surface that ships afterwards (decision D2: engine 3.1.0 / DSL 2.1). Result
vocabulary (`PASS`, `PARTIAL`, `FAIL`, `BLOCKED`, `N/A`, `WAIVED`) is the one defined in
harness.md §1.

## 0. What the baseline says in one paragraph

Measured on 2026-09-06 against branch `release/engine-3.0.0` (`16b2cc2`) with external oracles
built for the purpose (music21 10.5.0, LilyPond 2.25.12, the MusicXML 3.1 XSD): the harness has
53 assertions, 12 pass, 4 are partial, 36 fail, 1 is blocked. What passes is real and worth
keeping: the notated MusicXML projection is XSD-valid, music21 reads it (18 parts, 116 measures,
2 820 note objects for the largest local piece), and LilyPond engraves it with zero warnings in
three seconds; chord identification agrees with music21 on every non-symmetric quality; the
multi-track MIDI importer keeps parts. What fails is the rest of "interchange": the notated
exporter hard-codes the beat unit (7/8 exports as 7/4), drops key and tempo changes, dynamics,
slurs, pickup and holds; the exact-tick MusicXML exporter serializes chord tones in sequence; the
MIDI exporter flattens 18 layers into one channel and loses half the notes; the MusicXML importer
flattens four Bach voices into a 92-second monody; the `tuning:` directive is accepted and
silently ignored; and no oracle is part of the toolchain. The starting analysis is right that
music21 and LilyPond are far ahead; the measured position is that AudioForge can already hand
them a valid score, and the work is to make that hand-off faithful and honest, not to compete.

## 1. Core principle

Same as harness.md §1: a roadmap item is complete only when implementation exists, its harness
rows execute, they pass, the named evidence is stored, and the milestone gate accepts it.
Three additions specific to this surface:

- **Oracles decide, not self-assessment.** Interchange claims are judged by the tools the
  surface interoperates with: the MusicXML 3.1 XSD (validity), music21 (structural parity),
  LilyPond (engravability with zero warnings). A row that only checks our own output against
  our own reader is not evidence of interchange.
- **Lossy is acceptable, silent is not.** Every construct of the score and notation layers
  has a declared projection per format: preserved, quantized, lossy with a registered
  diagnostic code, or unsupported with a code. Silence on a dropped construct is a FAIL.
- **Position is stated.** Deep musicology and engraving are delegated (ADR-0011); the harness
  never asserts that AudioForge analyses or engraves better than the oracles, only that what it
  claims is true.

## 2. Harness architecture

### 2.1 Layers and oracles

| Layer | Proves | Tools | Runs |
|---|---|---|---|
| L0 Contract | Manifest, INTEROP matrix, README, ADR describe the surface exactly; registries have `--check` twins | `make manifest-check docs-gen-check`, the new `interop.coverage()` matrix check, `grep` | local, CI |
| L1 Projection | Exporters emit the declared MusicXML/MIDI for each construct; importer reconstructs parts, chords, attribute changes | `pytest` on `tests/test_interop.py` + new `tests/test_notation_oracles.py` | local, CI |
| L2 Oracle | XSD validity; music21 structural parity (parts, measures, time and key signatures, pitch multisets, durations, tempo marks); LilyPond zero-warning engraving; music21 chord roots | `xmlschema` + vendored XSD; `music21.converter`; `musicxml2ly` + `lilypond` from the `lilypond` wheel | local with the `oracles` extra; CI oracle job |
| L3 Render truth | The tuning directive drives frequencies (FFT); 12-TET default byte-identical | `pytest`, `numpy.fft`, `render_golden --check` | local, CI |
| L4 Human | None required by this harness: engraving quality is LilyPond's, musicology is music21's; the proof sheet is labelled, not judged | — | — |

### 2.2 Categories

`NORA` oracle toolchain · `NXML` notated MusicXML export · `NIMP` MusicXML import · `NMIDI`
MIDI export/import · `NTUN` tuning directive · `NANA` analysis honesty and parity · `NENG`
proof sheet and engraving · `NDOC` contract and documentation · `NGATE` fixtures, gate and
evidence · `NPERF` budgets · `NSEM` semantic score/notation fields. Security, permissions,
deployment and rollback have no surface-specific rows: the release harness owns them, and this
work adds no credentials, network paths or deploy steps (the oracles are a dev extra).

### 2.3 Execution environments

| Name | Definition | Used by |
|---|---|---|
| Reference | `./.venv` Python 3.13.12 on the reference machine; Noto Music font present | L0, L1, L3 |
| Oracle venv | `uv venv <dir> --python 3.12 && uv pip install music21 lilypond xmlschema`; becomes `uv pip install -e '.[oracles]'` after `RN-O-001` | L2 (T0 used a scratch venv built by hand) |
| LilyPond | `lilypond` PyPI wheel 2.25.12 (`lilypond.executable()`); tools `musicxml2ly`, `lilypond` | `NENG-001`, `NENG-002`, `NPERF-002` |
| XSD | `musicxml.xsd`, `xml.xsd`, `xlink.xsd` from `w3c/musicxml` tag `v3.1`; vendored under `tests/fixtures/musicxml/xsd/` by `RN-O-001` | `NXML-001` |
| GitHub Actions | oracle job (`RN-O-004`), blocked by the same startup failure as the release harness | `NORA-004` |

### 2.4 Fixtures and test data

- **Fixture corpus** `tests/fixtures/notation/*.af` (`RN-O-002`, ≥ 8 specs) with an
  `expected.json` per spec listing constructs (meter, pickup, key changes, tempo changes,
  chords, cross-bar ties, polymeter, dynamics, articulations, slurs, holds, sections, tuplets,
  lyrics, microtonal pitches). T0 used two ad-hoc specs (`fixture`: G major 3/4, two parts,
  a chord, a cross-bar tie; `odd`: 7/8 with a key change) and the gitignored 116-bar
  orchestral composition (18 layers, 2 580 notes, 43 tempo points).
- **Corpus round-trip fixtures** `tests/fixtures/notation/corpus/` (`RN-I-004`): two
  public-domain Bach chorales written to MusicXML by music21 (T0 used `bach/bwv66.6`).
- **Chord parity set**: all 12 roots × the 25 `CHORD_QUALITIES` in closed voicing (300
  collections), generated, not stored.
- No network, no credentials; the XSD and wheels are fetched once at install.

### 2.5 Evidence and reporting

`scripts/harness-notation.sh <checkpoint>` (from §8, materialized by `RN-O-005`) writes
`docs/evolution/evidence-notation/<checkpoint>/summary.tsv`, one log per row, and copies the
oracle reports (XSD error list, music21 parity JSON, LilyPond logs). Heavy artifacts (`.ly`,
PDFs, exported XML of the large piece) go under `work/`, gitignored. Until the runner exists,
the T0 evidence lines are transcribed verbatim in §4.3.

## 3. Test registry

Shared preconditions: reference environment; repository root; a named commit. Oracle rows
(`L2`) require the oracle venv; without it they report `BLOCKED` with the missing tool named,
never `PASS`. `Mode` is `A` automated; every row here is automatable. `T0` is the measured
baseline; `Target` the desired result; `Green by` the checkpoint whose gate needs the row.

### 3.1 NORA — oracle toolchain

Failure meaning: interchange claims cannot be verified by anyone but the person who built a
venv by hand.

| ID | Requirement | Procedure | Pass criteria | Mode | T0 | Target | Roadmap | Green by |
|---|---|---|---|---|---|---|---|---|
| HARNESS-NORA-001 | The `oracles` dev extra installs music21, the LilyPond wheel and xmlschema | `uv venv <d> --python 3.12 && uv pip install --python <d>/bin/python -e '.[oracles]'`; import music21, xmlschema; run `lilypond --version` | all three succeed; versions pinned in `pyproject.toml` | A | FAIL: no such extra (T0 oracles live in a scratch venv) | PASS | RN-O-001 | T1 |
| HARNESS-NORA-002 | The MusicXML 3.1 XSD is vendored with its licence and used offline | `ls tests/fixtures/musicxml/xsd/{musicxml,xml,xlink}.xsd LICENSE*`; `xmlschema.XMLSchema(...)` loads without network | files present; schema loads | A | FAIL: fetched to scratch at T0 (335 762 + 5 695 + 2 280 bytes), not in tree | PASS | RN-O-001 | T1 |
| HARNESS-NORA-003 | `make oracle-check` runs the oracle tests and skips loudly without the extra | `make oracle-check` with and without the extra | exit 0 with the extra; without it prints `oracle-check: SKIPPED — install '.[oracles]'` and exits 0 | A | FAIL: no target, no oracle tests | PASS | RN-O-003 | T1 (skeleton), T3 (green) |
| HARNESS-NORA-004 | A CI job installs the extra and runs `make oracle-check` | `gh run list --workflow ci` job `oracles` green on the branch head | success | A | BLOCKED: GitHub Actions end in `startup_failure` for every run (release harness HARNESS-CI-001) | PASS | RN-O-004 | T5 |

### 3.2 NXML — notated MusicXML export

Preconditions: fixture corpus; oracle venv for rows marked (oracle). Failure meaning: the
score a user opens in MuseScore or LilyPond contradicts the spec.

| ID | Requirement | Procedure | Pass criteria | Mode | T0 | Target | Roadmap | Green by |
|---|---|---|---|---|---|---|---|---|
| HARNESS-NXML-001 | (oracle) Every fixture's notated export validates against the MusicXML 3.1 XSD | `export_notated_musicxml` for each fixture → `xmlschema.iter_errors` | 0 errors on every fixture | A | PARTIAL: VALID on the two ad-hoc specs and on the 116-bar piece; no committed corpus yet | PASS | RN-O-003, RN-O-002 | T3 |
| HARNESS-NXML-002 | Meter beats and unit come from the spec; bar length from the spec, not a CLI flag; per-part polymeter as per-part time signatures or a lossy code | export the 7/8 fixture; read `<time>` | `<beats>7</beats><beat-type>8</beat-type>`; measure count equals ceil(beats / bar) | A | FAIL: exports `7/4` (`beat-type` hard-coded to 4; `beats_per_bar` from `--bars`) | PASS | RN-X-001 | T2 |
| HARNESS-NXML-003 | `key_map` changes appear as `<key>` at the measure of change | export fixture with `key: C major, 3.5b=F major` | two `<key>` entries per part with fifths 0 then −1 at the right measure | A | FAIL: one `<key>` per part, initial key only | PASS | RN-X-002 | T2 |
| HARNESS-NXML-004 | `tempo_map` changes appear as `<direction>`/`<sound tempo>` at their measures (dense rubato maps thinned to a documented resolution) | export the orchestral piece (43 tempo points) | music21 `MetronomeMark` count equals the thinned point count | A | FAIL: exactly one `<sound tempo>` | PASS | RN-X-003 | T2 |
| HARNESS-NXML-005 | `pickup:` exports as an anacrusis (implicit measure) and downbeats align | export a pickup fixture | music21 first measure duration equals the pickup; barlines on downbeats | A | FAIL: no pickup handling in `interop.py` | PASS | RN-X-004 | T2 |
| HARNESS-NXML-006 | `dynamic` marks export as `<dynamics>` | export a fixture with `pp … ff` marks | music21 `Dynamic` objects equal the marks | A | FAIL: 0 `<dynamics>` in a piece with dynamic curves (lossy_dynamic_curve reported) | PASS | RN-X-006 | T3 |
| HARNESS-NXML-007 | `art` and slur groups export as `<articulations>` and `<slur>`; unrepresentable ones carry `lossy_articulation` for MusicXML too | export a fixture with slurs and staccato | music21 spanners and articulations match | A | FAIL: 0 emitted; `lossy_articulation` is reported for MIDI only | PASS | RN-X-007 | T3 |
| HARNESS-NXML-008 | `holds` export as `<fermata>`; form sections as `<rehearsal>` marks | export a fixture with a fermata and three sections | counts match | A | FAIL: neither emitted | PASS | RN-X-008 | T3 |
| HARNESS-NXML-009 | The exact-tick exporter (`export_musicxml`) emits one part per layer and `<chord/>` for simultaneous onsets | export the two-part fixture with a triad | `<part>` count 2; `<chord/>` count 2; music21 total quarterLength equals the notated export's | A | FAIL: 1 part, 0 `<chord/>`; chord tones serialized (music21 reads 30 beats of note time for 24) | PASS | RN-X-005 | T2 |
| HARNESS-NXML-010 | (oracle) music21 structural parity per fixture: parts = pitched layers, measures = ceil(duration / bar), time signatures = meter(s), key signatures = key_map, pitch multiset per part = spec, total quarterLength per part = spec sum within quantization | parity script over the corpus | all comparisons equal | A | PARTIAL: parts, measures and pitch multisets match on the fixture (2 parts, 4 measures, 3/4, fifths 1); meter unit and key changes fail (NXML-002/003) | PASS | RN-O-003, RN-X-001…005 | T3 |
| HARNESS-NXML-011 | Lossy diagnostics enumerate exactly the constructs each export dropped, and the INTEROP.md matrix is generated from the same registry | `interop_diagnostics(spec, fmt)` vs constructs present; `python -m audioforge.tools.gen_interop --check` | every dropped construct has a code; matrix check green | A | FAIL: four hand-listed codes; no matrix; pickup/tempo/key/holds dropped silently | PASS | RN-X-010 | T3 |

### 3.3 NIMP — MusicXML import

Failure meaning: a score imported for rendering is musically wrong (voices serialized, chords
arpeggiated in time, wrong tempo).

| ID | Requirement | Procedure | Pass criteria | Mode | T0 | Target | Roadmap | Green by |
|---|---|---|---|---|---|---|---|---|
| HARNESS-NIMP-001 | One layer per `<part>`, named from `part-name` | import `bwv66.6` (4 parts) | 4 layers with part names | A | FAIL: 1 layer for 4 parts | PASS | RN-I-001 | T2 |
| HARNESS-NIMP-002 | `<chord/>`, `<backup>`, `<forward>`, `<voice>` produce simultaneous onsets and voice-aware cursors | import the chorale; compare onset sets per part with music21 offsets | equal | A | FAIL: 165 distinct onsets for 165 notes; 144 beats laid end to end | PASS | RN-I-002 | T2 |
| HARNESS-NIMP-003 | `divisions`, `<time>`, `<key>`, `<sound tempo>` changes are honoured per measure; ties merge into one event | import a fixture with mid-piece changes | imported `tempo_map`, `key_map`, meter and merged notes match | A | FAIL: the importer reads the first `divisions` and first `sound` only; ties stay separate | PASS | RN-I-003 | T2 |
| HARNESS-NIMP-004 | (oracle) Corpus round trip: music21 corpus piece → our import: duration within 1 %, notes per part equal, spec validates and renders | vendored chorales | all criteria | A | FAIL: 91.875 s for a 25 s chorale; single part | PASS | RN-I-004 | T3 |
| HARNESS-NIMP-005 | Self round trip: notated export → import → same parts, onsets and pitch multisets (quantization documented) | every fixture | equal within quantization | A | FAIL (import flattens parts) | PASS | RN-I-005 | T3 |

### 3.4 NMIDI — MIDI export and import

| ID | Requirement | Procedure | Pass criteria | Mode | T0 | Target | Roadmap | Green by |
|---|---|---|---|---|---|---|---|---|
| HARNESS-NMIDI-001 | Multi-track MIDI import keeps parts and timing | import music21's MIDI of `bwv66.6` | layers = tracks; duration within 10 % of 25 s | A | PASS: 4 layers (36/42/44/41 notes), 22.5 s, 96 bpm | PASS | RN-O-003 (regression) | T1 |
| HARNESS-NMIDI-002 | (oracle) MIDI export writes one track per layer and every note survives | export the orchestral piece; `music21.converter.parse` | parts = 18; notes = 2 580 | A | FAIL: 1 part, 1 315 notes (single channel; same-pitch notes across layers cut each other) | PASS | RN-X-005 | T2 |
| HARNESS-NMIDI-003 | MIDI export carries the tempo map as tempo events | same | MetronomeMark count = 43 | A | FAIL: 1 tempo event (`bpm` only; `tempo_map` ignored) | PASS | RN-X-005 | T2 |

### 3.5 NTUN — tuning directive

Failure meaning: the DSL accepts a microtuning instruction and renders 12-TET without saying so
(ROADMAP AF-M05 calls this a correctness defect).

| ID | Requirement | Procedure | Pass criteria | Mode | T0 | Target | Roadmap | Green by |
|---|---|---|---|---|---|---|---|---|
| HARNESS-NTUN-001 | `tuning: edo divisions=19` drives the render | render a sine at a 19-EDO degree; FFT peak | within ± 5 cents of `base_hz · 2^(k/19)` | A | FAIL: renderer never reads `notation.tuning`; B4 renders at 493.883 Hz (12-TET) | PASS | RN-T-002 | T4 |
| HARNESS-NTUN-002 | Without a tuning directive, renders are byte-identical to today | `render_golden --check` after RN-T-002 | 5/5 exact | A | PASS: goldens byte-for-byte on `16b2cc2` | PASS | RN-T-002 | T4 |
| HARNESS-NTUN-003 | Until NTUN-001 passes, a non-12-EDO tuning compiles with a registered `tuning_not_rendered` diagnostic (the row becomes N/A once NTUN-001 passes) | compile the 19-EDO spec | diagnostic present; code in the manifest | A | FAIL: compiles with no diagnostic | PASS | RN-T-001 | T1 |
| HARNESS-NTUN-004 | Microtonal pitches export as MIDI pitch bend and MusicXML decimal `<alter>`; unrepresentable cases carry a code | export the 19-EDO fixture; music21 reads alters | alters within 0.01; bends present | A | FAIL (nothing microtonal exists to export) | PASS | RN-T-003 | T4 |

### 3.6 NANA — analysis honesty and parity

| ID | Requirement | Procedure | Pass criteria | Mode | T0 | Target | Roadmap | Green by |
|---|---|---|---|---|---|---|---|---|
| HARNESS-NANA-001 | (oracle) Chord roots agree with music21 for non-symmetric qualities | 12 roots × 25 qualities in closed voicing; `identify_chord` vs `music21.chord.Chord.root()` | ≥ 95 % agreement over collections both resolve, recorded disputes excluded | A | PASS: 154 of 156 (98.7 %); disputes recorded: `7sus4`/`dom7sus4` (music21 names the quartal tetramirror from the fourth), two `dim` spellings | PASS | RN-A-001 | T3 |
| HARNESS-NANA-002 | Symmetric and relative collections are declared ambiguous with candidates, and the documented set matches exactly | same run; `docs/MIGRATION_3.md` / `DSL_SPEC.md` list | ambiguous set == {dim7, aug, min7≡6, m7b5≡m6, sus2≡sus4} (120 collections) and the docs name it | A | PARTIAL: behaviour present (120 ambiguous, 0 unrecognized); docs mention only C6/Am7 | PASS | RN-A-001 | T3 |
| HARNESS-NANA-003 | Analysis reports state their scope; no key-finding, roman-numeral or realism claim is made | `analyze_audio` report has `assessment_scope`; grep docs for unbacked claims | present; none found | A | PASS: `signal_and_declared_expectations; musical merit requires listening`; voicing documented as a bounded transformation | PASS | RN-O-003 (regression) | T1 |
| HARNESS-NANA-004 | Pitch-class-set theory (AF-M01) is reachable through `analyze` (normal form, prime form, IC vector, set class) | `run_tool("analyze", {"pitch_classes": [0,4,7]})` | fields returned; MCP contract test | A | FAIL: `theory_pcset` is internal only | PASS | RN-A-002 | T5 |
| HARNESS-NANA-005 | The music21-bridge decision (D3) is recorded | ADR-0011 names the choice | recorded | A | FAIL | PASS | RN-A-003, RN-D-004 | T1 |

### 3.7 NENG — proof sheet and engraving

| ID | Requirement | Procedure | Pass criteria | Mode | T0 | Target | Roadmap | Green by |
|---|---|---|---|---|---|---|---|---|
| HARNESS-NENG-001 | (oracle) Every fixture's notated export engraves through `musicxml2ly` + `lilypond` with zero warnings | run both; grep logs | exit 0; 0 warning/error lines; PDF produced | A | PASS: fixture and 116-bar piece, 0 warnings, 3.2 s | PASS | RN-O-003 | T3 |
| HARNESS-NENG-002 | `audioforge score --engrave` uses the LilyPond backend when the extra is installed and gives a structured hint otherwise | run with and without the extra | PDF produced / `score: install '.[engrave]'` with a documented exit code | A | FAIL: no such option | PASS | RN-P-003 | T5 |
| HARNESS-NENG-003 | The matplotlib PDF is named a proportional proof sheet everywhere; the word "engrave" is reserved for LilyPond | `grep -in engrav audioforge/score.py docs AGENTS.md` outside the LilyPond backend | 0 hits for the proof sheet | A | FAIL: `score.py` says "Engrave" five times | PASS | RN-P-001 | T1 |
| HARNESS-NENG-004 | The proof sheet renders dynamics text without missing-glyph warnings | `pytest -W error::UserWarning tests/test_score.py tests/test_score_layout.py` | passes | A | FAIL: six `Glyph … missing from font(s) Noto Music` warnings (letters `l`, `p`) | PASS | RN-P-002 | T5 |

### 3.8 NDOC — contract and documentation

| ID | Requirement | Procedure | Pass criteria | Mode | T0 | Target | Roadmap | Green by |
|---|---|---|---|---|---|---|---|---|
| HARNESS-NDOC-001 | `docs/INTEROP.md` carries a generated coverage matrix (construct × format → preserved / quantized / lossy code / unsupported) with a `--check` twin | `python -m audioforge.tools.gen_interop --check` | in sync; every `score_layer` and `notation` construct present | A | FAIL: prose with four codes | PASS | RN-X-010 | T3 |
| HARNESS-NDOC-002 | The capability manifest lists notation directives (`tuning`, `tuplet`, `lyrics`) with rendering status and the interop coverage | read `docs/capability-manifest.json` | keys present; manifest-check green | A | FAIL: `tuplet` and `lyrics` absent; `score_layer` covers five properties only | PASS | RN-D-001 | T3 |
| HARNESS-NDOC-003 | README has a "Notation and analysis" section stating scope and delegation | grep README | section present and guarded by `tests/test_docs_regression.py` | A | FAIL: README never mentions score, notation or MusicXML | PASS | RN-D-002 | T1 |
| HARNESS-NDOC-004 | `DSL_GAP_SPEC.md` G6/G8 state the measured limits (inert tuning, flattened import) with harness IDs instead of "closed" | grep | statements present | A | FAIL: both say closed | PASS | RN-D-003 | T1 |
| HARNESS-NDOC-005 | ADR-0011 records the positioning: semantic score contract, oracle-verified interchange, engraving and musicology delegated, proof sheet retained | `ls docs/adr/0009-*.md`; sections | accepted | A | FAIL | PASS | RN-D-004 | T1 |

### 3.9 NGATE — fixtures, gate and evidence

| ID | Requirement | Procedure | Pass criteria | Mode | T0 | Target | Roadmap | Green by |
|---|---|---|---|---|---|---|---|---|
| HARNESS-NGATE-001 | A committed fixture corpus with expected-features JSON exists (≥ 8 specs) | `ls tests/fixtures/notation/*.af` | ≥ 8 and each compiles | A | FAIL: none | PASS | RN-O-002 | T1 |
| HARNESS-NGATE-002 | The surface's existing tests keep passing | `pytest tests/test_interop.py tests/test_score.py tests/test_score_layout.py tests/test_theory_pcset.py tests/test_gap_closure.py` | all pass | A | PASS: 46 passed | PASS | RN-O-003 | every checkpoint |
| HARNESS-NGATE-003 | `make check` green and coverage ≥ 90.1 % with the new code | `make check`; `coverage report` | exit 0; ≥ 90.1 | A | PASS: 910 passed on `16b2cc2`; coverage 90.96 % at 3.0.0 | PASS | RN-O-003 | every checkpoint |
| HARNESS-NGATE-004 | Goldens unchanged by notation work | `render_golden --check` | 5/5 exact | A | PASS | PASS | RN-O-003 | every checkpoint |
| HARNESS-NGATE-005 | The runner exists and evidence bundles are tracked | `scripts/harness-notation.sh <T>`; `git ls-files docs/evolution/evidence-notation/<T>` | summary with all 53 IDs; tracked | A | FAIL: runner only in §8; T0 evidence transcribed in §4.3 | PASS | RN-O-005 | T1 |
| HARNESS-NGATE-006 | The plan is registered in `docs/backlog.yml` | `grep -c 'harness-notation' docs/backlog.yml`; governance script | ≥ 1; green | A | FAIL | PASS | RN-D-005 | T1 |

### 3.10 NPERF — budgets (reference machine)

| ID | Requirement | Procedure | Pass criteria | Mode | T0 | Target | Roadmap | Green by |
|---|---|---|---|---|---|---|---|---|
| HARNESS-NPERF-001 | Notated MusicXML export ≤ 1 s and MIDI export ≤ 0.5 s for a 3 000-note spec | time both on the orchestral piece (2 580 notes) | within budget | A | PASS: 0.05 s / 0.01 s | PASS | RN-Q-001 | T5 |
| HARNESS-NPERF-002 | (oracle) `musicxml2ly` + `lilypond` ≤ 30 s for 116 measures | time the pipeline | ≤ 30 s | A | PASS: 0.9 s + 3.2 s | PASS | RN-Q-001 | T5 |
| HARNESS-NPERF-003 | Proof-sheet PDF ≤ 15 s for 116 measures | `audioforge score` on the piece | ≤ 15 s | A | PASS: 9.8 s (642 KB) | PASS | RN-Q-001 | T5 |
| HARNESS-NPERF-004 | MusicXML import ≤ 1 s for a four-part ten-measure chorale | time `import_musicxml` | ≤ 1 s | A | PASS: 0.001 s (before the part-aware rewrite; re-measured at T2) | PASS | RN-Q-001 | T5 |

### 3.11 NSEM — semantic score and notation fields

| ID | Requirement | Procedure | Pass criteria | Mode | T0 | Target | Roadmap | Green by |
|---|---|---|---|---|---|---|---|---|
| HARNESS-NSEM-001 | Every `score_layer` property (meter, pickup, form, repeat, polymeter) has a defined projection or a registered lossy code in both exporters | read the coverage matrix; export a fixture using all five | no silent drop | A | FAIL: meter partially (unit wrong), pickup/form/polymeter dropped silently; repeat expanded (documented) | PASS | RN-X-010, RN-X-001…008 | T3 |
| HARNESS-NSEM-002 | `notation.tuplets` and `notation.lyrics` project to `<time-modification>` and `<lyric>`, or carry a code | export a fixture with both | music21 reads tuplets and lyrics, or codes emitted | A | PARTIAL: `lossy_lyrics` is reported; tuplets dropped silently | PASS | RN-X-009 | T3 |

## 4. Baseline run — T0

**Tree under test.** `release/engine-3.0.0` at `16b2cc2` (engine 3.0.0, clean tree). Oracle
venv: music21 10.5.0, `lilypond` wheel 2.25.12 (GNU LilyPond 2.25.12, Guile 3.0), xmlschema
4.3.2, MusicXML 3.1 XSD (`w3c/musicxml` tag `v3.1`). Date 2026-09-06.

### 4.1 Totals

| Count | Value |
|---|---|
| Total assertions | 53 |
| PASS | 12 (NMIDI-001, NTUN-002, NANA-001, NANA-003, NENG-001, NGATE-002/003/004, NPERF-001…004) |
| PARTIAL | 4 (NXML-001, NXML-010, NANA-002, NSEM-002) |
| FAIL | 36 |
| BLOCKED | 1 (NORA-004: GitHub Actions) |
| N/A | 0 |
| Verified target-state coverage | 12 / 53 = 23 % |

### 4.2 Coverage by target capability

| Capability (report §3) | Rows | T0 |
|---|---|---|
| NREQ-1 notated export structure and validity | NXML-001…005, NXML-010 | PARTIAL (valid and engravable; structure wrong) |
| NREQ-2 exact-tick and MIDI exports keep parts, chords, tempo | NXML-009, NMIDI-001…003 | FAIL (import side PASS) |
| NREQ-3 expressive notation projected or declared | NXML-006…008, NXML-011, NSEM-001/002 | FAIL / PARTIAL |
| NREQ-4 import fidelity | NIMP-001…005 | FAIL |
| NREQ-5 tuning honest then real | NTUN-001…004 | FAIL (default path PASS) |
| NREQ-6 analysis honesty and parity | NANA-001…005 | PASS on parity and scope; FAIL on exposure and decision record |
| NREQ-7 proof sheet labelled, engraving delegated | NENG-001…004 | PASS on engravability; FAIL on labelling, backend, glyphs |
| NREQ-8 contract and docs exact | NDOC-001…005, NGATE-006 | FAIL |
| NREQ-9 oracles in the toolchain | NORA-001…004, NGATE-001/005 | FAIL / BLOCKED |
| NREQ-10 budgets | NPERF-001…004 | PASS |

### 4.3 Load-bearing evidence lines (verbatim from the T0 session)

```
oracle venv                        : music21 10.5.0 ; GNU LilyPond 2.25.12 (running Guile 3.0) ; xmlschema 4.3.2 ; XSD musicxml.xsd 335762 B, xml.xsd 5695 B, xlink.xsd 2280 B
fixture (G major, 3/4, 2 parts, 13 events) notated export : XSD VALID ; music21 parts=2 notes+chords=13 (pitches 15) time=['3/4'] key_fifths=[1] measures=4 ; musicxml2ly exit=0 0 warn/err ; lilypond exit=0 0 warn/err ; 42485 B pdf
fixture raw export                 : XSD VALID ; music21 parts=1 measures=1 notes=13 total quarterLength 30.00 vs 24.00 notated ; <chord/> count 0 (notated: 2)
odd fixture (meter 7 8, key_map C→F at 3.5b) : notated <time> ('7','4') ; <key> count 1 fifths ['0'] ; raw <time> ('7','8') ; raw <key> 0
the_first_light (18 layers, 2580 notes, 43 tempo points, 6 sections, D minor, 4/4) : notated export 0.63 MB in 0.05 s ; XSD VALID ; music21 parts=18 notes+chords=2820 measures=116 in 0.9 s ; musicxml2ly 0.86 s, lilypond 3.17 s, 0 warnings, 269235 B pdf ; <dynamics> 0 <slur 0 <articulations 0 <sound tempo 1 <key> 18 fermata 0 rehearsal 0 ; lossy codes ['lossy_dynamic_curve']
the_first_light MIDI export        : 21140 B in 0.01 s ; music21 reads parts=1 notes=1315 tempo marks=1 duration_qL=464.0
bwv66.6 (music21 corpus: 4 parts, 165 notes, 10 measures, f# minor, 4/4) : our MusicXML import → layers 1, notes 165, distinct onsets 165, note time 144.0 beats end to end, duration_s 91.875, bpm 96 ; validates True ; import 0.001 s
bwv66.6 MIDI (music21) → our MIDI import : layers 4 (36/42/44/41 notes), duration_s 22.5, bpm 96 ; validates True
tuning: edo divisions=19           : compiles True, no diagnostic ; notation.tuning stored, hash-excluded ; renderer reads notation.tuning: False ; B4 → 493.883 Hz
chord parity (12 roots × 25 qualities, closed) : resolved 180 ambiguous 120 unrecognized 0 ; music21 root agreement 154 / 300 ; ambiguous by quality {min7b5,m7b5,dim7,min7,sus2,sus4,aug,m7,m6,6}×12 ; resolved-but-different {7sus4:12, dom7sus4:12, dim:2}
proof sheet                        : synth_voice 2 pages 36821 B 1.4 s ; the_first_light 641615 B 9.8 s ; suite warnings: Glyph 108 (l) / 112 (p) missing from font(s) Noto Music (6)
surface tests                      : 46 passed (test_interop 7, test_score 3, test_score_layout 12, test_theory_pcset 12, test_gap_closure 8) ; make check on 16b2cc2: 910 passed ; goldens 5/5
manifest                           : score_layer properties {form, meter, pickup, polymeter, repeat} ; interop {cli, exports [midi, musicxml], imports [midi, musicxml]} ; 'tuplet' 0 hits, 'lyrics' 0 hits ; README hits for score|notation|musicxml: 0 ; score.py 'engrav' hits: 5
```

## 5. Progress model — checkpoints

| Checkpoint | Name | Must be PASS to leave | Expected to flip | Roadmap milestone |
|---|---|---|---|---|
| T0 | Baseline | — | — | M0 |
| T1 | Honesty and oracles | NORA-001, NORA-002, NORA-003 (skeleton), NGATE-001, NGATE-005, NGATE-006, NENG-003, NTUN-003, NDOC-003, NDOC-004, NDOC-005, NANA-005 | the surface says what it is; oracles installable | M1 |
| T2 | Interchange core | NXML-002…005, NXML-009, NIMP-001…003, NMIDI-002, NMIDI-003 | structure comes from the spec; parts and chords survive both ways | M2 |
| T3 | Oracle integration | NXML-001, NXML-006…008, NXML-010, NXML-011, NIMP-004, NIMP-005, NSEM-001, NSEM-002, NDOC-001, NDOC-002, NANA-001, NANA-002, NENG-001, NORA-003 (green) | parity green on the corpus; generated matrix | M3 |
| T4 | Tuning activation | NTUN-001, NTUN-002, NTUN-004 (NTUN-003 becomes N/A) | the directive renders | M4 |
| T5 | Hardening | NPERF-001…004, NENG-002, NENG-004, NANA-004, NORA-004 (or waiver while Actions are down) | budgets, backend, glyphs, CI | M5 |
| T6 | Desired state | every non-waived row PASS; release tagged per D2 | — | M6 |

Delivery progress at T0: 0 of 36 roadmap items complete (1 parked by design: RN-T-004). Verified
coverage: 23 %.

## 6. Quality gates

| Gate | Opens | Blocking rows | Rationale |
|---|---|---|---|
| Honesty gate | T1 → T2 | NENG-003, NTUN-003, NDOC-003, NDOC-004, NDOC-005 | Nothing about the surface may overstate what it does before more of it is built. |
| Oracle gate | T1 → T2 | NORA-001, NORA-002, NGATE-001 | Interchange work without oracles would be judged by our own reader. |
| Structure gate | T2 → T3 | NXML-002…005, NXML-009, NIMP-001…003, NMIDI-002/003 | Expressive projection on a wrong measure grid is wasted. |
| Parity gate | T3 → T4 | NXML-001, NXML-010, NXML-011, NIMP-004/005, NENG-001, NANA-001/002, NSEM-001/002 | The corpus must read the same in music21 and engrave in LilyPond before touching frequencies. |
| Contract gate | T3 → T4 | NDOC-001, NDOC-002 | Generated matrix and manifest before the tuning change adds more rows. |
| Render-truth gate | T4 → T5 | NTUN-001, NTUN-002 (goldens), plus the release harness `GATE-003` | A tuning that changes 12-TET bytes is a regression, not a feature. |
| Performance gate | T5 → T6 | NPERF-001…004 | Budgets measured on the reference machine. |
| Release gate | T6 | all non-waived rows; ADR-0011 accepted; version per D2 | Completion is demonstrated, not declared. |

Classification: all rows blocking at their gate except `NORA-004` (accepted temporarily while
Actions are down; waivable with the release harness's owner and expiry), `NANA-004` and
`NENG-002` (non-blocking capability additions, decisions D5/D4), `NENG-004` (non-blocking).
Waivers follow harness.md §6.3 (owner, reason, expiry, remediation) in
`docs/evolution/evidence-notation/waivers.tsv`.

## 7. Final harness state (definition of complete)

One run of `scripts/harness-notation.sh T6` on the tagged commit shows: every fixture's
notated export XSD-valid, read by music21 with the same parts, measures, signatures, pitches
and durations as the spec, and engraved by LilyPond with zero warnings; the exact-tick and MIDI
exports preserve parts, chords and tempo; the importer reconstructs the vendored chorales within
1 % duration and exact per-part note counts and round-trips our own exports; the tuning
directive moves the fundamental to the declared cents while the goldens stay byte-identical;
chord parity holds and the ambiguity set is documented; the manifest, generated INTEROP matrix,
README, DSL_GAP_SPEC and ADR-0011 agree; budgets hold; zero unexplained failures; zero
blocked rows; waivers, if any, named with owner and expiry. The proof sheet is still a proof
sheet, and says so.

## 8. Runner

The executable runner is `scripts/harness-notation.sh`; its implementation is
`audioforge/tools/notation_acceptance.py`. The registry in §3 owns the 53 assertion IDs.
The runner supports T1, T2 and T3, classifying future milestone rows as N/A with their due
checkpoint. An exploratory `--skip-full` run records NGATE-003 as BLOCKED and exits nonzero.
The default run executes the complete local gate and coverage.

```bash
ORACLE_PY=/path/to/oracle-venv/bin/python scripts/harness-notation.sh T3
```

Missing oracles yield BLOCKED for dependent rows. Pytest selections must contain at least
one test and no skip, failure or error in their JUnit report. A failed or blocked required
row makes the runner exit nonzero. NORA-001 installs the pinned extra in a fresh environment
using the local uv cache (populate it with `uv pip install -e '.[dev,oracles]'` first).
Schema access is local-only. No warning category is filtered from the LilyPond logs.
The shell wrapper adds the oracle wheel's binary directory to `PATH` so that
`musicxml2ly` can resolve its own `lilypond --version` probe.

Evidence includes all row logs, the command/interpreter/commit context, JUnit reports, and
XSD, music21 and LilyPond reports. Generated heavy artifacts and environments stay in
`work/`, which is gitignored. The evidence must be tracked for NGATE-005 to pass; a first
run produces that bundle before the final tracked verification run.

The original proposed shell runner checked several file names rather than behavior and
could report a skipped oracle selection as PASS. This implementation replaces that draft.
The original notation branch's ADR-0009 is integrated as ADR-0011 because the main branch
already assigned ADR-0009 to stereo playback. The original proposed 3.1/2.1 release numbers
remain historical; this checkpoint is Unreleased on engine 3.1 / DSL 2.0.

## 9. Checkpoint log

Rows are appended by the agent that ran `scripts/harness-notation.sh <T>`; the evidence
bundle is the source, this table is the index. Counts are PASS / FAIL / BLOCKED over all
53 IDs; "targeted" is the subset whose *Green by* column names the checkpoint.

| Checkpoint | Commit | Run (UTC) | PASS / FAIL / BLOCKED | Targeted rows | Notes |
|---|---|---|---|---|---|
| T1 | `8e550c5` | 2026-09-06 | 16 / 37 / 0 | 13 of 13 PASS (NGATE-005 passes once the bundle is committed) | Oracles via `ORACLE_PY`; the first run used the wrong interpreter (worktree has no `.venv`) and was discarded. |
| T2 | `73728b7` | 2026-09-06 | 31 / 22 / 0 | NXML-002…005/009, NIMP-001…003, NMIDI-002/003 | Run on a clean detached worktree at the commit; a first run on a tree with T3 edits in progress was discarded. |
| T3 | `cb6f9b8` | 2026-09-06 12:15–13:10 | 42 / 0 / 0; 11 N/A | All 42 rows due by T3 PASS | Isolated integration snapshot; all 257 source hashes match this commit. Full gate green, coverage 91.69%, goldens 5/5. See [delivery record](evidence-notation/T3/delivery.json) for the clean oracle rerun after the shell setup correction. |
