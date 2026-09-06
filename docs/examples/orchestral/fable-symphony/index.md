---
disclaimer:
  notice: >-
    Examples describe authored intent. Render manifests and measurements provide
    technical evidence; they do not certify musical quality.
  generated_by: "scripts/examples.py via Codex"
  date: "2026-09-06"
---

<!-- Generated from catalog.json and the adjacent DSL by scripts/examples.py docs. -->


# Fable Symphony — synthesis

The original four-movement Fable Symphony in C, using synthesis. Its historical DSL is retained for study.

[All examples](../../index.md) · [Download the complete DSL](fable_symphony.af)

**Source status:** Historical DSL; requires migration before rendering.

**Instrument resources:** No external instrument library.

## Render and listen

Run from the repository root after installing AudioForge and any pinned libraries:

```sh
.venv/bin/python scripts/examples.py render fable-symphony
.venv/bin/python scripts/examples.py gallery
```

Open `docs/examples/listen.html` in a browser. It pairs local audio with the DSL and reports missing renders. New renders go into this example's `audio/current/`; earlier audio and manifests remain in `audio/`. WAVs, MP3s, stems and detailed render evidence are local artifacts and are not included in a source-only checkout.

The render command records compilation, resource and rendering failures in `docs/examples/render-report.json`; a historical score is never silently skipped.

## Recorded source limitations

- fable_symphony: spec.layers[1].notes[95].curves[0].points[0]: pitch_cents value 2400.000062 outside +/-2400

## DSL preview

The download above contains the full score.

```text
# =============================================================================
# AudioForge DSL 1.7 · Engine 2.14.0
#
# "Fable" — Symphony in C, in four movements
# An ode to Anthropic Fable
#
# Original composition (not a transcription of any existing score).
# generated_by: Claude Opus 4.8 via Claude Code
# date: 2026-06-11
#
# This is a SYNTHESIS-ONLY realization: every voice is a built-in NumPy
# oscillator (sine / saw / triangle / pad / organ / pluck / modal). No sampled
# `instrument:` layers, no `library:` pin, no native-kernel voices
# (bowed/blown/brass/struck/sympathetic) — so it renders deterministically on
# any machine with numpy + scipy, no C compiler, no content library.
#
# DESIGN
# ------
# One germinal "fable_theme" (a rising, story-telling line in C major) is
# stated, questioned, played-with, and finally apotheosized across four
# movements, developed by the engine's compile-time transforms
# (transpose / diatonic / invert / retrograde / stretch).
#
#   I.   The Kindling             — Allegro    (C major, bright)
#   II.  The Listening            — Adagio     (A-minor colour, contemplative)
#   III. The Play of Counterpoint — Scherzo    (diminution + a counter-voice)
#   IV.  Fable, Entire            — Maestoso    (C major, full ensemble, apotheosis)
#
# Tempo held at 100 bpm (1 beat = 0.6 s) so beat->second mapping is linear and
# the movement boundaries below are exact.
#
# DSL NOTE: `notes:` is an inline comma-separated event list whose first event
# sits on the `notes:` line; `play <motif>` statements are standalone body
# lines (no `notes:` header). Both may appear in one layer body.
# =============================================================================
```
