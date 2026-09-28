---
disclaimer:
  notice: >-
    No information within this document should be taken for granted. Any statement
    or premise not backed by a real logical definition or verifiable reference may
    be invalid, erroneous, or a hallucination.
  generated_by: "Claude Opus 4.8 via Claude Code; revised by Claude Opus 5.5 via Claude Code"
  date: "2026-09-28"
---

# ADR-0004: Native kernels fail loudly, never silently substitute

- **Status:** Accepted (records existing practice)
- **Date:** 2026-07-05

## Context
Some voices/effects (bowed, blown, brass, struck, sympathetic oscillators; ladder,
tape fx; plate modulation) are on-demand-compiled native C kernels for speed and
fidelity. A missing C compiler must not change the audio.

## Decision
Native kernels require a C compiler; if it is absent they **fail loudly** rather
than silently falling back to different audio. `make native-check` asserts a
compiler is present; these capabilities are marked `experimental`
(environment-dependent) in the manifest (AF-R07).

## Consequences
Determinism (ADR-0001) is preserved — the same spec never renders different bytes
depending on whether a kernel silently substituted. The cost is an explicit
build-tool dependency, surfaced honestly.

## Amendment (2026-09-28, engine 3.2.0)

[ADR-0012](0012-native-dsp-kernels-bounded-drift.md) extends native kernels from the
voices and effects listed above to every render (limiter, filters, halls, delays,
saturation, wavetable voices, curves). A C compiler is therefore required for all
rendering, not only for the `experimental` capabilities, and the "fail loudly" rule
applies engine-wide. One exception is allowed: a fallback proven bit-identical by a
test (`resample_poly` → scipy). Kernels are built per CPU (`-march=native`, FMA
contraction off) and cached under a CPU-keyed path.
