---
disclaimer:
  notice: >-
    Examples describe authored intent. Render manifests and measurements provide
    technical evidence; they do not certify musical quality.
  generated_by: "scripts/examples.py via Codex"
  date: "2026-09-06"
---

<!-- Generated from catalog.json and the adjacent DSL by scripts/examples.py docs. -->


# House 00 — source loop

The four-bar engine-rendered loop that house_03_chop samples; rendered once to samples/house_source_loop.wav and pinned by hash.

[All examples](../../index.md) · [Download the complete DSL](house_00_source_loop.af)

**Source status:** Compiles with the current engine.

**Instrument resources:** No external instrument library.

## Render and listen

Run from the repository root after installing AudioForge and any pinned libraries:

```sh
.venv/bin/python scripts/examples.py render house-00-source-loop
.venv/bin/python scripts/examples.py gallery
```

Open `docs/examples/listen.html` in a browser. It pairs local audio with the DSL and reports missing renders. New renders go into this example's `audio/current/`; earlier audio and manifests remain in `audio/`. WAVs, MP3s, stems and detailed render evidence are local artifacts and are not included in a source-only checkout.

The render command records compilation, resource and rendering failures in `docs/examples/render-report.json`; a historical score is never silently skipped.

## DSL preview

The download above contains the full score.

```text
# house_00_source_loop — the "record" the chop track samples.
# A four-bar (16-beat, 7.742 s) disco-flavoured loop rendered by this engine (no third-party
# material): Rhodes-ish organ stabs, a plucked bass, a clap and hats. Rendered
# once, mixed to mono 16-bit as audioforge/data/samples/house_source_loop.wav; house_03_chop.af pins its sha256.
asset house_00_source_loop { kind: loop
  duration: 7.742s
  tempo: 124bpm
  key: F minor
  meter: 4 4

  layer bass : notes { osc: pluck
    gain: -8db
    notes: F2 @ 0b for 0.5b, F2 @ 1b for 0.5b, Ab2 @ 1.5b for 0.5b, F2 @ 2b for 0.5b, C3 @ 3b for 0.5b, Eb2 @ 3.5b for 0.5b,
           F2 @ 4b for 0.5b, F2 @ 5b for 0.5b, Ab2 @ 5.5b for 0.5b, F2 @ 6b for 0.5b, Bb2 @ 7b for 0.5b, C3 @ 7.5b for 0.5b,
           Db2 @ 8b for 0.5b, Db2 @ 9b for 0.5b, F2 @ 9.5b for 0.5b, Db2 @ 10b for 0.5b, Ab2 @ 11b for 0.5b, Eb2 @ 11.5b for 0.5b,
           Eb2 @ 12b for 0.5b, Eb2 @ 13b for 0.5b, G2 @ 13.5b for 0.5b, Eb2 @ 14b for 0.5b, Bb2 @ 15b for 0.5b, C3 @ 15.5b for 0.5b
    fx: lowpass(900hz, q=0.9), saturate(amount=0.2) }
  layer stabs : notes { osc: organ
    gain: -14db
    notes: F3min7 @ 0.5b for 0.5b voicing drop2, F3min7 @ 2.5b for 0.75b voicing drop2,
           F3min7 @ 4.5b for 0.5b voicing drop2, Bb3min7 @ 6.5b for 0.75b voicing drop2,
           Db3maj7 @ 8.5b for 0.5b voicing drop2, Db3maj7 @ 10.5b for 0.75b voicing drop2,
           Eb3maj7 @ 12.5b for 0.5b voicing drop2, C3min7 @ 14.5b for 1.25b voicing drop2
    env: a=0.005s d=0.12s s=0.5 r=0.08s
    fx: highpass(180hz), chorus(rate=0.6, depth=4, delay=16, voices=3, mix=0.35) }
  layer clap : drums { voice: clap
    gain: -10db
    pattern: ....x.......x... }
  layer hat : drums { voice: hat
    gain: -16db
    decay: 0.4
    pattern: ..x...x...x...x. }
  master { peak: -1db }
}
```
