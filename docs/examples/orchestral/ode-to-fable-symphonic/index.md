---
disclaimer:
  notice: >-
    Examples describe authored intent. Render manifests and measurements provide
    technical evidence; they do not certify musical quality.
  generated_by: "scripts/examples.py via Codex"
  date: "2026-09-06"
---

<!-- Generated from catalog.json and the adjacent DSL by scripts/examples.py docs. -->


# Ode to Fable — symphonic rewrite

The symphonic rewrite of Ode to Fable, preserved as a separate score and render identity.

[All examples](../../index.md) · [Download the complete DSL](ode_to_fable_symphonic.af)

**Source status:** Compiles with the current engine.

**Instrument resources:** `VSCO-2-CE-1.1.0@ff140e8b5c5d6916ccf8088b0fc7dfb632f434d056aa764400905fdbd5824b0e`

## Render and listen

Run from the repository root after installing AudioForge and any pinned libraries:

```sh
.venv/bin/python scripts/examples.py render ode-to-fable-symphonic
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
# "Ode to Fable" — Symphony in D  (SYMPHONIC REWRITE)
# for Claude Fable 5 (Anthropic), released 2026-06-09
#
# Original composition. generated_by: Claude Opus 4.8 via Claude Code · 2026-06-11
#
# This rewrite answers a craft critique of the first version: stop PLACING three
# motifs as labels and instead METABOLIZE one cell into the whole work, develop
# it, and make D minor EARN its way to D major across the entire arc.
#
# ONE CELL — everything is born from it:
#   MYTHOS = D F E A, rhythm short-short-short-LONG  (intervals: m3, semitone, P4)
#     • FABLE  is DERIVED from it — same contour & rhythm-echo, the minor 3rd
#       lifted to major, then a lyric fall (F A G C / Bb A F).
#     • OPUS   is MYTHOS INVERTED — the calming descent IS the lineage turned
#       inward (D B C G -> D).
#     • The RHYTHM (short-short-short-LONG) is itself a motif: the timpani hammers
#       it as a "destiny" tag on D and the dominant A.
#
# THE ARGUMENT (earned D minor -> D major):
#   I.   MYTHOS         — the cell cannot cadence; D minor, deceptive endings.
#   DEV. THE ARGUMENT   — fragmentation, inversion, compression, augmentation,
#                         and a contrapuntal CONFLICT of all three motifs at once.
#   II.  THE TEMPERING  — the great A7 dominant is reached and WITHDRAWN (the
#                         fallback); OPUS interrupts; the key refuses to resolve.
#   III. THE TELLING    — FABLE humanizes the material in F major, but an A pedal
#                         lurks and deceptive cadences keep denying D.
#   IV.  GENERALLY AVAILABLE — the prepared A7 FINALLY resolves to D MAJOR; FABLE
#                         and MYTHOS combine; the cell turns bright (F#).
#   CODA — the opening cell returns as D F# E A over D major: the dissonant F
#          lifted to F#, the same four notes, resolved FROM WITHIN.
#
# Harmony is deliberately less trailer-functional: diminished pivots, chromatic
```
