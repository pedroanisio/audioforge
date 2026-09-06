---
disclaimer:
  notice: >-
    Examples describe authored intent. Render manifests and measurements provide
    technical evidence; they do not certify musical quality.
  generated_by: "scripts/examples.py via Codex"
  date: "2026-09-06"
---

<!-- Generated from catalog.json and the adjacent DSL by scripts/examples.py docs. -->


# Ode to Fable — symphonic rewrite, revision 2

A second symphonic rewrite of Ode to Fable, focused on voice leading and musical conflict.

[All examples](../../index.md) · [Download the complete DSL](ode_to_fable_symphonic_v2.af)

**Source status:** Compiles with the current engine.

**Instrument resources:** `VSCO-2-CE-1.1.0@ff140e8b5c5d6916ccf8088b0fc7dfb632f434d056aa764400905fdbd5824b0e`

## Render and listen

Run from the repository root after installing AudioForge and any pinned libraries:

```sh
.venv/bin/python scripts/examples.py render ode-to-fable-symphonic-v2
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
# "Ode to Fable" — Symphony in D  (SYMPHONIC REWRITE, v2: voice-leading & conflict)
# for Claude Fable 5 (Anthropic), released 2026-06-09
#
# Original composition. generated_by: Claude Opus 4.8 via Claude Code · 2026-06-11
#
# v2 answers a second craft critique of the generative rewrite. The architecture
# was sound (one cell -> MYTHOS/FABLE/OPUS/FATE); this pass pursues musical
# INEVITABILITY over architecture, on seven specific points:
#   1. The development is longer and harsher — the cell is not let go.
#   2. A real ORCHESTRAL dominant build precedes IV (tremolo + the FATE rhythm on
#      A + a held A/E + bass A-pedal + woodwind fragments) -> silence -> D major.
#      (No cinematic tom roll.)
#   3. OPUS INTERRUPTS the D-major arrival once, pulling back to shadow, before
#      the major proves itself.
#   4. FABLE and MYTHOS combine into ONE explicit hybrid theme (`apotheosis`):
#      the bright cell D-F#-E-A launches the lyric fall.
#   5. Chromatic INNER LINES (violas/clarinet/bassoon) crawl through the mixture
#      region — harmony made of lines, not blocks.
#   6. D major arrives QUIETLY first (strings only); brass/bells are withheld until
#      it has been tested.
#   7. The coda CADENCE quotes the exact original rhythm (short-short-short-LONG)
#      one last time.
#
# Section times (engine beat->second integral, with rubato):
#   I 0–31s · DEV 31–56s · II 56–88s · III 88–136s · BUILD 136–145s
#   IV(quiet arrival) 145s · IV(triumph) 159s · coda 180s
# =============================================================================

asset ode_to_fable_symphonic_v2 {

  kind:       soundtrack
  duration:   208s
```
