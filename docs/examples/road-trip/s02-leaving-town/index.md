---
disclaimer:
  notice: >-
    Examples describe authored intent. Render manifests and measurements provide
    technical evidence; they do not certify musical quality.
  generated_by: "scripts/examples.py via Codex"
  date: "2026-09-06"
---

<!-- Generated from catalog.json and the adjacent DSL by scripts/examples.py docs. -->


# S02 Leaving Town

02 — Leaving Town. Neighborhood roads, first jokes in the car, the road motif is introduced plainly. Relaxed 98 BPM groove, bouncy warm bass.

[All examples](../../index.md) · [Download the complete DSL](s02_leaving_town.af)

**Source status:** Compiles with the current engine.

**Instrument resources:** No external instrument library.

## Render and listen

Run from the repository root after installing AudioForge and any pinned libraries:

```sh
.venv/bin/python scripts/examples.py render s02-leaving-town
.venv/bin/python scripts/examples.py gallery
```

Open `docs/examples/listen.html` in a browser. It pairs local audio with the DSL and reports missing renders. New renders go into this example's `audio/current/`; earlier audio and manifests remain in `audio/`. WAVs, MP3s, stems and detailed render evidence are local artifacts and are not included in a source-only checkout.

The render command records compilation, resource and rendering failures in `docs/examples/render-report.json`; a historical score is never silently skipped.

## DSL preview

The download above contains the full score.

```text
# 02 — Leaving Town. Neighborhood roads, first jokes in the car, the road
# motif is introduced plainly. Relaxed 98 BPM groove, bouncy warm bass.
asset s02_leaving_town {
  kind: soundtrack
  duration: 540s
  tempo: 98bpm
  key: A major
  groove: swing16 0.12
  emotion: wonder=0.5, calm=0.3, triumph=0.2

  marker neighborhood     @ 0s
  marker first_laugh      @ 60s
  marker road_motif_intro @ 180s
  marker edge_of_town     @ 480s

  motif road {
    A4  @ 0b   for 1b   vel 0.7
    C#5 @ 1b   for 1b   vel 0.75
    E5  @ 2b   for 1b   vel 0.8
    D5  @ 3b   for 1.5b vel 0.78
    C#5 @ 4.5b for 0.5b vel 0.7
    A4  @ 5b   for 3b   vel 0.65
  }

  bus pump {
    duck: source=kick amount=4.5db attack=0.01s release=0.18s threshold=-40db
    fx: saturate(amount=0.08, warmth=0.2)
  }

  layer kick : drums {
    voice: kick
    pattern: X.......X.......
    tune: -4st
    decay: 0.5
    snap: 0.35
```
