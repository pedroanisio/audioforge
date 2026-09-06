---
disclaimer:
  notice: >-
    This is a historical delivery record. Its measurements refer to the retained
    engine 3.0.0 recording; current rendering may produce different audio.
  generated_by: "Codex"
  date: "2026-09-06"
---

# The First Light

See the [repository disclaimer](https://github.com/pedroanisio/audioforge/blob/main/DISCLAIMER.md).

For current rendering and source requirements, use the [example guide](index.md).

An original five-minute orchestral overture in D minor and D major, composed and rendered with AudioForge.

Listen: 320 kbps MP3 (`audio/the_first_light.mp3`, local artifact) · Master: 48 kHz / 24-bit WAV (`audio/the_first_light.wav`, local artifact)

A quiet oboe call opens the piece. The violins turn that call into an active first theme; flute, oboe and clarinet introduce a longer, singing second theme over pizzicato strings and harp. A sequential development draws the music back toward D, where both ideas return in major. The coda broadens into a final tonic and its natural release.

| Time | Section | Character |
|---|---|---|
| 0:00 | Before dawn | Quiet introduction; oboe and answering bassoon |
| 0:27 | The road awakens | First theme; violin melody and spiccato motion |
| 1:24 | A window of light | Lyrical woodwinds, pizzicato strings and harp |
| 2:33 | Passing shadows | Sequential development, exchanges and timpani crescendo |
| 3:21 | The returning road | Themes return in D major with fuller orchestration |
| 4:16 | First light | Slowing coda, final tonic and release |

The score contains 116 bars and 2,580 note events across 18 render layers. It uses recorded string ensembles, flute, oboe, clarinet, bassoon, horn, harp and timpani. Sustained, spiccato and pizzicato textures use their corresponding recorded patches. A shared tempo map, explicit dynamic curves, modest coordinated timing variation, orchestral panning and a hall effect shape the performance. There are no synthetic articulation fallbacks or multiplied sample ensembles.

The delivered WAV contains exactly **14,400,000 stereo frames: 300.000 seconds**. The notated score reaches its end at 294 seconds, leaving six seconds for release and decay. Independent FFmpeg measurement reports **−19.8 LUFS integrated**, **8.4 LU loudness range**, and **−4.9 dB true peak**. The master used no limiter gain reduction.

The acceptance report (`validation.json`, local artifact) records compilation, source/IR agreement, strict routing, 261 verified sample hashes, instrument ranges, note identities, harmony, independently integrated tempo, every stem, actual audio measurements, and a fresh-process reproduction check. Its scope is technical delivery and explicit score structure; these measurements do not certify musical taste or replace a human listening judgment.

The full repository gate passed: **884 tests passed, 2 skipped**; all five golden renders reproduced exactly. Six existing score-PDF font warnings are retained in the complete gate log (`evidence/make-check.log`, local artifact). This delivery does not include a PDF score. A timing-validator correction made during this composition now follows the actual tempo map, fermatas and layer offsets; three new regressions passed.

Editable composition: [Python authoring source](compose.py), [AudioForge score](the_first_light.af), compiled IR (`the_first_light.ir.json`, local artifact), and form/harmony/note ledger (`program.json`, local artifact). The manifest (`audio/the_first_light.manifest.json`, local artifact) identifies the WAV and all 18 stems; the render plan (`audio/the_first_light.plan.json`, local artifact) records every note's sample route. Stems are premaster layers, as exported by AudioForge, rather than separately mastered listening mixes.

Sample credit: **Versilian Studios, VSCO 2 Community Edition 1.1.0**. The installed library's bundled license (`libraries/VSCO-2-CE-1.1.0/LICENSE`) is CC0 1.0 Universal. The exact library pin and selected sample hashes are retained in the score and acceptance report. AudioForge reports two ignored source-SFZ fields, `group_label` and `ampeg_dynamic`; the authored performance uses explicit dynamic curves and the engine's velocity crossfades, and does not depend on those fields.

To reproduce from the repository root, with the same installed library and dependencies:

```sh
AUDIOFORGE_JOBS=2 .venv/bin/python -m audioforge.cli verify \
  docs/examples/orchestral/the-first-light/the_first_light.ir.json \
  docs/examples/orchestral/the-first-light/audio/the_first_light.manifest.json
```

This historical engine 3.0.0 delivery used JSON IR for verification. Current engines accept `.af` as well, but reproducing these archived bytes requires the original engine and numeric environment. The original render used four workers; verification uses two.

To repeat all composition acceptance checks against the retained evidence:

```sh
PYTHONPATH=. .venv/bin/python docs/examples/orchestral/the-first-light/validate.py \
  docs/examples/orchestral/the-first-light/audio \
  --gate-log docs/examples/orchestral/the-first-light/evidence/make-check.log \
  --verify-log docs/examples/orchestral/the-first-light/evidence/reproduce.log --final
```
