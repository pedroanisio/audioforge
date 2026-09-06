---
disclaimer:
  notice: >-
    Examples describe authored intent. Render manifests and measurements provide
    technical evidence; they do not certify musical quality.
  generated_by: "scripts/examples.py via Codex"
  date: "2026-09-06"
---

<!-- Generated from catalog.json and the adjacent DSL by scripts/examples.py docs. -->


# Unser Leben ist ein Schatten

A historical double-choir motet score retained as a notation and diagnostic example, with an unresolved library pin.

[All examples](../../index.md) · [Download the complete DSL](unser_leben.af)

**Source status:** Historical DSL; requires migration before rendering.

**Instrument resources:** `vstochoral@0000000000000000000000000000000000000000000000000000000000000000`

## Render and listen

Run from the repository root after installing AudioForge and any pinned libraries:

```sh
.venv/bin/python scripts/examples.py render unser-leben
.venv/bin/python scripts/examples.py gallery
```

Open `docs/examples/listen.html` in a browser. It pairs local audio with the DSL and reports missing renders. New renders go into this example's `audio/current/`; earlier audio and manifests remain in `audio/`. WAVs, MP3s, stems and detailed render evidence are local artifacts and are not included in a source-only checkout.

The render command records compilation, resource and rendering failures in `docs/examples/render-report.json`; a historical score is never silently skipped.

## Recorded source limitations

- line 140: notes: needs its first event on the same line (continue across lines with trailing commas); play statements are layer-body lines, not notes: entries

## DSL preview

The download above contains the full score.

```text
# =============================================================================
# AudioForge DSL 1.6 · Engine 2.13.0
#
# "Unser Leben ist ein Schatten"
# Johann Bach (1604–1673)
# Double-choir motet for CCAT + ATTB  |  Bb minor  |  ~125 measures
#
# Source: Hofmeister edition of 1823 (SLUB Dresden, Ref: Pl.-Nr. 906),
#         transcribed by Rémy Claverie — CC BY-SA
#         IMSLP ref: IMSLP404011-PMLP654264
#
# MAPPING NOTES
# -------------
# 1. Instrument voices: `bowed` voices require a C compiler at render time
#    (native kernel). If unavailable, the engine will refuse loudly — substitute
#    `pad` or `organ` as synthetic fallbacks and note the change in the manifest.
# 2. The stage block uses the bundled St Albans IR (CC BY 4.0; attribution
#    required — see samples/stalbans_ortf_ir.ATTRIBUTION.txt).
# 3. No note-level pitch data is encoded here. The score's music notation
#    symbols are not recoverable from the PDF text layer (LilyPond CID glyphs);
#    this composition maps structural, timbral, emotional, and lyric metadata
#    faithfully. Full note encoding requires manual transcription from the
#    printed score or an OMR pipeline (e.g. Audiveris).
# 4. Two representative motifs ARE encoded from the score's legible lyric
#    syllable rhythm (syllabic mapping → rhythm approximation in beats).
# 5. The `library:` pin below is a placeholder SHA-256. Replace with the
#    actual manifest hash of your choral library before compiling.
# =============================================================================

asset unser_leben_ein_schatten {

  kind:       signature
  duration:   250s                       # 125 measures × 4/4 at 120 bpm
  samplerate: 48000
  bitdepth:   24
```
