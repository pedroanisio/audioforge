---
disclaimer:
  notice: >-
    No information within this document should be taken for granted. Statements
    require verification against the implementation and validation evidence.
  generated_by: "Codex"
  date: "2026-09-06"
---

# ADR-0009: Native stereo samples and recorded interval playback

- **Status:** Implemented locally; validation accompanies the change.
- Engine: 3.1.0; DSL and IR remain 2.0.

## Context

The instrument decoder averaged stereo recordings before resampling. Later
panning and reverb could not recover their original channel differences.
Slurs used stationary sustains with an attack offset and a synthesized pitch
ramp. An SFZ sustain loop does not establish that a transition was recorded.

## Decision

Decode mono recordings to `(frames,)` and stereo recordings to `(frames, 2)`.
Apply the same resampling clock, loop and envelope independently to both
channels. Promote mono regions at constant power when mixed with stereo.
Balance native stereo layers without channel crossfeed, at unity in the center.
Preserve separately seated ensemble players and the native direct stereo image;
the existing stage's shared room send remains a mono excitation of its stereo IR.
Reject unsupported surround recordings explicitly.

The library manifest may declare `recorded_transitions` per instrument. Each
entry identifies one exact directed interval, one sample containing the
transition and destination sustain, timing and recording provenance. The
existing library hash covers this mapping and its sample bytes. Planning and
rendering share resolution. A recorded lead begins before the score's destination
onset; the preceding note hands over at that actual start. Playback applies no
synthetic pitch ramp to a recorded transition. Missing mappings retain disclosed
approximation behavior, including refusal under strict routing.

## Consequences

Instrument stereo renders change intentionally, so the engine version and
generated contracts change together. Mono sample shape and processing remain
compatible. Existing stereo mixes should be checked and remastered. Manifest
transition provenance is an author's claim; hash verification establishes byte
identity, not that a human performed those bytes. Delivery evidence must examine
real source recordings separately. This implementation supports one recording
per interval and articulation; it does not claim a complete orchestral legato bank,
transition velocity layers, dedicated release samples or a Kontakt interpreter.

Regression tests are in `test_sampler_stereo.py` and `test_recorded_legato.py`.
The revised First Light demonstration preserves the original for comparison and
adds real viola transitions, varied accompaniment, a fresh complete render,
independent signal measurements and reproduction evidence.
