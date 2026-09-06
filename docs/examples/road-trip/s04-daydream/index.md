---
disclaimer:
  notice: >-
    Examples describe authored intent. Render manifests and measurements provide
    technical evidence; they do not certify musical quality.
  generated_by: "scripts/examples.py via Codex"
  date: "2026-09-06"
---

<!-- Generated from catalog.json and the adjacent DSL by scripts/examples.py docs. -->


# S04 Daydream

04 — Window Seat Daydream. Clouds, fields, distant hills. Drums lighten; bell synths and a childlike (not childish) melody carry the section.

[All examples](../../index.md) · [Download the complete DSL](s04_daydream.af)

**Source status:** Compiles with the current engine.

**Instrument resources:** No external instrument library.

## Render and listen

Run from the repository root after installing AudioForge and any pinned libraries:

```sh
.venv/bin/python scripts/examples.py render s04-daydream
.venv/bin/python scripts/examples.py gallery
```

Open `docs/examples/listen.html` in a browser. It pairs local audio with the DSL and reports missing renders. New renders go into this example's `audio/current/`; earlier audio and manifests remain in `audio/`. WAVs, MP3s, stems and detailed render evidence are local artifacts and are not included in a source-only checkout.

The render command records compilation, resource and rendering failures in `docs/examples/render-report.json`; a historical score is never silently skipped.

## DSL preview

The download above contains the full score.

```text
# 04 — Window Seat Daydream. Clouds, fields, distant hills. Drums lighten;
# bell synths and a childlike (not childish) melody carry the section.
asset s04_daydream {
  kind: soundtrack
  duration: 540s
  tempo: 100bpm
  key: A major
  groove: laidback 0.25
  emotion: wonder=0.7, calm=0.4, intimacy=0.3

  marker window_gaze    @ 0s
  marker clouds_drift    @ 180s
  marker distant_hills   @ 360s
  marker second_thought  @ 480s

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
    pattern: X.......x.......
    tune: -3st
    decay: 0.55
    snap: 0.2
    bend: 0.1
    gain: -24db
    humanize: 0.07
    auto gain: 0s=-34.4, 189s=-39.6, 351s=-39.6, 540s=-34.4
  }
```
