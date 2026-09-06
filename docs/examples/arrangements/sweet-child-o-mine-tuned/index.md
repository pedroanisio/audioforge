---
disclaimer:
  notice: >-
    Examples describe authored intent. Render manifests and measurements provide
    technical evidence; they do not certify musical quality.
  generated_by: "scripts/examples.py via Codex"
  date: "2026-09-06"
---

<!-- Generated from catalog.json and the adjacent DSL by scripts/examples.py docs. -->


# Sweet Child o’ Mine — tuned synthesis

A tuned synthesis realization of the MIDI arrangement, retained separately from its sampled version.

[All examples](../../index.md) · [Download the complete DSL](sweet_child_o_mine.tuned.af)

**Source status:** Compiles with the current engine.

**Instrument resources:** No external instrument library.

## Render and listen

Run from the repository root after installing AudioForge and any pinned libraries:

```sh
.venv/bin/python scripts/examples.py render sweet-child-o-mine-tuned
.venv/bin/python scripts/examples.py gallery
```

Open `docs/examples/listen.html` in a browser. It pairs local audio with the DSL and reports missing renders. New renders go into this example's `audio/current/`; earlier audio and manifests remain in `audio/`. WAVs, MP3s, stems and detailed render evidence are local artifacts and are not included in a source-only checkout.

The render command records compilation, resource and rendering failures in `docs/examples/render-report.json`; a historical score is never silently skipped.

## DSL preview

The download above contains the full score.

```text
# ==========================================================================
# AudioForge DSL — TUNED arrangement (scripts/tune_scom.py)
# Source: docs/examples/arrangements/sweet-child-o-mine/inputs/sweetchildofmine.mid (import-midi -> tuned mix)
# ARCHITECTURAL REQUIREMENT (PALS's LAW): verified by compiling this DSL.
# ==========================================================================

asset sweet_child_o_mine {
  kind:       soundtrack
  duration:   274.341s
  samplerate: 48000
  bitdepth:   24
  tempo:      135.010bpm

  bus af_drums {
    gain: 0db
    fx: transient(attack=3, sustain=-1),
        comp(threshold=-13, ratio=3, attack=0.004, release=0.11, knee=4),
        peak(75hz, gain=2, q=0.9), peak(5000hz, gain=2, q=0.8)
  }

  bus af_gtr {
    gain: -1db
    fx: comp(threshold=-15, ratio=2, attack=0.012, release=0.14, knee=6),
        reverb(decay=0.8, mix=0.06)
  }

  # --- drum kit (channel 10 -> real drum voices) ---
  layer drumsnare : drums {
    voice:   snare
    gain:    -5db
    humanize: 0.12
    snap:    0.7
    bus:     af_drums
    pattern: "................................................................................................................................................................................................................................................................................x.x.x.x.x.x.X.......X.......X.......X.......X.......X.......X.......X.......X.......X.......X.......X.......X.......X.......X.....X.....X...X.......X.......X.......X.......X.......X.......X.......X.......X.......X.......X.......X.......X.......X.......X.....X.....X...X.......X.......X.......X.......X.......X.......X.......X.......X.......X.......X.......X.......X.......X.......X.....X.....X...X.......X.......X.......X.......X.......X.......X.......X.......X.......X.......X.......X.......X.......X.......X.......X.....X.........X.......X.......X.......X.......X.......X.......X.......X.......X.......X.......X.......X.......X.......X.....X.....X...X.......X.......X.......X.......X.......X.......X.......X.......X.......X.......X.......X.......X.......X.......X.....X.....X...X.......X.......X.......X.......X.......X.......X.......X.......X.......X.......X.......X.......X.......X.......X.....X.....X...X.......X.......X.......X.......X.......X.......X.......X.......X.......X.......X.......X.......X.......X.......X.......X.....X.........X.......X.......X.......X.......X.......X.......X.......X.......X.......X.......X.......X...x.x.x.x.x.x.x.x.x.x.x.x.X.X.X.......X.......X.......X.......X.......X.......X.......X.......X.......X.......X.......X.......X.......X.......X.......X.......X.......X.......X.......X.......X.......X.......X.......X.......X.......X.......X.......X.......X.......X.......X.......X.......X.......X.......X.......X.......X.......X.......X.......X.......X.......X.......X.......X.......X.......X.......X.......X.......X.......X...............X...............X...............X.......X.......X.......X.......X.......X...x.x.x.x.x.x.x.x.x.x.x.x.X.X.X.......X.......X.......X.......X.......X.......X.......X.......X.......X.......X.......X.......X.......X.......X.......X.......X.......X.......X.......X.......X.......X.......X.......X.......X.......X.......X.......X.......X.......X.......X...x..x.x..X..X.X......X.......X.......X.......X.......X.......X...x..x.x..X..X.X......X.......X.......X.......X.......X.......X...x..x.x..X..X.X......X.......X.......X.......X.......X.......X...x..x.x..X..X.X......X.......X.......X.......X.......X.......X...x..x.x..X..X.X......."
  }
```
