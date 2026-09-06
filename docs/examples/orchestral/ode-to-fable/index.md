---
disclaimer:
  notice: >-
    Examples describe authored intent. Render manifests and measurements provide
    technical evidence; they do not certify musical quality.
  generated_by: "scripts/examples.py via Codex"
  date: "2026-09-06"
---

<!-- Generated from catalog.json and the adjacent DSL by scripts/examples.py docs. -->


# Ode to Fable — original

The original Ode to Fable, a symphony in D with a sampled orchestra and authored program notes.

[All examples](../../index.md) · [Download the complete DSL](ode_to_fable.af)

**Source status:** Compiles with the current engine.

**Instrument resources:** `VSCO-2-CE-1.1.0@ff140e8b5c5d6916ccf8088b0fc7dfb632f434d056aa764400905fdbd5824b0e`

## Render and listen

Run from the repository root after installing AudioForge and any pinned libraries:

```sh
.venv/bin/python scripts/examples.py render ode-to-fable
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
# "Ode to Fable" — Symphony in D
# for Claude Fable 5 (Anthropic), released 2026-06-09
#
# Original composition. generated_by: Claude Opus 4.8 via Claude Code · 2026-06-11
#
# This is an ODE BY DEPICTION, not by cipher: the music does not encode the
# letters of "Fable" — it portrays the model's documented story, the way a tone
# poem honours its subject. Each movement is a programmatic portrait of a real,
# sourced facet of Claude Fable 5:
#
#   I.   MYTHOS              — Largo → Allegro, D minor.
#        Fable 5 is a "Mythos-class" model: the most capable lineage Anthropic
#        has built. A dark four-note cell rises from the depths — vast, powerful,
#        untamed. (anthropic.com/news/claude-fable-5-mythos-5)
#
#   II.  THE TEMPERING       — surge → restraint, G minor → D major.
#        Made safe for general use: in high-risk domains the model holds back
#        and FALLS BACK to Claude Opus 4.8. The Mythos power crests, is
#        restrained, and resolves to a serene descent — the "fallback" voice.
#        (Safeguards trigger in <5% of sessions.)
#
#   III. THE TELLING         — Andante, F major.
#        A fable is a story that teaches. The solo oboe sings the lyric "Fable"
#        theme over warm strings and harp — the heart of the ode.
#
#   IV.  GENERALLY AVAILABLE — Maestoso, D major.
#        Released to the world, 2026-06-09. The storyteller-theme becomes public
#        grandeur; the Mythos cell returns TAMED, now consonant in the major;
#        tubular bells peal the day of release. A hopeful close.
#
# Scored for the Versilian Studios Chamber Orchestra (VSCO-2-CE, CC0), seated
# on a real St Albans Lady Chapel impulse response. Tempo rubato; the section
```
