---
disclaimer:
  notice: >-
    No information within this document should be taken for granted. Any statement
    or premise not backed by a real logical definition or verifiable reference may
    be invalid, erroneous, or a hallucination.
  generated_by: "Claude Fable 5.1 via Claude Code"
  date: "2026-09-06"
---

# ADR-0011: Electronic-production effects and sample editing

**Status:** Accepted
**Date:** 2026-09-06

## Context

A capability assessment against French house (the Daft Punk idiom) found the production
skeleton present — drum machine, sidechain `duck:`, resonant `ladder` sweeps, saturation,
loudness — and two signature elements absent: the robot voice and the chopped-record
sampling workflow, plus the modulation family (phaser, flanger, chorus) and lo-fi colour.
`PURPOSE.md` and ADR-0002 keep the engine non-vocal: it must not *generate* voices.

## Decision

1. **Modulation and lo-fi effects.** `phaser` and `flanger` are native kernels
   (`audioforge/native/phaser.c`, `flanger.c`): both are time-varying recursions
   (swept allpass cascade with feedback; swept fractional delay with feedback) that a
   fixed convolution cannot express, so they follow the `ladder`/`tape` precedent
   (ADR-0004: native, fail loud). `chorus` (multi-voice modulated delay, no feedback)
   and `bitcrush` (quantization + sample-and-hold) are pure numpy. All four are in
   `schema.FX_TYPES`, the DSL builder table, the decompiler table and the manifest;
   the drift gate checks the set. References: first-order allpass phaser and delay-line
   flanger/chorus per Zölzer, *DAFX* (2nd ed., 2011), §2.3 and §2.6.
2. **Vocoder as a bus sidechain, not a voice.** `vocoder: source=<layer|bus:name> …`
   on a bus mirrors `duck:`: the bus mix is the carrier, the named signal the
   modulator. It is a channel vocoder (Dudley 1939 lineage): log-spaced second-order
   Butterworth band-passes, one-pole envelope followers, band products summed and
   level-matched to the carrier RMS. The modulator is whatever the spec routes — a
   supplied recording enters only as a hash-pinned `sample` layer (ADR-0002), a drum
   pattern gives the rhythmic "talking synth" without any speech. The engine therefore
   still generates no vocals, speech or lyrics; it processes signals it is given.
3. **Sample editing in the IR.** `sample` layers gain `offset_s`, `length_s`,
   `reverse`, `stretch` (phase-vocoder time stretch, `audioforge/stretch.py`;
   Flanagan & Golden 1966, Dolson 1986) and `slices` (equal division; pattern digits
   pick a slice, `x`/`X` play the first). Edits apply after hash verification and
   resampling, before triggering, so the content address still names the source
   recording and the edit is explicit, diffable IR.
4. **Licensing stays the user's.** Nothing here changes the sample-catalog policy:
   the engine plays what it is given and records its hash; provenance of the material
   is the author's responsibility.

## Consequences

* Existing renders are byte-identical (goldens unchanged); the new constructs are
  opt-in.
* The decompiler now emits sample-layer `file`/`sha256`/`pitch`/edits, bus
  `duck:`/`vocoder:` and layer `start:` — three pre-existing round-trip gaps closed
  because the new tests demanded them.
* Five tracks under `static/samples/house_*.af` are the executable proof; their
  manifests are recorded in `docs/ELECTRONIC_TRACKS.md`.
* Not done: formant/LPC vocoding, transient-preserving stretch, phaser with
  stereo-offset LFOs. All are extensions of these kernels, none a new scope.
