---
disclaimer:
  notice: >-
    No information within this document should be taken for granted. Claims
    require verification against the implementation and its acceptance tests.
  generated_by: "GPT-6 via Codex"
  date: "2026-09-05"
---

# AudioForge

Deterministic audio-asset generation for production pipelines. A pinned spec and engine produce reproducible audio within a verified runtime environment. Non-vocal by design: music, sound design, SFX, ambience, beats, loops, jingles, transitions, and branded sonic identities.

```
.af DSL  ──compile──▶  JSON IR (hashed ground truth)  ──render──▶  WAV + manifest
 agents                inspectable, mutable, versioned            sha256-verified
```

## Disclaimer

This work is subject to the methodological caveats and commitments described in [@DISCLAIMER.md](./DISCLAIMER.md).
> No statement or premise not backed by a real logical definition or verifiable reference should be taken for granted.

## Why deterministic

Every spec is canonically hashed (with the engine version folded in). The manifest records `spec_hash` and `output_sha256`; `audioforge verify` re-renders and compares bytes — a CI gate against silent drift. Randomness derives from named component paths under `performance_seed` and `variant`; changing gain or metadata preserves the performance. The complete spec hash still identifies the render contract. No wall clocks, no global RNG.

## Quick start

Engine 3.0 changes audible behavior. Read the [migration guide](docs/MIGRATION_3.md) for gate/release, gain, mastering, repeat and performance-seed changes. The [acceptance ledger](docs/MUSICAL_CORRECTNESS.md) separates measured correctness from listening judgments.

```bash
python -m audioforge.cli validate static/samples/transition_sweep.af
python -m audioforge.cli compile  static/samples/transition_sweep.af   # inspect the IR
python -m audioforge.cli render   static/samples/transition_sweep.af -o out --stems
python -m audioforge.cli batch    static/samples -o out
```

```python
from audioforge import AudioForge

forge = AudioForge()
result = forge.compile(open("static/samples/transition_sweep.af").read())
asset = result.assets[0]                      # diagnostics in result.diagnostics
asset.set("layers.2.gain_db", -10)            # schema-checked mutation
meta = asset.export("out", preset="social_video", stems=True)
```

## The DSL

Full grammar in [docs/DSL_SPEC.md](docs/DSL_SPEC.md). The short version:

```
asset cue_v1 {
  kind: cue
  duration: 12s
  tempo: 60bpm
  key: C minor
  emotion: awe=0.8, tension=0.4          # compile-time macros, IR-visible
  intensity: 0s=0.2, 9s=1.0, 12s=0.1     # -> master gain automation
  marker climax @ 9s

  motif rise { C4 @ 0b for 2b
               G4 @ 2b for 2b vel 0.9 }

  layer pad : notes {
    osc: organ
    gain: -9db
    env: a=2s d=1s s=0.85 r=3s
    notes: C3 @ 0b for 8b, G3 @ 0b for 8b
    play rise @ 4b transpose +12st
    fx: lowpass(1500hz), reverb(decay=6s, mix=0.5)
    auto cutoff: 0s=400, 9s=3000
  }
  master { width: 0.85
           lufs: -16
           peak: -1db }
}
```

Design rule: **the DSL is sugar; the JSON IR is truth.** Emotion tags, intensity curves, motifs, and key expand at compile time into explicit parameters, so an agent can always read exactly what will render. The agent-facing concepts behind this — the consumption model, the universality claim, and the open pillars toward it — are organized in [AI-CORE.md](AI-CORE.md).

## Production features

* **Loudness & dynamics** — BS.1770-style gated LUFS targeting backed by a lookahead true-peak limiter (4× oversampled, stereo-linked, iterative makeup); stereo-linked glue and 3-band multiband compression (`comp`, `mbcomp`); always-on DC blocker before quantization. Gain reduction is reported in the manifest.
* **Stems** — `--stems` writes per-layer pre-master stereo files, each seeded-dithered on its own deterministic path.
* **Sync** — markers land in the manifest and a `.markers.json` sidecar; an example plugin exports EDL marker lists for editors.
* **Export presets** — `social_video` (48k/16/−14 LUFS), `broadcast` (48k/24/−23), `cinematic_master` (96k/24/−16), `web_preview` (22k05/16). Presets derive a re-id'd spec, so every delivery variant is itself hash-tracked.
* **Loop safety** — `loopsafe: on` checks duration under the actual tempo/hold map and measures the premaster and delivered seam and tails.

## SDK & plugins

`audioforge.sdk.AudioForge` is the integration surface: `compile / load_file / load_spec` → `AudioAsset` with `validate / set / mutated / render / preview / export`. Compilation never raises on user input — agents get structured `Diagnostic`s with line numbers.

Five extension points (`audioforge.plugins`): oscillators, fx, drum voices, exporters, validators. Plugins receive an injected seeded RNG and must use no other entropy; plugin names live in specs, so spec hashing covers plugin selection automatically. See `examples/custom_plugin.py`.

## The validate/render contract (v2.14)

From an external review (2026-06-10): `validate` now performs resource **binding**, not just shape checks — `OK: valid` means render-ready, placeholder pins get a distinct diagnostic, render refuses with structured line-cited lists instead of raw tracebacks, and a property test locks the contract (render-time SpecErrors must be pre-reported by validate). DSL ergonomics: multiline `auto` continuation, self-explaining `notes:`/`play` diagnostics, and `slur( play …, play … )` support. `pytest -q` now collects cleanly; `scripts/run_tests.sh` is the canonical full runner. The review's three fixtures live in `static/fixtures/` as diagnostic regressions.

## Stage & room (v2.13 — P4)

The `stage{}` block + `seat: -16deg @ 4.5m`: per-source direct path (1/r, ISO-flavored air shelf, constant-power pan + ITD with verified sign and ~0.33 ms magnitude at 30°), second-order image-source early reflections over a parameterized shoebox (21 arrivals measured, cached), and one shared stereo hall convolution per stage with a content-addressed measured IR — shipped: Lady Chapel, St Albans Cathedral from OpenAIR (CC BY 4.0, attribution recorded). Mic taps close/tree/ambient blend spot, main-pair-with-early, and tail. A staged layout puts sections left and right, timpani 12 m deep, width 0.64 side/mid.

## Orchestral performance model (v2.12 — P3)

**Legato joins** connect contiguous monophonic slur groups using the selected sample's loop or attack boundary, an equal-power crossfade and a pitch glide. This is an approximation, declared in the render plan. **Section multiplication** creates seeded players with a shared timing clock and separate offsets, detune and round-robins; it does not reproduce an independently recorded section. **Phrasing** applies a documented arch by time within the group and preserves authored note gates. `routing: fallbacks=forbid` rejects these approximate sampled routes.

## Orchestral dynamics & articulation (v2.11 — P2)

A `dynamic:` curve (`pp..fff` marks, hairpins) drives **time-varying equal-power velocity-layer crossfades** in the sampler — measured on real VSCO violins: pp selects the 738 Hz-centroid soft layer, ff the 1027 Hz loud layer, one held note moves between them under a hairpin — plus curve-driven brightness on synth voices and a −9 dB..0 level term. **Articulations** per note (`art tremolo`) resolve to sampled maps when present, else to documented synthetic fallbacks recorded in the render manifest. `trill` expands key-aware at compile time.

## Orchestral Tier S (v2.10 — P1)

A **deterministic SFZ-subset sampler** (key/velocity mapping, seeded round-robins, ampeg, loop crossfades, rate-adaptive windowed-sinc resampling with antialias filtering) reading **content-addressed instrument libraries**: `audioforge libgen` pins every sample byte and the instrument mapping into one manifest hash that folds into the spec hash; `instrument` layers play through it with the standard performance machinery. Verified against a real CC0 VSCO 2 Community Edition subset (fetch script in `scripts/`): byte-identical re-renders through 37 pinned files.

## Palette depth (v2.9)

A **blown reed waveguide** (native kernel sibling to bowed; loop-gain constants solved analytically), **parametric drum voices** (tune/decay/snap/bend), **procedural foley** (rain, wind, fire, surf — deterministic ambience competing directly with packs), **sample-pack ingestion** (`audioforge ingest dir/` → hashed catalog + paste-ready snippets), and **hash-pinned convolution IRs** (real spaces, content-addressed) — the shipped `stone_room_ir.wav` is one.

## Variation at scale (v2.8)

One spec → a **pack** (`audioforge pack --variants 8`: seeded variant siblings + `vary()` structural choice sets, every render hash-tracked in a pack manifest), a **campaign** (declared `cutdowns { 15s: keep … }` spliced from one premaster with crossfades and per-cut loudness, full lineage), and an **intensity ladder** (`--intensity 0.3/0.6/1.0`).

## Composition ergonomics (v2.7)

**Chord symbols with voicings** (`C3min7 … voicing drop2`), an **arpeggiator** (`arp: updown rate=0.25b octaves=2`), **Euclidean rhythms** (`pattern: euclid(5,16)`), **motif transforms** (invert / retrograde / stretch / diatonic, key-aware), and **tempo & key maps** — real accelerandi via exact analytic beat→time integration, and mid-cue modulation. Everything compiles to explicit events; the IR stays the ground truth.

## Mix & production (v2.6)

**Buses with shared FX** (one space per group instead of per layer), **sidechain ducking** (kick ducks pads; a hash-pinned VO sample ducks the whole music bus), **parametric EQ** (RBJ peak/shelves on layers, buses, and master), **transient shaping** and **glue saturation** (oversampled biased-tanh with even-harmonic warmth).

## Instrument classes (v2.5)

Five new voices: **custom modal tables** (define `modes:` triplets in the DSL — infinite bespoke percussion), **wavetable morphing** (`osc: morph` with `scan` as an automation target), a **granular texture engine** (seeded grain clouds over any synthesized source), a **bowed waveguide** (native friction-curve kernel; needs a C compiler, fails loudly without), and the **content-addressed sample layer** — specs pin a sample's SHA-256, renders verify it byte-for-byte, pattern mode triggers real one-shots through the groove/humanize pipeline (sample shipped in `samples/`).

## Performance realism (v2.4)

Notes stop sitting on a perfect grid with identical timbre: **groove templates** (swing/shuffle/laid-back/pushed feels as explicit per-16th timing+accent arrays in the IR), **seeded humanization** (±ms timing and velocity jitter from per-note RNG — deterministic imperfection), **velocity→brightness** (soft notes are duller, not just quieter), **portamento** and **per-note vibrato** (delayed, fading in, rendered via pitch-envelope synthesis).

## Instruments (v2.1)

Research-grade, fully mechanized voices — no samples, all seed-deterministic: **PADsynth** ensemble pads (Nasca's public-domain Gaussian-harmonic IFFT, perfectly looping), **Karplus-Strong** plucked strings (Jaffe/Smith lineage, fractional tuning, pick-position comb), **modal resonator banks** (bell/glass/marimba/gong/steel mode tables with frequency-dependent decay), **supersaw unison** (golden-ratio phase decorrelation), and exact-Fourier wavetables that lift the old 64-harmonic cap to full Nyquist bandwidth. Spatial (Tier 2): a **Dattorro plate** (the published 1997 figure-8 tank — delay lengths, diffusion coefficients, and stereo output-tap tables, rendered as an exact LTI impulse response and applied by FFT convolution) and a **per-band FDN hall** (8 coprime delay lines, Householder feedback, independent low/high RT60 — long lows, faster highs). Both are true stereo on the master bus with decorrelated tails; a **Freeverb-lineage hall** remains as the lightweight option, alongside the convolution reverb. Saturation runs 4× oversampled; 16-bit exports get high-pass TPDF dither.

## Layout

```
audioforge/          engine: determinism, synth, fx, sequencer, loudness,
                     schema (IR validation), render, dsl, sdk, plugins, cli
static/samples/      reference .af corpus (quick-start; e.g. transition_sweep.af)
static/fixtures/     diagnostic-regression fixtures (.af)
AI-CORE.md           agent-facing core concepts (consumption model,
                     IR-is-truth, universality claim, open pillars)
docs/DSL_SPEC.md     full DSL grammar + emotion mapping table
examples/            agent_loop.py, integration_pipeline.py, custom_plugin.py
tests/               determinism suite + v2 suite (DSL, SDK, plugins,
                     automation, LUFS, stems, reproducibility)
```

## Notation and analysis

AudioForge is a render contract, not a notation program (ADR-0009). What it offers:

* **Semantic score fields** — `meter`, `pickup`, `form`, `repeat`, `polymeter` compile to
  `spec.score` and, since 3.0, drive rendering (repeats expand, meter sets groove phase).
  `tuning: edo divisions=N` drives the render (n-EDO, chain-of-fifths spelling; ADR-0010);
  `tuplet:` and `lyrics:` compile to typed `spec.notation` metadata that the notated export writes.
* **Interchange** — `audioforge export-musicxml` (exact-tick, and `--notated` quantized to
  measures), `export-midi`, `import-musicxml`, `import-midi`. The notated export is judged by
  the MusicXML 3.1 schema, by music21 and by LilyPond (`make oracle-check`, needs
  `uv pip install -e '.[oracles]'`). Parts, chords, meter, key and tempo changes, the pickup,
  dynamics, articulations, slurs, tuplets, lyrics, fermatas, sections and repeats survive
  the notated round trip; `docs/INTEROP.md` is the generated construct × format matrix, and
  anything an export drops carries a registered code from `interop_diagnostics()`.
* **Analysis** — chord identity from evidence (ambiguous or unrecognised collections are
  reported, never guessed), key-aware extensions, conservative cadence candidates, a
  pitch-class-set core (normal/prime form, interval-class vector). No key finding, no
  roman numerals, no stylistic judgment: export MusicXML and use music21 for those.
* **Proof sheet** — `audioforge score` draws a proportional PDF (noteheads at beat × pitch,
  duration bars, stage plot, intensity ribbon, provenance). It is a proof sheet, not
  engraving; `audioforge score --engrave` (engine 3.1 line) hands the notated MusicXML to
  LilyPond when the `engrave` extra is installed.

Current limits are measured in `docs/evolution/harness-notation.md`.

## Honest limits

* The LUFS meter is a production-consistent BS.1770-style approximation, not a certified meter; manifests record measured values so you can confirm against a reference meter where compliance matters. The limiter is a clean lookahead design, not a multi-stage mastering limiter.
* The plate and FDN render the exact published topologies as impulse responses. Plate delay-line modulation (`mod>0`) is available via an on-demand-compiled native kernel (validated against the Python path at machine epsilon for mod=0); it requires a C compiler and fails loudly rather than silently substituting different audio.
* The compressors are deterministic offline lookahead-RMS designs with documented semantics — built for reproducibility, not analog emulation.
* IR computation is a sequential Python loop bounded by tail length (~2-4 s per parameter set, cached); long multi-space cinematic masters render in tens of seconds rather than seconds.
* Determinism is guaranteed within an environment; cross-platform float reproducibility is *checked* by the `verify` gate rather than assumed.
* Recorded material uses content-addressed WAV sample layers or pinned SFZ-subset instrument libraries. Recorded transitions and ensemble realism depend on the source material; synthesized approximations are declared in the render plan.

Requires Python 3.10+, numpy, scipy. Engine 3.0.0 · DSL 2.0.
