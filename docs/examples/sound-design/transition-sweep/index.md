---
disclaimer:
  notice: >-
    Examples describe authored intent. Render manifests and measurements provide
    technical evidence; they do not certify musical quality.
  generated_by: "scripts/examples.py via Codex"
  date: "2026-09-06"
---

<!-- Generated from catalog.json and the adjacent DSL by scripts/examples.py docs. -->


# Transition sweep

A two-second rising transition with a cut marker; the self-contained quick-start example.

[All examples](../../index.md) · [Download the complete DSL](transition_sweep.af)

**Source status:** Compiles with the current engine.

**Instrument resources:** No external instrument library.

## Render and listen

Run from the repository root after installing AudioForge and any pinned libraries:

```sh
.venv/bin/python scripts/examples.py render transition-sweep
.venv/bin/python scripts/examples.py gallery
```

Open `docs/examples/listen.html` in a browser. It pairs local audio with the DSL and reports missing renders. New renders go into this example's `audio/current/`; earlier audio and manifests remain in `audio/`. WAVs, MP3s, stems and detailed render evidence are local artifacts and are not included in a source-only checkout.

The render command records compilation, resource and rendering failures in `docs/examples/render-report.json`; a historical score is never silently skipped.

## DSL preview

The download above contains the full score.

```text
asset transition_sweep {
  kind: transition
  duration: 2s
  tempo: 120bpm
  marker cut_point @ 1s
  layer riser : sweep {
    shape: sine
    from: 220hz
    to: 1760hz
    duration: 2s
    gain: -14db
    env: a=0.02s d=0.1s s=0.8 r=0.1s
  }
  layer pulse : drums {
    voice: kick
    pattern: x...
    gain: -12db
  }
  layer air : noise {
    color: white
    duration: 2s
    gain: -28db
    env: a=0.01s d=0.2s s=0.6 r=0.2s
  }
  master {
    peak: -1db
  }
}
```
