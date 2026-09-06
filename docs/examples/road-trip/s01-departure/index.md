---
disclaimer:
  notice: >-
    Examples describe authored intent. Render manifests and measurements provide
    technical evidence; they do not certify musical quality.
  generated_by: "scripts/examples.py via Codex"
  date: "2026-09-06"
---

<!-- Generated from catalog.json and the adjacent DSL by scripts/examples.py docs. -->


# S01 Departure

01 — Departure / Everyone Gets In. Bags in the trunk, seatbelts, morning anticipation. No real beat yet — a warm sub heartbeat and dashboard clicks.

[All examples](../../index.md) · [Download the complete DSL](s01_departure.af)

**Source status:** Compiles with the current engine.

**Instrument resources:** No external instrument library.

## Render and listen

Run from the repository root after installing AudioForge and any pinned libraries:

```sh
.venv/bin/python scripts/examples.py render s01-departure
.venv/bin/python scripts/examples.py gallery
```

Open `docs/examples/listen.html` in a browser. It pairs local audio with the DSL and reports missing renders. New renders go into this example's `audio/current/`; earlier audio and manifests remain in `audio/`. WAVs, MP3s, stems and detailed render evidence are local artifacts and are not included in a source-only checkout.

The render command records compilation, resource and rendering failures in `docs/examples/render-report.json`; a historical score is never silently skipped.

## DSL preview

The download above contains the full score.

```text
# 01 — Departure / Everyone Gets In. Bags in the trunk, seatbelts, morning
# anticipation. No real beat yet — a warm sub heartbeat and dashboard clicks.
asset s01_departure {
  kind: soundtrack
  duration: 480s
  tempo: 84bpm
  key: A major
  emotion: calm=0.55, intimacy=0.45, wonder=0.35
  intensity: 0s=0.1, 480s=0.3

  marker ignition      @ 0s
  marker doors_close    @ 18s
  marker pulling_away   @ 240s
  marker gentle_hum     @ 420s

  motif road {
    A4  @ 0b   for 1b   vel 0.7
    C#5 @ 1b   for 1b   vel 0.75
    E5  @ 2b   for 1b   vel 0.8
    D5  @ 3b   for 1.5b vel 0.78
    C#5 @ 4.5b for 0.5b vel 0.7
    A4  @ 5b   for 3b   vel 0.65
  }

  layer heartbeat : drums {
    voice: kick
    pattern: X...............
    tune: -6st
    decay: 0.7
    snap: 0.15
    bend: 0.1
    gain: -30db
    humanize: 0.1
    auto gain: 0s=-52.5, 144s=-50, 336s=-48.8, 480s=-47.5
  }
```
