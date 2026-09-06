---
disclaimer:
  notice: >-
    Examples describe authored intent. Render manifests and measurements provide
    technical evidence; they do not certify musical quality.
  generated_by: "scripts/examples.py via Codex"
  date: "2026-09-06"
---

<!-- Generated from catalog.json and the adjacent DSL by scripts/examples.py docs. -->


# S06 Big View

06 — Big View / Mountain or Ocean Reveal. Everyone sees something beautiful outside. D major (the album's emotional lift). The road motif returns as the main theme, wide and bright but never harsh. 124 BPM.

[All examples](../../index.md) · [Download the complete DSL](s06_big_view.af)

**Source status:** Compiles with the current engine.

**Instrument resources:** No external instrument library.

## Render and listen

Run from the repository root after installing AudioForge and any pinned libraries:

```sh
.venv/bin/python scripts/examples.py render s06-big-view
.venv/bin/python scripts/examples.py gallery
```

Open `docs/examples/listen.html` in a browser. It pairs local audio with the DSL and reports missing renders. New renders go into this example's `audio/current/`; earlier audio and manifests remain in `audio/`. WAVs, MP3s, stems and detailed render evidence are local artifacts and are not included in a source-only checkout.

The render command records compilation, resource and rendering failures in `docs/examples/render-report.json`; a historical score is never silently skipped.

## DSL preview

The download above contains the full score.

```text
# 06 — Big View / Mountain or Ocean Reveal. Everyone sees something
# beautiful outside. D major (the album's emotional lift). The road motif
# returns as the main theme, wide and bright but never harsh. 124 BPM.
asset s06_big_view {
  kind: soundtrack
  duration: 540s
  tempo: 124bpm
  key: D major
  groove: pushed 0.12
  emotion: awe=0.7, triumph=0.6, wonder=0.5, cinematic_intensity=0.5

  marker the_reveal  @ 0s
  marker breath_taken @ 60s
  marker full_view    @ 300s
  marker held_gaze     @ 480s

  motif road {
    D5  @ 0b   for 1b   vel 0.7
    F#5 @ 1b   for 1b   vel 0.75
    A5  @ 2b   for 1b   vel 0.8
    G5  @ 3b   for 1.5b vel 0.78
    F#5 @ 4.5b for 0.5b vel 0.7
    D5  @ 5b   for 3b   vel 0.65
  }

  bus pump {
    duck: source=kick amount=5db attack=0.008s release=0.16s threshold=-36db
    fx: saturate(amount=0.1, warmth=0.24)
  }
  bus air {
    fx: delay(time=0.234, feedback=0.26, mix=0.18), hall(rt60=2.4, mix=0.2)
  }

  layer intro_riser : sweep {
    shape: saw
```
