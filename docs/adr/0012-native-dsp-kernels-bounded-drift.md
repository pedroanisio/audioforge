---
disclaimer:
  notice: >-
    No information within this document should be taken for granted. Any statement
    or premise not backed by a real logical definition or verifiable reference may
    be invalid, erroneous, or a hallucination.
  generated_by: "Claude Opus 5.5 via Claude Code"
  date: "2026-09-28"
---

# ADR-0012: Engine-wide native DSP kernels and bounded numeric drift

- **Status:** Accepted
- **Date:** 2026-09-28

## Context
Rendering spent most of its CPU in whole-signal numpy passes, thousands of short
`scipy.signal.lfilter` calls, pure-Python recursion loops (Freeverb combs, FDN impulse
responses, Karplus-Strong feedback), single huge FFT convolutions, and subnormal-number
stalls in decaying feedback over silence. A 10x CPU-time reduction was requested; the
operator accepted numerical drift provided it is bounded, inaudible, re-pinned and
documented (engine version bump, migration guide). Before this decision only the
physical-model voices, `ladder`/`tape` and modulated plate were native
([ADR-0004](0004-native-kernels-fail-loud.md)).

## Decision
We will render every spec through native C kernels (`audioforge/native/dsp.c`,
`upfirdn.c`; wrappers and the `ENGINE_KERNELS` registry in `audioforge/_native.py`):
true-peak detection, oversampled saturation, Freeverb, FDN IR generation, static,
multi-channel, batched and time-varying biquads, delay taps, wavetable playback,
Karplus-Strong feedback, running minimum and automation curves. Rules:

- A C compiler is required for every render; without one, rendering fails loudly
  (ADR-0004). A fallback is allowed only where a test proves it bit-identical
  (`resample_poly` → scipy, `tests/test_native_resample.py`).
- Kernels are built with `-O3 -march=native -ffp-contract=off -fno-fast-math` and
  cached under a key of source, flags and CPU identity. Vectorization is lane-parallel
  only (no reassociated reductions), so SSE2, AVX2 and AVX-512 builds produce the same
  bits (verified for every kernel wrapper when this ADR was written).
- Recursive kernels flush values below 1e-290 to zero in software (portable,
  unlike FTZ/DAZ flags).
- Long-IR reverbs use batched float32 overlap-add FFTs for transforms of 2^17 points
  or more; smaller transforms and the limiter/compressor windows stay float64.
- Output may change across engine versions within a stated bound. For 3.2.0 the
  bound is −131 dBFS maximum per-sample difference from 3.1.0 over the example
  corpus. Each such change bumps `ENGINE_VERSION`, re-pins the golden lock and is
  documented in the migration guide with its sources and sizes.

## Consequences
Render CPU fell 4.4x over the locally renderable examples (1009 s → 230 s); short
CLI renders fell ~7.5x. Determinism within one environment is unchanged (ADR-0001),
but the environment now includes the host CPU the kernels were built for and the C
compiler; the golden lock's `numeric_env` does not yet record either (AF-R16).
Open items: `validate` does not check for a compiler, so "render-ready" assumes one;
the capability `status` no longer separates native from non-native paths (everything
is native); the kernel cache is never evicted and its key does not include the
compiler version. Enforced by `make native-check`, `tests/test_native_resample.py`,
`scripts/drift_inspect.py` (`ENGINE_KERNELS` both ways) and `make golden-check`.
