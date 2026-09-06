---
disclaimer:
  notice: >-
    Examples describe authored intent. Render manifests and measurements provide
    technical evidence; they do not certify musical quality.
  generated_by: "scripts/examples.py via Codex"
  date: "2026-09-06"
---

<!-- Generated from catalog.json and the adjacent DSL by scripts/examples.py docs. -->


# 2030 — orchestral theme

A two-minute orchestral theme for Painting with FrameGraph, following foundation, composition, restart and refinement.

[All examples](../../index.md) · [Download the complete DSL](2030.af)

**Source status:** Compiles with the current engine.

**Instrument resources:** `VSCO-2-CE-1.1.0@ff140e8b5c5d6916ccf8088b0fc7dfb632f434d056aa764400905fdbd5824b0e`

## Render and listen

Run from the repository root after installing AudioForge and any pinned libraries:

```sh
.venv/bin/python scripts/examples.py render 2030
.venv/bin/python scripts/examples.py gallery
```

Open `docs/examples/listen.html` in a browser. It pairs local audio with the DSL and reports missing renders. New renders go into this example's `audio/current/`; earlier audio and manifests remain in `audio/`. WAVs, MP3s, stems and detailed render evidence are local artifacts and are not included in a source-only checkout.

The render command records compilation, resource and rendering failures in `docs/examples/render-report.json`; a historical score is never silently skipped.

## DSL preview

The download above contains the full score.

```text
# 2030 — theme for "Painting with FrameGraph"  (orchestral, gap-safe)
# A reading of framegraph-reconstruction-evolution-4k60.mp4 in sound.
# Voiced with the VSCO-2 Community Edition orchestra (content-addressed, pinned).
# Sustained bed = seamless synth pad; sampled strings/basses are re-bowed every
# 6 beats (VSCO sustains are non-looping ~7 s one-shots). Verified: zero
# render_plan_sustain_gap warnings.  Foundation -> Composition -> Grind ->
# Restart at v90 (A minor -> C major) -> Refinement, over an invariant clock.

asset theme_2030 {
  kind: cue
  duration: 120s
  tempo: 90bpm
  key: A minor, 120b=C major
  library: "VSCO-2-CE-1.1.0@ff140e8b5c5d6916ccf8088b0fc7dfb632f434d056aa764400905fdbd5824b0e"
  emotion: wonder=0.55, awe=0.4, tension=0.3, triumph=0.45, calm=0.35, intimacy=0.2
  intensity: 0s=0.15, 24s=0.32, 44s=0.55, 78s=0.6, 80s=0.34, 84s=0.42, 110s=0.9, 116s=0.86, 120s=0.7

  marker foundation  @ 0s
  marker composition @ 24s
  marker grind       @ 44s
  marker restart     @ 80s
  marker refinement  @ 84s
  marker final_frame @ 116s

  motif seed {
    A3 @ 0b   for 1b   vel 0.6
    C4 @ 1b   for 1b   vel 0.66
    E4 @ 2b   for 1.5b vel 0.72
    D4 @ 3.5b for 1.5b vel 0.68
  }

  # Act I underpainting: a seamless synth pad — the large, stable regions that never drop.
  layer bed : notes {
    osc: pad
    bandwidth: 55c
```
