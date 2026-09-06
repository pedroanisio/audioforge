---
disclaimer:
  notice: >-
    Examples describe authored intent. Render manifests and measurements provide
    technical evidence; they do not certify musical quality.
  generated_by: "scripts/examples.py via Codex"
  date: "2026-09-06"
---

<!-- Generated from catalog.json and the adjacent DSL by scripts/examples.py docs. -->


# Fable Symphony — orchestra

An orchestral realization of the four-movement Fable Symphony in C using the pinned VSCO Community Edition library.

[All examples](../../index.md) · [Download the complete DSL](fable_symphony_orchestral.af)

**Source status:** Compiles with the current engine.

**Instrument resources:** `VSCO-2-CE-1.1.0@ff140e8b5c5d6916ccf8088b0fc7dfb632f434d056aa764400905fdbd5824b0e`

## Render and listen

Run from the repository root after installing AudioForge and any pinned libraries:

```sh
.venv/bin/python scripts/examples.py render fable-symphony-orchestral
.venv/bin/python scripts/examples.py gallery
```

Open `docs/examples/listen.html` in a browser. It pairs local audio with the DSL and reports missing renders. New renders go into this example's `audio/current/`; earlier audio and manifests remain in `audio/`. WAVs, MP3s, stems and detailed render evidence are local artifacts and are not included in a source-only checkout.

The render command records compilation, resource and rendering failures in `docs/examples/render-report.json`; a historical score is never silently skipped.

## DSL preview

The download above contains the full score.

```text
# =============================================================================
# AudioForge DSL 1.7 · Engine 2.14.0
#
# "Fable" — Symphony in C, in four movements  (ORCHESTRAL realization)
# An ode to Anthropic Fable
#
# Original composition (not a transcription of any existing score).
# generated_by: Claude Opus 4.8 via Claude Code
# date: 2026-06-11
#
# Scored for the full Versilian Studios Chamber Orchestra, Community Edition
# (VSCO-2-CE, CC0 / public-domain sample set), resolved on disk:
#     library: vsco2-ce @ 97beb25c…
# Sampled sections: violins / violas / cellos / contrabasses (sus, spiccato,
# pizzicato), flute, oboe, clarinet, bassoon, French horn, trumpet, tuba,
# timpani, glockenspiel, tubular bells, and harp.
#
# Same germinal `fable_theme` as the synthesis version, now distributed across
# the orchestra and developed with the engine's compile-time transforms
# (transpose / diatonic / invert / retrograde / stretch).
#
#   I.   The Kindling             — Allegro    trumpet fanfare, strings, timpani
#   II.  The Listening            — Adagio     solo oboe over hushed strings
#   III. The Play of Counterpoint — Scherzo    spiccato strings, pizz bass, winds
#   IV.  Fable, Entire            — Maestoso    full tutti, horns, bells, organ-weight
#
# Tempo held at 100 bpm (1 beat = 0.6 s); movement boundaries are exact.
# Each VSCO instrument exposes a single 'sustain' articulation — pizz/spic
# timbres are SEPARATE instruments (ViolinEnsPizz, ViolinEnsSpic, …), so the
# articulation is chosen by instrument, not by per-note `art`.
# =============================================================================

asset fable_symphony_orchestral {

  kind:       soundtrack
```
