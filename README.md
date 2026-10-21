---
disclaimer:
  notice: >-
    No information within this document should be taken for granted. Claims
    require verification against the implementation and its acceptance tests.
  generated_by: "GPT-6 via Codex; revised by Claude Opus 5.5 via Claude Code"
  date: "2026-09-28"
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

## Install

Requires Python 3.10+ and a C compiler (`cc`, `gcc` or `clang`) on `PATH`: every render runs
through native kernels compiled on first use (`make native-check` confirms the compiler).

```bash
uv sync --extra dev                  # or: python -m pip install -e '.[dev]'
```

Runtime dependencies: lark, numpy, scipy, matplotlib. Optional extras: `dev` (tests),
`oracles` (MusicXML XSD, music21 on Python 3.11+, LilyPond; `make oracle-check`) and
`engrave` (LilyPond only). The `audioforge` console script is equivalent to
`python -m audioforge.cli`.

## Quick start

Engine 3.0 changes audible behavior. Read the [migration guide](docs/MIGRATION_3.md) for gate/release, gain, mastering, repeat and performance-seed changes. Engine 3.2 changes output bits again (native kernels, at most −131 dBFS from 3.1 on the example corpus) and renders with about 4.4× less CPU; see "Engine 3.2: render cost and numeric drift" in the same guide. The [acceptance ledger](docs/MUSICAL_CORRECTNESS.md) separates measured correctness from listening judgments.

```bash
python -m audioforge.cli validate docs/examples/sound-design/transition-sweep/transition_sweep.af
python -m audioforge.cli compile  docs/examples/sound-design/transition-sweep/transition_sweep.af   # inspect the IR
python -m audioforge.cli render   docs/examples/sound-design/transition-sweep/transition_sweep.af -o out --stems
python -m audioforge.cli batch    docs/examples/sound-design/transition-sweep -o out
```

```python
from audioforge import AudioForge

forge = AudioForge()
result = forge.compile(open("docs/examples/sound-design/transition-sweep/transition_sweep.af").read())
asset = result.assets[0]                      # diagnostics in result.diagnostics
asset.set("layers.2.gain_db", -10)            # schema-checked mutation
meta = asset.export("out", preset="social_video", stems=True)
```

## Cues for video

A library of 36 prebuilt, parameterized cues — music beds that fit any length, stings,
transitions, UI, foley and ambience — renders on demand and drops into our
scene-render videos as resolved `<generated provider="audioforge">` assets:

```bash
audioforge cue list
audioforge scene add scene.xml bed/documentary-airy "key='E minor'" --id mus-bed --duck-under bus-vo
audioforge scene add scene.xml transition/whoosh duration=0.8 --id fx-cut --start 12.4
audioforge scene resolve --check scene.xml     # CI: exit 3 when a cue is stale
```

Guide, loudness standard and catalog: [docs/CUES.md](docs/CUES.md).

## Composition examples

Browse [all compositions](docs/examples/index.md) for the DSL, source requirements and render commands. Generate the local listening gallery with `.venv/bin/python scripts/examples.py gallery`, then open `docs/examples/listen.html`.

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

* **Expressive performance techniques** — first-class note modifiers (`tech palm_mute`, `dead_note`, `let_ring`, `accent`, `harmonic`, `sul_ponticello`, …), note-scope timbre curves (`cutoff(Nhz)`, `level(Ndb)`, `scan(N)`), and fretted/stringed mechanics (`tuning:`, `string N`, `fret N`, `max_fret:`). Every technique **lowers at compile time** to explicit, diffable, hash-owned IR — the renderer never receives a private "technique" concept (IR schema 1.2; see [docs/DSL_SPEC.md](docs/DSL_SPEC.md)).
* **Public-domain sample catalog** — `audioforge sample-catalog` builds content-addressed, license-audited SFZ instrument libraries from public sources (download → analyze → group → generate SFZ → manifest), with per-file license evidence. Full spec in [docs/goal.md](docs/goal.md).
* **Loudness & dynamics** — BS.1770-style gated LUFS targeting backed by a lookahead true-peak limiter (4× oversampled, stereo-linked, iterative makeup); stereo-linked glue and 3-band multiband compression (`comp`, `mbcomp`); always-on DC blocker before quantization. Gain reduction is reported in the manifest.
* **Stems** — `--stems` writes per-layer pre-master stereo files, each seeded-dithered on its own deterministic path.
* **Sync** — markers land in the manifest and a `.markers.json` sidecar; an example plugin exports EDL marker lists for editors.
* **Export presets** — `social_video` (48k/16/−14 LUFS), `broadcast` (48k/24/−23), `cinematic_master` (96k/24/−16), `web_preview` (22k05/16/−16). Presets derive a re-id'd spec, so every delivery variant is itself hash-tracked.
* **Loop safety** — `loopsafe: on` checks duration under the actual tempo/hold map and measures the premaster and delivered seam and tails.

## SDK & plugins

`audioforge.sdk.AudioForge` is the integration surface: `compile(dsl)` and `load_file(path)` return a `CompileResult` (assets + diagnostics); `load_spec(dict)` returns an `AudioAsset`. An `AudioAsset` offers `validate / set / mutated / render / preview / export`, plus `plan`, `analyze`, `variant`, `with_intensity`, `export_cutdowns` and `to_json / to_dsl / to_midi / to_musicxml`; `AudioForge` also provides `export_pack`, `catalog`, `import_midi` and `import_musicxml`. DSL compilation never raises on user input — agents get structured `Diagnostic`s with line numbers; JSON specs are validated directly and raise `SpecError`. Agent tool schemas (`tool_schemas` / `run_tool`) and an MCP server (`python -m audioforge.mcp`) expose the same surface; see [docs/AGENT_TOOLS.md](docs/AGENT_TOOLS.md).

**Sound match** (`audioforge.match`, `scripts/sound_match.py`): give a target sample, get back an editable `.af` patch by offline analysis-by-synthesis — the engine is its own forward model, and the emitted patch is independently re-rendered to report a *verified* confidence, not an asserted one. See [docs/SOUND_MATCH.md](docs/SOUND_MATCH.md).

Five extension points (`audioforge.plugins`): oscillators, fx, drum voices, exporters, validators. Fx and drum-voice plugins receive an injected seeded RNG; no plugin may use other entropy; plugin names live in specs, so spec hashing covers plugin selection automatically. See `examples/custom_plugin.py`.

## The validate/render contract (v2.14)

From an external review (2026-06-10): `validate` now performs resource **binding**, not just shape checks — `OK: valid` means render-ready (on a host with a C compiler; `validate` does not check for one), placeholder pins get a distinct diagnostic, render refuses with structured line-cited lists instead of raw tracebacks, and a property test locks the contract (render-time SpecErrors must be pre-reported by validate). DSL ergonomics: multiline `auto` continuation, self-explaining `notes:`/`play` diagnostics, and `slur( play …, play … )` support. `pytest -q` now collects cleanly; `scripts/run_tests.sh` is the canonical full runner. The review's three historical scores live in `docs/examples/archive/` (historical DSL, migration required) and are covered by the DSL-AST golden snapshot.

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

One spec → a **pack** (`audioforge pack --variants 8`: seeded variant siblings + `vary()` structural choice sets, every render hash-tracked in a pack manifest), a **campaign** (declared `cutdowns { 15s: keep … }` spliced from one premaster with crossfades and per-cut loudness, full lineage), and an **intensity ladder** (`render --intensity 0.3`, then `0.6`, then `1.0`; also accepted by `campaign`).

## Composition ergonomics (v2.7)

**Chord symbols with voicings** (`C3min7 … voicing drop2`), an **arpeggiator** (`arp: updown rate=0.25b octaves=2`), **Euclidean rhythms** (`pattern: euclid(5,16)`), **motif transforms** (invert / retrograde / stretch / diatonic, key-aware), and **tempo & key maps** — real accelerandi via exact analytic beat→time integration, and mid-cue modulation. Everything compiles to explicit events; the IR stays the ground truth.

## Mix & production (v2.6)

**Buses with shared FX** (one space per group instead of per layer), **sidechain ducking** (kick ducks pads; a hash-pinned VO sample ducks the whole music bus), **parametric EQ** (RBJ peak/shelves on layers, buses, and master), **transient shaping** and **glue saturation** (oversampled biased-tanh with even-harmonic warmth).

## Instrument classes (v2.5)

Five new voices: **custom modal tables** (define `modes:` triplets in the DSL — infinite bespoke percussion), **wavetable morphing** (`osc: morph` with `scan` as an automation target), a **granular texture engine** (seeded grain clouds over any synthesized source), a **bowed waveguide** (native friction-curve kernel; needs a C compiler, fails loudly without), and the **content-addressed sample layer** — specs pin a sample's SHA-256, renders verify it byte-for-byte, pattern mode triggers real one-shots through the groove/humanize pipeline (samples ship inside the package, in `audioforge/data/samples/`).

## Performance realism (v2.4)

Notes stop sitting on a perfect grid with identical timbre: **groove templates** (swing/shuffle/laid-back/pushed feels as explicit per-16th timing+accent arrays in the IR), **seeded humanization** (±ms timing and velocity jitter from per-note RNG — deterministic imperfection), **velocity→brightness** (soft notes are duller, not just quieter), **portamento** and **per-note vibrato** (delayed, fading in, rendered via pitch-envelope synthesis).

## Instruments (v2.1)

Research-grade, fully mechanized voices — no samples, all seed-deterministic: **PADsynth** ensemble pads (Nasca's public-domain Gaussian-harmonic IFFT, perfectly looping), **Karplus-Strong** plucked strings (Jaffe/Smith lineage, fractional tuning, pick-position comb), **modal resonator banks** (bell/glass/marimba/gong/steel mode tables with frequency-dependent decay), **supersaw unison** (golden-ratio phase decorrelation), and exact-Fourier wavetables that lift the old 64-harmonic cap to full Nyquist bandwidth. Spatial (Tier 2): a **Dattorro plate** (the published 1997 figure-8 tank — delay lengths, diffusion coefficients, and stereo output-tap tables, rendered as an exact LTI impulse response and applied by FFT convolution) and a **per-band FDN hall** (8 coprime delay lines, Householder feedback, independent low/high RT60 — long lows, faster highs). Both are true stereo on the master bus with decorrelated tails; a **Freeverb-lineage hall** remains as the lightweight option, alongside the convolution reverb. Saturation runs 4× oversampled; 16-bit exports get high-pass TPDF dither.

## Command line

`audioforge <command>` (or `python -m audioforge.cli <command>`); `audioforge --version`
prints the engine and DSL versions. [docs/DSL_SPEC.md](docs/DSL_SPEC.md#cli) has the
complete command block, and [AGENTS.md](AGENTS.md) the verb table (both test-gated
against `cli.py`).

| Area | Commands |
|---|---|
| Author and inspect | `validate` (`--no-resolve`), `compile`, `decompile`, `plan` (`--explain`), `grammar` (`--format ebnf\|gbnf`), `capabilities`, `repair` |
| Render | `render` (`--stems`, `--preset`, `--variant`, `--intensity`, `--jobs`, `--analyze`, `--plan`, `--explain`), `batch`, `verify SPEC MANIFEST` (exit 2 on mismatch) |
| Variation | `pack` (`--variants`, `--preset`), `campaign` (`--preset`, `--intensity`) |
| Video cues | `cue list / show / dsl / render / gallery`, `scene resolve` (`--check`, `--force`), `scene add` |
| Samples and libraries | `ingest`, `libgen`, `sample-catalog search / resolve-openverse / download / analyze / build-sfz / audit-license / review` |
| Notation | `export-musicxml` (`--notated`, `--bars`), `export-midi`, `import-musicxml`, `import-midi`, `score` |

## Environment variables

| Variable | Effect |
|---|---|
| `AUDIOFORGE_JOBS` | Layer-rendering threads (default 1; `render --jobs` sets it). Output is byte-identical for any value. |
| `AUDIOFORGE_NATIVE_CACHE` | Directory for compiled kernels (default `$XDG_CACHE_HOME/audioforge` or `~/.cache/audioforge`). Kernels are keyed by source, compiler flags and CPU identity. |
| `AUDIOFORGE_MALLOC_TUNE=0` | Leave glibc malloc untouched during renders (by default freed render buffers are kept for reuse and returned when the render ends). |
| `OPENBLAS_NUM_THREADS` | Defaults to 1 when `audioforge` is imported before numpy (idle BLAS workers only burn CPU); an explicit value wins. |

## Development

`make check` is the gate CI runs: native-check, schema/manifest/interop/golden/drift/version/
docs/lock/floor drift gates, then the full suite (`scripts/run_tests.sh`). `make help` lists
every target; discrete fast gates such as `make docs-check` exist for local iteration.
Generated artifacts (`docs/ir.schema.json`, `docs/capability-manifest.json`,
`docs/DIAGNOSTIC_CODES.md`, `docs/INTEROP.md`, `docs/reference.md`,
`docs/capabilities.md`, `tests/golden/audio.lock.json`) are rewritten by their tools under
`audioforge/tools/`, never by hand.

## Layout

```
audioforge/          engine package
  dsl.py, lark_parser.py      .af DSL: grammar (LALR) and compiler to the JSON IR
  schema.py, ir_schema.py     IR validation and the generated JSON Schema
  render.py, sequencer.py     layer rendering, timelines, mixing, mastering
  synth.py, sampler.py, ...   voices: synthesis, SFZ-subset sampler, foley, samples
  fx.py, spaces.py, dynamics.py, loudness.py, convolution.py   effects and mastering
  _native.py, native/*.c      ctypes wrappers and C kernels (compiled on first use)
  sdk.py, cli.py, agent_tools.py, mcp/   integration surfaces
  interop.py, musicxml.py, score.py      MIDI/MusicXML interchange, proof sheets
  tools/                      generators and gates behind `make check`
docs/                DSL spec, IR schema, migration guide, ADRs, generated references
docs/examples/       compositions: DSL, documentation and local rendered audio
examples/            agent_loop.py, integration_pipeline.py, custom_plugin.py, reverb_ab.py
samples/             shipped content-addressed samples and impulse responses
scripts/             test runner, example gallery, drift inspection, library fetchers
static/fixtures/     focused acceptance/rejection fixtures (.af)
tests/               pytest suite, golden locks and fixtures
AI-CORE.md           agent-facing core concepts (consumption model, IR-is-truth,
                     universality claim, open pillars)
```

## Notation and analysis

AudioForge is a render contract, not a notation program (ADR-0011). What it offers:

* **Semantic score fields** — `meter`, `pickup`, `form`, `repeat`, `polymeter` compile to
  `spec.score` and, since 3.0, drive rendering (repeats expand, meter sets groove phase).
  `tuning: edo divisions=N` drives the render (n-EDO, chain-of-fifths spelling; ADR-0014);
  `tuplet:` and `lyrics:` compile to typed `spec.notation` metadata that the notated export writes.
* **Interchange** — `audioforge export-musicxml` (exact-tick, and `--notated` quantized to
  measures), `export-midi`, `import-musicxml`, `import-midi`. The notated export is judged by
  the MusicXML 3.1 schema, by music21 and by LilyPond (`make oracle-check`, needs
  `uv pip install -e '.[oracles]'`; music21 installs on Python 3.11+ only). Parts, chords, meter, key and tempo changes, the pickup,
  dynamics, articulations, slurs, tuplets, lyrics, sections and repeats are projected.
  Fermata positions are shown, but their pause lengths are unspecified on import.
  Polymeter uses the global score meter with `lossy_polymeter`;
 `docs/INTEROP.md` is the generated construct × format matrix, and
  anything an export drops carries a registered code from `interop_diagnostics()`.
* **Analysis** — chord identity from evidence (ambiguous or unrecognised collections are
  reported, never guessed), key-aware extensions, conservative cadence candidates, a
  pitch-class-set core (normal/prime form, interval-class vector). No key finding, no
  roman numerals, no stylistic judgment: export MusicXML and use music21 for those.
* **Proof sheet** — `audioforge score` draws a proportional PDF (noteheads at beat × pitch,
  duration bars, stage plot, intensity ribbon, provenance). It is a proof sheet, not
  engraving. Use `musicxml2ly` followed by `lilypond` for typeset scores. A built-in `score --engrave` backend is planned for notation M5; the `engrave` extra only pre-installs LilyPond for the external path.

Current limits are measured in `docs/evolution/harness-notation.md`.

## Electronic production

The French-house toolkit (ADR-0015): a `drums` machine with groove and swing, sidechain
`duck:` pumping, resonant `ladder` sweeps under `auto cutoff:`, and since this line
`phaser`, `flanger`, `chorus` and `bitcrush` effects, a bus `vocoder:` that lets any layer's
spectral envelope shape a synth bus (robot voices from material you supply — the engine
generates no voice), and sample layers that can be cut (`offset`, `length`), reversed,
time-stretched at constant pitch and chopped into pattern-triggered `slices`. Five
tracks in `docs/examples/electronic/house-*/house_*.af` exercise every piece; `docs/ELECTRONIC_TRACKS.md`
lists them with their render manifests.

## Honest limits

* The LUFS meter is a production-consistent BS.1770-style approximation, not a certified meter; manifests record measured values so you can confirm against a reference meter where compliance matters. The limiter is a clean lookahead design, not a multi-stage mastering limiter.
* The plate and FDN render the exact published topologies as impulse responses. Plate delay-line modulation (`mod>0`) uses a native kernel validated against the IR path at machine epsilon for mod=0.
* Rendering requires a C compiler: limiting, filtering, saturation, halls, delays and wavetable voices run in native kernels (`audioforge/native/`), built with `-O3 -march=native -ffp-contract=off` and cached per CPU. Without a compiler, rendering fails loudly rather than substituting different audio.
* The compressors are deterministic offline lookahead-RMS designs with documented semantics — built for reproducibility, not analog emulation.
* The Dattorro plate IR is still a sequential Python loop (0.8–2.6 s CPU for 3.6–12 s tails, cached per process and parameter set); FDN IRs are generated natively. The two 10-minute examples (`s03_highway_opens`, `last_24h`) render in 24 s and 34 s of CPU.
* Determinism is guaranteed within an environment (native kernels give identical bits across SSE2/AVX2/AVX-512 builds); cross-platform float reproducibility is *checked* by the `verify` gate rather than assumed.
* The vocoder is a channel vocoder (band envelopes), not a formant or LPC model; the time stretch is a plain phase vocoder (transients smear at large ratios). Neither generates voices.
* Recorded material uses content-addressed WAV sample layers or pinned SFZ-subset instrument libraries. Recorded transitions and ensemble realism depend on the source material; synthesized approximations are declared in the render plan.
* A measured A/B against a professional sample-based renderer (FluidSynth + FluidR3_GM) is recorded in [docs/RENDER_QUALITY_COMPARISON.md](docs/RENDER_QUALITY_COMPARISON.md) (`audioforge.quality`, `scripts/compare_render_quality.py`).

Requires Python 3.10+, lark, numpy, scipy, matplotlib and a C compiler. Engine 3.3.1 · DSL 2.0.
