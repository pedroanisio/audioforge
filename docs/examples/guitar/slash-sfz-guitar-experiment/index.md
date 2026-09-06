---
disclaimer:
  notice: >-
    Examples describe authored intent. Render manifests and measurements provide
    technical evidence; they do not certify musical quality.
  generated_by: "scripts/examples.py via Codex"
  date: "2026-09-06"
---

<!-- Generated from catalog.json and the adjacent DSL by scripts/examples.py docs. -->


# Sampled guitar experiment

A 24-second SFZ guitar experiment with a rock-ballad backing, using the Karoryfer Emilyguitar recordings.

[All examples](../../index.md) · [Download the complete DSL](slash_sfz_guitar_experiment.af)

**Source status:** Compiles with the current engine.

**Instrument resources:** `sfz-guitar-experiment@52d4a8638474a50fc675de788babe5950fccbbefa6b82b5730dfd96ca0a56c9b`

## Render and listen

Run from the repository root after installing AudioForge and any pinned libraries:

```sh
.venv/bin/python scripts/examples.py render slash-sfz-guitar-experiment
.venv/bin/python scripts/examples.py gallery
```

Open `docs/examples/listen.html` in a browser. It pairs local audio with the DSL and reports missing renders. New renders go into this example's `audio/current/`; earlier audio and manifests remain in `audio/`. WAVs, MP3s, stems and detailed render evidence are local artifacts and are not included in a source-only checkout.

The render command records compilation, resource and rendering failures in `docs/examples/render-report.json`; a historical score is never silently skipped.

## DSL preview

The download above contains the full score.

```text
# Local SFZ guitar experiment using the CC0 Karoryfer Emilyguitar library.
# This is intentionally current DSL only: sampled guitar notes plus a simple
# rock-ballad backing bed, no proposed bend/vib/dyn sugar.

asset slash_sfz_guitar_experiment {
  kind: cue
  duration: 24s
  samplerate: 48000
  bitdepth: 24
  tempo: 96bpm
  key: A minor
  groove: laidback 0.20
  perform: style=melodic_rock expressivity=0.65 rubato=arch amount=0.035 segment=1b
  library: "sfz-guitar-experiment@52d4a8638474a50fc675de788babe5950fccbbefa6b82b5730dfd96ca0a56c9b"

  marker motif @ 0s
  marker answer @ 8s
  marker peak @ 17s

  bus band {
    gain: -2db
    fx: hall(rt60=1.5, damp=0.42, mix=0.13)
  }

  layer pad : tone {
    osc: pad
    note: A3
    bandwidth: 28c
    env: a=0.8 d=0.4 s=0.75 r=1.8
    gain: -17db
    bus: band
  }

  layer harmony : notes {
    osc: organ
```
