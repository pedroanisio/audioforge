---
disclaimer:
  notice: >-
    Examples describe authored intent. Render manifests and measurements provide
    technical evidence; they do not certify musical quality.
  generated_by: "scripts/examples.py via Codex"
  date: "2026-09-06"
---

<!-- Generated from catalog.json and the adjacent DSL by scripts/examples.py docs. -->


# Rock-ballad solo — historical target

An original rock-ballad solo target retained with its historical DSL and placeholder guitar-library pin.

[All examples](../../index.md) · [Download the complete DSL](slash_style_solo.af)

**Source status:** Historical DSL; requires migration before rendering.

**Instrument resources:** `singlecut-bridge-v1@0000000000000000000000000000000000000000000000000000000000000000`

## Render and listen

Run from the repository root after installing AudioForge and any pinned libraries:

```sh
.venv/bin/python scripts/examples.py render slash-style-solo
.venv/bin/python scripts/examples.py gallery
```

Open `docs/examples/listen.html` in a browser. It pairs local audio with the DSL and reports missing renders. New renders go into this example's `audio/current/`; earlier audio and manifests remain in `audio/`. WAVs, MP3s, stems and detailed render evidence are local artifacts and are not included in a source-only checkout.

The render command records compilation, resource and rendering failures in `docs/examples/render-report.json`; a historical score is never silently skipped.

## Recorded source limitations

- line 134: notes: malformed note entry or unknown note modifier near 'A4'; expected NOTE @ STARTb for DURb with supported modifiers

## Supporting material

[Historical design notes](design.md)

## DSL preview

The download above contains the full score.

```text
# =============================================================================
# GOLDEN TARGET FIXTURE — slash_style_solo.af
# Original composition in the lead-guitar idiom of a Slash-style rock ballad.
# NOT a transcription of any recorded solo. Style is the target; notes are new.
#
# Purpose: the acceptance artifact for docs/goal.md (Continuous Performance
# Curves, AF-P1/G11). Everything in this file is current DSL 1.9 surface
# EXCEPT the per-note curve sugar bend(...) / vib(...) / dyn(...), which is
# the proposed DSL 1.10 surface lowering to the goal's Required IR Contract
# (notes[].curves: pitch_cents + dynamic; note_beats basis; linear/hold/pow:k).
# See GOLDEN_FIXTURE_slash_style_solo.md for the construct-by-construct
# conformance table, the expected IR for the signature note, and gates.
#
# Library pin is a deliberate all-zeros UNBOUND PLACEHOLDER (DSL_SPEC §4):
# the catalog currently contains zero guitars; structural compile must pass,
# validate must report the placeholder distinctly, render-ready arrives with
# guitar-library onboarding (design review F5).
# =============================================================================

asset slash_style_solo {
  kind: cue
  duration: 42s
  samplerate: 48000
  bitdepth: 24
  tempo: 76bpm
  key: A minor
  groove: laidback 0.35
  # rubato is the in-repo precedent for macro -> dense explicit points [1.9]
  perform: style=cinematic expressivity=0.8 rubato=arch amount=0.10 segment=0.5b
  library: "singlecut-bridge-v1@0000000000000000000000000000000000000000000000000000000000000000"

  marker solo_start @ 1.6s
  marker climax @ 25.3s
  marker peak_hold @ 31.6s

```
