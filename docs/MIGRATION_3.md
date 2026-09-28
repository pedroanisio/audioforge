---
disclaimer:
  notice: >-
    No information within this document should be taken for granted. Behavioral
    claims below are bounded by the named implementation and acceptance tests.
  generated_by: "GPT-6 via Codex; revised by Claude Opus 5.5 via Claude Code"
  date: "2026-09-28"
---

# Migrating to engine 3.0, DSL 2.0 and IR 2.0

This release corrects audible behavior. Existing specifications can produce
different levels, note tails, sample spectra, arrangements and performances.
Review renders and regenerate manifests and golden hashes. Structural migration
through `audioforge.ir_schema.migrate_ir_spec` preserves numeric authoring intent;
it does not reproduce an older engine's audio.

Upgrading from 3.1 to 3.2 changes output bits but nothing audible and adds a C
compiler requirement for every render; see
[Engine 3.2: render cost and numeric drift](#engine-32-render-cost-and-numeric-drift).

## Levels, gates and sample playback

Instrument layer gain now applies once, including virtual sections. A `gain:
-6db` adjustment changes the stem by -6 dB; the earlier path applied -12 dB.
Rebalance affected parts by listening in context. Doubling a previous gain value
can approximate its old stem level, but does not restore other old behaviors.

For note events, duration is the held gate. Release starts at note-off, including
notes released during attack or decay. A 0.5-second gate with a 0.2-second release
can sound until 0.7 seconds, subject to available sample data and asset length.
Leave enough room for release and effect tails. If an old duration intentionally
included the synth release, shorten the gate explicitly after converting seconds
through the tempo/hold map. The old fixed-window envelope remains appropriate
for finite non-note sounds such as a noise sweep.

The sampler filters according to instantaneous playback rate and source sample
rate. High frequencies that would fold below Nyquist are suppressed during
transposition and glides. `loop_sustain` exits into the recorded sample tail at
note-off; `loop_continuous` continues looping during its release envelope.

Mastering preserves levels below the ceiling by default. To request the old
peak-normalization intention, write:

```text
master {
  normalize: peak
  peak: -1db
}
```

An explicit `lufs:` target requests loudness normalization; it cannot be combined
with `normalize: peak`. Export presets request their documented LUFS targets.
Fades occur before measurement and normalization. Every mode enforces the
oversampled true-peak ceiling. The LUFS algorithm remains the documented
BS.1770-style implementation, with reported measurements and limited iteration;
a difficult target need not be reached exactly.

## Stable performances during editing

Layer names must be unique within an asset: since 3.0 they identify performance
random streams and stems, so two layers sharing a name would draw identical
randomness and sum coherently (+6 dB instead of +3 dB for two noise beds).
Validation rejects duplicates (`spec.layers[i].name: duplicate layer name`).


`performance_seed: 42` selects a take. Its default is zero. The seed and `variant`
derive a performance hash; named layer/component/event paths derive local random
streams. The complete spec hash, including the engine version, still identifies
the render contract. Both hashes appear in render manifests.

Gain, pan, metadata and edits to another layer no longer reseed unrelated
performances. Keep layer names stable to preserve their identities. Notes use
authored `id` values when present, otherwise onset, pitch and voice plus a
duplicate occurrence index. IDs must be non-empty and unique within a layer.
Renaming a layer, changing note identity, or changing the seed/variant can change
the take. Adding a duplicate unlabelled event can shift duplicate identities;
explicit IDs remove that ambiguity. The SDK `AudioAsset.variant()` changes the
take; compile-time `vary()` choices still require compilation with a variant.

Humanization mixes a shared beat clock with a smaller part-onset deviation;
simultaneous notes in a chord share their onset. Virtual section players use
that clock plus seeded player offsets. Sample plans use the same event schedule,
dynamic selection and per-player seed paths as rendering.

## Harmony, phrases and instrument fidelity

Voicing identifies chord quality and root across inversions and doublings.
Existing sevenths are preserved. Requested extensions use the key at that chord's
onset; without a key, documented quality defaults apply. Ambiguous collections
remain unchanged and are reported (`ambiguous_harmony`, with every candidate) unless an
authored chord symbol resolves them. The ambiguous set is exactly the symmetric and
relative-equivalent qualities of the chord table: `dim7` (four roots share one
collection), `aug` (three roots), `min7`/`m7` ≡ `6` of the relative major (C6/Am7),
`min7b5`/`m7b5` ≡ `m6` of the relative minor (F#m7b5/Am6), and `sus2` ≡ `sus4`
(Csus2/Gsus4) — 120 of the 300 root × quality collections. Every other collection
resolves to one root; parity with music21 is measured by `HARNESS-NANA-001/002`. `voice_leading=on` searches registers/inversions to minimize
squared voice motion while preserving chord tones, timing, gates and event count.
This is a bounded transformation, not a claim of stylistic musical judgment.

Authored form spans and slurs take priority in phrase grouping; remaining groups
follow activity and rests under the meter. Generic expressivity does not invent
slurs, shorten final gates, add vibrato or master compression. Its neutral arch
peaks at the phrase midpoint by time. Cadence labels are conservative candidates
requiring resolved dominant-to-tonic roots, a declared major/minor key and a local
downbeat. They do not prove perceived closure. Emotion tags remain inspectable
production presets; `sadness` and `urgency` remain metadata-only.

Sampled legato connects only contiguous monophonic events in the same voice and
slur: the next note must start no later than 0.02 beats after, and no earlier than
0.25 beats before, the previous note's end, and each onset must carry one note.
Detached slurs (a rest inside the slur) and slurred dyads re-attack; the render plan
carries a `transition` decision only for joined notes. The selected region's loop or attack metadata chooses the source offset;
there is no fixed 60 ms skip. A crossfade/read-rate glide approximates a transition
between stationary samples. Multiplying a solo sample into a section also remains
an approximation. Neither supplies a recorded physical transition or independently
recorded ensemble.

Technique expansion retains `technique_render` evidence describing its controls
and fidelity. The plan reports approximate techniques, sampled joins and section
multiplication. Use `routing: fallbacks=forbid` when approximations are unacceptable;
`warn` emits warnings and `allow` retains informational evidence. A physical
technique name alone is not evidence that the source library contains that gesture.

## Quoted strings

Quoted values are JSON strings: `\\` is a backslash, `\t` a tab, `\"` a quote. A
Windows path must be written `"C:\\samples\\kick.wav"`; a bare backslash sequence
that is not a JSON escape, or a literal control character inside quotes, is a compile
error (`invalid quoted JSON string escape`). Engine 2.16 accepted the raw text.

## Repeats, meter and loop safety

`repeat: verse x2` means two passes including the original. Named, nonoverlapping
sections must fit within the source duration. Expansion extends the asset and
moves following material later. Counts range from 1 to 32; expanded duration
remains within the engine's duration limits.

The expanded contract is validated before compilation succeeds. A cut that creates a gate shorter than the minimum 0.001 beat is rejected; move the cut or adjust the authored event.

Expanded IR contains explicit notes, tempo/hold/key maps, form spans, control
curves and markers. Executable repeats are consumed, with source windows retained
under `intent.arrangement`. Discontinuous cuts re-articulate clipped note gates
and preserve release tails. Continuous sounds repeat dry source windows with
short seam tapers before their effects; those cuts do not preserve an arbitrarily
long dry sound beyond its chosen source window. Effects process the expanded
timeline and can ring across the cuts.

Curve input-clock mappings preserve cropped power curves, logarithmic cutoff
ramps and offset automation. `time_offset` shifts a curve's input;
`time_map` splices contiguous `[source_start, source_end, destination]` windows
in its declared time basis. Canonical decompilation uses `automation_ir:` and
`notes_ir:` JSON strings when needed, and `clip_source:`/`clip_map:` for repeated
continuous sounds. These fields are validated render data and affect hashes.

Beats remain quarter-note units. Meter and per-layer polymeter set local bar and
groove phase. Beat zero starts the pickup; the first full downbeat follows the
pickup's declared number of beats. Meter does not silently rescale authored note
times. Phrase rubato uses one conductor curve from authored form or merged part
activity, avoiding independent contradictory part clocks.

`loopsafe: on` checks whole beats under the actual tempo/hold map and measures
unfaded and delivered boundary jumps and tail energy. It rejects detected
truncated releases or unsafe seams. Default loop fade-out is zero. A loop whose last
gate ends exactly at the boundary now fails when its release runs past the end (the
2.16 renderer faded it silently); shorten that gate by the release time, or end it
earlier, so the tail completes inside the loop. Cutdowns are deliveries, not loops:
`loopsafe` applies to the full asset render only. These finite signal checks do not
certify that a loop feels rhythmically or harmonically complete; they do not replace
listening.

Default SDK/CLI/agent validation computes the loop buffer to check these measured conditions before declaring it render-ready. Use SDK `resolve=False`, agent request `resolve: false`, or CLI `--no-resolve` for structural validation only.

## Render cost of anti-alias resampling

Resampling cost now grows with playback rate: the sampler's windowed-sinc kernel
widens so that content which would fold below Nyquist is filtered. That is the correct
behaviour and it costs time in proportion to transposition. Measured on the
reference machine (one 1 s note from a 2 s 48 kHz source, `render_region`, best of
three):

| Transposition | Engine 2.16.0 | Engine 3.0.0 | Ratio |
|---|---|---|---|
| 0 semitones | 41 ms | 57 ms | 1.4× |
| +12 semitones | 42 ms | 110 ms | 2.7× |
| +24 semitones | 41 ms | 204 ms | 5.0× |

Playback at or below the source rate costs about the same as before. Separately,
automation declared in layer beats (`time_basis: layer_beats`) is mapped to seconds per
sample through the tempo/hold map. Engine 3.0 did that per sample in Python (1.9 s against
0.5 s for seconds-based automation on a 30 s tone); engine 3.2 vectorizes it (0.058 s
against 0.017 s for a 30 s gain curve). Large upward
transpositions of long sampled parts (orchestral libraries pitched far from their
key centres) render noticeably slower; `--jobs` parallelises across layers, not
inside one note. `tests/test_perf_budget.py` pins the shape of the curve (ratio
bounds), and `docs/evolution/harness.md` `HARNESS-PERF-002` pins the absolute
budget on the reference machine.

## Engine 3.2: render cost and numeric drift

Engine 3.2.0 renders the same specs with about 4.4x less CPU (1009 s -> 230 s over the 17
locally renderable compositions in `docs/examples`; short CLI renders ~7.5x less, most of it
startup). Nothing audible changes, but output samples are not bit-identical to 3.1.0:

| Source of difference | Size (max per-sample, measured) |
|---|---|
| float32 FFTs in long-IR reverbs (`reverb`, `fdn`, `plate`, `convolve`) | ~ -126 dB re the reverb's output peak |
| float32 inverse FFT in `pad` (PADsynth) tables | ~ -132 dB re the table peak |
| libm-free `tanh` in `saturate`; limiter/compressor windows via float64 overlap-add | ~ 1e-15 relative |
| summation order in LUFS block powers, automation `exp` instead of `10**x` | ~ 1e-15 relative |
| subnormal flushing (values below 1e-290 set to 0 in recursive kernels) | none audible (below -5800 dBFS) |

End to end, every composition in `docs/examples` stays within -131 dBFS of engine 3.1.0 --
below the 24-bit quantization step, so 24-bit masters differ at most in isolated LSBs and
dither. Golden hashes (`tests/golden/audio.lock.json`) were re-pinned for 3.2.0.

Determinism is unchanged: a given engine version renders identical bytes run to run on a
given machine. The native kernels are built for the host CPU (`-march=native`) with FMA
contraction and fast-math disabled and use only lane-parallel vectorization, so builds for
different vector widths (SSE2/AVX2/AVX-512) produce the same bits; the kernel cache key
includes the CPU identity. A C compiler is now required for every render, not only for the
physical-model voices (`make native-check`).

What to expect operationally: `validate` does not check for the compiler, so a spec
reported render-ready still fails at render on a host without one (`render failed: ...
needs a C compiler`); run `make native-check` in new environments. Compiled kernels live
in `$AUDIOFORGE_NATIVE_CACHE` (default `$XDG_CACHE_HOME/audioforge` or
`~/.cache/audioforge`), one file per kernel source, flag set and CPU; nothing evicts old
entries, and the key does not include the compiler version, so clear the cache after
changing compilers. The stage hall (`stage:` blocks) still convolves in float64 through
`scipy.signal.oaconvolve` and is unaffected by the float32 change.

Process-level effects of importing the engine: `OPENBLAS_NUM_THREADS` defaults to 1 (set it
before importing numpy to override), and during a render glibc keeps freed large buffers for
reuse, returning them to the OS when the render ends; set `AUDIOFORGE_MALLOC_TUNE=0` to
leave malloc untouched.

## Rolling back to engine 2.16.0

Rollback is a checkout of the previous tag; nothing is deployed anywhere else.
Four facts were established by rehearsal (`HARNESS-RB-002`):

1. `git checkout engine-2.16.0` (tag `282756e`, 2026-06-12) or `git revert` of the
   merge. Manifests written by 3.0.0 will then fail `verify` with `MISMATCH`, as
   3.0.0 fails 2.16.0 manifests; re-render after rolling back.
2. The tag predates the `Makefile`; its gate is `sh scripts/run_tests.sh`.
3. That script hardcodes `python3`. Point it at the reference interpreter with a
   wrapper script on `PATH` (`printf '#!/bin/sh\nexec /path/.venv/bin/python "$@"\n'`),
   not a symlink: a venv interpreter reached through an outside symlink loses its
   site-packages.
4. Its catalog-freshness guard needs the gitignored `libraries/` tree (link it into
   the checkout), and even then `test_current_txt_matches_fresh_tree_snapshot` fails
   in this locale because the 2.16.0 test ran `tree -a` without
   `LC_ALL=C --charset=UTF-8`. Every engine test passes (395 at rehearsal); that one
   red test is a fixture check, not engine behaviour.

`scripts/harness.sh` implements this as `HARNESS-RB-002` and stores the log under
`docs/evolution/evidence/<checkpoint>/`.

## Analysis and acceptance evidence

Audio analysis always reports observations. Suggestions about bass, stereo width,
brightness or dynamics depend on declared expectations. SDK asset analysis passes
the compiled spec. A direct agent/MCP `analyze` request accepts `context`, either a
spec or an expectation object such as `{"stereo":"mono","expect_bass":false}`.
Authored note rests are distinguished from unexpectedly silent written activity.
No spectrum, waveform or reproducibility hash is presented as a musical-quality
score.

Generate numerical probes and an offline listening-review page:

```bash
python -m audioforge.tools.musical_acceptance --out /tmp/audioforge-review
# Optional: compare with an isolated checkout of the previous engine.
python -m audioforge.tools.musical_acceptance --out /tmp/audioforge-comparison \
  --baseline-root /path/to/previous-checkout
```

The seven cases cover seventh preservation, phrase gates, repeat duration,
release timing, deliberate quiet levels, sample alias rejection and instrument
gain. They build their own pinned sample fixture. The manifest records measurements
and output hashes. The HTML embeds audio, conceals A/B version labels until revealed,
and exports listener-entered judgments as JSON. It starts with `not_reviewed`;
no subjective ratings are inferred from the numerical results.

The full requirement-to-evidence ledger is [MUSICAL_CORRECTNESS.md](MUSICAL_CORRECTNESS.md).
[ADR-0007](adr/0007-musical-render-semantics.md) records the contract decision.
`make check` verifies generated contracts, golden reproducibility, registry and
version/documentation consistency, and the canonical test suites.
