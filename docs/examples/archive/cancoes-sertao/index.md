---
disclaimer:
  notice: >-
    Examples describe authored intent. Render manifests and measurements provide
    technical evidence; they do not certify musical quality.
  generated_by: "scripts/examples.py via Codex"
  date: "2026-09-06"
---

<!-- Generated from catalog.json and the adjacent DSL by scripts/examples.py docs. -->


# Canções do Sertão

Three historical movements for an eight-cello ensemble. The source retains placeholder instrument-library pins.

[All examples](../../index.md) · [Download the complete DSL](cancoes_sertao.af)

**Source status:** Historical DSL; requires migration before rendering.

**Instrument resources:** `vstocello@0000000000000000000000000000000000000000000000000000000000000000`

## Render and listen

Run from the repository root after installing AudioForge and any pinned libraries:

```sh
.venv/bin/python scripts/examples.py render cancoes-sertao
.venv/bin/python scripts/examples.py gallery
```

Open `docs/examples/listen.html` in a browser. It pairs local audio with the DSL and reports missing renders. New renders go into this example's `audio/current/`; earlier audio and manifests remain in `audio/`. WAVs, MP3s, stems and detailed render evidence are local artifacts and are not included in a source-only checkout.

The render command records compilation, resource and rendering failures in `docs/examples/render-report.json`; a historical score is never silently skipped.

## Recorded source limitations

- line 169: notes: needs its first event on the same line (continue across lines with trailing commas); play statements are layer-body lines, not notes: entries

## DSL preview

The download above contains the full score.

```text
# =============================================================================
# AudioForge DSL 1.6 · Engine 2.13.0
#
# "CANÇÕES DO SERTÃO"
# (Songs of the Backlands)
#
# An original work for Orchestra of Violoncelli
# 8 cellos in 4 stands — same forces as the Bachianas Brasileiras tradition
#
# I.   EMBOLADA    — Animato (♩ = 109)   Bb minor → D major     ~132s
# II.  MODINHA     — Andante (♩ = 63)    Eb major               ~171s
# III. CONVERSA    — Un poco animato (♩ = 96) Bb minor → Bb major ~275s
#
# COMPOSITIONAL CONCEPT
# ----------------------
# Three movements each carry a dual identity: a Brazilian popular form
# and a Bachian structural archetype, fused rather than juxtaposed.
#
# I.  EMBOLADA: rapid-fire syncopated Brazilian vocal game → Toccata energy,
#     imitative 16th-note figuration. Rhythmic cell: 3+3+2 sixteenth groupings
#     (baião/embolada feel). 8 cellos enter in staggered pairs, building
#     from a single line to a full 8-part texture, then dissolving back.
#
# II. MODINHA: sentimental Brazilian parlour song → Bach Sarabande aria.
#     Singing solo cello emerges from sustained lower-stand harmonics;
#     inner voices provide rocking 6/8 accompaniment; bass holds pedal.
#     Modal inflections (Dorian/Mixolydian) bridge the two worlds.
#
# III.CONVERSA: cello "conversation" → 4-voice fugue with Brazilian accentuation.
#     Subject is a chromatic descent in Bb minor; answer at the dominant;
#     stretto from m.55; Picardy-third Bb major resolution at the close.
#     All four stands participate as independent fugal voices.
#
# STAGE LAYOUT (antiphonal, left-to-right arc)
# Stand 1 (Celli I & II):   -20° @ 4.0m   upper melodic
```
