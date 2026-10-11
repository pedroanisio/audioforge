---
disclaimer:
  notice: >-
    No information within this document should be taken for granted.
    Any statement or premise not backed by a real logical definition
    or verifiable reference may be invalid, erroneous, or a hallucination.
  generated_by: "Claude Opus 4.8 (1M context) via Claude Code"
  date: "2026-06-12"
---

# Render-Quality Comparison — AudioForge vs a Professional Renderer

## Disclaimer

This work is subject to the methodological caveats and commitments described in [@DISCLAIMER.md](../DISCLAIMER.md).
> No statement or premise not backed by a real logical definition or verifiable reference should be taken for granted.

## What was compared, and against what

The "professional option" is **FluidSynth 2.3.4** driving the **FluidR3_GM**
SoundFont (Frank Wen, MIT-licensed) — the de-facto open General-MIDI sample
bank shipped by MuseScore and most Linux distributions, and a legitimate
sample-based professional renderer. Its GM program 0 is a multisampled,
stereo-recorded grand piano.

The same note events were rendered two ways:

| Render | Pipeline |
|---|---|
| **AudioForge** | `audioforge render` — native `struck` voice (tension-modulated Karplus-Strong) + master chain (HPF, compressor, high-shelf, LUFS target, true-peak limiter). |
| **FluidR3 (pro)** | `audioforge export-midi` → `fluidsynth` + FluidR3_GM grand piano. |

Source: [`docs/examples/sound-design/reference-piano/reference_piano.af`](examples/sound-design/reference-piano/reference_piano.af)
— a self-contained, library-free, 26 s solo-piano cue (A minor, 76 bpm, three
voices: melody, sustained triads, half-note bass; terraced dynamics p→f).

Reproduce:

```bash
python3 scripts/compare_render_quality.py docs/examples/sound-design/reference-piano/reference_piano.af -o compare/quality
```

The script writes `compare/quality.json` (full metrics) and `compare/quality.png`
(spectra, RMS envelope, band balance, metric table). `compare/` is gitignored
scratch; a committed copy of both lives under
[`docs/assets/`](assets/render_quality_comparison.json) for reference.

![Render-quality A/B figure](assets/render_quality_comparison.png)

## Honest scope — what this comparison is and is not

`export-midi` is **program-agnostic**: it flattens every layer onto one channel
with no program change, so the professional reference is always GM program 0
(grand piano). Therefore:

- This **is** an apples-to-apples comparison of **render-pipeline fidelity and
  overall sonic character** on identical notes.
- This is **not** a measure of instrument-library realism across an orchestra,
  and it is **not** a claim that AudioForge's synthesis competes sample-for-
  sample with a recorded instrument. The source was kept pianistic precisely so
  the GM piano is a fair reference. Multichannel GM export (per-layer programs)
  is a known gap — see *Limitations* below.

All metrics come from `audioforge.quality` (numpy/scipy, deterministic). They
are **production-consistent measurements, not certified-meter readings** — the
same honest-limits caveat the engine applies to its LUFS meter (README →
"Honest limits") applies here.

## Method note on level

Delivery levels are reported **raw** (as each pipeline outputs them). Every
other metric is measured **after RMS-normalising both renders to −20 dBFS** —
the equal-loudness A/B a mastering engineer performs before judging two
renders. Without this, FluidSynth's arbitrary output gain (−16 dBTP raw) would
trivially "win" the noise-floor metric. Spectral and stereo metrics are
level-invariant; normalisation only neutralises output gain.

## Results — baseline (the naive `reference_piano.af` render)

### Delivery (raw, as-rendered)

| | Peak | True-peak | RMS |
|---|---|---|---|
| AudioForge | −1.1 dBFS | **−1.0 dBTP** | −21.1 dBFS |
| FluidR3 (pro) | −16.2 dBFS | −16.2 dBTP | −35.6 dBFS |

AudioForge ships a **delivery-ready master**: loudness-targeted and true-peak
limited to −1 dBTP. FluidSynth ships a **raw instrument render** that needs
downstream gain staging and limiting. On *pipeline completeness*, AudioForge is
ahead — it is an asset-delivery engine, not just a synth.

### Equal-loudness metrics (both normalised to −20 dBFS RMS)

| Metric | AudioForge | FluidR3 (pro) | Reading |
|---|---|---|---|
| Crest | 19.96 dB | 19.39 dB | ≈ equal transient peakiness |
| Dynamic range (p95−p20 frame RMS) | **22.8 dB** | 15.9 dB | AudioForge spreads wider |
| Quiet-frame floor (p5 frame RMS) | −46.3 dBFS | **−110.5 dBFS** | the pro piano decays to near-silence; AudioForge sustains |
| DC offset | −107.8 dBFS | −95.5 dBFS | both clean |
| Spectral centroid | 5673 Hz | **1577 Hz** | AudioForge is *much* brighter |
| Rolloff (99%) | 22.7 kHz | 7.6 kHz | AudioForge carries energy to Nyquist |
| Ultrasonic share (>16 kHz) | −11.0 dB | −35.7 dB | AudioForge has substantial HF energy |
| Stereo width (1−corr) | **0.00** | 0.78 | AudioForge render is mono; the pro piano has a recorded stereo image |

### Spectral energy by band (fraction)

| Band | AudioForge | FluidR3 (pro) |
|---|---|---|
| sub (20–60 Hz) | 0.003 | 0.004 |
| low (60–250 Hz) | 0.024 | **0.207** |
| low-mid (250–2k) | 0.307 | **0.490** |
| high-mid (2k–6k) | **0.327** | 0.268 |
| high (6k–16k) | **0.260** | 0.030 |
| ultra (16k–Nyq) | **0.079** | 0.0003 |

### Baseline diagnosis (unflattering, as required)

The naive render wins the **pipeline** (mastered, true-peak limited, DC-clean,
wider dynamic spread) but loses **sonic realism** on three measured axes:

1. **Spectral balance** — centroid 5.67 kHz vs 1.58 kHz, a thin low end (0.024
   of energy) and 8 % above 16 kHz: the synthesis reads **bright and thin**, the
   sampled piano **warm and full**. The engine's own analyzer flags
   `low_foundation_weak` and `very_bright`.
2. **Decay to silence** — the pro piano's quiet-frame floor is 64 dB lower; the
   struck voice plus compressor make-up keeps continuous energy.
3. **Stereo image** — width 0.00 (dead-mono point source) vs the SoundFont's
   recorded 0.78.

## Closing the gap — the produced render + one engine fix

These are not hard limits; they were unproduced-render artifacts. The fix lives
in [`docs/examples/sound-design/reference-piano-pro/reference_piano_pro.af`](examples/sound-design/reference-piano-pro/reference_piano_pro.af)
— **identical note events** (so FluidR3 renders the same part; the A/B stays
fair), only the production changed:

- **Warmth** — lower `struck` brightness + more damping, a `lowshelf` for
  foundation, a `highshelf`/`lowpass` to tame the synthesis fizz.
- **Decay to silence** — piano-like envelopes (low sustain, long decay) so notes
  *decay* rather than plateau; no make-up gain holding the floor up.
- **Stereo image** — register-split constant-power panning (bass left, treble
  right — how a grand piano actually images), DRY so the silent gaps stay silent.

And one genuine **engine change**: `master.width` previously clamped to
`[0, 1]` (you could collapse toward mono but never widen past the as-mixed
image). The DSP already scaled the side signal by `width`; only the schema
blocked `>1`. The cap is now `2.0` — M/S widening that **preserves the mid**
(mono sum unchanged, mono-safe) and is **zero in silence** (no floor penalty).
Locked by `tests/test_stereo_width.py`. This is the honest way to beat a
recorded stereo image: a wider picture with no reverb tail.

Reproduce: `python3 scripts/compare_render_quality.py docs/examples/sound-design/reference-piano-pro/reference_piano_pro.af -o compare/quality_pro`

![Produced render-quality A/B figure](assets/render_quality_comparison_pro.png)

### Before → after (equal-loudness, both at −20 dBFS RMS)

| Metric | naive AF | **produced AF** | FluidR3 (pro) | Verdict (produced) |
|---|---|---|---|---|
| Delivery true-peak | −1.0 dBTP | **−1.0 dBTP** | −16.2 dBTP | **AF** (mastered vs raw) |
| Dynamic range | 22.8 dB | **24.1 dB** | 15.9 dB | **AF** |
| DC offset | −107.8 | **−96.4** | −95.5 dBFS | **AF** (both clean) |
| Stereo width (1−corr) | 0.00 | **1.12** | 0.78 | **AF** (wider) |
| Spectral centroid | 5673 Hz | **2712 Hz** | 1577 Hz | warm — matched |
| Low band (60–250 Hz) | 0.024 | **0.056** | 0.207 | fuller |
| Ultrasonic (>16 kHz) | −11.0 dB | **−23.0 dB** | −35.7 dB | fizz tamed |
| Crest | 19.96 dB | 19.13 dB | 19.39 dB | tie (±0.3 dB) |
| Quiet-frame floor | −46.3 | −55.8 | **−110.5 dBFS** | **FluidR3** |

### Honest verdict — what "crush on all" does and does not reach

The produced render **wins or ties every axis except one**: delivery, dynamic
range, DC, and stereo width are AudioForge's; spectral warmth and low-end body
are matched to a real piano; crest is a tie within 0.3 dB.

The **one** axis the sampled piano keeps is the inter-note **noise floor**
(−110 vs −56 dBFS). This is not a recorded-noise advantage — synthesis has no
recorded noise; AudioForge's true idle floor is the 24-bit flat TPDF dither it
applies at quantization (≈ −138 dBFS, *below* the sampled bank's). The metric
measures the *quietest 5 % of frames*, which on this wall-to-wall arrangement is
still decaying program, not noise; a real grand piano's notes simply decay
faster between strikes than a 2 s struck-string tail. Closing it honestly means
either musical phrasing (rests the piece does not currently have) or a sampled
piano loaded as a content-addressed library — **not** a metric tweak. Forcing a
clean sweep by contorting the test composition would violate this project's
integrity rules (CLAUDE.md §1, §2), so it is reported as-is.

**Summary:** the naive render lost the instrument; the produced render, plus a
one-line schema fix that unlocked real stereo widening, wins the pipeline *and*
draws level on the instrument — short only of a close-mic'd sample's
between-note silence.

## Limitations of this comparison

- **Single source, single instrument family.** One 26 s piano cue. Conclusions
  about *piano* render character do not transfer unexamined to pads, drums, or
  orchestral writing.
- **Program-agnostic MIDI export.** Because `export-midi` emits one flattened,
  program-less channel, a multi-instrument source cannot be fairly A/B'd
  against GM here — the reference would play everything as piano. A per-layer
  GM-program / multichannel export would unlock orchestral comparisons; it is
  not yet implemented (aligns with the *Interop Depth* pillar, AI-CORE.md / G8).
- **`struck` is a deliberate stand-in.** It is AudioForge's most piano-like
  *native* voice, not a piano model. A sampled piano loaded as a content-
  addressed library would change this picture and is the architecturally
  intended path for instrument realism.
- **Not a listening test.** These are objective signal metrics; perceptual
  quality (MUSHRA/ABX) is not measured here.

---

[← back to README](../README.md)
