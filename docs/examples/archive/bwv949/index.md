---
disclaimer:
  notice: >-
    Examples describe authored intent. Render manifests and measurements provide
    technical evidence; they do not certify musical quality.
  generated_by: "scripts/examples.py via Codex"
  date: "2026-09-06"
---

<!-- Generated from catalog.json and the adjacent DSL by scripts/examples.py docs. -->


# BWV 949 — Fugue in A major

Fugue in A major, BWV 949. A historical transcription retained with its original DSL limitations and placeholder library identity.

[All examples](../../index.md) · [Download the complete DSL](bwv949.af)

**Source status:** Historical DSL; requires migration before rendering.

**Instrument resources:** `vstobaroque@0000000000000000000000000000000000000000000000000000000000000000`

## Render and listen

Run from the repository root after installing AudioForge and any pinned libraries:

```sh
.venv/bin/python scripts/examples.py render bwv949
.venv/bin/python scripts/examples.py gallery
```

Open `docs/examples/listen.html` in a browser. It pairs local audio with the DSL and reports missing renders. New renders go into this example's `audio/current/`; earlier audio and manifests remain in `audio/`. WAVs, MP3s, stems and detailed render evidence are local artifacts and are not included in a source-only checkout.

The render command records compilation, resource and rendering failures in `docs/examples/render-report.json`; a historical score is never silently skipped.

## Recorded source limitations

- line 176: notes: needs its first event on the same line (continue across lines with trailing commas); play statements are layer-body lines, not notes: entries

## DSL preview

The download above contains the full score.

```text
# =============================================================================
# AudioForge DSL 1.6 · Engine 2.13.0
#
# Fuge A-Dur (Fugue in A major)
# Johann Sebastian Bach (1685–1750)
# BWV 949
#
# Source: Neue Bach-Ausgabe (NBA) V/9.2, pp. 163–167
#         IMSLP ref: IMSLP948874-PMLP180814
#         Score: raster PDF — notation read visually (no extractable text layer)
#
# SCORE READING NOTES (what was directly observed, what was inferred)
# -------------------------------------------------------------------
# Observed:
#   - Key: A major (3 sharps — F#, C#, G#)
#   - Time: C (4/4)
#   - Duration: 87 measures, ending on a fermata chord (final system, p.167)
#   - Texture: 3-voice keyboard fugue (Soprano RH upper, Alto RH lower, Bass LH)
#   - "Pedal" marking visible at mm. 79 and 85 (sostenuto/organ pedal indication)
#   - Subject: ascending scalar run in 16th notes, A major, ~3 beats
#   - Stretto: visible from mm. 44-54 (overlapping entries at close distance)
#   - Final chord: sustained A-major triad with fermata
# Inferred (no explicit marking, standard Baroque practice):
#   - Tempo: ♩ ≈ 84 bpm (scholarly consensus for this character of 4/4 fugue)
#   - No ornament realization encoded (trills etc. not expanded here)
#   - Dynamic shaping follows terraced Baroque convention, not romantic arcs
# NOT encoded:
#   - Individual note pitches beyond the subject/answer/countersubject motifs
#     (87-measure 3-voice fugue; complete note encoding requires OMR or
#     manual transcription; the motif-based model approximates all entries)
# =============================================================================

asset bwv949_fuge_a_dur {

  kind:       signature
```
