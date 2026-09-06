---
disclaimer:
  notice: >-
    Examples describe authored intent. Render manifests and measurements provide
    technical evidence; they do not certify musical quality.
  generated_by: "scripts/examples.py via Codex"
  date: "2026-09-06"
---

<!-- Generated from catalog.json and the adjacent DSL by scripts/examples.py docs. -->


# The Last 24 Hours

A ten-minute techno arc at 128 BPM in A minor: groove, breakdown, drop, uplift and return.

[All examples](../../index.md) · [Download the complete DSL](last_24h.af)

**Source status:** Compiles with the current engine.

**Instrument resources:** No external instrument library.

## Render and listen

Run from the repository root after installing AudioForge and any pinned libraries:

```sh
.venv/bin/python scripts/examples.py render last-24h
.venv/bin/python scripts/examples.py gallery
```

Open `docs/examples/listen.html` in a browser. It pairs local audio with the DSL and reports missing renders. New renders go into this example's `audio/current/`; earlier audio and manifests remain in `audio/`. WAVs, MP3s, stems and detailed render evidence are local artifacts and are not included in a source-only checkout.

The render command records compilation, resource and rendering failures in `docs/examples/render-report.json`; a historical score is never silently skipped.

## DSL preview

The download above contains the full score.

```text
# last_24h — a 10-minute techno arc of the last day in the codebase.
# 128 BPM · A minor · four-on-the-floor, sidechained bass, acid, stabs, lead.
# boot → groove → build → the bug (breakdown) → the fix (drop) → the joy
# (uplift) → tools & cover (breakdown) → the concept paper (climax) → committed.

asset last_24h {
  kind: soundtrack
  duration: 600s
  tempo: 128bpm
  key: A minor
  groove: swing16 0.18
  emotion: urgency=0.5, triumph=0.45, cinematic_intensity=0.5, wonder=0.3

  marker boot       @ 0s
  marker groove     @ 60s
  marker build      @ 150s
  marker the_bug    @ 210s
  marker the_fix    @ 270s
  marker the_joy    @ 330s
  marker the_tools  @ 420s
  marker the_paper  @ 480s
  marker committed  @ 570s

  # sidechain bus — the techno pump: bass, stabs and pad ducked by the kick
  bus pump {
    duck: source=kick amount=7db attack=0.006s release=0.15s threshold=-42db
    fx: saturate(amount=0.12, warmth=0.2)
  }
  # shared space for stabs and lead
  bus air {
    fx: delay(time=0.234, feedback=0.28, mix=0.16), hall(rt60=1.8, mix=0.12)
  }

  # --- drums ---------------------------------------------------------------
  layer kick : drums {
```
