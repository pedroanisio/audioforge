---
disclaimer:
  notice: >-
    Examples describe authored intent. Render manifests and measurements provide
    technical evidence; they do not certify musical quality.
  generated_by: "scripts/examples.py via Codex"
  date: "2026-09-06"
---

<!-- Generated from catalog.json and the adjacent DSL by scripts/examples.py docs. -->


# Reference piano — produced

The same solo-piano cue with the production choices that close the measured render-quality gap (docs/RENDER_QUALITY_COMPARISON.md).

[All examples](../../index.md) · [Download the complete DSL](reference_piano_pro.af)

**Source status:** Compiles with the current engine.

**Instrument resources:** No external instrument library.

## Render and listen

Run from the repository root after installing AudioForge and any pinned libraries:

```sh
.venv/bin/python scripts/examples.py render reference-piano-pro
.venv/bin/python scripts/examples.py gallery
```

Open `docs/examples/listen.html` in a browser. It pairs local audio with the DSL and reports missing renders. New renders go into this example's `audio/current/`; earlier audio and manifests remain in `audio/`. WAVs, MP3s, stems and detailed render evidence are local artifacts and are not included in a source-only checkout.

The render command records compilation, resource and rendering failures in `docs/examples/render-report.json`; a historical score is never silently skipped.

## DSL preview

The download above contains the full score.

```text
# =============================================================================
# reference_piano_pro.af — the fully *produced* sibling of reference_piano.af.
#
# Identical note events (same pitches, timing, velocities), so the MIDI export
# — and therefore the professional FluidR3 reference — is unchanged. Only the
# production differs, to show AudioForge already has the tools to win the
# render-quality A/B on the realism axes the naive render lost:
#
#   * Stereo image: register-split constant-power panning (bass left, treble
#     right — how a grand piano actually images) + a light decorrelated stereo
#     room. Panned DRY layers raise stereo width WITHOUT filling the silent
#     gaps, so the noise floor stays low.
#   * Warmth: lower struck-string brightness + more damping, a low-shelf for
#     foundation, and a high-shelf/low-pass to tame the synthesis fizz toward a
#     piano's spectral balance.
#   * Decay to silence: no make-up compression sustaining the floor — the
#     struck voice decays to true digital silence (synthesis has no recorded
#     noise floor to begin with).
#
# Compare:  python3 scripts/compare_render_quality.py \
#               static/samples/reference_piano_pro.af -o compare/quality_pro
# =============================================================================

asset reference_piano_pro {

  kind:       cue
  duration:   26s
  samplerate: 48000
  bitdepth:   24
  tempo:      76bpm
  key:        A minor

  # Right-hand melody — panned right, warm and singing.
  layer melody : notes {
    osc:        struck
```
