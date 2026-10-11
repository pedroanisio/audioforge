---
disclaimer:
  notice: >-
    Examples describe authored intent. Render manifests and measurements provide
    technical evidence; they do not certify musical quality.
  generated_by: "scripts/examples.py via Codex"
  date: "2026-09-06"
---

<!-- Generated from catalog.json and the adjacent DSL by scripts/examples.py docs. -->


# House 04 — phase & flange

The modulation family on arpeggios: phaser pad, flanger hats, chorus keys, a bit-crushed breakdown and a tape lead.

[All examples](../../index.md) · [Download the complete DSL](house_04_phase.af)

**Source status:** Compiles with the current engine.

**Instrument resources:** No external instrument library.

## Render and listen

Run from the repository root after installing AudioForge and any pinned libraries:

```sh
.venv/bin/python scripts/examples.py render house-04-phase
.venv/bin/python scripts/examples.py gallery
```

Open `docs/examples/listen.html` in a browser. It pairs local audio with the DSL and reports missing renders. New renders go into this example's `audio/current/`; earlier audio and manifests remain in `audio/`. WAVs, MP3s, stems and detailed render evidence are local artifacts and are not included in a source-only checkout.

The render command records compilation, resource and rendering failures in `docs/examples/render-report.json`; a historical score is never silently skipped.

## DSL preview

The download above contains the full score.

```text
# house_04_phase — "Phase & flange". The modulation family on arpeggios: phaser on the
# pad, flanger on the hats, chorus on the keys, a bit-crushed breakdown, a synth
# lead through the tape kernel, everything pumping under the kick.
asset house_04_phase { kind: soundtrack
  duration: 62s
  tempo: 124bpm
  key: D minor, 64b=F major
  meter: 4 4
  groove: swing16 0.15
  form: intro 0b for 16b, arps 16b for 48b, breakdown 64b for 32b, outro 96b for 32b
  bus drums {
    fx: comp(threshold=-12, ratio=3, attack=0.004, release=0.08)
  }
  bus arps {
    gain: -2db
    duck: source=kick amount=6db attack=0.008s release=0.2s threshold=-40db
    fx: lowpass(5000hz, q=1.0), saturate(amount=0.1), chorus(rate=0.7, depth=6, delay=20, voices=4, mix=0.35, stereo=1)
    auto cutoff: 0s=1200, 16s=5000, 62s=6000
  }
  bus hats {
    gain: 2db
    fx: flanger(rate=0.18, depth=2.5, delay=1.5, feedback=0.55, mix=0.5, stereo=0.5), plate(decay=0.45, mix=0.22)
  }
  bus pads {
    gain: 2db
    duck: source=kick amount=5db attack=0.01s release=0.22s threshold=-40db
    fx: phaser(rate=0.22, depth=0.85, stages=6, feedback=0.45, center=700hz, spread=2.2, mix=0.55, stereo=0.5), plate(decay=0.7, mix=0.3)
  }
  bus crush {
    gain: -4db
    duck: source=kick amount=5db attack=0.01s release=0.2s threshold=-40db
    fx: bitcrush(bits=5, downsample=4, mix=0.85), lowpass(3000hz, q=1.4), plate(decay=0.5, mix=0.25)
  }
  layer kick : drums { voice: kick
    bus: drums
```
