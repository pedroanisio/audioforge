---
disclaimer:
  notice: >-
    Examples describe authored intent. Render manifests and measurements provide
    technical evidence; they do not certify musical quality.
  generated_by: "scripts/examples.py via Codex"
  date: "2026-09-06"
---

<!-- Generated from catalog.json and the adjacent DSL by scripts/examples.py docs. -->


# Fable Symphony — orchestra, revision 2

The second orchestral realization of Fable Symphony, retained alongside its earlier versions.

[All examples](../../index.md) · [Download the complete DSL](fable_symphony_orchestral_v2.af)

**Source status:** Compiles with the current engine.

**Instrument resources:** `VSCO-2-CE-1.1.0@ff140e8b5c5d6916ccf8088b0fc7dfb632f434d056aa764400905fdbd5824b0e`

## Render and listen

Run from the repository root after installing AudioForge and any pinned libraries:

```sh
.venv/bin/python scripts/examples.py render fable-symphony-orchestral-v2
.venv/bin/python scripts/examples.py gallery
```

Open `docs/examples/listen.html` in a browser. It pairs local audio with the DSL and reports missing renders. New renders go into this example's `audio/current/`; earlier audio and manifests remain in `audio/`. WAVs, MP3s, stems and detailed render evidence are local artifacts and are not included in a source-only checkout.

The render command records compilation, resource and rendering failures in `docs/examples/render-report.json`; a historical score is never silently skipped.

## DSL preview

The download above contains the full score.

```text
# =============================================================================
# AudioForge DSL 1.7 · Engine 2.14.0
#
# "Fable" — Symphony in C, in four movements  (ORCHESTRAL realization, v2)
# An ode to Anthropic Fable
#
# Original composition. generated_by: Claude Opus 4.8 via Claude Code · 2026-06-11
#
# v2 closes the self-inflicted polish gaps of v1 by USING the DSL features I
# had skipped — each verified against the engine before writing:
#   • SPATIALIZATION — a real `stage{}` (St Albans Lady Chapel IR) with every
#       section `seat:`-placed by azimuth + distance. (seat and bus are mutually
#       exclusive — the stage IS the staged layer's bus — so the v1 buses are
#       gone; the hall now provides the common room.)
#   • RUBATO — a tempo map: Allegro I → ritard into Adagio II → Vivace III →
#       broad Maestoso IV → a closing ritardando. Markers, the intensity arc and
#       the duration are set from the engine's analytic beat→second integral.
#   • MODULATION — key map C major → A minor (II) → C major, so the key-aware
#       diatonic transforms actually colour the Adagio in the relative minor.
#   • LEGATO — `legato` on the sustained melodic lines (real sampled legato
#       joins); spiccato/pizz lines stay detached.
#   • VOICING — register-separated strings (violas up an octave, open-fifth
#       cellos) + the `voicing open/spread` keyword on the harp, to kill v1's
#       muddy close clusters.
#   • HARP — the real sampled Harp, now `arp:`-eggiated, not block chords.
#   • TRANSITIONS — dominant pedals + timpani rolls bridge the movement seams.
#
# Tempo map (beat→bpm) and the resulting section times (engine TempoMap):
#   I  0–64b  0.00–37.82s   II 64–128b 37.82–89.34s
#   III 128–192b 89.34–118.66s   IV 192–280b 118.66–185.27s  (coda @ 256b/160.64s)
# =============================================================================

asset fable_symphony_orchestral_v2 {

  kind:       soundtrack
```
