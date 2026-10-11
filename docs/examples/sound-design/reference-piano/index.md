---
disclaimer:
  notice: >-
    Examples describe authored intent. Render manifests and measurements provide
    technical evidence; they do not certify musical quality.
  generated_by: "scripts/examples.py via Codex"
  date: "2026-09-06"
---

<!-- Generated from catalog.json and the adjacent DSL by scripts/examples.py docs. -->


# Reference piano — baseline

A self-contained solo-piano cue rendered for the A/B against a sample-based renderer (docs/RENDER_QUALITY_COMPARISON.md); the naive baseline.

[All examples](../../index.md) · [Download the complete DSL](reference_piano.af)

**Source status:** Compiles with the current engine.

**Instrument resources:** No external instrument library.

## Render and listen

Run from the repository root after installing AudioForge and any pinned libraries:

```sh
.venv/bin/python scripts/examples.py render reference-piano
.venv/bin/python scripts/examples.py gallery
```

Open `docs/examples/listen.html` in a browser. It pairs local audio with the DSL and reports missing renders. New renders go into this example's `audio/current/`; earlier audio and manifests remain in `audio/`. WAVs, MP3s, stems and detailed render evidence are local artifacts and are not included in a source-only checkout.

The render command records compilation, resource and rendering failures in `docs/examples/render-report.json`; a historical score is never silently skipped.

## DSL preview

The download above contains the full score.

```text
# =============================================================================
# reference_piano.af — a self-contained solo-piano cue for render-quality A/B.
#
# Purpose: a deterministic, library-free keyboard piece whose AudioForge
# realization can be compared, render-for-render, against a professional
# sample-based renderer (FluidSynth + FluidR3_GM grand piano) playing the
# exact same note events exported via `audioforge export-midi`.
#
# Why piano: `export-midi` is program-agnostic (one flattened channel), so the
# professional reference is GM program 0 — a grand piano. Keeping the material
# pianistic makes that reference musically appropriate. AudioForge renders the
# same notes with its native struck-string voice (tension-modulated
# Karplus-Strong) and full master chain.
#
# 8 bars, A minor, 4/4 at 76 bpm. Three voices: a flowing right-hand melody,
# sustained left-hand triads, and a half-note bass — a terraced dynamic arc
# from p to f and back, enough polyphony and sustain to stress both renderers.
# =============================================================================

asset reference_piano {

  kind:       cue
  duration:   26s
  samplerate: 48000
  bitdepth:   24
  tempo:      76bpm
  key:        A minor

  # Right-hand melody — eighth-note line, terraced crescendo across the arc.
  layer melody : notes {
    osc:        struck
    tension:    0.0
    brightness: 0.62
    damping:    0.42
    gain:       -8db
```
