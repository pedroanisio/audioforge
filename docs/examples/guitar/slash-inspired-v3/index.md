---
disclaimer:
  notice: >-
    Examples describe authored intent. Render manifests and measurements provide
    technical evidence; they do not certify musical quality.
  generated_by: "scripts/examples.py via Codex"
  date: "2026-09-06"
---

<!-- Generated from catalog.json and the adjacent DSL by scripts/examples.py docs. -->


# Expressive hard-rock solo

A one-minute sampled hard-rock guitar study with explicit note-scoped pitch and dynamic curves.

[All examples](../../index.md) · [Download the complete DSL](slash_inspired_v3.af)

**Source status:** Compiles with the current engine.

**Instrument resources:** `sfz-guitar-experiment@52d4a8638474a50fc675de788babe5950fccbbefa6b82b5730dfd96ca0a56c9b`

## Render and listen

Run from the repository root after installing AudioForge and any pinned libraries:

```sh
.venv/bin/python scripts/examples.py render slash-inspired-v3
.venv/bin/python scripts/examples.py gallery
```

Open `docs/examples/listen.html` in a browser. It pairs local audio with the DSL and reports missing renders. New renders go into this example's `audio/current/`; earlier audio and manifests remain in `audio/`. WAVs, MP3s, stems and detailed render evidence are local artifacts and are not included in a source-only checkout.

The render command records compilation, resource and rendering failures in `docs/examples/render-report.json`; a historical score is never silently skipped.

## DSL preview

The download above contains the full score.

```text
# Original expressive hard-rock guitar solo for AudioForge render testing.
# Uses the local CC0 Karoryfer Emilyguitar SFZ library plus explicit
# note-scoped pitch/dynamic curves for bends, vibrato, and falloffs.

asset slash_inspired_v3 {
  kind: cue
  duration: 60s
  samplerate: 48000
  bitdepth: 24
  tempo: 76bpm
  key: A minor
  groove: laidback 0.28
  perform: style=expressive_hard_rock expressivity=0.88 rubato=arch amount=0.055 segment=0.5b
  library: "sfz-guitar-experiment@52d4a8638474a50fc675de788babe5950fccbbefa6b82b5730dfd96ca0a56c9b"

  marker breath_in @ 0s
  marker first_bend @ 3.4s
  marker answer @ 11.5s
  marker climb @ 25.0s
  marker peak_hold @ 32.5s
  marker resolve @ 50.5s

  bus band {
    gain: -3db
    fx: hall(rt60=1.85, damp=0.48, mix=0.10)
  }

  layer pad : tone {
    osc: pad
    note: A2
    bandwidth: 28c
    env: a=1.8 d=0.4 s=0.70 r=2.8
    gain: -20db
    bus: band
  }
```
