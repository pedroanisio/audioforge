---
disclaimer:
  notice: >-
    Examples describe authored intent. Render manifests and measurements provide
    technical evidence; they do not certify musical quality.
  generated_by: "scripts/examples.py via Codex"
  date: "2026-09-06"
---

<!-- Generated from catalog.json and the adjacent DSL by scripts/examples.py docs. -->


# S05B Road Game Pt2

05b — Road Game / Momentum, part II. The trip becomes active again; same game continues, denser and brighter, still tasteful — not a rave.

[All examples](../../index.md) · [Download the complete DSL](s05b_road_game_pt2.af)

**Source status:** Compiles with the current engine.

**Instrument resources:** No external instrument library.

## Render and listen

Run from the repository root after installing AudioForge and any pinned libraries:

```sh
.venv/bin/python scripts/examples.py render s05b-road-game-pt2
.venv/bin/python scripts/examples.py gallery
```

Open `docs/examples/listen.html` in a browser. It pairs local audio with the DSL and reports missing renders. New renders go into this example's `audio/current/`; earlier audio and manifests remain in `audio/`. WAVs, MP3s, stems and detailed render evidence are local artifacts and are not included in a source-only checkout.

The render command records compilation, resource and rendering failures in `docs/examples/render-report.json`; a historical score is never silently skipped.

## DSL preview

The download above contains the full score.

```text
# 05b — Road Game / Momentum, part II. The trip becomes active again;
# same game continues, denser and brighter, still tasteful — not a rave.
asset s05b_road_game_pt2 {
  kind: soundtrack
  duration: 360s
  tempo: 121bpm
  key: A major
  groove: pushed 0.18
  emotion: triumph=0.5, wonder=0.3, cinematic_intensity=0.35

  marker bonus_round      @ 0s
  marker momentum_builds  @ 180s
  marker crest            @ 320s

  motif road {
    A4  @ 0b   for 1b   vel 0.7
    C#5 @ 1b   for 1b   vel 0.75
    E5  @ 2b   for 1b   vel 0.8
    D5  @ 3b   for 1.5b vel 0.78
    C#5 @ 4.5b for 0.5b vel 0.7
    A4  @ 5b   for 3b   vel 0.65
  }

  bus pump {
    duck: source=kick amount=6.5db attack=0.006s release=0.12s threshold=-37db
    fx: saturate(amount=0.12, warmth=0.22)
  }

  layer kick : drums {
    voice: kick
    pattern: X...X...X...X...
    tune: -3st
    decay: 0.45
    snap: 0.55
    bend: 0.3
```
