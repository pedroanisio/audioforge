---
disclaimer:
  notice: >-
    No information within this document should be taken for granted. Any statement
    or premise not backed by a real logical definition or verifiable reference may
    be invalid, erroneous, or a hallucination.
  generated_by: "Claude Fable 5.1 via Claude Code"
  date: "2026-09-06"
---

# ADR-0009: Notation is a semantic contract with oracle-verified interchange

- **Status:** Accepted (branch `feat/notation-interchange`, engine 3.1 line)
- **Date:** 2026-09-06

## Context

AudioForge carries score fields (`meter`, `pickup`, `form`, `repeat`, `polymeter`),
notation metadata (`tuning`, `tuplet`, `lyrics`), MIDI and MusicXML import/export, an
evidence-based harmony analysis with a pitch-class-set core, and a matplotlib PDF drawn by
the `score` verb. Measured against external oracles on 2026-09-06
(`docs/evolution/harness-notation.md` §4): the notated MusicXML export is schema-valid, read
by music21 with the right part and measure structure, and engraved by LilyPond with zero
warnings; but the same exporter hard-codes the beat unit and drops key and tempo changes,
dynamics, slurs, pickup and holds; the exact-tick and MIDI exports flatten parts and chords;
the importer flattens a four-voice chorale into one line; the tuning directive compiles and
is never read. music21 and LilyPond are far ahead for musicology and engraving and will
stay ahead.

## Decision

1. AudioForge owns the **semantic score contract**: every score and notation construct has
   a declared projection per interchange format, one of `preserved`, `quantized`,
   `lossy` (with a registered diagnostic code) or `unsupported` (with a code). The registry
   `audioforge.interop.coverage()` is the single source; `docs/INTEROP.md` carries its
   generated matrix with a `--check` twin; `interop_diagnostics()` derives from it. Silence
   on a dropped construct is a defect.
2. **Interchange is judged by the oracles**, not by our own reader: the MusicXML 3.1 XSD
   (validity), music21 (structural parity: parts, measures, time and key signatures, pitch
   multisets, durations, tempo marks) and LilyPond (engraving with zero warnings). They are
   a development extra (`.[oracles]`), never a runtime dependency, and `make oracle-check`
   skips loudly without them.
3. **Engraving is delegated.** The matplotlib PDF is a *proportional proof sheet* that shows
   what the engine knows and a staff cannot (stage, intensity, provenance); it is named so
   everywhere. Real engraving is `audioforge score --engrave`, which runs `musicxml2ly` and
   `lilypond` from the `lilypond` wheel when installed and otherwise says how to install it.
4. **Musicology is delegated.** AudioForge states what its analysis knows (chord identity
   from evidence, declared ambiguity for symmetric and relative collections, conservative
   cadence candidates, pitch-class-set operations) and parity-checks the chord roots against
   music21. It does not implement key finding, roman-numeral analysis or stylistic judgment,
   and it does not call music21 in-process: users export MusicXML and analyse there
   (decision D3 of the plan).
5. **The tuning directive must be honest, then real.** Until the resolver lands, a non-12-EDO
   `tuning:` compiles with the registered diagnostic `tuning_not_rendered`. The n-EDO
   resolver (`audioforge/tuning.py`) then drives every pitch-to-frequency path, proven by an
   FFT assertion, with the default path byte-identical (golden gate). Just intonation,
   historical temperaments and Scala import remain AF-M05 backlog work.

## Consequences

Exporter output changes for every spec (structure now comes from the spec) and importer output
changes for multi-part files; both are corrections and ship as engine 3.1.0 / DSL 2.1 with a
migration note. The `oracles` extra adds about 60 MB of development dependencies and a vendored
W3C schema. The proof sheet loses the word "engrave". Harness rows: `HARNESS-NDOC-005`,
`HARNESS-NANA-005`, and the NXML/NIMP/NENG/NTUN families that this record governs.
