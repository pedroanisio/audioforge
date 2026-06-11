# AudioForge — Smart Music DSL: the musical-intelligence compiler

**Date:** 2026-06-10
**Engine:** 2.14.0 · DSL 1.7
**Builds on:** [North-Star](PROPOSAL_north_star_studio_dsl_ir.md) ·
[Issues](REVIEW_2026-06-10_issues_and_proposals.md)

---

## 0. The problem, named precisely

A spec that validates, resolves, and renders deterministically can still sound
like **bad MIDI**. Evidence: the generated A-major fugue is continuous (2 %
silence) and consonant, yet lifeless. Why? Because the DSL today asks the author
for **notes on a grid** and the engine renders them **literally** — no performer,
no producer, no harmonic depth in between.

"MIDI feel" is a precise set of deficits. Each has a known musical remedy, and
**the engine already has the low-level primitive** for most of them — they're just
opt-in, per-layer, and dumb (no musical reasoning drives them):

| MIDI deficit | Musical remedy | Engine primitive that exists |
|--------------|----------------|------------------------------|
| Rigid timing | micro-timing, agogic accents, phrase-final lengthening, rubato | `humanize`, `groove`, tempo maps |
| Flat dynamics | metric accent, contour-following, phrase arcs, hairpins | `dynamic:` curves, `vel`, velocity→brightness |
| Detached notes | legato/slur, articulation, breath | `slur`, `legato`, `art`, phrasing |
| Thin timbre | ensemble (divisi/unison detune), octave doublings, body | `section`, `detune`, layering, PADsynth |
| Sterile harmony | 7ths/9ths/suspensions, voice-leading, non-chord tones | chord symbols, voicings |
| Dry sound | reverb, hall, real-space convolution, glue | reverb/FDN/plate/`convolve`, bus FX, saturation |
| Static texture | orchestration changes, builds, dynamic automation | `intensity`, `auto`, emotion macros |

**The DSL is not smart because it makes the author assemble all of this by hand,
correctly, every time.** A smart music DSL encodes the *knowledge* — performance
practice, orchestration, harmony, acoustics — as **compile-time intelligence and
musical defaults**, fully consistent with the project's law: *the DSL is sugar,
the IR is truth.* These directives are new sugar that expands to the explicit
performance/production IR the engine already renders.

---

## 1. The design: four enrichment passes + high-level directives

Add a **musical-intelligence layer** to the compiler: high-level directives that
expand, deterministically, into the dense IR. Authors write intent; the compiler
writes the performance.

### New directives (sugar)

```
voicing:  richness=0.7 extensions=7,9         # harmony pass
ensemble: strings size=8 spread=0.6 octaves=1 # orchestration pass
perform:  style=baroque expressivity=0.7       # performance pass
space:    hall=cathedral depth=0.7             # production pass
```

…or, at the top, one word that sets musical defaults for all four:

```
style: baroque        # (or: romantic, cinematic, jazz, ambient, pop)
```

### Pass 1 — Harmony (compositional intelligence)
From a chord track (or inferred from the bass+melody), generate **voice-led**
inner voices with **extensions and non-chord tones** (passing, suspension 4–3,
appoggiatura, 9–8) instead of bare triads. Smooth voice-leading (common-tone
retention, stepwise motion, no parallel 5ths/8ves). Output: explicit notes in the
IR.

### Pass 2 — Orchestration (timbre & texture)
Turn one thin line into a **section**: seeded detuned unison players (the existing
`section`), **octave doublings**, register-appropriate **timbre layering** (an
attack voice + a sustained body/pad bed), and divisi on sustained harmony. This is
where thin → rich.

### Pass 3 — Performance (expressivity)
The anti-MIDI pass. Applied with musical reasoning, not random jitter:
- **Dynamics**: metric accent (strong beats up), melodic-contour (higher = louder),
  **phrase arcs** (crescendo to the phrase peak, diminuendo to the cadence),
  hairpins from a `dynamic:` curve.
- **Timing**: seeded micro-timing; **agogic** lengthening of phrase-peaks and
  cadential notes; **phrase-final ritardando** via a tempo-map tail.
- **Articulation**: auto-**slur** melodic runs (legato), detach cadences;
  velocity→brightness so soft is also duller; delayed **vibrato** on long notes.

### Pass 4 — Production (space & glue)
Bus structure with a **shared reverb/return**; a real **hall or cathedral
convolution** send (the bundled St Albans IR); master **glue** (gentle comp,
EQ tilt, light saturation, width). Dynamic **swells** tied to phrase/intensity.

All four are deterministic (seeded from the spec hash) — richness without losing
the byte-identical moat.

---

## 2. Why this is the *right* DSL improvement

- It is the difference between a **note sequencer** and a **music system**. It is
  what makes the DSL "master music" rather than transcribe it.
- It is **AI-leverage**: an agent emits intent (`style: baroque`, a chord track, a
  melodic contour) — a *small, reliable* surface — and the compiler supplies the
  thousands of expressive micro-decisions that an LLM cannot reliably enumerate
  note-by-note. This is exactly how a smart DSL makes AI authorship produce *good*
  music, not valid-but-dead music.
- It **reuses the engine's existing strengths** (humanize, section, dynamic,
  voicings, convolution) — the work is the *intelligence and defaults*, not new DSP.
- It closes the loop with the north-star's **analysis pass**: render → measure
  (dynamic range, spectral richness, masking) → critique → re-expand.

---

## 3. Prototype (this turn)

`static/renders/_smart_render.py` implements a first cut of all four passes over a
compact harmonic+melodic spec and renders a rich realization of the A-major piece.
Before/after vs. the thin fugue is reported in
[static/renders/RICHNESS.md](../static/renders/RICHNESS.md). The prototype proves
the concept externally; the productization is to fold these as `perform/ensemble/
voicing/space/style` directives into `dsl.py` so any spec gets them.

---

## 4. Roadmap fit

This is **Pillar A (best AI-ready DSL)** of the north-star, deepened: the DSL
becomes smart by carrying musical knowledge. Sequence:

1. **Performance pass** (biggest anti-MIDI win, lowest risk) — dynamics + timing +
   articulation as a `perform:` directive.
2. **Orchestration pass** — `ensemble:` auto-divisi + doublings + body.
3. **Production pass** — `space:` shared reverb/convolution + master glue.
4. **Harmony pass** — `voicing:` voice-leading + extensions (most compositional).
5. **`style:` presets** that set musically-correct defaults for all four.

Determinism, IR-is-truth, and compile-never-raises remain non-negotiable.
