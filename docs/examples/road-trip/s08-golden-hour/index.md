---
disclaimer:
  notice: >-
    Examples describe authored intent. Render manifests and measurements provide
    technical evidence; they do not certify musical quality.
  generated_by: "scripts/examples.py via Codex"
  date: "2026-09-06"
---

<!-- Generated from catalog.json and the adjacent DSL by scripts/examples.py docs. -->


# S08 Golden Hour

08 — Golden Hour Drive. Warm light, second wind, less machine more human. Home key returns (A major). Organic-feeling percussion, warm bass, 112 BPM.

[All examples](../../index.md) · [Download the complete DSL](s08_golden_hour.af)

**Source status:** Compiles with the current engine.

**Instrument resources:** No external instrument library.

## Render and listen

Run from the repository root after installing AudioForge and any pinned libraries:

```sh
.venv/bin/python scripts/examples.py render s08-golden-hour
.venv/bin/python scripts/examples.py gallery
```

Open `docs/examples/listen.html` in a browser. It pairs local audio with the DSL and reports missing renders. New renders go into this example's `audio/current/`; earlier audio and manifests remain in `audio/`. WAVs, MP3s, stems and detailed render evidence are local artifacts and are not included in a source-only checkout.

The render command records compilation, resource and rendering failures in `docs/examples/render-report.json`; a historical score is never silently skipped.

## DSL preview

The download above contains the full score.

```text
# 08 — Golden Hour Drive. Warm light, second wind, less machine more human.
# Home key returns (A major). Organic-feeling percussion, warm bass, 112 BPM.
asset s08_golden_hour {
  kind: soundtrack
  duration: 540s
  tempo: 112bpm
  key: A major
  groove: swing16 0.1
  emotion: calm=0.4, intimacy=0.4, wonder=0.5, triumph=0.3

  marker engine_restarts @ 0s
  marker second_wind      @ 120s
  marker warm_light       @ 360s
  marker long_shadows     @ 480s

  motif road {
    A4  @ 0b   for 1b   vel 0.7
    C#5 @ 1b   for 1b   vel 0.75
    E5  @ 2b   for 1b   vel 0.8
    D5  @ 3b   for 1.5b vel 0.78
    C#5 @ 4.5b for 0.5b vel 0.7
    A4  @ 5b   for 3b   vel 0.65
  }

  bus pump {
    duck: source=kick amount=4db attack=0.012s release=0.2s threshold=-42db
    fx: saturate(amount=0.08, warmth=0.26)
  }

  layer kick : drums {
    voice: kick
    pattern: X.......X.......
    tune: -3st
    decay: 0.55
    snap: 0.3
```
