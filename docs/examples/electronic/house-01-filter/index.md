---
disclaimer:
  notice: >-
    Examples describe authored intent. Render manifests and measurements provide
    technical evidence; they do not certify musical quality.
  generated_by: "scripts/examples.py via Codex"
  date: "2026-09-06"
---

<!-- Generated from catalog.json and the adjacent DSL by scripts/examples.py docs. -->


# House 01 — filter house

A four-on-the-floor machine pumping under the kick with a resonant low-pass sweep across the form; 124 BPM, F minor.

[All examples](../../index.md) · [Download the complete DSL](house_01_filter.af)

**Source status:** Compiles with the current engine.

**Instrument resources:** No external instrument library.

## Render and listen

Run from the repository root after installing AudioForge and any pinned libraries:

```sh
.venv/bin/python scripts/examples.py render house-01-filter
.venv/bin/python scripts/examples.py gallery
```

Open `docs/examples/listen.html` in a browser. It pairs local audio with the DSL and reports missing renders. New renders go into this example's `audio/current/`; earlier audio and manifests remain in `audio/`. WAVs, MP3s, stems and detailed render evidence are local artifacts and are not included in a source-only checkout.

The render command records compilation, resource and rendering failures in `docs/examples/render-report.json`; a historical score is never silently skipped.

## DSL preview

The download above contains the full score.

```text
# house_01_filter — "Filter house". The French-house core move: a four-on-the-floor
# machine, a bus that pumps under the kick (sidechain duck), a resonant low-pass
# on the music bus and a whole-mix low-pass on the master, both swept open and
# closed across the form. 124 bpm, F minor.
asset house_01_filter { kind: soundtrack
  duration: 62s
  tempo: 124bpm
  key: F minor
  meter: 4 4
  groove: swing16 0.25
  form: intro 0b for 32b, groove 32b for 64b, outro 96b for 32b
  bus drums {
    gain: -1db
    fx: comp(threshold=-14, ratio=3, attack=0.005, release=0.08), saturate(amount=0.12)
  }
  bus perc {
    gain: -1db
    fx: plate(decay=0.45, mix=0.25), chorus(rate=0.6, depth=3, delay=12, voices=2, mix=0.3, stereo=1)
  }
  bus music {
    gain: -2db
    duck: source=kick amount=7db attack=0.008s release=0.22s threshold=-42db
    fx: lowpass(600hz, q=3.0), saturate(amount=0.18, warmth=0.4), chorus(rate=0.5, depth=4, delay=14, voices=3, mix=0.3, stereo=1), plate(decay=0.5, mix=0.28)
    auto cutoff: 0s=500, 15s=1400, 31s=6000, 47s=12000, 55s=1600, 62s=400
  }
  layer kick : drums { voice: kick
    bus: drums
    gain: -3db
    tune: -2st
    decay: 0.55
    snap: 0.6
    pattern: x...x...x...x... }
  layer clap : drums { voice: clap
    bus: perc
    gain: -12db
```
