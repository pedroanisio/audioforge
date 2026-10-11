---
disclaimer:
  notice: >-
    Examples describe authored intent. Render manifests and measurements provide
    technical evidence; they do not certify musical quality.
  generated_by: "scripts/examples.py via Codex"
  date: "2026-09-06"
---

<!-- Generated from catalog.json and the adjacent DSL by scripts/examples.py docs. -->


# House 05 — around the block

The full arrangement combining every electronic production tool, with a key change, a tempo ramp and repeats; about two minutes.

[All examples](../../index.md) · [Download the complete DSL](house_05_full.af)

**Source status:** Compiles with the current engine.

**Instrument resources:** No external instrument library.

## Render and listen

Run from the repository root after installing AudioForge and any pinned libraries:

```sh
.venv/bin/python scripts/examples.py render house-05-full
.venv/bin/python scripts/examples.py gallery
```

Open `docs/examples/listen.html` in a browser. It pairs local audio with the DSL and reports missing renders. New renders go into this example's `audio/current/`; earlier audio and manifests remain in `audio/`. WAVs, MP3s, stems and detailed render evidence are local artifacts and are not included in a source-only checkout.

The render command records compilation, resource and rendering failures in `docs/examples/render-report.json`; a historical score is never silently skipped.

## DSL preview

The download above contains the full score.

```text
# house_05_full — "Around the block". The full arrangement: filter intro, talking-synth
# verse, chopped-sample drop, phased/flanged/crushed bridge and a stretched outro,
# with a key change, a tempo ramp and repeats expanding the form. ~2 minutes.
asset house_05_full { kind: soundtrack
  duration: 124s
  tempo: 124bpm, 224b=124bpm, 256b=112bpm
  key: F minor, 128b=Ab major, 192b=F minor
  meter: 4 4
  groove: swing16 0.22
  form: intro 0b for 32b, verse 32b for 32b, drop 64b for 32b, bridge 96b for 32b, verse2 128b for 32b, drop2 160b for 32b, outro 192b for 64b
  bus drums {
    gain: -1db
    fx: comp(threshold=-13, ratio=3, attack=0.004, release=0.08), saturate(amount=0.1)
  }
  bus mouth {
    gain: -60db
    fx: bandpass(1000hz, q=1.6)
    auto cutoff: 0s=600, 3s=2200, 6s=700, 9s=2800, 12s=600, 15s=1600, 18s=3200, 21s=800, 24s=600, 27s=2200, 30s=700, 33s=2800, 36s=600, 39s=1600, 42s=3200, 45s=800, 48s=600, 51s=2200, 54s=700, 57s=2800, 60s=600, 63s=1600, 66s=3200, 69s=800, 72s=600, 75s=2200, 78s=700, 81s=2800, 84s=600, 87s=1600, 90s=3200, 93s=800, 96s=600, 99s=2200, 102s=700, 105s=2800, 108s=600, 111s=1600, 114s=3200, 117s=800, 124s=600
  }
  bus robot {
    gain: -2db
    vocoder: source=bus:mouth bands=20 low=90hz high=7500hz smooth=0.005s depth=1.2 mix=0.95
    duck: source=kick amount=5db attack=0.01s release=0.2s threshold=-40db
    fx: highpass(120hz), saturate(amount=0.15), plate(decay=0.6, mix=0.22)
  }
  bus hats {
    gain: 2db
    fx: flanger(rate=0.15, depth=2, delay=1.5, feedback=0.45, mix=0.4, stereo=0.5), plate(decay=0.45, mix=0.22)
  }
  bus pads {
    gain: 2db
    duck: source=kick amount=5db attack=0.01s release=0.22s threshold=-40db
    fx: phaser(rate=0.2, depth=0.8, stages=6, feedback=0.4, center=700hz, spread=2, mix=0.5, stereo=0.5), plate(decay=0.7, mix=0.3)
  }
  bus music {
```
