---
disclaimer:
  notice: >-
    Examples describe authored intent. Render manifests and measurements provide
    technical evidence; they do not certify musical quality.
  generated_by: "scripts/examples.py via Codex"
  date: "2026-09-06"
---

<!-- Generated from catalog.json and the adjacent DSL by scripts/examples.py docs. -->


# House 03 — chop shop

The sampling workflow on the engine's own loop: slices re-sequenced by pattern, reversed, time-stretched and bit-crushed.

[All examples](../../index.md) · [Download the complete DSL](house_03_chop.af)

**Source status:** Compiles with the current engine.

**Instrument resources:** No external instrument library.

## Render and listen

Run from the repository root after installing AudioForge and any pinned libraries:

```sh
.venv/bin/python scripts/examples.py render house-03-chop
.venv/bin/python scripts/examples.py gallery
```

Open `docs/examples/listen.html` in a browser. It pairs local audio with the DSL and reports missing renders. New renders go into this example's `audio/current/`; earlier audio and manifests remain in `audio/`. WAVs, MP3s, stems and detailed render evidence are local artifacts and are not included in a source-only checkout.

The render command records compilation, resource and rendering failures in `docs/examples/render-report.json`; a historical score is never silently skipped.

## DSL preview

The download above contains the full score.

```text
# house_03_chop — "Chop shop". The sampling workflow: the engine's own rendered loop
# (audioforge/data/samples/house_source_loop.wav, pinned by hash) is cut into slices, re-sequenced
# by pattern digits, reversed, time-stretched at constant pitch and bit-crushed.
asset house_03_chop { kind: soundtrack
  duration: 62s
  tempo: 124bpm
  key: F minor
  meter: 4 4
  groove: swing16 0.2
  form: intro 0b for 16b, chop 16b for 80b, outro 96b for 32b
  bus drums {
    fx: comp(threshold=-12, ratio=3, attack=0.004, release=0.08), saturate(amount=0.1)
  }
  bus perc {
    gain: 2db
    fx: plate(decay=0.45, mix=0.25), chorus(rate=0.6, depth=3, delay=12, voices=2, mix=0.3, stereo=1)
  }
  bus chops {
    gain: -2db
    duck: source=kick amount=6db attack=0.008s release=0.2s threshold=-40db
    fx: lowpass(6000hz, q=0.8), saturate(amount=0.12), chorus(rate=0.5, depth=4, delay=14, voices=3, mix=0.45, stereo=1), plate(decay=0.4, mix=0.22)
    auto cutoff: 0s=900, 8s=6000, 31s=8000, 40s=1500, 47s=7000, 62s=700
  }
  layer kick : drums { voice: kick
    bus: drums
    gain: -3db
    decay: 0.5
    snap: 0.6
    pattern: x...x...x...x... }
  layer clap : drums { voice: clap
    bus: perc
    gain: -13db
    pan: -0.35
    pattern: ....x.......x... }
  layer hat : drums { voice: hat
```
