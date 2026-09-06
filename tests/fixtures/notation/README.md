---
disclaimer:
  notice: >-
    No information within this document should be taken for granted.
    Any statement or premise not backed by a real logical definition
    or verifiable reference may be invalid, erroneous, or a hallucination.
  generated_by: "Claude Fable 5.1 via Claude Code"
  date: "2026-09-06"
---

# Notation fixture corpus

## Disclaimer

This work is subject to the methodological caveats and commitments described in [@DISCLAIMER.md](../../../DISCLAIMER.md).
> No statement or premise not backed by a real logical definition or verifiable reference should be taken for granted.

Back to the [root README](../../../README.md).

Eleven small `.af` specs, each with an `*.expected.json` naming the notation constructs it
carries (meter unit, pickup, key and tempo changes, chords, cross-bar ties, rests, polymeter,
dynamics, articulations, slurs, form sections and repeats, tuplets, lyrics, a 19-EDO tuning,
and overlapping voices with independent durations).
`tests/test_notation_oracles.py` exports each one and judges the result with the MusicXML 3.1
XSD, music21 and LilyPond (`docs/evolution/harness-notation.md`, `HARNESS-NGATE-001`,
`HARNESS-NXML-*`). Add a fixture when a construct gains a projection; never edit an expected
file to make a test pass.


Measure counts include the complete declared source duration, including silence after
the last note, and pad the final bar. At 120 bpm, an 8-second source is 16 quarter
beats: 3/4 needs 6 bars, 7/8 needs 5, and a 1-beat pickup in 6/8 needs the pickup plus
5 full bars. The branch's earlier expectations counted only the last sounding note;
the M3 integration corrects those expectations against the source durations. Repeated
sections are signs in the notated score and expand on the performed timeline.
