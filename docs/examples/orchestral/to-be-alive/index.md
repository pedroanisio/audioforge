---
disclaimer:
  notice: >-
    Examples describe authored intent. Render manifests and measurements provide
    technical evidence; they do not certify musical quality.
  generated_by: "scripts/examples.py via Codex"
  date: "2026-09-06"
---

<!-- Generated from catalog.json and the adjacent DSL by scripts/examples.py docs. -->


# To Be Alive

A two-minute orchestral cue moving from D major toward E major, with plucked textures, a synth bed and a melodic climax.

[All examples](../../index.md) · [Download the complete DSL](to_be_alive.af)

**Source status:** Compiles with the current engine.

**Instrument resources:** `VSCO-2-CE-1.1.0@ff140e8b5c5d6916ccf8088b0fc7dfb632f434d056aa764400905fdbd5824b0e`

## Render and listen

Run from the repository root after installing AudioForge and any pinned libraries:

```sh
.venv/bin/python scripts/examples.py render to-be-alive
.venv/bin/python scripts/examples.py gallery
```

Open `docs/examples/listen.html` in a browser. It pairs local audio with the DSL and reports missing renders. New renders go into this example's `audio/current/`; earlier audio and manifests remain in `audio/`. WAVs, MP3s, stems and detailed render evidence are local artifacts and are not included in a source-only checkout.

The render command records compilation, resource and rendering failures in `docs/examples/render-report.json`; a historical score is never silently skipped.

## DSL preview

The download above contains the full score.

```text
# to_be_alive — a 120 s celebration of being alive and making art.
# D major, lifting to E major at the climax. Plucky, life-affirming textures
# (harp, pizzicato, spiccato, glockenspiel) over a seamless synth pad; violins,
# horns and trumpet soar at the peak. Verified: zero render_plan_sustain_gap.

asset to_be_alive {
  kind: soundtrack
  duration: 120s
  tempo: 100bpm
  key: D major, 112b=E major
  library: "VSCO-2-CE-1.1.0@ff140e8b5c5d6916ccf8088b0fc7dfb632f434d056aa764400905fdbd5824b0e"
  emotion: wonder=0.7, awe=0.55, triumph=0.6, calm=0.4, intimacy=0.35, cinematic_intensity=0.3
  intensity: 0s=0.28, 14s=0.5, 34s=0.62, 53s=0.72, 67s=0.95, 91s=1.0, 101s=0.8, 116s=0.62

  marker dawn        @ 0s
  marker theme       @ 14.4s
  marker build       @ 52.8s
  marker climax      @ 67.2s
  marker resolution  @ 100.8s

  # the joy motif — an arch that opens upward and settles home
  motif joy {
    D4  @ 0b   for 1b   vel 0.7
    F#4 @ 1b   for 1b   vel 0.75
    A4  @ 2b   for 1b   vel 0.8
    B4  @ 3b   for 1b   vel 0.82
    A4  @ 4b   for 2b   vel 0.85
    F#4 @ 6b   for 1.5b vel 0.75
  }

  # seamless warmth — the harmonic ground that never drops
  layer bed : notes {
    osc: pad
    bandwidth: 50c
    gain: -15db
```
