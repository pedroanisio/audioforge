---
disclaimer:
  notice: >-
    No information within this document should be taken for granted. The
    linked reports retain the executable evidence for the claims below.
  generated_by: "Codex"
  date: "2026-09-06"
---

# The First Light — revised

See the [repository disclaimer](https://github.com/pedroanisio/audioforge/blob/main/DISCLAIMER.md).

Listen to the five-minute MP3 (`audio/the_first_light.mp3`, local artifact) · 48 kHz / 24-bit WAV (`audio/the_first_light.wav`, local artifact) · Validation report (`validation.json`, local artifact)

An original orchestral overture in D minor and D major, rendered by AudioForge
3.1.0. The revised score contains **1,912 notes, 19 parts and 116 bars**. Its two
themes pass through six sections, from a quiet introduction to a major-key return.
The score ends at 294 seconds, leaving a six-second release tail. The delivered
WAV contains exactly **14,400,000 stereo frames: 300.000 seconds**.

The three quality corrections are implemented and exercised in this recording:

| Correction | Verified evidence |
|---|---|
| Preserve recorded stereo | All 261 selected recordings retain both original channels, checked sample-for-sample against an independent decoder. Resampling, loops, dynamics, effects, panning, sections and stems have regression coverage. |
| Play recorded note transitions | Twelve viola joins use four genuine directed-interval recordings. Plans identify their source hashes, trim and arrival times. Independent pitch analysis confirms both recorded endpoints. Missing intervals still fail strict routing. |
| Rewrite the backing | The violin accompaniment has 32 distinct rhythms, up from two. The longest run of identical nonempty rhythm falls from 24 bars to one. More rests, changing bass answers and a broader reprise replace the repeated eighth-note figure. |

The recorded viola replies begin near **0:03.4, 1:29.9 and 2:47.0**. Their
premaster energy sits between **-8.5 and -3.5 dB** relative to the other
parts during each reply. This checks their balance in the actual mix.

All **59 delivery checks pass**. Independent FFmpeg measurement reports
**-19.8 LUFS**, **8.7 LU** loudness range and
**-4.9 dBTP**. There is no limiter gain reduction, clipping,
unexplained silence or truncated ending. All 19 stems and the MP3 decode and
match their recorded hashes. A fresh process re-rendered the `.af` with two
workers and reproduced the four-worker master byte for byte.

The complete repository gate (`evidence/make-check.log`, local artifact) passes with **939 tests
passed, 2 skipped**, and six existing score-PDF font warnings. Coverage (`evidence/coverage.log`, local artifact)
is **91.18%**, above the 90.1% gate. No PDF score is included in this delivery.
These checks establish technical delivery and explicit musical structure;
subjective quality and comparison with commercial libraries still require listening.

Source and evidence: [composition](compose.py), [AudioForge score](the_first_light.af),
IR (`the_first_light.ir.json`, local artifact), form and note ledger (`program.json`, local artifact),
render plan (`audio/the_first_light.plan.json`, local artifact), manifest (`audio/the_first_light.manifest.json`, local artifact),
acceptance log (`evidence/acceptance.log`, local artifact), reproduction log (`evidence/reproduce.log`, local artifact).
The original recording (`../the-first-light/audio/the_first_light.mp3`, local artifact) and
[delivery](../the-first-light/delivery.md) remain intact for comparison. The original
was rendered by engine 3.0.0; its historical hashes are specific to that engine.

Recordings: Versilian Studios VSCO 2 Community Edition 1.1.0 (CC0), plus
[David Hilowitz's educational viola legato demo](https://www.youtube.com/watch?v=j9OfaBw4n0c).
The latter supplies four ascending intervals; this is limited recorded coverage,
not a complete orchestral legato bank. The demo archive supplies no separate
sample-redistribution license; its local source provenance is retained by the
combined library. See [playback details](../../../ORCHESTRAL_PLAYBACK.md).

To reproduce with the installed, pinned library:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 AUDIOFORGE_JOBS=2 .venv/bin/python -m audioforge.cli verify \
  docs/examples/orchestral/the-first-light-revised/the_first_light.af \
  docs/examples/orchestral/the-first-light-revised/audio/the_first_light.manifest.json
```

To repeat acceptance:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONPATH=. .venv/bin/python docs/examples/orchestral/the-first-light-revised/validate.py \
  docs/examples/orchestral/the-first-light-revised/audio \
  --gate-log docs/examples/orchestral/the-first-light-revised/evidence/make-check.log \
  --verify-log docs/examples/orchestral/the-first-light-revised/evidence/reproduce.log --final
```

Master SHA-256: `5c4e87549433209a238c894c5e581ab01b423c48b3a3b5e010bb8da45f3ab627`.

[Back to AudioForge](../../../index.md)
