---
disclaimer:
  notice: >-
    No information within this document should be taken for granted. Any statement
    or premise not backed by a real logical definition or verifiable reference may
    be invalid, erroneous, or a hallucination.
  generated_by: "Claude Fable 5.1 via Claude Code"
  date: "2026-09-06"
---

# ADR-0014: n-EDO tuning resolution

**Status:** Accepted (roadmap-notation RN-T-002/RN-T-003, checkpoint T4)
**Date:** 2026-09-06
**Supersedes:** the interim `tuning_not_rendered` diagnostic introduced at T1

## Context

`tuning: edo divisions=N base=A4 hz=440` has compiled to `spec.notation.tuning` since
DSL 2.0 and was never read by any render path: a 19-EDO spec rendered in 12-TET
(`HARNESS-NTUN-001` FAIL at T0, `docs/evolution/harness-notation.md`). T1 made this
loud with a diagnostic; this decision makes it true. AF-M05 in `docs/backlog.yml` asks
for the full microtuning surface (just intonation, historical temperaments, Scala
files); this ADR delivers slice 1 — equal divisions of the octave — and fixes the
semantics the rest must respect.

## Decision

1. **Spelling follows the chain of fifths.** In N-EDO the fifth is
   `P = round(N · log2(3/2))` steps, a sharp raises by `7P − 4N` steps, and the letters
   C D E F G A B sit at `k·P mod N` for their fifths index k = 0 2 4 −1 1 3 5. This is
   the regular (meantone-family) mapping every EDO shares; for N = 12 it is 12-TET
   exactly, for N = 19 it yields the standard 19-EDO note names (C C♯ D♭ D … B C♭),
   and for N = 24 / 31 / 17 a sharp spans two steps. Reference: the regular
   temperament mapping of an EDO by its fifth (e.g. Milne, Sethares & Plamondon,
   "Isomorphic controllers and Dynamic Tuning", *Computer Music Journal* 31(4), 2007,
   doi:10.1162/comj.2007.31.4.15, §"Tuning continua"); the 19-EDO spelling matches the
   standard table (Yasser, *A Theory of Evolving Tonality*, 1932; Wikipedia "19 equal
   temperament", notation section). The letter formula is a first-principles
   consequence of the fifth being the generator.
2. **Reference pitch.** `base` (a note name) sounds at `hz`; every other note is
   `hz · 2^((steps(note) − steps(base)) / N)`.
3. **Default path untouched.** `Tuning()` (12, A4, 440) delegates to
   `synth.note_to_freq`, the single 12-TET definition, so specs without a directive
   render byte-identically (`HARNESS-NTUN-002`, `render_golden --check`).
4. **Threading.** The renderer attaches a `_tuning` sidecar to each layer next to the
   existing `_score` sidecar — only when a non-default tuning is declared — and every
   note-to-frequency site (`sequencer.render_note_track`, `performance.schedule_notes`,
   tone and grain layers in `render.py`, the plan's layer preparation) resolves through
   `tuning.freq_for(event, layer)`. The IR and its hash are unchanged; the sampler's
   fractional MIDI path already carries microtonal offsets into its resample ratio.
5. **Explicit frequencies are never retuned.** `freq_hz` (and the compile-time
   `freq:` sugar that derives one from a note) means what it says.
6. **Interchange (RN-T-003).** MusicXML exports write the decimal `<alter>` of each
   note relative to the 12-TET natural of its letter (music21 reads it as a microtonal
   accidental). MIDI exports write RPN 0 (pitch-bend sensitivity ±2 semitones) and a
   per-note pitch bend before each note-on; when a layer needs two different bends at
   once the export reports `lossy_tuning` instead of pretending. Imports round decimal
   alters to 12-TET names and list them under `_meta.import.dropped`.

## Consequences

* A spec with a non-12 `tuning:` now renders differently from 3.0.0 — it renders as
  written for the first time. No golden or shipped composition declares one.
* `tuning_not_rendered` is retired from the manifest; `HARNESS-NTUN-003` is N/A.
* Slice 2 (AF-M05: JI tables, historical temperaments, Scala import) must plug into
  `Tuning.note_to_freq` and keep decisions 3 and 5.

## Amendment (2026-10-21, engine 3.3.1)

_Amended by Claude Opus 5.5 via Claude Code._ Decision 6 claimed that music21 reads a
bare decimal `<alter>` as a microtonal accidental. That is false for the pinned music21
10.5.0: `MusicXMLImporter.xmlToPitch` builds `pitch.Accidental(alter)` when a note has no
`<accidental>` element, and that rejects any value that is not a multiple of 0.5
(`MusicXMLImportException: incorrect accidental -0.105 for pitch B4`). Given an
`<accidental>`, it keeps the written accidental and stores the decimal alter with
`setAttributeIndependently`. The oracle gate (`make oracle-check`) failed on
`microtonal_19edo` from the moment decimal alters landed. It never ran in CI until
engine 3.3.0, when the release workflow first ran it.

LilyPond has the matching limit. `musicxml2ly` spells only half- and quarter-tone
alterations (`musicexp.pitch_generic`). It truncates any other fraction toward zero with
the warning "Language does not support microtones contained in the piece". A 19-EDO
C#5 (alter 0.789) was therefore engraved as C natural.

Decision 6 now reads:

* Under a non-12-EDO tuning, both MusicXML exports keep the decimal `<alter>` (the
  sounding pitch). Every pitched note also carries `<accidental>` with its written
  spelling (`natural`, `sharp`, `flat`, …). MusicXML separates the two on purpose. 12-TET
  exports are byte-for-byte unchanged.
* `score --engrave` (`lilypond.engraving_musicxml`) engraves the written spelling, which
  is the notated export without the tuning. It reports the choice in
  `EngraveResult.tuning_note`, and the CLI prints it. The LilyPond oracle verifies that
  input, which is identical to the notated export under 12-TET
  (`tests/test_lilypond_backend.py`).
