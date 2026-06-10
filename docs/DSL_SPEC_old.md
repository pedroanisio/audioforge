# AudioForge DSL Specification (v1.0)

The `.af` DSL is the authoring surface for humans and AI agents. It compiles to a JSON spec — the deterministic intermediate representation (IR) that the engine renders. Everything expressive in the DSL (emotion tags, intensity curves, motifs, key) is **expanded at compile time** into explicit JSON parameters, so the IR is always the single, inspectable ground truth for what will be rendered. Same DSL text → same IR → same spec hash → byte-identical audio.

## 1. Lexical rules

Comments run from `#` to end of line (a `#` *inside* an identifier, as in `C#4`, is part of the identifier). Statements are line-oriented; a property list continues onto the next line if the current line ends with a comma or is inside parentheses.

Numbers may carry a unit suffix, which is validated against what the property expects:

| Unit | Meaning | Example |
|------|---------|---------|
| `s` | seconds | `duration: 36s` |
| `b` | beats | `C4 @ 8b for 2b` |
| `bpm` | tempo | `tempo: 60bpm` |
| `db` | decibels | `gain: -9db` |
| `hz` | frequency | `lowpass(1800hz)` |
| `st` | semitones | `transpose +12st` |
| `c` | cents | `detune: 7c` |

Notes are written as pitch names: `C4`, `F#2`, `Eb3`, `A-1` (MIDI-style octaves, A4 = 440 Hz). Raw frequencies are accepted anywhere a note is: `432hz @ 0b for 4b`.

## 2. Structure

```
asset <id> {
  <asset properties>
  marker <name> @ <time_s>
  motif <name> { <note events> }
  layer <name> : <type> { <layer properties> }
  master { <master properties> }
}
```

A file may contain multiple `asset` blocks; each compiles to its own spec.

### 2.1 Asset properties

| Property | Value | Compiles to |
|----------|-------|-------------|
| `kind:` | `signature` `sfx` `loop` `jingle` `transition` `cue` `bed` `soundtrack` | `kind` |
| `duration:` | seconds | `duration_s` |
| `samplerate:` | integer Hz | `sample_rate` (default 48000) |
| `bitdepth:` | `16` or `24` | `bit_depth` (default 24) |
| `tempo:` | bpm | `bpm` |
| `swing:` | 0..1 | `swing` |
| `key:` | e.g. `C minor`, `A major` | `key` (metadata + advisory scale check) |
| `loopsafe:` | `on` | `loop_safe` (validates whole-beat duration) |
| `emotion:` | `name=0..1, ...` | `emotion` metadata + macro expansion (§5) |
| `intensity:` | `time=0..1, ...` | master `gain_db` automation + `intensity_curve` metadata |

Known emotion tags: `tension awe sadness triumph suspense intimacy urgency calm fear wonder cinematic_intensity`. Unknown tags are kept as metadata with a warning.

### 2.2 Markers

`marker climax @ 26s` — compiled into `markers`, written to the manifest and a `.markers.json` sidecar for video-timeline alignment (and exportable as an EDL via plugin).

### 2.3 Motifs and `play`

```
motif ascent {
  C4 @ 0b for 1.5b vel 0.7
  G4 @ 3b for 2b vel 0.85
}
layer voice : notes {
  ...
  play ascent @ 10b
  play ascent @ 24b transpose +12st vel 1.1
}
```

`play` expands the motif into the layer's note list at compile time, offsetting starts, scaling velocities, and transposing (transposed notes compile to explicit `freq_hz`). Motifs are pure macros — the IR contains only the expanded notes.

### 2.4 Layer types and properties

`layer <name> : <type>` where type is `tone`, `sweep`, `noise`, `drums`, or `notes` (plugin oscillators and drum voices extend `osc:`/`voice:` choices).

Common: `gain:` (db), `pan:` (-1..1, constant-power), `start:` (s), `env: a=… d=… s=… r=…` (ADSR; a/d/r in seconds, s is level 0..1), `fx:` (§3), `auto <target>:` (§4).

| Type | Specific properties |
|------|--------------------|
| `tone` | `osc:` (`sine saw square triangle fm organ pad pluck modal`), `note:` or `freq:`, `detune:` (cents), `duration:`, `fmratio:`/`fmindex:` for FM |
| `sweep` | `shape:`, `from:`/`to:` (hz), `curve:` (`lin`/`exp`), `duration:` |
| `noise` | `color:` (`white pink brown`), `duration:` |
| `drums` | `voice:` (`kick snare hat open_hat clap tom` + plugins), `pattern:` (16th-note string, `x` hit, `X` accent, `.` rest) |
| `notes` | `osc:`, `notes:` event list, `play` statements, `loop:` (beats — repeats the note block) |

### 2.5 Master properties

`width:` (0..1 stereo width), `peak:` (db true-peak ceiling), `lufs:` (integrated loudness target, §6), `fadein:`/`fadeout:` (s), `fx:`, `auto gain:`.

### 2.6 Instrument voices (v2.1)

The classic shapes are bandlimited to Nyquist via exact-Fourier wavetables. Three physical/spectral instrument classes and a unison stage extend them; all randomness derives from the per-note seeded RNG, so every voice is byte-reproducible.

| Voice | Properties (defaults) | Character |
|-------|----------------------|-----------|
| `osc: pad` | `bandwidth: 40c`, `harmonics: 48` | PADsynth (Nasca, public domain): Gaussian-widened harmonics via one IFFT — lush, perfectly-looping ensemble pads |
| `osc: pluck` | `damping: 0.5`, `brightness: 0.6`, `pluckpos: 0.28` | Extended Karplus-Strong string: seeded noise burst into a fractionally tuned recirculating delay |
| `osc: modal` | `material: bell|glass|marimba|gong|steel`, `modedecay: Ns` | Resonator bank of exponentially decaying partials at the material's mode ratios, plus a seeded strike transient |
| any classic shape | `unison: N` (2..16), `spread: Nc` | Supersaw-style detuned stack with golden-ratio phase offsets (deterministic, no RNG) |

### 2.7 Performance realism (v2.4)

All deviation from the grid is drawn from per-note seeded RNG paths or fixed templates — "imperfect" and byte-reproducible at once. Everything expands into explicit, inspectable IR values.

| Property | Where | Compiles to / behavior |
|----------|-------|------------------------|
| `groove: <name> [amount]` | asset | Template × amount expanded into explicit 16-slot `timing` (fractions of a 16th) and `accent` arrays, applied to drum patterns and note onsets. Templates: `straight swing16 shuffle laidback pushed heavy_one` |
| `humanize: 0..1` (or `time=…s vel=…`) | notes/drums layers | Macro expands to `{timing_s, vel}` (at 1.0: ±18 ms, ±15%); per-hit seeded jitter on timing and level |
| `velbright: 0..1` | notes layers | Velocity→timbre: soft notes get a lowpass pulled toward the fundamental (vel 0.3 vs 1.0 measured at 400 vs 1923 Hz centroid on a saw); loud notes stay open |
| `glide: Ns` | notes layers | Portamento: exponential pitch slide from the previous note (monophonic-line semantics) over N seconds |
| `vibrato: rate=Hz depth=Nc delay=Ns` | notes layers | Per-note vibrato entering after `delay` with a fade-in, the way played vibrato behaves. Applies to oscillator voices; the physical models (pluck/modal) ignore pitch envelopes by design |

Glide and vibrato render through pitch-envelope synthesis (phase integration / variable-rate table reads), bandlimited at the envelope's maximum frequency.

### 2.8 Instrument classes (v2.5)

| Voice / layer | Syntax | Notes |
|---------------|--------|-------|
| Custom modal tables | `osc: modal` + `modes: 1.0 1.0 1.0, 2.31 0.6 0.4, …` | `ratio amp t60_share` triplets (1–32) override the material table — bespoke percussion from a list of numbers |
| Wavetable morphing | `osc: morph` + `scan: 0..1` or `auto scan: 0s=0, 8s=1` | Scan sweeps sine→triangle→pulse→saw→square between bandlimited frames; scan is a first-class automation target, works under glide/vibrato |
| Granular | `layer x : grain` + `source:` (any osc or noise color), `srcdur`, `grainsize`, `density`, `pitchspread`, `scatter` | Seeded grain clouds over a synthesized source; onsets/positions/pitches from one seeded stream — shimmers, never changes between renders |
| Bowed waveguide | `osc: bowed` + `pressure: 0.2..1`, `bowpos: 0.05..0.45`, `brightness` | McIntyre-Woodhouse/STK-lineage friction-curve waveguide; native C kernel (needs a compiler, fails loudly without). Pitch envelopes ignored (physical model) |
| Content-addressed samples | `layer x : sample` + `file: "name.wav"`, `sha256: "…64 hex…"`, then `start:` one-shot or `pattern:` drum-grid | Spec pins the sample's content hash; render verifies bytes and refuses mismatches. Pattern mode gets groove/humanize like any drum. WAV PCM 16/24/32-bit, auto mono-mix + deterministic resample. Search paths: `audioforge.samples.add_sample_path()` |

The sample layer ends the synthesis-only ceiling without giving up reproducibility: same spec + same sample bytes = same output; a swapped file can never silently change a render.

### 2.9 Mix & production (v2.6)

**Buses** — declare before layers reference them; processed in declaration order:
```
bus music {
  gain: -1db
  duck: source=kick amount=5db attack=0.012s release=0.18s threshold=-38db
  fx: peak(400hz, gain=-2, q=1.1), hall(rt60=2.3s, mix=0.22), saturate(amount=0.15)
  auto gain: 0s=-3db, 8s=0db
}
layer pad : tone { ... bus: music ... }
```
Layers without `bus:` route directly to the master. A bus applies duck → fx chain → gain → gain automation, then sums into the mix. `duck.source` is a layer name or `bus:<name>` of an *earlier* bus (cycles are impossible by construction). A hash-pinned VO sample layer as duck source gives automatic voiceover ducking.

**New fx** (usable in layer, bus, and master chains):

| fx | args | behavior |
|----|------|----------|
| `peak(freq, gain, q)` | RBJ cookbook | parametric bell |
| `lowshelf(freq, gain)` / `highshelf(freq, gain)` | RBJ cookbook | shelves |
| `transient(attack, sustain)` | dB, ±12 | envelope-follower transient shaper: onsets vs body |
| `saturate(amount, mix, warmth)` | 0..1 | 4x-oversampled biased-tanh glue; `warmth` adds even harmonics; `mix=0` is bit-exact bypass |

Sidechain duck gain is computed per 1 ms block with exact piecewise-exponential attack/release — deterministic, no per-sample loops. `presets/mix_ab.af` renders the same arrangement flat and fully produced.

### 2.10 Composition ergonomics (v2.7)

All of this expands at compile time into explicit note events and pattern strings — the IR remains the complete ground truth.

**Chords** — root-with-octave + quality, anywhere a note goes (including motifs): `C3min7 @ 4b for 2b vel 0.7 voicing drop2`. Qualities: maj min m dim aug 6 7 9 m6 m7 maj7 min7 maj9 min9 m9 sus2 sus4 add9 dim7 min7b5. Voicings: close (default) drop2 drop3 spread open wide inv1 inv2.

**Arpeggiator** — layer property; chords in that layer sequence instead of block: `arp: updown rate=0.25b octaves=2 gate=0.85`. Patterns: up down updown downup random (the random order is seeded from layer name + event index — compile-stable).

**Euclidean rhythms** — `pattern: euclid(5,16)` or `euclid(5,16,rot)` expands via Bjorklund to the explicit x/. string; combine with groove accents.

**Motif transforms** — flags on `play`, applied retrograde → invert → stretch → diatonic → transpose: `play theme @ 8b invert`, `play theme @ 14b retrograde diatonic -2`, `play theme @ 34b stretch 1.5`. `diatonic ±N` moves by scale degrees in the key in force at the play position; chromatic passing tones keep their offset from the nearest lower scale tone.

**Tempo maps** — `tempo: 92bpm, 20b=92bpm, 26b=116bpm` ramps linearly in BPM between points; beat→seconds is the exact analytic integral, so accelerandi are smooth, not stepped. All grids (notes, drums, groove, swing, loops) follow the map; layer starts, automation, and markers stay in real seconds.

**Key maps** — `key: A minor, 26b=C major` modulates: scale advisories and `diatonic` transforms resolve the key at each position.

### 2.11 Variation at scale (v2.8)

One spec is a pack factory and a campaign master.

**Seeded variants** — a `variant` tag folds into the spec hash, coherently re-realizing every seeded path (pad textures, humanize, grains, dither) while the composed note IR stays identical. Same tag = byte-identical forever; new tag = a sibling, not a clone. SDK: `forge.compile(src, variant="v3")`, `asset.variant(tag)`; CLI: `render --variant v3`.

**vary() choice sets** — structural variation: any property can offer alternatives, resolved per variant by a stable SHA-256 of variant|asset|scope|prop (CRC32 measurably fails to flip on sequential tags): `pattern: vary(X...x..., X..x..x.)`, `grainsize: vary(0.06s, 0.12s)`, `groove: vary(laidback 0.5, pushed 0.4)`. No variant = alternative 0, the canonical render. Resolved values are explicit in the compiled IR.

**Packs** — `audioforge pack spec.af --variants 8 [--preset …]` / `forge.export_pack(src, dir, n=8)`: N hash-tracked renders + `pack.manifest.json` tying every file to its variant tag, spec hash, and output hash.

**Campaign cutdowns** — declare the matrix in the asset:
```
cutdowns {
  15s: keep 0s to 5.5s, keep 19.5s to 30s, fade 0.5s
  6s: keep 23.5s to 30s, fade 0.5s
}
```
The premaster renders once; each cutdown splices its keep-windows with equal-power crossfades, then gets the full loudness/fade finish at the declared target. The validator checks windows assemble to the declared length (±1 s). Manifests record parent spec hash + windows — full lineage. CLI: `audioforge campaign spec.af`.

**Intensity-parameterized renders** — `asset.with_intensity(0.3)` / `render --intensity 0.3` scales the intensity-curve-derived master automation: the same cue at a different dramatic temperature, hash-tracked.

### 2.12 Palette depth (v2.9)

**Blown waveguide** — `osc: blown` + `pressure`, `brightness`: STK-Clarinet-lineage reed model in a native kernel (needs a C compiler; fails loudly). Reed constants were solved from the fixed-point loop-gain equation so it self-oscillates across the whole pressure range; cylindrical-bore spectrum (odd harmonics dominant). Seeded breath turbulence comes from the layer RNG. Pitch envelopes ignored (physical model); like the bowed kernel it speaks ~2% sharp of nominal.

**Drum-voice depth** — drums layers take `tune: ±Nst`, `decay: 0.25..4`, `snap: 0..1` (transient/noise balance), `bend: 0..1.5` (pitch-sweep depth): the built-in kit becomes a parametric kit.

**Procedural foley** — `layer x : foley { model: rain|wind|fire|surf  intensity: 0..1  brightness: 0..1 }`: seeded event clouds and gust/wave envelopes over shaped noise. Rain = wash + droplet transients; wind = gusting spectral tilt; fire = rumble + hiss + seeded pops; surf = asymmetric swells that brighten as they break. Deterministic like everything else.

**Sample-pack ingestion** — `audioforge ingest dir/` (or `samples.ingest(dir)`): hashes and catalogs every WAV (duration, rate, peak, centroid, one-shot/loop guess) and emits ready-to-paste, hash-pinned `layer … : sample` snippets. Packs you already own become deterministic raw material.

**Hash-pinned convolution** — `convolve(file="room_ir.wav", sha256="…", mix=0.3)` in any chain: real spaces under the same content-addressing discipline as samples; the IR is energy-normalized and byte-verified, mismatches refuse with both hashes named. Mono IR applied per channel in stereo chains.

## 3. FX chains

`fx: lowpass(1800hz), reverb(decay=6s, mix=0.5)` — comma-separated calls, applied in order. Positional args fill the call's primary parameter.

| Call | Parameters (defaults) | IR |
|------|----------------------|-----|
| `lowpass(hz, q=0.7071)` | cutoff, resonance | `filter/lowpass` |
| `highpass(hz, q=0.7071)` | | `filter/highpass` |
| `bandpass(hz, q=0.9)` | | `filter/bandpass` |
| `delay(time=0.25, feedback=0.3, mix=0.3)` | seconds, 0..1, 0..1 | `delay` |
| `reverb(decay=1.2, mix=0.25)` | seconds, 0..1 | `reverb` (deterministic seeded IR) |
| `drive(amount=0.3)` | 0..1 | `drive` (tanh) |
| `tremolo(rate=5, depth=0.5)` | Hz, 0..1 | `tremolo` |
| `gain(db=0)` | | `gain` |
| `hall(rt60=2.5, damp=0.4, mix=0.3)` | seconds, 0..1, 0..1 | Freeverb-lineage hall: parallel lowpass-feedback combs + series allpasses |
| `plate(decay=0.7, damp=0.3, predelay=0, mod=0, modrate=1, mix=0.3)` | feedback 0.1..0.97, 0..1, s, 0..1, Hz, 0..1 | Dattorro 1997 plate: the published figure-8 tank, delay lengths, and output-tap tables; `decay` is the tank feedback coefficient as in the paper. `mod>0` engages the original's delay-line modulation (chorus shimmer) via the native kernel — requires a C compiler, validated to reproduce the LTI path at machine epsilon when mod=0 |
| `fdn(rt60=3, rt60_high=rt60*0.4, crossover=2500, size=1, mix=0.3)` | s, s, Hz, 0.5..2, 0..1 | 8-line Householder FDN with per-line shelving losses: independent low-band and high-band RT60 — long lows, faster highs, the frequency-dependent decay of natural rooms. True stereo on the master bus |
| `comp(threshold=-18, ratio=2.5, attack=0.03, release=0.15, knee=6, makeup=0)` | dB, ratio, s, s, dB, dB | Lookahead RMS glue compressor (windowed-RMS detector, soft knee, smoothed gain). Stereo-linked on the master bus |
| `mbcomp(threshold=-20, ratio=2, low=180, high=2800, ...)` | + crossover Hz | 3-band glue: LR4 crossovers, per-band stereo-linked compression — tames bass bloom and harsh highs independently |
| *any plugin name* | named args pass through | `{type: name, ...}` |

## 4. Automation

```
auto cutoff: 0s=400, 26s=2400, 36s=600     # first filter in this fx chain
auto gain:   0s=-12db, 26s=0db             # layer or master gain envelope
```

Breakpoints are linearly interpolated (log-domain for cutoff). Gain automation is a sample-accurate multiplier; cutoff automation drives a block-based time-varying biquad with carried filter state. Compiles to `automation: [{target, points}]`.

## 5. Emotion macro expansion (exact mapping)

Emotion never invents notes or changes timing. It only adjusts spatial/spectral framing, and every adjustment is visible in the compiled IR:

| Derived axis | Formula | Effect |
|--------------|---------|--------|
| `awe` | `awe + 0.6·wonder` | reverb `decay_s ×(1+0.8·awe)` (cap 15 s), reverb `mix +0.15·awe` (cap 0.7), master width `+0.25·awe` |
| `big` | `cinematic_intensity + 0.5·triumph` | master width `+0.15·big` (cap 1.0) |
| `calm` | `calm + 0.5·intimacy` | `fade_in ≥ 0.6·calm` s, `fade_out ≥ 1.2·calm` s |
| `dark` | `tension + fear + 0.7·suspense` | appends master lowpass at `9000·(1−0.65·min(dark,1))` Hz |

`sadness` and `urgency` are currently metadata-only (they inform humans/agents but trigger no macro). An `intensity:` curve maps value `v` → master gain `−14·(1−v)` dB.

## 6. Loudness, peaks, loops

`lufs:` engages a BS.1770-style measurement (K-weighting, 400 ms gated blocks), gains to the target, and runs a lookahead true-peak limiter at the `peak:` ceiling (4× oversampled, stereo-linked detection). The gain→limit pass iterates so heavy transient limiting cannot leave the integrated loudness short of target; the manifest reports `measured_lufs`, `applied_gain_db`, maximum gain reduction, and `final_lufs`. Without `lufs:`, output is peak-normalized to `peak:`. 16-bit exports use high-pass TPDF dither (noise energy pushed above the audible band); 24-bit uses flat TPDF. `loopsafe: on` fails compilation if the duration is not a whole number of beats.

## 7. Diagnostics contract (for agents)

* Parse/compile errors raise with **line numbers** (`line 12: expected 'for'…`).
* Non-fatal advice comes back as warnings: out-of-scale notes (chromaticism is allowed — it's advisory), unknown properties (ignored, named), hot gains, emotion expansion notes.
* The SDK (`AudioForge.compile`) never raises on user input; everything is a structured `Diagnostic(severity, message)`.

## 8. Versioning

The DSL carries `DSL_VERSION`; the engine carries `ENGINE_VERSION`, which is folded into every spec hash — so any engine change that could alter rendered bytes automatically changes all hashes, and stale caches can never masquerade as current renders.

## 9. Mastering chain order (v2.3)

The master stage runs: fx chain (including any comp/mbcomp/spaces) → master gain automation → always-on DC blocker (~8 Hz) → LUFS gain + lookahead true-peak limiter (iterative makeup) → seeded dither → quantize. The compressors are deterministic offline lookahead-RMS designs, not analog feedback models — documented semantics over vintage mythology.

## 10. Space architecture note (v2.2)

`plate` and `fdn` are sample-sequential feedback topologies. With delay-line modulation omitted they are linear time-invariant, so the engine computes each network's stereo impulse response once (a tight loop bounded by tail length, cached per parameter set) and applies it by FFT convolution — exact topology, vectorized rendering, no native dependencies. On the master bus they are true stereo (mono-summed network input, decorrelated left/right tap outputs); inside layer chains they run mono via the averaged response. The original Dattorro design includes a small chorus-like delay modulation that an LTI rendering cannot reproduce; if that shimmer is ever needed, the path is a compiled per-sample kernel.
