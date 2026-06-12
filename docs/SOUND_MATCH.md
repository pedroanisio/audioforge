---
disclaimer:
  notice: >-
    No information within this document should be taken for granted.
    Any statement or premise not backed by a real logical definition
    or verifiable reference may be invalid, erroneous, or a hallucination.
  generated_by: "Claude Opus 4.8 (1M context) via Claude Code"
  date: "2026-06-12"
---

# Sound Match — audio → an editable AudioForge patch

## Disclaimer

This work is subject to the methodological caveats and commitments described in [@DISCLAIMER.md](../DISCLAIMER.md).
> No statement or premise not backed by a real logical definition or verifiable reference should be taken for granted.

## What it does

Give it a target sample; it returns a **playable, inspectable `.af` patch** whose
render approximates the target's timbre and amplitude shape:

```bash
python3 scripts/sound_match.py TARGET.wav -o out/name
# writes out/name.af  (the patch)  +  out/name.match.json  (the report)
```

```python
from audioforge.match import match_patch
res = match_patch(target_stereo, sample_rate)
res["dsl"]                # the .af patch text, ready to edit/render
res["confidence"]         # 0..1, from an independent re-render (not asserted)
res["ranking"]            # the scored shortlist
```

This is the workflow advantage a preset browser cannot give: *"recreate this
sound as a synth patch I can keep editing."* It is the offline, deterministic,
agent-authorable counterpart to the audio-to-patch feature commercial synths are
racing toward — and AudioForge is structurally suited to it because the output
is an explicit, hash-trackable contract, not a black box.

## How it works (analysis-by-synthesis)

```
target sample
   │  estimate pitch (autocorrelation, octave-safe) + ADSR (from the RMS envelope)
   ▼
candidate patches  ──render (the engine is its own forward model)──▶ audio
   │  score vs target: log-frequency spectral-envelope L1  +  amplitude-envelope L1
   ▼
best patch  ──RE-RENDER + RE-SCORE──▶  verified_distance, confidence
   ▼
emit .af (round-trips: recompiles to the scored spec)
```

The search is a fixed, deterministic grid over oscillator (`sine triangle saw
square fm organ pad pluck struck modal`), low-pass brightness, and — for `fm` —
ratio/index. The ADSR is fitted from the target, not searched. Same target bytes
→ same patch, every time.

## The verification contract (PALS's Law, applied to inference)

An inferred patch is an approximation, never ground truth. `match_patch` does
**not** report the optimiser's own score: it independently re-renders the chosen
patch and re-measures, so `verified_distance` and `confidence` are *measured*
fidelity. A caller (human or agent) gates on that number. On a real drum
one-shot, for example, the matcher still returns a patch but reports a low
confidence (~0.3) rather than pretending — the verification catches the poor
spectral fit even when periodicity is detected.

This is the bright line for the whole "neural synth" direction: learning and
inference belong in the **offline authoring front-end that emits explicit,
verified IR**; the render path stays deterministic DSP. A future neural encoder
may *propose better starting patches*, but it never renders the audio and never
bypasses the re-render check.

## Honest limits (this first slice)

- **Pitched, single-voice timbres** are the supported case. Drums/noise,
  evolving/morphing timbres, and polyphony are not modelled yet — they return a
  patch with honest low confidence, not a silent wrong answer.
- **Pitch is quantised to the nearest semitone** — the only pitch the `tone` DSL
  surface exposes (`note:`; there is no raw-Hz tone property). The reported
  `f0_hz` keeps the exact estimate.
- **Coarse parameter grid.** A local refine / CMA-ES pass and a learned
  proposal model are the obvious next steps; the engine-as-forward-model and the
  verified-output contract already make them safe to add.
- Not a perceptual (listening-test) match; the objective is spectral-envelope +
  amplitude-envelope distance.

---

[← back to README](../README.md)
