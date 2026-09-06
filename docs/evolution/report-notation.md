---
disclaimer:
  notice: >-
    No information within this document should be taken for granted.
    Any statement or premise not backed by a real logical definition
    or verifiable reference may be invalid, erroneous, or a hallucination.
  generated_by: "Claude Fable 5.1 via Claude Code"
  date: "2026-09-06"
---

# Implementation Assessment and Evolution Plan: notation, interchange and musical analysis

**Current checkpoint — 2026-09-06:** notation M1–M3 is complete in implementation
commit `cb6f9b8`, with all 42 assertions due by T3 passing and 91.69% coverage.
See [the integration and acceptance record](NOTATION_PHASE3.md) for the delivered
behavior, evidence and remaining milestones. The assessment below preserves the
original T0 baseline and proposed release numbering; this integration remains
Unreleased on engine 3.1.0 / DSL 2.0.

Companion artifacts: [harness-notation.md](harness-notation.md) (53 assertions, measured T0,
runner) and [roadmap-notation.xlsx](roadmap-notation.xlsx) (36 items, 7 milestones, 35
dependency edges, 13 risks, 7 decisions). IDs are shared: `NREQ-n` requirements here,
`RN-<ws>-<nnn>` roadmap items, `HARNESS-N<CAT>-<nnn>` assertions. This plan sits after the
engine 3.0.0 release governed by [report.md](report.md); it targets engine 3.1.0 / DSL 2.1
(decision D2).

## 1. Executive summary

**The starting analysis is right about the ranking and wrong about the shape of the gap.**
music21 and LilyPond are far ahead for musicology and engraving, and AudioForge should not try
to catch them. But "semantic handles plus a basic PDF" understates one thing and hides another.
It understates the hand-off: the notated MusicXML that AudioForge already produces validates
against the MusicXML 3.1 schema, music21 reads it with the right part and measure structure,
and LilyPond engraves the 116-bar orchestral composition with zero warnings in three seconds.
It hides the failures: that same exporter hard-codes the beat unit so 7/8 arrives as 7/4,
drops every key change, tempo change, dynamic, slur, hold and pickup; the exact-tick exporter
serializes chord tones in sequence; the MIDI exporter flattens eighteen layers into one channel
and loses half the notes; the importer turns a four-voice Bach chorale into a ninety-two-second
monody; and the `tuning:` directive is accepted and silently rendered in 12-TET. The accurate
statement is: the hand-off to the leaders works, its fidelity does not, and nothing in the
repository can verify either.

**Where the system is today.** Score fields (`meter`, `pickup`, `form`, `repeat`,
`polymeter`) are semantic handles that 3.0.0 made executable for rendering; notation metadata
(`tuning`, `tuplet`, `lyrics`) is typed, hash-excluded and inert; harmony analysis identifies
chords from evidence and declares ambiguity rather than guessing; a pitch-class-set core
exists but is unreachable from the agent surface; the `score` verb draws a proportional proof
sheet with matplotlib. The harness measured 53 assertions on 2026-09-06: 12 pass, 4 partial,
36 fail, 1 blocked; verified coverage 23 %.

**Where it needs to go.** A surface that says exactly what it is and can prove it: a
semantic score contract whose every construct has a declared projection per format
(preserved, quantized, lossy with a code, unsupported), exporters and an importer whose
fidelity is judged by the oracles themselves, a tuning directive that either drives the render
or says it does not, analysis claims stated and parity-checked against music21, and a PDF that
is called a proof sheet while real engraving is delegated to LilyPond through an optional
backend.

**The most important gaps.** (1) No oracle is part of the toolchain, so interchange claims are
unverifiable in the repository (`NORA-*`). (2) Structural export defects: beat unit, key and
tempo changes, pickup, chords in the exact-tick and MIDI paths (`NXML-002…005`, `NXML-009`,
`NMIDI-002/003`). (3) Import flattens parts and chords (`NIMP-*`). (4) The inert tuning
directive, which the project's own roadmap calls a correctness defect (`NTUN-*`). (5) The
contract and docs do not describe the surface: no coverage matrix, no manifest entries for
notation directives, no README section, "closed" gap-spec entries that are open, and a
docstring that calls the proof sheet engraving (`NDOC-*`, `NENG-003`).

**The strategy.** Honesty first, oracles second, structure third, parity fourth, tuning last.
T1 makes the surface truthful and installs the oracles as a dev extra; T2 fixes measure
structure and part/chord fidelity in both directions; T3 makes music21 and LilyPond parity
green on a committed fixture corpus and generates the coverage matrix; T4 activates n-EDO
tuning with an FFT proof and byte-identical goldens; T5 adds budgets, the LilyPond backend and
the CI oracle job; T6 releases as 3.1.0. Deep musicology (Track M beyond chord identity) and
just intonation stay in the backlog by design.

**Major risks.** Oracle weight and version drift; the MusicXML import subset (voices,
cross-staff, grace notes) never being finite unless written down; tuning threading through
the sampler without moving 12-TET bytes; the same dead CI that blocks the release roadmap;
and the temptation to build an engraver.

**Expected end state.** One runner invocation on the tagged commit shows every fixture
schema-valid, read by music21 with the spec's structure, engraved by LilyPond warning-free,
imported back with the same parts and chords, the tuning directive moving the fundamental to
its declared cents while goldens stay byte-identical, and a manifest, INTEROP matrix, README
and ADR that agree with each other and with the code.

## 2. Current state

### 2.1 Architecture as observed

Notation lives entirely outside the render path, which is the right place for it: nothing in
`audioforge/score.py`, `audioforge/interop.py` or `audioforge/theory_pcset.py` feeds back into
synthesis. Four components make up the surface:

| Component | What it does | Size and tests |
|---|---|---|
| Score fields (`schema.py`, `arrangement.py`, `dsl.py`) | `meter`, `pickup`, `form`, `repeat`, `polymeter` compile to `spec.score`; since 3.0.0 repeats expand into an explicit timeline and meter/pickup drive groove phase | covered by the release harness (`MUS-004`) |
| Notation metadata (`spec.notation`) | `tuning: edo …`, `tuplet:`, `lyrics:` compile to typed, hash-excluded metadata; no consumer reads them | `tests/test_gap_closure.py` (8 tests) |
| Interop (`interop.py`, 659 lines) | MIDI export (single track), multi-track MIDI import with pitch-bend, exact-tick MusicXML export, quantized "notated" MusicXML export (measures, key, time, ties, chords, clefs), MusicXML import, lossy-diagnostic codes, session bundle | `tests/test_interop.py` (7) |
| Analysis (`harmony.py`, `theory.py`, `theory_pcset.py`, `analysis.py`) | Evidence-based chord identity, key-aware extensions, conservative cadence candidates, pitch-class-set operations (normal/prime form, IC vector, set class), signal analysis with declared scope | `tests/test_theory_pcset.py` (12), `tests/test_musical_correctness.py` |
| Proof sheet (`score.py`, 720 lines) | matplotlib PDF: proportional noteheads at (beat, pitch) with duration bars, clefs, key signatures, barlines, stage plot, intensity ribbon, dynamics, provenance block; Noto Music glyphs | `tests/test_score.py` (3), `tests/test_score_layout.py` (12) |

### 2.2 Quality level as measured on 2026-09-06

| Measurement | Result | Harness |
|---|---|---|
| Notated MusicXML of a 3/4 two-part fixture: XSD 3.1 validity, music21 structure, LilyPond | VALID; 2 parts, 4 measures, 3/4, one sharp, pitches match; `musicxml2ly` + `lilypond` 0 warnings | NXML-001, NXML-010, NENG-001 |
| Same for the 116-bar orchestral composition (18 layers, 2 580 notes, 43 tempo points) | VALID; 18 parts, 116 measures, 2 820 note objects; export 0.05 s; LilyPond 3.2 s, 0 warnings, 269 KB | NXML-001, NENG-001, NPERF-001/002 |
| 7/8 fixture with a key change | exported as `7/4`; one `<key>`, initial only | NXML-002, NXML-003 |
| Tempo map (43 points), dynamics, slurs, articulations, holds, sections in the export | one `<sound tempo>`; zero of everything else | NXML-004, NXML-006…008 |
| Exact-tick MusicXML export of a chord | no `<chord/>`; tones serialized (music21 reads 30 beats of note time for 24) | NXML-009 |
| MIDI export of the orchestral piece read by music21 | 1 part, 1 315 of 2 580 notes, 1 tempo mark | NMIDI-002, NMIDI-003 |
| MIDI import of a four-part chorale | 4 layers, 163 notes, 22.5 s (correct) | NMIDI-001 |
| MusicXML import of the same chorale | 1 layer, 165 notes at 165 distinct onsets, 91.9 s for a 25 s piece | NIMP-001, NIMP-002, NIMP-004 |
| `tuning: edo divisions=19` | compiles with no diagnostic; renderer never reads it; B4 at 493.883 Hz | NTUN-001, NTUN-003 |
| Chord roots vs music21, 12 roots × 25 qualities | 154 of 156 agree where both resolve; 120 collections deliberately "ambiguous"; disputes: `7sus4`/`dom7sus4`, two `dim` spellings | NANA-001, NANA-002 |
| Proof sheet | golden spec 2 pages, 1.4 s; orchestral piece 642 KB, 9.8 s; six missing-glyph warnings in the suite | NPERF-003, NENG-004 |
| Documentation | README: zero mentions of score, notation or MusicXML; manifest lacks `tuplet`/`lyrics`; INTEROP.md lists four codes; `score.py` says "Engrave" five times | NDOC-002/003, NENG-003 |

### 2.3 Limitations and technical debt

Three kinds, each with a different owner in the plan.

**Fidelity debt (code).** The notated exporter takes its bar length from a CLI flag and
hard-codes the quarter as beat unit; it ignores `key_map`, `tempo_map`, `pickup`, `holds`,
sections, dynamics, articulations, slurs, tuplets and lyrics, and reports only two of those
losses. The exact-tick exporter and the MIDI exporter flatten layers and chords. The importer
reads the first `divisions` and the first tempo, ignores `<part>` boundaries, `<chord/>`,
`<backup>` and `<voice>`, and keeps ties as separate notes.

**Honesty debt (docs and contract).** `DSL_GAP_SPEC.md` marks G6 and G8 "closed" while the
tuning directive is inert and the importer flattens ensembles; the capability manifest omits
two of three notation directives; INTEROP.md claims MIDI "preserves pitch, start, duration,
velocity, tempo, and note order" but for a multi-layer spec it preserves none of those for
half the notes; the proof sheet is called engraving.

**Verification debt (toolchain).** No oracle exists in the repository. Every claim about
interchange was, until this measurement, checked only by our own reader reading our own
writer, which cannot detect the flattening the oracles exposed in minutes.

### 2.4 Operational constraints

Oracles are heavy (music21 plus a 30 MB LilyPond wheel) and belong in a dev extra, never at
runtime. LilyPond runs from a PyPI wheel on Linux, macOS and Windows; no system install is
needed. GitHub Actions still do not execute jobs (release harness `CI-001`), so any oracle CI
job waits for the same administrative fix. Noto Music is present on the reference machine but
lacks Latin glyphs, which is the source of the dynamics warnings.

### 2.5 Facts, inferences, assumptions, unknowns

**Observed facts.** Every row of §2.2, transcribed verbatim in harness-notation.md §4.3: the
oracle versions, the XSD verdicts, the music21 counts, the LilyPond logs, the import numbers,
the tuning check, the chord parity table, the timings, the documentation greps.

**Inferred conditions.** The MIDI note loss is caused by all layers sharing one channel so
that a note-off from one layer ends the same pitch sounding in another; the code (single
format-0 track, `_notes()` flattening, single tempo meta event) supports this, but the exact
count of collisions was not traced note by note. The importer's 92-second result follows from
its single cursor advancing across parts; the mechanism is visible in the code.

**Assumptions.** The `lilypond` wheel and music21 remain installable from PyPI; Bach chorales
from music21's corpus may be vendored as public-domain fixtures; the release roadmap merges
before this work lands, so the base is `main` at engine 3.0.0.

**Unknowns requiring validation.** Whether LilyPond accepts per-part time signatures for
polymeter without warnings (RN11); how much of the MusicXML importer subset (voices,
cross-staff, grace notes, transposing instruments) the corpus fixtures exercise; whether
threading a tuning resolver through the sampler's resample ratios keeps 12-TET bytes identical
(RN12, gated by goldens).

## 3. Desired state

Ten requirements, each decided by the named assertions (the workbook's Traceability sheet).

| Req | Target capability | We know it is achieved when |
|---|---|---|
| NREQ-1 | The notated export derives its structure from the spec and is oracle-valid | `NXML-001…005`, `NXML-010` PASS on the committed corpus |
| NREQ-2 | Exact-tick MusicXML and MIDI exports keep parts, chords and the tempo map | `NXML-009`, `NMIDI-001…003` PASS |
| NREQ-3 | Every expressive and structural construct is projected or declared lossy by code | `NXML-006…008`, `NXML-011`, `NSEM-001/002` PASS |
| NREQ-4 | The importer reconstructs parts, chords and attribute changes; corpus and self round trips hold | `NIMP-001…005` PASS |
| NREQ-5 | The tuning directive is loud while inert, then drives the render with 12-TET bytes unchanged | `NTUN-003` at T1, then `NTUN-001/002/004` PASS at T4 |
| NREQ-6 | Analysis claims are stated and parity-checked; the pitch-class-set core is reachable | `NANA-001…005` PASS |
| NREQ-7 | The PDF is a labelled proof sheet; engraving is delegated to LilyPond through an optional backend | `NENG-001…004` PASS |
| NREQ-8 | Manifest, generated INTEROP matrix, README, gap spec and ADR describe the surface exactly | `NDOC-001…005`, `NGATE-006` PASS |
| NREQ-9 | Oracles are part of the toolchain and the gate | `NORA-001…004`, `NGATE-001…005` PASS |
| NREQ-10 | Budgets hold | `NPERF-001…004` PASS |

Nothing here asks AudioForge to analyse or engrave better than the tools it hands off to.

## 4. Gap analysis

**Gap 1: no oracle in the toolchain.** Current: music21, LilyPond and the XSD exist only in a
scratch venv built for this measurement. Desired: `.[oracles]` dev extra, vendored XSD,
`make oracle-check` that skips loudly, a CI job. Consequence: interchange claims are
unverifiable by anyone else. Work: `RN-O-001`, `RN-O-003`, `RN-O-004`. Prerequisites: none;
the CI job needs Actions fixed. Risks: RN1, RN2, RN5, RN6. Validation: `NORA-001…004`.
Complete at T1 (extra, XSD, target) and T5 (CI).

**Gap 2: no committed fixture corpus.** Current: two ad-hoc specs and a gitignored
composition. Desired: ≥ 8 fixtures with expected-features JSON and two vendored chorales.
Consequence: parity cannot be a standing test. Work: `RN-O-002`, `RN-I-004`. Prerequisites:
none. Risks: RN3. Validation: `NGATE-001`, `NIMP-004`. Complete at T1 (corpus), T3 (chorales).

**Gap 3: measure structure is wrong in the notated export.** Current: beat unit hard-coded,
bar length from a flag, key and tempo changes and pickup dropped. Desired: all derived from the
spec, per-part polymeter represented or coded. Consequence: a 7/8 piece prints as 7/4; a
modulating piece prints in one key. Work: `RN-X-001…004`. Prerequisites: Gap 2. Risks: RN11.
Validation: `NXML-002…005`. Complete at T2.

**Gap 4: parts and chords are flattened on the way out.** Current: exact-tick MusicXML has one
part and no `<chord/>`; MIDI is one channel with a single tempo. Desired: one part or track per
layer, chords marked, tempo map emitted. Consequence: half the notes of an orchestral piece
vanish in MIDI; chord durations are wrong in exact MusicXML. Work: `RN-X-005`. Prerequisites:
Gap 2. Risks: none. Validation: `NXML-009`, `NMIDI-002/003`. Complete at T2.

**Gap 5: parts and chords are flattened on the way in.** Current: single cursor across parts;
first attributes only; ties unmerged. Desired: one layer per part, chord and voice aware,
attribute changes honoured. Consequence: an imported chorale is a 92-second monody.
Work: `RN-I-001…003`, then `RN-I-004/005`. Prerequisites: Gap 2. Risks: RN8. Validation:
`NIMP-001…005`. Complete at T2 and T3.

**Gap 6: expressive notation is silently lost.** Current: dynamics, articulations, slurs,
fermatas, rehearsal marks, tuplets absent; only `lossy_dynamic_curve` and `lossy_lyrics`
reported. Desired: projected where MusicXML represents them, coded otherwise. Consequence:
the score is a pitch skeleton and the user is not told. Work: `RN-X-006…009`. Prerequisites:
Gap 3. Risks: RN10. Validation: `NXML-006…008`, `NSEM-002`. Complete at T3.

**Gap 7: no coverage contract.** Current: INTEROP.md prose and four codes; the manifest lists
five score properties and no notation directives. Desired: an `interop.coverage()` registry
generating the INTEROP matrix with a `--check` twin, lossy diagnostics derived from it,
manifest entries. Consequence: users and agents cannot know what survives export without
reading code. Work: `RN-X-010`, `RN-D-001`. Prerequisites: Gaps 3–6. Risks: none. Validation:
`NXML-011`, `NSEM-001`, `NDOC-001/002`. Complete at T3.

**Gap 8: the tuning directive is inert.** Current: accepted, stored, never read. Desired: an
interim `tuning_not_rendered` diagnostic, then an n-EDO resolver with FFT proof and
byte-identical 12-TET, then microtonal interop. Consequence: an agent that writes 19-EDO gets
12-TET and no warning. Work: `RN-T-001…003`. Prerequisites: T3 parity gate before touching
frequencies. Risks: RN4, RN12. Validation: `NTUN-001…004`. Complete at T1 (diagnostic) and T4.

**Gap 9: analysis behaviour undocumented and unreachable.** Current: ambiguity set implicit;
pitch-class-set core internal; bridge decision unrecorded. Desired: documented set with parity
test, `analyze` exposes set-class fields, ADR-0009 records the music21 stance. Work:
`RN-A-001…003`. Prerequisites: oracles (parity). Risks: RN5. Validation: `NANA-001…005`.
Complete at T3 and T5.

**Gap 10: the PDF is mislabelled; real engraving is one flag away.** Current: `score.py` says
engrave; dynamics letters warn; LilyPond path exists only by hand. Desired: proof sheet
labelled, glyphs fixed, `score --engrave` backend. Work: `RN-P-001…003`. Prerequisites:
Gap 1 (backend). Risks: RN9. Validation: `NENG-002…004`. Complete at T1 and T5.

**Gap 11: documentation and records.** Current: README silent; gap spec says closed; no ADR.
Desired: README section, corrected G6/G8 with harness IDs, ADR-0009, backlog items. Work:
`RN-D-002…005`. Prerequisites: none. Validation: `NDOC-003…005`, `NGATE-006`. Complete at T1.

**Gap 12: budgets unmeasured.** Current: timings taken by hand at T0, all comfortable.
Desired: budget tests. Work: `RN-Q-001`. Validation: `NPERF-001…004`. Complete at T5.

## 5. Architecture and evolution strategy

**Position (ADR-0009).** AudioForge owns the semantic score contract and its faithful
projection; it delegates engraving to LilyPond and musicology to music21 through that
projection. The proof sheet stays as the dependency-free view of what the engine knows that a
staff cannot show (stage, intensity, provenance), and is named accordingly.

**Components that remain.** The score fields and their 3.0 render semantics; `spec.notation`
as hash-excluded metadata; the proof sheet's layout code; the pitch-class-set core; the
evidence-based chord identity and its refusal to guess; the session bundle.

**Components that change.** `interop.export_notated_musicxml` (structure from the spec,
expressive projection, per-part polymeter), `export_musicxml` and `export_midi_bytes` (parts,
chords, tempo map), `import_musicxml` (parts, chords, voices, attribute changes, ties),
`interop_diagnostics` (derived from a coverage registry), `capabilities.py` (notation and
interop coverage entries), `score.py` (labelling, glyph font, optional LilyPond backend),
`dsl.py`/`synth.note_to_freq`/`sampler`/`plan` (tuning resolver), INTEROP.md (generated
matrix), README, DSL_GAP_SPEC.

**Components that are replaced.** None. In particular, no in-house engraver and no
music-theory reimplementation; that is the point of the starting analysis, and the plan holds
to it.

**New components.** `pyproject` extra `oracles` (and its alias `engrave`), vendored MusicXML
3.1 XSD, `tests/fixtures/notation/` corpus, `tests/test_notation_oracles.py`,
`audioforge/tools/gen_interop.py` (matrix generator with `--check`), `audioforge/tuning.py`
(n-EDO resolver), `tests/test_tuning.py`, `tests/test_notation_perf.py`, ADR-0009,
`scripts/harness-notation.sh`.

**Migration boundaries and compatibility.** Additive DSL (no new syntax is required; existing
`tuning:`, `tuplet:`, `lyrics:` gain behaviour) → DSL 2.1. The only render-affecting change is
tuning activation, and only for specs that carry a non-12-EDO directive (none exist in the
repository); the default path is proven byte-identical by the golden gate. Exporter output
changes for every spec (that is the fix), so downstream consumers of our MusicXML/MIDI see
different, correct files; the exact-tick exporter keeps its role as the interchange of record
and the notated exporter its documented quantization. Importer output changes for multi-part
files (correct parts instead of a monody). Release as engine 3.1.0 with a migration section.

**Data migration.** None; no stored data. Users re-export.

**Rollout.** Branch from `main` after 3.0.0 merges; PR per milestone or one PR gated by the
harness; oracle tests run locally until Actions execute; tag 3.1.0 at T6.

**Rollback.** Revert the tag; exporters and importer are pure functions with no persisted
state; the tuning resolver is a no-op without a directive, so reverting it changes nothing for
existing specs.

## 6. Dependency analysis

**Independent, can start on day 1.** `RN-O-001` oracles extra and XSD; `RN-O-002` fixture
corpus; `RN-O-005` runner; `RN-T-001` interim tuning diagnostic; `RN-P-001` proof-sheet
labelling; `RN-D-002` README section; `RN-D-003` gap-spec correction; `RN-D-004` ADR-0009;
`RN-D-005` backlog items. Nine items, all XS or S.

**Dependent.** Every export and import item depends on the corpus (there is nothing to judge
against otherwise); `RN-X-002…004` and `RN-X-006…009` depend on `RN-X-001` because keys,
tempi, dynamics and slurs attach to measures that must first be right; `RN-X-010` depends on
the last projected construct because a matrix describing intentions is a promise, not a
contract; `RN-I-002…005` depend on `RN-I-001` because chords and attribute changes are per
part; `RN-T-002` waits for the T3 parity gate so that frequency changes are not mixed with
structure fixes in the same evidence; `RN-T-003` depends on the resolver and on the per-part
exporters; `RN-P-003` depends on the oracles extra and on correct time signatures; `RN-O-004`
depends on the oracle tests and, externally, on the release roadmap's Actions fix.

**Enabling.** `RN-O-001`, `RN-O-002`, `RN-O-005` unlock every measurement; `RN-X-010` unlocks
the manifest and docs; `RN-D-004` fixes the positioning the README and the bridge decision
inherit.

**Blocking.** `RN-O-002` blocks all fidelity work; `RN-X-001` blocks all expressive
projection; `RN-I-001` blocks all import work.

**Parallel.** Workstreams D (docs), P (proof sheet), A (analysis) and T-001 run alongside the
critical path; within X, items 002–004 and 006–009 are parallel once 001 lands; within I, 002
and 003 are parallel once 001 lands.

**Sequential critical path.** `RN-O-001` → `RN-O-002` → `RN-X-001` → `RN-X-005` → `RN-I-001`
→ `RN-I-002` → `RN-O-003` green → `RN-X-010` → `RN-T-002` → release. Why this order: oracles
before fixtures because fixtures are judged by oracles; fixtures before exporter changes
because a fix without a fixture is untested; measure structure before parts and chords because
part-level parity is meaningless on a wrong grid; parts and chords before import because the
self round trip needs both sides; parity green before the matrix because the matrix must
describe what is; the matrix before tuning because tuning adds rows to it; tuning last because
it is the only change that touches frequencies.

## 7. Risks and decision points

- **Architectural.** RN8: the MusicXML import subset must be finite and written down, or the
  importer will forever be "almost right"; the coverage matrix is the instrument. RN11:
  polymeter has no universal MusicXML rendering; per-part time signatures where LilyPond
  accepts them, a code otherwise. RN13: the notated export is quantized by construction and
  must not be mistaken for the IR.
- **Implementation.** RN5: oracle heuristics drift; parity asserts structure (parts, measures,
  signatures, pitch multisets), not judgments. RN12: the tuning resolver must return the exact
  current expression when no directive is present; the golden gate decides.
- **Operational.** RN1 dependency weight (dev extra only); RN6 dead CI (shared with the release
  roadmap); RN9 wheel platform coverage (degrade to a hint).
- **Security.** None added: no network at runtime, no credentials; the extra is fetched at
  install like any dependency.
- **Data.** None; no stored data. Legal: RN2 (XSD under the W3C Community Final Specification
  Agreement, vendored with notice) and RN3 (public-domain chorales).
- **Performance.** All budgets pass at T0 with wide margins; the part-aware importer must not
  regress `NPERF-004`.
- **Migration.** RN4: tuning activation changes hashes only for specs that carry a directive.
- **External dependencies.** PyPI (music21, lilypond, xmlschema), the `w3c/musicxml`
  repository for the XSD (fetched once), GitHub Actions (down).

Unresolved decisions, with the recommendation:

| ID | Decision | Recommended | Alternative and cost |
|---|---|---|---|
| D1 | Tuning: implement or remove the directive? | Interim loud diagnostic now; n-EDO resolver at T4 with FFT proof; JI/temperaments/Scala stay parked | Remove `tuning:` from DSL 2.x: honest but abandons the roadmap's P1 capability |
| D2 | Release vehicle | Engine 3.1.0 / DSL 2.1 after 3.0.0 | Fold into 3.0.0: delays a release that is already gated on CI and mixes concerns |
| D3 | music21 in-process bridge | No: export MusicXML and document the workflow; results from music21 are external | Optional `analyze --musicology`: convenience, but blurs whose analysis it is |
| D4 | Engraving | Optional LilyPond backend via the wheel; proof sheet remains default | Proof sheet only (honest, less useful); in-house engraver (rejected outright) |
| D5 | Expose pitch-class-set theory through `analyze` | Yes, small and already implemented | Leave internal: a finished capability agents cannot reach |
| D6 | Exact-tick exporter | Fix parts and chords, keep as interchange of record | Deprecate: loses the only exact-timing projection |
| D7 | Oracle gate placement | Separate `make oracle-check`, loud skip without the extra, CI installs it | Inside `make check`: breaks every local gate without the extra |

## 8. Conclusion

**Recommended path.** Take the starting analysis at its word and stop competing: name the PDF
a proof sheet, put the oracles in the toolchain, and make the hand-off to LilyPond and music21
faithful. Then, and only then, make the tuning directive real.

**Why this sequencing.** The two cheapest changes remove the two falsehoods (engraving,
tuning) on day one; the oracles turn every later claim into a measurement; measure structure
must precede expressive projection because dynamics on a wrong grid are worse than none; parity
must precede frequency changes because the golden and parity gates are the only protection
against mixing a structure regression with a tuning regression.

**What must happen first.** `RN-O-001` and `RN-O-002`, with the honesty items beside them.
Nothing downstream is measurable without the oracles and a corpus.

**What can happen in parallel.** Documentation, proof-sheet labelling, the ADR, the backlog
registration and the interim tuning diagnostic: nine day-one items, none on the critical path
after T1.

**What constitutes completion.** harness-notation.md §7: one runner invocation on the tagged
3.1.0 commit with every non-waived assertion at PASS, zero unexplained failures, zero blocked
rows, and a manifest, matrix, README and ADR that agree.

**The resulting system.** An engine whose score fields compile to sound and to a MusicXML that
LilyPond engraves and music21 analyses without loss it did not declare; an importer that keeps
an ensemble an ensemble; a tuning directive that tunes; analysis that says what it knows and
declines what it cannot know; and a proof sheet that calls itself one. Not a notation
program, and not pretending to be.
