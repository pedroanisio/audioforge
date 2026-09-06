---
disclaimer:
  notice: >-
    Examples describe authored intent. Render manifests and measurements provide
    technical evidence; they do not certify musical quality.
  generated_by: "scripts/examples.py via Codex"
  date: "2026-09-06"
---

<!-- Generated from catalog.json and the adjacent DSL by scripts/examples.py docs. -->


# S07 Rest Stop

07 — Rest Stop / Night Air. Gas station lights, snacks, a quiet reset. No kick. Ambient, reflective — a rest, not a mystery. D major, sparse.

[All examples](../../index.md) · [Download the complete DSL](s07_rest_stop.af)

**Source status:** Compiles with the current engine.

**Instrument resources:** No external instrument library.

## Render and listen

Run from the repository root after installing AudioForge and any pinned libraries:

```sh
.venv/bin/python scripts/examples.py render s07-rest-stop
.venv/bin/python scripts/examples.py gallery
```

Open `docs/examples/listen.html` in a browser. It pairs local audio with the DSL and reports missing renders. New renders go into this example's `audio/current/`; earlier audio and manifests remain in `audio/`. WAVs, MP3s, stems and detailed render evidence are local artifacts and are not included in a source-only checkout.

The render command records compilation, resource and rendering failures in `docs/examples/render-report.json`; a historical score is never silently skipped.

## DSL preview

The download above contains the full score.

```text
# 07 — Rest Stop / Night Air. Gas station lights, snacks, a quiet reset.
# No kick. Ambient, reflective — a rest, not a mystery. D major, sparse.
asset s07_rest_stop {
  kind: soundtrack
  duration: 420s
  tempo: 80bpm
  key: D major
  emotion: calm=0.6, intimacy=0.5, wonder=0.3

  marker pulling_in   @ 0s
  marker snacks         @ 60s
  marker stretch_legs  @ 120s
  marker quiet_stars   @ 300s

  motif road {
    D5  @ 0b   for 1b   vel 0.7
    F#5 @ 1b   for 1b   vel 0.75
    A5  @ 2b   for 1b   vel 0.8
    G5  @ 3b   for 1.5b vel 0.78
    F#5 @ 4.5b for 0.5b vel 0.7
    D5  @ 5b   for 3b   vel 0.65
  }

  layer night_air : noise {
    color: pink
    start: 0s
    duration: 420s
    gain: -40db
    env: a=6s d=0.2s s=0.9 r=6s
    fx: bandpass(1200hz), highpass(300hz)
    auto gain: 0s=-35.6, 50.4s=-45.2, 420s=-45.2
  }

  layer pad : notes {
    osc: pad
```
