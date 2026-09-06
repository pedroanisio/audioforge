# Notation Phase 3 — integration and acceptance

This checkpoint integrates notation M1–M3 from `feat/notation-interchange` commit
`8d3b989` into the engine 3.1 codebase. The governing artifacts are the
[roadmap workbook](roadmap-notation.xlsx), [harness](harness-notation.md), and
[ADR-0011](../adr/0011-notation-interchange-oracles.md).

## Delivered behavior

- MusicXML keeps one part per pitched layer, independent voices for overlaps,
  unequal note durations, duplicate pitches, cross-bar ties, meter and pickup.
  Key changes retain their offsets, including changes within measures.
- Tempo maps, dynamics and hairpins, articulations and slurs, fermata signs,
  rehearsal marks, repeat barlines, tuplets and lyric text have explicit projections.
- MIDI uses a conductor plus one track per part. Tempo events survive import;
  simultaneous equal pitches in 18 parts survive the music21 check.
- MusicXML import follows chords, backup/forward and voice cursors, honors attribute
  changes and merges ties. Two committed Bach chorales validate and render, with
  written and performed durations checked separately against music21.
- The generated [interchange matrix](../INTEROP.md) and capability manifest share
  the registry used for diagnostics. The SDK, CLI, agent tools and MCP expose
  the notation projection; CLI conversion losses appear on stderr.

## Validation evidence

The [T3 summary](evidence-notation/T3/summary.tsv) accounts for all 53 harness IDs.
Rows due after M3 are marked N/A with their later checkpoint, not counted as delivered.
[Commands and environment](evidence-notation/T3/context.json), per-row logs and
[structured results](evidence-notation/T3/results.json) make each verdict reviewable.
The runner rejects empty or skipped pytest selections, missing oracles, failed commands,
and incomplete gates. The roadmap updater refuses to advance M3 until every required
row is PASS.

The oracle environment pins music21 10.5.0, LilyPond 2.25.12 and xmlschema 4.3.2.
All 11 authored fixtures are checked against the offline MusicXML 3.1 schema,
compared with music21, and passed through musicxml2ly and LilyPond with no warning
category excluded. The independent parity test compares each source note's pitch,
onset and duration, including overlapping voices. Reports are under
[evidence-notation/T3/reports](evidence-notation/T3/reports/).

```bash
uv venv /tmp/audioforge-notation-oracles --python 3.12
uv pip install --python /tmp/audioforge-notation-oracles/bin/python -e '.[dev,oracles]'
ORACLE_PY=/tmp/audioforge-notation-oracles/bin/python scripts/harness-notation.sh T3
```

## Explicit projection limits

Polymeter uses the global score meter and emits `lossy_polymeter`, retaining note
onsets and durations. This satisfies the roadmap's permitted fallback and avoids
the LilyPond converter's bar-check warnings. A fermata preserves a hold's position;
its seconds are omitted with `lossy_hold`, and import records `fermata_duration`
without inventing pause lengths. Tempo ramps become documented stepped marks.
Notation grids must be positive multiples of 1/32 quarter-note beat; the default
is 0.25. Lyrics remain metadata and do not generate singing.

Non-12-EDO tuning still emits `tuning_not_rendered`. Tuning activation is M4.
The integrated LilyPond backend, additional analysis tools, performance budgets,
glyph fixes and oracle CI job remain M5. This checkpoint changes neither the
runtime version nor the audio determinism contract. The original proposed
engine 3.1 / DSL 2.1 release numbers predate engine 3.1 stereo playback.
