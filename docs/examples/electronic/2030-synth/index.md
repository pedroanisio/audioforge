---
disclaimer:
  notice: >-
    Examples describe authored intent. Render manifests and measurements provide
    technical evidence; they do not certify musical quality.
  generated_by: "scripts/examples.py via Codex"
  date: "2026-09-06"
---

<!-- Generated from catalog.json and the adjacent DSL by scripts/examples.py docs. -->


# 2030 — synthesis study

A synthesis realization of the Painting with FrameGraph theme, following the same reconstruction story.

[All examples](../../index.md) · [Download the complete DSL](2030-synth.af)

**Source status:** Compiles with the current engine.

**Instrument resources:** No external instrument library.

## Render and listen

Run from the repository root after installing AudioForge and any pinned libraries:

```sh
.venv/bin/python scripts/examples.py render 2030-synth
.venv/bin/python scripts/examples.py gallery
```

Open `docs/examples/listen.html` in a browser. It pairs local audio with the DSL and reports missing renders. New renders go into this example's `audio/current/`; earlier audio and manifests remain in `audio/`. WAVs, MP3s, stems and detailed render evidence are local artifacts and are not included in a source-only checkout.

The render command records compilation, resource and rendering failures in `docs/examples/render-report.json`; a historical score is never silently skipped.

## DSL preview

The download above contains the full score.

```text
# 2030 — theme for "Painting with FrameGraph"
# A reading of framegraph-reconstruction-evolution-4k60.mp4 in sound.
# The verification clock never changes; the picture earns its detail act by act.
# Foundation -> Composition bloom -> Grind -> Restart at v90 (A minor -> C major) -> Refinement.

asset theme_2030 {
  kind: cue
  duration: 120s
  tempo: 90bpm
  key: A minor, 120b=C major
  emotion: wonder=0.55, awe=0.4, tension=0.3, triumph=0.45, calm=0.35, intimacy=0.2
  # element-count contour: coarse start, bloom, grind, dip at the restart, climb, plateau
  intensity: 0s=0.15, 24s=0.32, 44s=0.55, 78s=0.6, 80s=0.34, 84s=0.42, 110s=0.9, 116s=0.86, 120s=0.7

  marker foundation  @ 0s
  marker composition @ 24s
  marker grind       @ 44s
  marker restart     @ 80s
  marker refinement  @ 84s
  marker final_frame @ 116s

  # the seed: the single raster screenshot every trial reconstructs
  motif seed {
    A3 @ 0b   for 1b   vel 0.6
    C4 @ 1b   for 1b   vel 0.66
    E4 @ 2b   for 1.5b vel 0.72
    D4 @ 3.5b for 1.5b vel 0.68
  }

  # Act I underpainting: the large, stable, closed regions. Slow, sparse.
  layer foundation : notes {
    osc: pad
    bandwidth: 55c
    gain: -12db
    env: a=3s d=2s s=0.85 r=5s
```
