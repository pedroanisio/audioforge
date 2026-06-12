# AudioForge DSL Specification

**DSL 1.10 · Engine 2.16.0**

The `.af` DSL is the authoring surface for humans and AI agents. It compiles to a JSON spec — the deterministic intermediate representation (IR) that the engine renders. Everything expressive in the DSL (emotion tags, intensity curves, motifs, chords, transforms, groove templates, `vary()` choices) is **expanded at compile time** into explicit JSON parameters, so the IR is always the single, inspectable ground truth for what will be rendered. Under the same engine version, same DSL text → same IR → same spec hash → byte-identical audio.

This document is the implemented language reference. Remaining DSL architecture
and expressiveness gaps are tracked in [DSL_GAP_SPEC.md](DSL_GAP_SPEC.md).

---

## 1. Lexical rules

Comments run from `#` to end of line (a `#` *inside* an identifier, as in `C#4`, is part of the identifier). Statements are line-oriented; a property list continues onto the next line if the current line ends with a comma or is inside parentheses. Strings are double-quoted: `file: "kick_room.wav"`.

Numbers may carry a unit suffix, validated against what the property expects:

| Unit | Meaning | Example |
|------|---------|---------|
| `s` | seconds | `duration: 36s` |
| `b` | beats | `C4 @ 8b for 2b` |
| `bpm` | tempo | `tempo: 60bpm` |
| `db` | decibels | `gain: -9db` |
| `hz` | frequency | `lowpass(1800hz)` |
| `st` | semitones | `transpose +12st`, `tune: -4st` |
| `c` | cents | `detune: 7c`, `pitchspread: 30c` |
| `deg` | degrees | `seat: -16deg @ 4.5m` |
| `m` | meters | `size: 15m, 23m, 12m` |

**Pitches.** Notes are pitch names: `C4`, `F#2`, `Eb3`, `A-1` (MIDI-style octaves, A4 = 440 Hz). Raw frequencies are accepted anywhere a note is: `432hz @ 0b for 4b`. **Chord symbols** are a root-with-octave plus a quality, accepted anywhere a note is (including motifs): `C3min7`, `Ab2maj7`, `E4sus4`. Qualities: `maj min m dim aug 6 7 9 m6 m7 maj7 min7 maj9 min9 m9 sus2 sus4 add9 dim7 min7b5 m7b5 7sus4 dom7sus4 maj7#11 maj7s11` (`s11` spells #11 without the DSL comment char).

---

## 2. Asset structure

```
asset <id> {
  <asset properties and smart directives>
  marker <name> @ <time_s>
  motif <name> { <note events> }
  stage { <stage properties> }            # concert staging
  cutdowns { <cutdown lines> }            # campaign matrix (§11)
  bus <name> { <bus properties> }         # mix buses (§7)
  layer <name> : <type> { <layer properties> }
  master { <master properties> }
}
```

A file may contain multiple `asset` blocks; each compiles to its own spec. Buses must be declared before layers reference them.

### 2.1 Asset properties

| Property | Value | Compiles to |
|----------|-------|-------------|
| `kind:` | `signature sfx loop jingle transition cue bed soundtrack` | `kind` |
| `duration:` | seconds | `duration_s` |
| `samplerate:` | integer Hz | `sample_rate` (default 48000) |
| `bitdepth:` | `16` or `24` | `bit_depth` (default 24) |
| `tempo:` | bpm, or a **tempo map**: `96bpm, 20b=96bpm, 26b=128bpm` | `bpm` + `tempo_map` |
| `key:` | e.g. `C minor`, or a **key map**: `A minor, 26b=C major` | `key` + `key_map` |
| `swing:` | 0..1 | `swing` (legacy; prefer `groove:`) |
| `groove:` | `<template> [amount]` — `straight swing16 shuffle laidback pushed heavy_one` | explicit 16-slot `timing`/`accent` arrays |
| `loopsafe:` | `on` | `loop_safe` (validates whole-beat duration) |
| `emotion:` | `name=0..1, ...` | metadata + Emotion macro expansion |
| `intensity:` | `time=0..1, ...` | tagged master `gain_db` automation + `intensity_curve` |
| `library:` | `"name@manifest_sha256"` | `library` — pins a content-addressed instrument library; mandatory for `instrument` layers |
| `meter:` | `BEATS UNIT`, e.g. `7 8` | `score.meter` |
| `pickup:` | beats | `score.pickup_beats` |
| `form:` | `name STARTb for DURb, ...` | `score.sections` |
| `repeat:` | `section xN` | `score.repeats` |
| `polymeter:` | `layer BEATS UNIT` | `score.polymeter` |
| `style:` | style-pack name | deterministic defaults under `intent.style` and explicit render IR |
| `perform:` | `style=... expressivity=... rubato=arch amount=0.12 segment=0.25b` | phrase analysis + explicit performance parameters; rubato lowers to dense `tempo_map` points |
| `ensemble:` | `family size=N spread=... octaves=N` | explicit unison/section/octave events and role buses |
| `voicing:` | `richness=... extensions=...` | explicit chord extensions and generated voice-leading notes |
| `space:` | `hall=... depth=...` | explicit room/glue processing |

**Tempo maps** ramp BPM linearly between points; beat→seconds is the exact analytic integral (logarithmic per ramp segment), so accelerandi are smooth, not stepped. Keep them austere: `tempo_map` is only `[beat, bpm]` points. `fermata: 12b=1.5s` (or `hold:`) compiles to first-class `holds` events that insert absolute seconds at the named beat, before events at that beat and all later beats. `perform: rubato=...` is smart directive sugar: the compiler analyzes phrases and writes dense piecewise-linear tempo points with ≤2 ms segment error, so the render IR stays diffable and verifiable. Every musical grid — note starts/durations, drum steps, groove and swing offsets, loop expansion — follows the map plus holds. Layer `start:`, automation breakpoints, and markers remain in real seconds. **Key maps** modulate mid-asset: scale advisories and `diatonic` transforms (§3) resolve whichever key is in force at their position.

Known emotion tags: `tension awe sadness triumph suspense intimacy urgency calm fear wonder cinematic_intensity`. Unknown tags are kept as metadata with a warning.

### 2.2 Markers

`marker climax @ 26s` — compiled into `markers`, written to the manifest and a `.markers.json` sidecar for video-timeline alignment.

---

## 3. Motifs, `play`, and transforms

```
motif ascent {
  C4 @ 0b for 1.5b vel 0.7
  G4 @ 3b for 2b vel 0.85
}
layer voice : notes {
  play ascent @ 10b
  play ascent @ 18b invert vel 0.9
  play ascent @ 26b retrograde diatonic -2
  play ascent @ 34b stretch 1.5 transpose +12st
}
```

`play` expands the motif into the layer's note list at compile time. Transform flags apply in a fixed, documented order: **retrograde → invert → stretch → diatonic → transpose → vel**.

| Flag | Behavior |
|------|----------|
| `retrograde` | reverses the motif in time (end-aligned) |
| `invert` | chromatic mirror around the motif's first (earliest, then lowest) pitch |
| `stretch N` | starts and durations × N (augmentation/diminution) |
| `diatonic ±N` | moves each pitch N scale degrees within the key in force at the play position (key map aware). Chromatic passing tones keep their offset from the nearest lower scale tone |
| `transpose ±Nst` | chromatic shift; fractional semitones compile to explicit `freq_hz` (chords need whole semitones) |
| `vel X` | velocity scale |

Motifs may contain chord symbols; transforms move the chord root and preserve the quality. Motifs are pure macros — the IR contains only expanded notes.

---

## 4. Layer types

`layer <name> : <type>` — the types are listed below. Common properties on every layer: `gain:` (db), `pan:` (-1..1, constant-power), `start:` (s), `duration:` (s, truncates), `env: a=… d=… s=… r=…` (ADSR; a/d/r seconds, s level 0..1), `fx:` (§9), `auto <target>:` (§10), `bus:` (§7).

| Type | Specific properties |
|------|--------------------|
| `tone` | `osc:` (§5), `note:`/`freq:`, `detune:` (c), `fmratio:`/`fmindex:`, voice params (§5) |
| `notes` | `osc:`, `notes:` event list, `play` statements, `loop:` (beats), `arp:` (§6), voice + performance params (§5–6) |
| `sweep` | `shape:` (an oscillator waveform), `from:`/`to:` (hz), `curve:` (`lin`/`exp`) |
| `noise` | `color:` (`white pink brown`) |
| `drums` | `voice:` (`kick snare hat open_hat clap tom` + plugins), `pattern:` (§6), depth params `tune: ±12st`, `decay: 0.25..4`, `snap: 0..1`, `bend: 0..1.5`, `humanize:` |
| `grain` | granular texture: `source:` (any oscillator or noise color), `note:`/`freq:` for pitched sources, `srcdur:` (s), `grainsize:` (s), `density:` (grains/s), `pitchspread:` (c), `scatter:` (0 = scan through the source, 1 = anywhere) |
| `sample` | content-addressed audio: `file: "name.wav"`, `sha256: "…64 hex…"`, then either `start:` (one-shot) or `pattern:` (drum-grid triggering with groove/humanize), `pitch: ±Nst`. WAV PCM 16/24/32-bit, auto mono-mix, deterministic resample. The pinned hash participates in the spec hash; a byte mismatch refuses with both hashes named |
| `audio` | recorded-audio authoring alias for `sample`: same `file`/`sha256` discipline, plus `preserve: stereo|channels` to keep source channels for non-pattern audio. It compiles to explicit `type: sample` IR with `source_kind: audio` |
| `foley` | procedural ambience: `model:` (`rain wind fire surf`), `intensity: 0..1`, `brightness: 0..1` |
| `instrument` | sampled instruments from a content-addressed library: `instrument:` (name in the manifest), `articulation:` (layer default, per-note `art` overrides), `dynamic:` curve, `notes:` events, performance props. Requires a spec-level `library:` pin |

**Validate means render-ready (since 2.14).** `validate` runs the structural schema check *plus* a resource-binding resolve pass: libraries located and manifest-verified, instruments and articulations resolved, sample/IR files found and hash-checked, native kernels probed. `OK: valid — render-ready` is a true predicate for "will render"; resource problems are reported as line-cited diagnostics, and `render` refuses with the same structured list rather than a raw traceback (`--no-resolve` gives the pure structural check). Timeline issues that still render, such as note events extending past the asset duration, are reported as warnings with paths. Pins that are one repeated hex character (e.g. all zeros) are reported distinctly as **unbound placeholders**. Source line numbers travel in a `_meta` sidecar that is **excluded from the spec hash** — the same music reformatted hashes identically.

**Render plans (since 2.16).** `audioforge plan spec.af` writes a derived
`audioforge.render-plan/1` artifact after validation/resource resolution and
before rendering. The plan records sampled routes, synthetic articulation
fallbacks, synth/native routes, evidence, diagnostics, and reserved cost fields;
it is not authored DSL. The hash-included authored policy lives under
`routing`: `fallbacks: allow|warn|forbid` and `stretch_warn_semitones: N`.
`audioforge render --plan file.plan.json` recomputes the plan and refuses stale
spec, engine, library, catalog, or policy inputs before audio is computed.
Render manifests record `plan_hash`, and exports write `<id>.plan.json`.

**Note events** (in `notes:` lists and motifs): `PITCH @ START for DUR [vel V] [voicing NAME] [art NAME]`, where `PITCH` is a note, frequency, or chord symbol. Note lists may wrap consecutive notes in `slur( …, … )` — the group shares a slur id in the IR. `slur( play m @ 0b, play m @ 4b … )` is also valid (since 2.14): the motif expansions join as **one** slur group; `play motif @ Nb legato` remains the single-motif shorthand. `notes:` needs its first event on the same line and continues across lines with trailing commas; `play` is a layer-body statement, one per line — the parser now says exactly this when the shapes are confused. Automation (`auto target:`) honors the same comma-newline continuation rule as every property list (fixed in 2.14). Articulations: `sustain staccato spiccato pizzicato tremolo marcato legato trill` — `trill` expands at compile time into alternating notes with the key-aware diatonic upper neighbor (0.125 b steps, reported in diagnostics). Chord voicings: `close` (default) `drop2 drop3 spread open wide inv1 inv2`. A chord expands to simultaneous notes — or to a sequence if the layer has an `arp:` (§6).

---

## 5. Oscillator voices

All oscillators are bandlimited; all randomness derives from per-note seeded RNG paths, so every voice is byte-reproducible.

| Voice | Properties (defaults) | Character |
|-------|----------------------|-----------|
| `sine saw square triangle` | — | exact-Fourier wavetables |
| `fm` | `fmratio: 2`, `fmindex: 0` | 2-operator FM |
| `organ` | — | drawbar partial stack |
| `pad` | `bandwidth: 40c`, `harmonics: 48` | PADsynth (public domain): Gaussian-widened harmonics — lush, perfectly-looping ensemble pads |
| `pluck` | `damping: 0.5`, `brightness: 0.6`, `pluckpos: 0.28` | extended Karplus-Strong string |
| `modal` | `material: bell glass marimba gong steel`, `modedecay: Ns`, **or** `modes: r a t, r a t, …` (1–32 `ratio amp t60_share` triplets — bespoke percussion from a list of numbers) | decaying-partial resonator bank + seeded strike |
| `morph` | `scan: 0..1` (automatable, §10) | wavetable morphing: sine→triangle→pulse→saw→square between bandlimited frames |
| `bowed` | `pressure: 0.2..1`, `bowpos: 0.05..0.45`, `brightness:` | McIntyre-Woodhouse/STK-lineage friction-curve waveguide (**native kernel** — needs a C compiler, fails loudly without) |
| `blown` | `pressure: 0.2..1`, `brightness:` | STK-Clarinet-lineage reed waveguide; loop-gain constants solved analytically so it self-oscillates across the pressure range; odd-harmonic cylindrical-bore spectrum; seeded breath turbulence (**native kernel**) |
| `brass` | `pressure: 0.2..1`, `brightness:`, `lip: 0..1` | STK-Brass-lineage lip-reed waveguide; in-loop wave-steepening brightens with pressure and a bell-flare rectifier supplies even harmonics; `lip` is the embouchure (bends pitch ±~20c); seeded breath turbulence (**native kernel**) |
| `struck` | `tension: 0..1`, `strike: 0..1`, `damping:`, `brightness:` | tension-modulated Karplus-Strong string: a hard strike starts sharp and glides down to nominal pitch (the "boing"); `tension: 0` reduces to the linear `pluck`; seeded strike excitation (**native kernel**) |
| `sympathetic` | `coupling: 0..1`, `buzz: 0..1`, `damping:`, `brightness:` | one struck string driving a bank of tarab strings (tuned to its near-harmonics) through a shared nonlinear (sitar-`buzz`) bridge; the un-struck strings ring on for an evolving halo; `coupling: 0` reduces to a single Karplus-Strong string; seeded strike excitation (**native kernel**) |
| any classic shape | `unison: 2..16`, `spread: Nc` | detuned stack, golden-ratio phases (no RNG); survives pitch envelopes |

The physical models (`pluck`, `modal`, `bowed`, `blown`, `brass`, `struck`, `sympathetic`) ignore pitch envelopes (glide/vibrato) by design. The `bowed`/`blown` waveguides speak ~2% sharp of nominal (delay-line quantization + excitation phase delay); `brass` carries a measured loop-phase correction (~±10c); `struck`/`sympathetic` (Karplus-Strong) are in tune. Plugin oscillators and drum voices extend the `osc:`/`voice:` choices.

---

## 6. Performance & rhythm

All deviation from the grid comes from per-note seeded RNG paths or fixed templates — "imperfect" and byte-reproducible at once, with everything expanded into explicit IR values.

| Property | Where | Behavior |
|----------|-------|----------|
| `groove: <name> [amount]` | asset | template × amount → explicit 16-slot timing (fractions of a 16th) and accent arrays, applied to drum patterns and note onsets |
| `humanize: 0..1` (or `time=…s vel=…`) | notes/drums | macro → `{timing_s, vel}` (at 1.0: ±18 ms, ±15%); per-hit seeded jitter |
| `velbright: 0..1` | notes | velocity→timbre: soft notes get a lowpass pulled toward the fundamental (measured: vel 0.3 vs 1.0 → 400 vs 1923 Hz centroid on a saw) |
| `glide: Ns` | notes | portamento from the previous note (monophonic-line semantics), exponential |
| `vibrato: rate=Hz depth=Nc delay=Ns` | notes | per-note vibrato entering after `delay` with a fade-in |
| `arp: <pattern> [rate=…b octaves=N gate=0..1]` | notes | chords in the layer sequence instead of sounding together. Patterns: `up down updown downup random` (`random` order is seeded from variant + layer + event index — compile-stable) |
| `slur( … )` / `play … legato` | notes/instrument | phrase groups (since 2.12). On instrument layers, consecutive slurred notes render with **legato joins**: the outgoing note holds through an equal-power crossfade (`legato: Ns`, default 0.05 s), the incoming note skips 60 ms past its recorded attack and glides its read rate from the previous pitch — a real smear, not a crossfade artifact. Synth layers use slurs for phrasing only (use `glide:` for portamento) |
| `section: size=N [spread=0..1] [detune=Nc] [timing=Ns]` | instrument | ensemble multiplication (since 2.12): N seeded virtual players — independent timing (±9 ms default), micro-detune (±7 c), per-player round-robin pools — spread across the stereo stage (the layer becomes true stereo; `pan:` offsets the whole section). Use multiplication to thicken or for divisi; it is not a substitute for independently recorded sections |
| `phrasing: 0..1` | notes/instrument | a deterministic arch over slur groups (since 2.12): velocities rise toward the group's pitch peak (±18% at 1.0) and ease after; the last note lifts (−5% duration, −7% velocity). Documented constants, no learned model |
| `dynamic: beats=mark, …` | notes/instrument | dynamics as timbre (since 2.11). Marks `ppp pp p mp mf f ff fff` map to documented 0..1 values (0.10/0.22/0.35/0.48/0.60/0.74/0.87/1.00); raw numbers accepted; a hairpin is simply two points. On **instrument** layers the curve drives equal-power, *time-varying* velocity-layer crossfades (a crescendo on one held note moves through the recorded layers) plus a −9 dB..0 level term — real dynamics are mostly timbre. On **notes** layers it drives brightness (full velbright coupling unless `velbright:` is set explicitly) and the same level term, with brightness sampled at note onset. Per-note `vel` remains a local accent on amplitude |

**Drum patterns** are 16th-note strings (`x` hit, `X` accent, `.` rest), or Euclidean: `pattern: euclid(5,16)` / `euclid(5,16,rot)` expands via Bjorklund to the explicit string. Glide and vibrato render through pitch-envelope synthesis (phase integration / variable-rate table reads), bandlimited at the envelope's maximum frequency.

---

## 7. Buses & mix

```
bus music {
  gain: -1db
  duck: source=kick amount=5db attack=0.012s release=0.18s threshold=-38db
  fx: peak(400hz, gain=-2, q=1.1), hall(rt60=2.3s, mix=0.22), saturate(amount=0.15)
  auto gain: 0s=-3db, 8s=0db
}
layer pad : tone { ... bus: music ... }
```

Layers without `bus:` route directly to the master. Buses process in declaration order: **duck → fx chain → gain → gain automation**, then sum into the mix. Bus fx run through the same true-stereo chain machinery as the master, so a bus hall is one shared reverb instance, not N copies.

**Sidechain ducking:** `duck.source` is a layer name or `bus:<name>` of an *earlier* bus (cycles are impossible by construction). The gain curve gates the source against `threshold` per 1 ms block, then approaches full/zero reduction with exact piecewise-exponential attack/release — deterministic, no per-sample loops. A hash-pinned VO sample layer as duck source gives reproducible voiceover ducking.

---

## 8. Stage & room (since 2.13)

For staged layers, per-layer reverb is replaced by a physically-motivated, fully deterministic chain (the fx path remains for sound design):

```
stage {
  hall: "stalbans_ortf_ir.wav@<sha256>"   # content-addressed measured IR
  mics: tree=0.72, close=0.22, ambient=0.4
  size: 15m, 23m, 12m                      # shoebox fit (default 18,26,10)
}
layer vln1 : instrument { ... seat: -16deg @ 4.5m ... }
```

`seat: <azimuth>deg @ <distance>m` places a source; seats and buses are mutually exclusive (the stage is the staged layer's bus). Three taps per source, blended by `mics:`: **close** = the spot mic (placement with distance clamped to 1.5 m); **tree** = the main-pair image: direct sound at distance (1/r gain, air absorption as a −0.3 dB/m high-shelf above 6 kHz — a documented approximation of ISO 9613-1 behavior, not a certified implementation — constant-power azimuth pan plus a sub-ms ITD) **plus** image-source early reflections over the shoebox (second order, reflection coefficient 0.82, closed-form, seedless, cached); **ambient** = one shared stereo convolution per stage with the pinned hall IR (stereo IRs give a decorrelated tail; the tail feed is distance-flat, as in real halls). The main pair captures direct + early sound together, so the mix model does too. Sectioned layers keep their internal stereo image; the seat adds distance, air, and the shared room. The shipped `stalbans_ortf_ir.wav` is the Lady Chapel, St Albans Cathedral from OpenAIR (University of York), **CC BY 4.0 — attribution required**, recorded in `samples/stalbans_ortf_ir.ATTRIBUTION.txt`; point `hall:` at any IR you own, pinned the same way.

## 9. FX chains

`fx: lowpass(1800hz), plate(decay=0.7, mix=0.3)` — comma-separated, applied in order; usable on layers, buses, and the master. Positional args fill the primary parameter.

| Call | Parameters (defaults) | Notes |
|------|----------------------|-------|
| `lowpass(hz, q=0.7071)` `highpass(hz, q=0.7071)` `bandpass(hz, q=0.9)` | | biquads; cutoff automatable (§10) |
| `peak(freq, gain, q=0.7071)` | dB ±24 | RBJ parametric bell |
| `lowshelf(freq, gain)` `highshelf(freq, gain)` | | RBJ shelves |
| `delay(time=0.25, feedback=0.3, mix=0.3)` | | |
| `reverb(decay=1.2, mix=0.25)` | | seeded-IR convolution reverb |
| `hall(rt60=2.5, damp=0.4, mix=0.3)` | | Freeverb-lineage combs + allpasses |
| `plate(decay=0.7, damp=0.3, predelay=0, mod=0, modrate=1, mix=0.3)` | feedback 0.1..0.97 | Dattorro 1997 tank, published constants. `mod>0` engages the original's delay modulation via the native kernel (needs a C compiler; mod=0 path validated to machine epsilon against it) |
| `fdn(rt60=3, rt60_high=rt60·0.4, crossover=2500, size=1, mix=0.3)` | | 8-line Householder FDN, per-line shelving: independent low/high RT60. True stereo on master/buses |
| `convolve(file="ir.wav", sha256="…", mix=0.3, gain=0db)` | | hash-pinned impulse response: real spaces under sample content-addressing. Energy-normalized; mismatch refuses. Mono IR per channel in stereo chains |
| `comp(threshold=-18, ratio=2.5, attack=0.03, release=0.15, knee=6, makeup=0)` | | lookahead windowed-RMS, soft knee; stereo-linked on master/buses |
| `mbcomp(threshold=-20, ratio=2, low=180, high=2800, …)` | | 3-band LR4 glue |
| `transient(attack=0, sustain=0)` | dB ±12 | envelope-follower transient shaper: onsets vs body |
| `saturate(amount=0.3, mix=1, warmth=0.3)` | | 4×-oversampled biased-tanh glue; `warmth` adds even harmonics; `mix=0` is bit-exact bypass |
| `drive(amount=0.3)` | | harder oversampled tanh |
| `ladder(cutoff, resonance=0.5, drive=0, mix=1)` | | nonlinear Moog-style transistor-ladder lowpass: 2×-oversampled tanh saturation inside the resonance feedback, so it self-oscillates and squelches as a flat biquad cannot (**native kernel**) |
| `tape(drive=0.4, flutter=0.3, tone=0.5, mix=1)` | | analog tape: LFO-swept fractional delay (wow/flutter) feeding a saturation with light magnetic hysteresis, plus HF loss (`tone`) — time-varying *and* nonlinear (**native kernel**) |
| `tremolo(rate=5, depth=0.5)` `gain(db)` | | |
| *any plugin name* | named args pass through | |

---

## 10. Automation

```
auto cutoff: 0s=400, 26s=2400, 36s=600    # first filter in this fx chain
auto gain:   0s=-12db, 26s=0db            # layer / bus / master gain
auto scan:   0s=0, 8s=1, 16s=0.2          # morph oscillator wavetable position
```

Breakpoints interpolate linearly (log-domain for cutoff; clipped 0..1 for scan). Gain is a sample-accurate multiplier; cutoff drives a block-based time-varying biquad with carried state; scan reaches the morph oscillator per-sample (sliced per note in `notes` layers). Breakpoint times are real seconds (tempo maps do not bend them).

### Performance curves

Compiled IR schema `1.1` uses the same curve object for continuous performance
state. `pitch_cents` is a relative pitch offset in cents and `dynamic` is a
normalized performance dynamic in `[0, 1]`. Curves may live on note events
(`note_beats` or `note_seconds`) or layer automation (`layer_beats` or
`layer_seconds`); existing automation targets continue to use layer scope.

The compiler lowers legacy expressive fields before render:

- `vibrato` becomes dense sampled `pitch_cents` curves.
- `glide_s` becomes linear-in-cents `pitch_cents` curves from the previous
  pitch offset to zero.
- authored `dynamic` breakpoints are re-emitted as explicit `dynamic` curves.

Interpolation is explicit in IR: points are `[time, value]` or
`[time, value, shape]`, where shape is `linear`, `hold`, or `pow:k`
(`k` in `[0.1, 10]`). Edges hold the nearest endpoint and single-point curves
are constants. Complex shapes should compile to dense breakpoints rather than
adding runtime-private logic. `pitch_cents` curves sum in cents and render as
`f_base * 2 ** (cents / 1200)`. Unsupported physical-model pitch curves reject
with `curve_unsupported_voice`; sampled instruments and synth notes consume
curves directly.

---

## 11. Variation at scale

One spec is a pack factory and a campaign master.

**Variants.** A `variant` tag folds into the spec hash, coherently re-realizing every seeded path (pad textures, humanize, grains, breath, dither) while the composed note IR stays identical. Under the same engine version, the same tag renders byte-identically. SDK: `forge.compile(src, variant="v3")`, `asset.variant(tag)`; CLI: `render --variant v3`.

**`vary()` choice sets** — structural variation. Any property value can offer alternatives, resolved per variant by a stable SHA-256 of variant|asset|scope|prop:

```
pattern: vary(X...x..., X..x..x.)
groove: vary(laidback 0.5, pushed 0.4)
grainsize: vary(0.06s, 0.12s)
```

No variant = alternative 0 (the canonical render). Resolved values are explicit in the compiled IR.

**Campaign cutdowns** — declared in the asset:

```
cutdowns {
  15s: keep 0s to 5.5s, keep 19.5s to 30s, fade 0.5s
  6s: keep 23.5s to 30s, fade 0.5s
}
```

The premaster renders once; each cutdown splices its keep-windows with equal-power crossfades, then gets the full loudness/fade finish at the declared targets. The validator requires windows to assemble to the declared length (±1 s). Manifests record parent spec hash + windows. CLI: `audioforge campaign spec.af`; packs: `audioforge pack spec.af --variants 8` (+ `pack.manifest.json`).

**Intensity ladder.** `asset.with_intensity(0.3)` / `--intensity 0.3` scales the intensity-curve-derived master automation — the same cue at a different dramatic temperature, hash-tracked.

---

## 12. Smart AI-agent directives

High-level musical intent may be written at asset level. Smart directives are
compile-time sugar: every render-affecting choice expands into explicit JSON IR
under normal layer/master parameters, while the original intent is preserved
under `intent` for agents to inspect. The semantic `intent` sidecar is excluded
from render hashes; only the explicit layer/master expansion can change audio
identity.

```
style: cinematic
perform:  style=cinematic expressivity=0.8
ensemble: synth size=5 spread=0.45 octaves=1
voicing:  richness=0.7 extensions=7,9
space:    hall=studio depth=0.5
```

`style:` supplies deterministic defaults from the style-pack registry. Built-ins:
`ambient baroque choral cinematic folk jazz metal minimalism pop romantic techno
trap`. Explicit directives override those defaults.

`perform:` first runs a deterministic phrase analysis over note layers and
preserves it under `intent.analysis.phrases`; then it expands to concrete
`humanize`, `phrasing`, `velbright`, `dynamic`, vibrato, slur ids, and phrase-peak
lengthening. `ensemble:` expands synth notes to unison/spread and sampled
instruments to `section`; `octaves` adds explicit octave-doubling note events and
role-routes layers through generated `af_bass`/`af_harmony`/`af_melody` buses.
`voicing:` adds requested 7/9/11/13 extensions to simultaneous chord stacks as
normal note events and may add `gen voice_leading`, `gen suspension`, or
`gen passing_tone` notes. `space:` appends deterministic master glue and creates
an `af_space` bus with shared room processing. The compiler emits a diagnostic
naming the expansion; inspect `compile` output to see the exact render-layer IR.

Structured `intent {}` blocks preserve higher-level agent goals without hiding
render behavior. Closed, typed fields are render-affecting:

```
intent {
  density: sparse      # sparse | balanced | dense -> layer gain deltas
  contour: arch        # flat | arch | rise | fall -> master gain automation
  texture: smooth      # neutral | smooth | airy | warm | bright -> master fx

  affect: tense        # metadata-only
  avoid: clipping, noise
  repair: "make the melody less rough"
  style_text: "reference-free glassy nocturne"
}
```

`density`, `contour`, and `texture` lower deterministically into explicit
render IR and record their expansion under `intent.structured.expansions`.
`affect`, `avoid`, `repair`, and `style_text` are metadata-only: they are
preserved under `intent.structured.metadata`, excluded from render hashes, and
cannot alter audio unless paired with a render-affecting field. Conflicts emit
warnings rather than silently resolving intent, for example `density: sparse`
with `ensemble size > 6`, or `avoid: clipping` with a master peak above
`-0.5db`. The decompiler preserves authored structured intent when
`intent.structured` is present; otherwise it emits the canonical render-layer
equivalent.

Semantic round-tripping uses the `_meta.semantic` sidecar emitted by the DSL
compiler. When present, `audioforge decompile` preserves authored motif
definitions, `play` statements, explicit smart directives, score sections,
buses, automation, and dynamics. Style-pack inverses are intentionally lossy
unless a safe semantic inverse is available, so those specs decompile to the
canonical render-layer equivalent. Agent tools can call
`audioforge.decompile.decompile_diagnostics(spec)` to detect lossy cases.

`audioforge capabilities` is the canonical agent manifest: it includes the
current engine/DSL versions, layer/FX/articulation enums, smart-directive
properties, structured intent block fields, style packs, score-layer syntax,
interop commands, examples, repair hints, and known incompatibilities.

---

## 13. Universal score, audio, style, and interop pillars

**Universal score/time layer.** `meter`, `pickup`, `form`, `repeat`, and
`polymeter` preserve musical structure under `score`. These fields do not hide
render behavior; they are semantic handles for agents and import/export tools,
while note events remain explicit.

```
meter: 7 8
pickup: 1b
form: intro 0b for 7b, verse 7b for 14b, refrain 21b for 7b
repeat: verse x2
polymeter: percussion 3 4
```

**Universal audio/source layer.** `audio` is the recorded-source authoring form.
It compiles to the same content-addressed sample IR used by `sample`, so vocals,
field recordings, stems, and found sound are deterministic resources:

```
layer vocal_take : audio {
  file: "take.wav"
  sha256: "...64 hex..."
  preserve: stereo
  start: 0s
}
```

**Universal style layer.** Style packs live in `audioforge.styles` and are listed
by `audioforge capabilities`. A style pack is just deterministic defaults for
`perform`, `ensemble`, `voicing`, and `space`, which then expand into explicit IR.

**Universal interop.** The explicit note IR can be exported to standard MIDI bytes
or MusicXML and imported back to a renderable synth-backed spec:

```
audioforge export-midi spec.af -o out.mid
audioforge import-midi out.mid --id from_midi
audioforge export-musicxml spec.af -o out.musicxml
audioforge import-musicxml out.musicxml --id from_xml
```

MIDI pitch-bend import becomes layer-scope `pitch_cents` automation and honors
RPN pitch-bend range when present. Arbitrary AudioForge pitch or dynamic curves
that cannot be represented by the current MIDI/MusicXML exporters are reported
through `interop_diagnostics()` as `lossy_pitch_curve` or
`lossy_dynamic_curve`.

---

## 14. Samples, libraries, ingestion

**Single files.** Sample and IR files resolve against registered search paths (default `./samples`; add with `audioforge.samples.add_sample_path(dir)` or in-memory `register_sample(name, bytes)`). `audioforge ingest dir/` hashes and catalogs every WAV and prints paste-ready, hash-pinned layer snippets.

**Instrument libraries.** A library is a directory of WAV + SFZ files plus a `library.manifest.json` pinning every byte and the instrument→SFZ mapping (the manifest hash covers both — remapping an instrument changes audio, so it changes the hash). `audioforge libgen dir/ --name N --license L` generates it; specs pin it with `library: "name@manifest_sha256"`, which folds into the spec hash; every sample is byte-verified at first load and mismatches refuse with both hashes named. Libraries resolve against `./libraries` plus `audioforge.library.add_library_path(dir)`.

**Articulations (since 2.11).** Per note (`art spiccato`) or per layer (`articulation:`). If the library samples the articulation, its SFZ map is selected; otherwise a documented synthetic fallback applies and is **recorded in the render manifest** (`articulation_fallbacks`) — loud, not silent: staccato/spiccato = sustain clamped to 0.18/0.12 s; pizzicato = shortest available articulation clamped to 0.10 s; marcato = +2.5 dB, hard attack; tremolo = seeded ~12 Hz re-trigger train; legato = sustain until the legato-join mechanism described in Performance & rhythm.

The sampler interprets a documented SFZ subset: `<control>/<global>/<group>/<region>` inheritance, `default_path`, key/velocity mapping (`key lokey hikey pitch_keycenter lovel hivel`), **seeded round-robins** (`seq_length/seq_position` — picked from the per-note RNG path, which includes the variant tag, so repeats vary, re-renders are byte-identical, and pack variants re-realize), `ampeg_*` envelopes, forward loops with equal-power seam crossfades (`loop_mode/loop_start/loop_end/loop_crossfade`), and `tune/transpose/volume`. Unknown opcodes are collected and reported, never silently honored. Resampling is a fixed 32-tap windowed-sinc kernel (measured ±0.3 cents through a 44.1k→48k pitch-shifted path). `pitch_cents` curves multiply the per-sample source-read rate before cumulative source-position integration, so bends and vibrato also cross looped sustain regions in source coordinates. Without a `dynamic` curve, velocity maps linearly to amplitude and selects layers on the 1–127 scale; with one, the curve owns selection and crossfade (§10).

---

## 15. Emotion macro expansion (exact mapping)

Emotion never invents notes or changes timing — only spatial/spectral framing, all visible in the compiled IR:

| Derived axis | Formula | Effect |
|--------------|---------|--------|
| `awe` | `awe + 0.6·wonder` | reverb `decay ×(1+0.8·awe)` (cap 15 s), reverb `mix +0.15·awe` (cap 0.7), width `+0.25·awe` |
| `big` | `cinematic_intensity + 0.5·triumph` | width `+0.15·big` (cap 1.0) |
| `calm` | `calm + 0.5·intimacy` | `fade_in ≥ 0.6·calm` s, `fade_out ≥ 1.2·calm` s |
| `dark` | `tension + fear + 0.7·suspense` | appends master lowpass at `9000·(1−0.65·min(dark,1))` Hz |

`sadness`/`urgency` are metadata-only. An `intensity:` curve maps value `v` → master gain `−14·(1−v)` dB. **Authoring note:** stacked dark tags can over-darken a mix (the macro warns with the resulting cutoff); brighten by lowering tension/fear/suspense or raising layer cutoffs.

---

## 16. Master block, loudness, mastering order

`width:` (0..2 — M/S side scale: 0 = mono, 1 = as-mixed, >1 widens beyond the mix; the mid is preserved so the mono sum is unchanged), `peak:` (dBFS true-peak ceiling), `lufs:` (integrated target), `fadein:`/`fadeout:` (s), `fx:`, `auto gain:`.

The master stage runs: **fx chain → gain automation → DC blocker (~8 Hz, always on) → LUFS gain + lookahead true-peak limiter (4× oversampled, stereo-linked, iterative makeup) → seeded dither → quantize**. `lufs:` uses a BS.1770-style measurement (K-weighting, gated 400 ms blocks); the manifest reports `measured_lufs`, `applied_gain_db`, max gain reduction, and `final_lufs`. Without `lufs:`, output is peak-normalized to `peak:`. 16-bit exports use high-pass TPDF dither; 24-bit flat TPDF. `loopsafe: on` fails compilation on non-whole-beat durations.

Export presets (SDK/CLI `--preset`): `social_video` 48k/16/−14 · `broadcast` 48k/24/−23 · `cinematic_master` 96k/24/−16 · `web_preview` 22k05/16/−16.

---

## 17. Includes (content-pinned imports, since DSL 1.10)

Reusable `motif`/`bus` definitions live in `.afi` fragment files and are pulled
into a `.af` with a SHA-256-pinned `import`, before any `asset`:

```
import "stdlib/rock_buses.afi" @ sha256:ab3f…
import "ourband/riffs.afi"     @ sha256:9c21…

asset song { … play riff @ 0b … }      # imported motif used like a local one
```

Resolution is **pure substitution that runs before the parser** — it reads,
verifies, de-duplicates, and inlines; it never computes. The rules that keep it
safe and reproducible:

- **Pinned** — the SHA-256 must match the file's bytes or compilation refuses
  (loud and local). The same discipline as `library:`/`sample` pins.
- **Reproducible** — the *resolved* source is what compiles, so an imported
  patch is byte-identical to the same patch written inline: same `spec_hash`,
  same audio. Import pins are recorded as provenance in `_meta.imports`
  (hash-excluded); rendered identity comes from the expanded events.
- **Acyclic** — the import graph is a DAG; cycles refuse. Diamonds (a fragment
  reached by two paths, same pin) de-duplicate to one inclusion.
- **Flat with collision detection** — two definitions of the same name refuse.
  Namespacing (`import … as ns`, `ns.name`) is a deliberate follow-up that
  needs a grammar change (`docs/adr/0001-dsl-extensions.md`).
- **Materialisable** — `audioforge expand spec.af [-o out.af]` writes the single
  fully-resolved file, so an agent can always read exactly what will render.

Imports require a file context (`load_file` / CLI), not a bare compiled string.

---

## 18. Determinism, manifests, versioning

Every render is keyed to the spec content hash; `ENGINE_VERSION` folds into it, so any engine change that could alter bytes changes all hashes — stale caches can never masquerade as current renders. Manifests record spec hash, output SHA-256, loudness report, markers, variant/intensity tags, and cutdown lineage. `audioforge render --analyze` also writes deterministic analysis features and actionable recommendations (`low_foundation_weak`, `mono_image`, `very_bright`, etc.) into the manifest for agent critique loops. `audioforge verify spec manifest` re-renders and compares output hashes — the CI reproducibility gate. Cross-platform float reproducibility is *checked* by that gate per environment, not assumed.

Runtime version metadata is owned by `audioforge.version`. The DSL banner in
this document, the capability manifest, `audioforge --version`, and compiled IR
`_meta.dsl_version` / `_meta.engine_version` must match those constants.
`docs/RELEASE_NOTES.md` records DSL and engine version changes, including
whether a migration is required.

## 18. Diagnostics contract (for agents)

The executable grammar lives in `audioforge.lark_parser` as a Lark grammar and is the source for the published EBNF/GBNF artifacts (`audioforge grammar --format ebnf|gbnf`). Parse/compile errors raise with line numbers. Non-fatal advice arrives as warnings: out-of-scale notes (advisory — chromaticism is allowed), unknown properties (ignored, named), emotion expansion notes, cutdown length mismatches, and note events that extend past the asset duration. The SDK (`AudioForge.compile`) never raises on user input — everything is a structured `Diagnostic(severity, message, path)`.

## 19. CLI

```
audioforge validate spec.af
audioforge compile  spec.af
audioforge expand   spec.af [-o out.af]            # inline content-pinned imports
audioforge plan     spec.(af|json) [-o file] [--explain]
audioforge decompile spec.(af|json)
audioforge repair   spec.af [--analysis FILE] [--feedback "…"]
audioforge capabilities
audioforge grammar  [--format ebnf|gbnf]
audioforge export-midi spec.(af|json) -o out.mid
audioforge import-midi out.mid [--id ID]
audioforge export-musicxml spec.(af|json) -o out.musicxml
audioforge import-musicxml out.musicxml [--id ID]
audioforge score    spec.(af|json) [-o out.pdf] [--title T] [--bars N]
audioforge render   spec.(af|json) [-o dir] [--preset P] [--stems] [--variant T] [--intensity K] [--analyze]
audioforge pack     spec.af [--variants N] [-o dir] [--preset P]
audioforge campaign spec.af [-o dir] [--preset P] [--intensity K]
audioforge ingest   samples_dir/ [-o catalog.json]
audioforge libgen   library_dir/ [--name N] [--version V] [--license L]
audioforge batch    specs_dir/ [-o dir]
audioforge verify   spec manifest
```

## 20. Honest limits

LUFS is a BS.1770-style approximation (manifests record measured values). Compressors are documented offline lookahead-RMS designs, not analog models. The native-kernel features — the `bowed`/`blown`/`brass`/`struck`/`sympathetic` voices, the `ladder` and `tape` effects, and plate-`mod` — need a C compiler and fail loudly without one (never a silent fallback that would change the audio). Space IRs are computed in a Python loop bounded by tail length (seconds per parameter set, cached). Physical models ignore pitch envelopes; the `bowed`/`blown` waveguides speak ~2% sharp (`brass` is loop-phase-corrected, `struck` is in tune). Layers are mono pre-pan, except sectioned instrument layers, staged layers, and non-pattern audio layers with `preserve: stereo|channels`, which are true stereo. The stage approximates: ISO 9613-1-flavored air shelf, integer-sample ITD (≤ ~21 µs quantization), image-source to second order only, no B-format decoding (stereo IRs only). Sample layers accept WAV PCM only. The darkness emotion macro can over-darken (it warns). Encoder-dependent formats (future FLAC/MP3) will sit outside the byte-hash guarantee. The sampler covers a documented SFZ subset only (no filters/LFOs/CC — AudioForge fx and automation own that ground); synth-layer dynamic brightness samples at note onset (the level term is fully time-varying); sampled-layer crossfades are time-varying throughout.
