---
disclaimer:
  notice: >-
    No information within this document should be taken for granted. Statements
    require verification against code, recordings and executable evidence.
  generated_by: "Codex"
  date: "2026-09-06"
---

# Orchestral playback in engine 3.1

AudioForge preserves native mono or stereo instrument recordings. Stereo
balance attenuates the opposite channel without crossfeeding it, with unity gain
at center. Mono instruments retain constant-power pan. Velocity crossfades,
loops, note curves, layer effects and stems keep both recording channels.
Stage close/tree direct paths retain the image; the existing shared hall send
uses mono excitation. Section multiplication balances each recorded player
independently and remains an approximation of multiple real players.

## Recorded transitions

Add `recorded_transitions` to an instrument entry passed to
`audioforge.library.generate_manifest(..., instruments=...)`. Rebuild the
manifest and update the score's library pin whenever mappings or samples change.
Paths are relative to the library root. One entry may match an exact directed
interval and articulation; ambiguous mappings fail.

```json
{
  "sfz": "viola.sfz",
  "articulations": {"sustain": "viola.sfz"},
  "recorded_transitions": [{
    "from_midi": 50,
    "to_midi": 52,
    "sample": "recordings/D3-to-E3.wav",
    "offset_frames": 46080,
    "lead_s": 0.13,
    "crossfade_s": 0.025,
    "release_s": 0.18,
    "provenance": {
      "source_url": "https://example.org/recording-session",
      "description": "Recorded D3 to E3 with destination sustain."
    }
  }]
}
```

Use a shared positive integer `slur` and a shared `voice` on contiguous notes.
An entry defaults to articulation `sustain`. Playback trims `offset_frames`
source frames, begins `lead_s` seconds before the written destination onset,
and fades the previous note out over `crossfade_s`. The recording then supplies
the destination sustain and an envelope release. There is no generated pitch
ramp. A note's expression curve holds its initial value during the recorded
lead, then follows the authored note clock. Source exhaustion, including the
trim and lead, is checked by the existing sustain-gap policy.
An interval whose required lead would precede the previous note is rejected;
the author must supply a faster take or leave a phrase break.

For an explicitly transposed mapping, also set `recorded_from_midi` and
`recorded_to_midi`. Both endpoints must move by the same interval; substituting
a different recorded interval fails. This first contract supports one recording
per interval, without velocity selection among transition takes or loop extension
of the recorded destination. Dynamic curves control its level. Sustains retain
the existing velocity-layer behavior.

Plans report recording identity, source hash, source frames/rate, timing and
provenance in `decision.transition`, with the outgoing handover in
`decision.transition_out`. A missing interval uses the disclosed stationary
sample approximation when permitted; `routing.fallbacks: forbid` rejects it.
Neither a filename nor a slur certifies a recording. Verify provenance and
inspect the actual source performance before describing a library as recorded
legato.

The [SFZ legato tutorial](https://sfzformat.com/tutorials/legato/) distinguishes
stationary-sample methods from recordings of note changes. AudioForge's manifest
contract is separate from SFZ `trigger`/`sw_previous` interpretation; importing an
arbitrary third-party SFZ does not automatically import its legato engine.

## Demonstration and validation

`docs/examples/orchestral/the-first-light-revised` contains a revised five-minute overture.
It uses the original VSCO Community Edition orchestra plus four ascending viola
intervals from [David Hilowitz's educational demo](https://www.youtube.com/watch?v=j9OfaBw4n0c).
The archive is publicly supplied by its author; it contains no separate license
grant for sample redistribution. Its recordings remain local to this demonstration.
The combined library records this distinction instead of relabeling those bytes CC0.

The original composition remains in `docs/examples/orchestral/the-first-light`. The revised
validator checks the delivered source, exact duration, real source identities,
preserved stereo information, accompaniment recurrence, master and stems,
independent loudness/peak measurements and fresh-process reproduction. These
checks establish specified behavior and technical delivery. Subjective musical
quality still requires a listening review.
