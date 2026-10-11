---
disclaimer:
  notice: >-
    Examples describe authored intent. Render manifests and measurements provide
    technical evidence; they do not certify musical quality.
  generated_by: "scripts/examples.py via Codex"
  date: "2026-09-06"
---

<!-- Generated from catalog.json and the adjacent DSL by scripts/examples.py docs. -->


# House 02 — talking synth

A bus vocoder: saw and pad chords carry the spectral envelope of a formant-swept noise bus; no voice is generated.

[All examples](../../index.md) · [Download the complete DSL](house_02_robot.af)

**Source status:** Compiles with the current engine.

**Instrument resources:** No external instrument library.

## Render and listen

Run from the repository root after installing AudioForge and any pinned libraries:

```sh
.venv/bin/python scripts/examples.py render house-02-robot
.venv/bin/python scripts/examples.py gallery
```

Open `docs/examples/listen.html` in a browser. It pairs local audio with the DSL and reports missing renders. New renders go into this example's `audio/current/`; earlier audio and manifests remain in `audio/`. WAVs, MP3s, stems and detailed render evidence are local artifacts and are not included in a source-only checkout.

The render command records compilation, resource and rendering failures in `docs/examples/render-report.json`; a historical score is never silently skipped.

## DSL preview

The download above contains the full score.

```text
# house_02_robot — "Talking synth". A vocoder bus: the saw/pad chords are the carrier,
# a hidden "mouth" bus (formant-swept noise plus a drum machine) is the modulator.
# The engine transfers the modulator's spectral envelope; nothing here is a voice.
asset house_02_robot { kind: soundtrack
  duration: 62s
  tempo: 124bpm
  key: A minor
  meter: 4 4
  groove: pushed 0.2
  form: intro 0b for 16b, talk 16b for 80b, outro 96b for 32b
  bus drums {
    fx: comp(threshold=-12, ratio=2.5, attack=0.004, release=0.09)
  }
  bus perc {
    gain: 2db
    fx: plate(decay=0.45, mix=0.25), chorus(rate=0.6, depth=3, delay=12, voices=2, mix=0.3, stereo=1)
  }
  bus mouth {
    gain: -60db
    fx: bandpass(900hz, q=1.6)
    auto cutoff: 0s=500, 2s=1800, 4s=700, 6s=2600, 8s=600, 10s=1500, 12s=3000, 14s=800, 16s=500, 18s=1800, 20s=700, 22s=2600, 24s=600, 26s=1500, 28s=3000, 30s=800, 32s=500, 34s=1800, 36s=700, 38s=2600, 40s=600, 42s=1500, 44s=3000, 46s=800, 48s=500, 50s=1800, 52s=700, 54s=2600, 56s=600, 58s=1500, 60s=3000, 62s=800
  }
  bus robot {
    gain: -1db
    vocoder: source=bus:mouth bands=20 low=90hz high=7500hz smooth=0.005s depth=1.2 mix=0.95
    duck: source=kick amount=4db attack=0.01s release=0.18s threshold=-40db
    fx: highpass(120hz), saturate(amount=0.15), chorus(rate=0.35, depth=4, delay=16, voices=3, mix=0.3, stereo=1), plate(decay=0.6, mix=0.25)
  }
  bus keys {
    gain: 0db
    duck: source=kick amount=6db attack=0.008s release=0.2s threshold=-40db
    fx: lowpass(2400hz, q=0.9), chorus(rate=0.4, depth=5, delay=18, voices=3, mix=0.45, stereo=1), plate(decay=0.5, mix=0.2)
  }
  layer kick : drums { voice: kick
    bus: drums
```
