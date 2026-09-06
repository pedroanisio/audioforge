---
disclaimer:
  notice: >-
    Examples describe authored intent. Render manifests and measurements provide
    technical evidence; they do not certify musical quality.
  generated_by: "scripts/examples.py via Codex"
  date: "2026-09-06"
---

<!-- Generated from catalog.json and the adjacent DSL by scripts/examples.py docs. -->


# S09 Arrival

09 — Arrival / One Last Look Back. Tired but happy; the trip becomes a memory. Drums strip away, the road motif returns slower and warmer, then a soft struck/synth hybrid carries it to silence. Not "the party ended" — "we shared something."

[All examples](../../index.md) · [Download the complete DSL](s09_arrival.af)

**Source status:** Compiles with the current engine.

**Instrument resources:** No external instrument library.

## Render and listen

Run from the repository root after installing AudioForge and any pinned libraries:

```sh
.venv/bin/python scripts/examples.py render s09-arrival
.venv/bin/python scripts/examples.py gallery
```

Open `docs/examples/listen.html` in a browser. It pairs local audio with the DSL and reports missing renders. New renders go into this example's `audio/current/`; earlier audio and manifests remain in `audio/`. WAVs, MP3s, stems and detailed render evidence are local artifacts and are not included in a source-only checkout.

The render command records compilation, resource and rendering failures in `docs/examples/render-report.json`; a historical score is never silently skipped.

## DSL preview

The download above contains the full score.

```text
# 09 — Arrival / One Last Look Back. Tired but happy; the trip becomes a
# memory. Drums strip away, the road motif returns slower and warmer, then
# a soft struck/synth hybrid carries it to silence. Not "the party ended" —
# "we shared something."
asset s09_arrival {
  kind: soundtrack
  duration: 420s
  tempo: 90bpm
  key: A major
  emotion: calm=0.55, intimacy=0.5, wonder=0.4, triumph=0.2

  marker last_stretch  @ 0s
  marker one_more_look  @ 180s
  marker home           @ 390s

  motif road {
    A4  @ 0b   for 1b   vel 0.7
    C#5 @ 1b   for 1b   vel 0.75
    E5  @ 2b   for 1b   vel 0.8
    D5  @ 3b   for 1.5b vel 0.78
    C#5 @ 4.5b for 0.5b vel 0.7
    A4  @ 5b   for 3b   vel 0.65
  }

  layer kick : drums {
    voice: kick
    pattern: X.......X.......
    tune: -4st
    decay: 0.5
    snap: 0.25
    bend: 0.15
    gain: -13db
    humanize: 0.09
    auto gain: 0s=-13, 84s=-13, 126s=-50, 420s=-50
  }
```
