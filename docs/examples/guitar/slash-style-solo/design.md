---
title: "Golden Target Fixture — slash_style_solo.af (conformance companion)"
author: Claude (Anthropic), under the system-architect skill
date: 2026-06-12
disclaimer:
  notice: >-
    This historical design record describes an earlier engine and proposed DSL.
    Verify present behavior using the adjacent example guide and current tests.
  generated_by: "Codex (relocation and historical-status note)"
  date: "2026-09-06"
status: target-fixture
scope: "Acceptance artifact for docs/goal.md (AF-P1/G11 curves); F5 onboarding dependency declared"
verified_against: "audioforge-latest.tar — Engine 2.16.0, DSL 1.9"
---

# Golden Target Fixture — `slash_style_solo.af`

Historical design record from June 2026. References to “today” below describe
engine 2.16.0 and DSL 1.9. See the [current example guide](index.md) for the
retained score’s present compile status.

## 1. What this fixture is

The end-to-end **target** for "express a Slash-style solo in the DSL": an original composition (style imitated, no recorded solo transcribed — see §6) whose backing renders on today's engine and whose lead line exercises every expressive construct the curves goal exists to deliver. It is written to become three things at once: the **DSL-surface design fixture** for goal.md Phase 7 (the proposed `bend()/vib()/dyn()` sugar), the **golden compile fixture** whose IR snapshot locks the lowering, and the **golden render fixture** once a guitar library is onboarded. One file, three gates, in that order.

The signature note (P1, `D5 @ 4b for 2b`) is deliberately the AF-P1 §2 motivating example verbatim — accelerating +2 st bend over the first 40 %, hold, vibrato widening 0→35 ¢ into the hold, −1 st release in the final 15 % — so the proposal's words, the goal's contract, and the fixture's bytes all describe the same sound.

## 2. Conformance table — what compiles today vs. what this fixture targets

| Construct in the fixture | Status | Authority |
|---|---|---|
| Asset header, tempo, key, `groove: laidback`, markers, `duration` | **1.9 ✓** | DSL_SPEC §2 |
| `perform: … rubato=arch …` (macro → dense tempo points) | **1.9 ✓** | DSL_SPEC §2.1 — the in-repo lowering precedent the curves work copies |
| `library:` all-zeros pin reported as **unbound placeholder** | **1.9 ✓** | DSL_SPEC §4 (validate semantics) |
| Backing layers: `tone`/`pad`, `notes`+chord symbols+voicings, `pluck` bass, `drums` patterns, bus + hall, `humanize` | **1.9 ✓** | DSL_SPEC §4–§7 |
| `instrument` layer: `articulation:`, `legato:`, `phrasing:`, layer `dynamic:` marks (time-varying velocity crossfade), `section`-free single lead | **1.9 ✓** | DSL_SPEC §4, §6 |
| `slur( … )` note-list groups; `play … legato` shorthand (used ×3 for the climax runs → slur ids 2–4); motif + `play` with `stretch`/`vel` | **1.9 ✓** | DSL_SPEC §3, §6 — **but see Finding V1**: the documented `slur( play m @ …, play m @ … )` form is rejected by the 2.16/1.9 compiler; the fixture uses the working `legato` shorthand instead |
| Lead FX chain: `drive`, `peak`, `convolve` (hash-pinned cab IR, placeholder), `delay`, `plate`; master `lufs`/`mbcomp` | **1.9 ✓** | DSL_SPEC §9, §16 |
| **Per-note `bend(T=V [powK], …)`** → `pitch_cents` breakpoints, `note_beats` | **1.10 PROPOSED** | goal.md Required IR Contract; AF-P1 v2.1 §5.2–5.4 |
| **Per-note `vib(rate= depth=A..B [@T1..T2] [delay=])`** → dense sampled `pitch_cents` (250 Hz, auto-rate-raise ≤ 0.25 ¢ error) | **1.10 PROPOSED** | goal.md Phase 3; AF-P1 v2.1 §5.7.1 |
| **Per-note `dyn(T=mark, …)`** → note-scoped `dynamic` curve (replaces layer curve over the note span, informational diagnostic) | **1.10 PROPOSED** | goal.md Dynamic rule |
| Slide-in / pre-bend / fall-off | **1.10 PROPOSED** — no new keywords: all are `bend()` breakpoints (start below 0, start above 0, dive at the end) | this fixture, P1/P2/P5 |
| Polyphonic per-note bend (P3 unison double-stop: static D5 over C5 bent +2 st) | **1.10 PROPOSED** — falls out of curves attaching to note events; nothing extra to build | AF-P1 v2.1 §5.4 |

Surface-design notes the fixture commits to (for goal.md Phase 7 to ratify or amend): curve times are **note-relative beats** (`note_beats`, the goal's default); `T=V` pairs reuse the language's existing list idiom (`auto gain: 0s=-3db`, `dynamic: 0b=mf`); the shape token (`pow2.5`) attaches to the segment **ending** at its point, matching the IR rule; `st` and `c` units are both legal and compile to cents; `dyn()` reuses the §6 dynamic-mark vocabulary. Comments never sit inside continued lists (lexical continuation rule, DSL_SPEC §1) — the phrase map is a block comment above `notes:` instead.

## 3. Expected IR for the signature note (the golden lowering)

Per goal.md's Required IR Contract, `D5 @ 4b for 2b vel 0.86 bend(0b=0c, 0.8b=+2st pow2.5, 1.7b=+2st, 2b=+1st) vib(rate=5.6 depth=0c..35c @0.9b..1.7b) dyn(0b=mf, 1.2b=ff, 2b=f)` must lower to (illustrative values; the checked-in snapshot is authoritative once generated):

```json
{"note": "D5", "start_beat": 4.0, "dur_beats": 2.0, "vel": 0.86, "slur": null,
 "curves": [
   {"target": "pitch_cents", "time_basis": "note_beats",
    "points": [[0.0, 0.0], [0.8, 200.0, "pow:2.5"], [1.7, 200.0], [2.0, 100.0]]},
   {"target": "pitch_cents", "time_basis": "note_beats",
    "t0": 0.9, "rate_hz": 250.0,
    "values": [0.0, 0.31, "… dense sinusoid, depth enveloped 0→35 over 0.9b..1.7b …"]},
   {"target": "dynamic", "time_basis": "note_beats",
    "points": [[0.0, 0.6], [1.2, 0.87], [2.0, 0.74]]}
 ]}
```

with the authored sugar preserved as provenance only:

```json
"_meta": {"semantic": {"authored_expression": [
  {"scope": "lead/notes[1]", "form": "bend(0b=0c, 0.8b=+2st pow2.5, 1.7b=+2st, 2b=+1st)", "line": 135},
  {"scope": "lead/notes[1]", "form": "vib(rate=5.6 depth=0c..35c @0.9b..1.7b)", "line": 135},
  {"scope": "lead/notes[1]", "form": "dyn(0b=mf, 1.2b=ff, 2b=f)", "line": 135}]}}
```

Contract checks this excerpt pins: the two `pitch_cents` curves **sum in cents**; `dynamic` mark values are the documented map (mf=0.60, ff=0.87, f=0.74); the dense vibrato is the **sampled encoding** (defined as linear breakpoints); `_meta.semantic` is hash-excluded while `curves` is hash-included; rendered frequency is `f_D5 · 2^(C(t)/1200)`.

## 4. Acceptance gates (in order)

1. **Gate A — structural compile (DSL 1.10):** the fixture compiles with `--no-resolve`; the only diagnostics are the expected informational ones (note-scope `dyn` overriding layer `dynamic` on three notes; placeholder pins). IR snapshot of the lead layer checked in; §3's note matches it. *Until 1.10 lands, the required interim behavior is a **structured DSLError** at the first curve token — see Finding V2: today it is a raw traceback, which the goal work must fix as a hardening prerequisite.*
2. **Gate B — validation semantics:** full `validate` reports the two all-zeros pins **distinctly as unbound placeholders** (library + cab IR), not as generic missing resources; all curve validation passes (strictly increasing times, shapes legal, pitch sums within bounds, one `dynamic` per scope); hash-discipline fixture — reformatting the file or editing the phrase-map comment leaves the spec hash unchanged; editing any curve point changes it.
3. **Gate C — render-ready (post-onboarding, F5):** with a real guitar library and cab IR pinned, `validate` is render-ready and `render` produces the golden audio + manifest (`verify()` byte-stable); the P5 held bend audibly moves through velocity layers (the existing sampler P2 machinery driven by the note-scope curve); the render plan (AF-P2, when landed) shows P1–P6 lead segments routed `sample` with zero articulation fallbacks.
4. **Gate D — round-trip:** `decompile` re-emits the authored `bend()/vib()/dyn()` forms from `_meta.semantic`; recompiled output is render-hash-equivalent (G4 pattern).

## 5. Verification record (run against the uploaded 2.16.0 / DSL 1.9 tree)

The fixture was machine-checked, not assumed. A **curve-stripped variant** (all `bend()/vib()/dyn()` suffixes removed by regex) compiles cleanly on the live compiler: 1 asset, 7 layers (`pad keys bass drums snare hat lead`), **37 lead note events**, **4 slur groups** (one explicit `slur(…)` in P2 + three `play … legato` runs), **97 dense tempo points** from the rubato lowering, and `validate_spec()` passes structurally with exactly the two expected smart-directive diagnostics. Everything labeled **1.9 ✓** in §2 is therefore demonstrated, not claimed.

Two findings fell out of the verification, each with a proposed action:

- **Finding V1 — doc/implementation drift on `slur(play, play)`.** DSL_SPEC §4 documents `slur( play m @ 0b, play m @ 4b … )` as valid since 2.14; the 2.16/1.9 compiler rejects it (`expected ':', got '('`) both as a notes-list element and as a layer-body statement, while `play … legato` works. **Action:** either implement the documented form or amend DSL_SPEC — and add the missing regression fixture either way; the docs-drift test suite (G1 pattern) evidently does not cover grammar-by-example claims.
- **Finding V2 — unknown note-suffix robustness defect.** With the curve sugar present, the 1.9 parser does not produce a structured diagnostic: it leaks raw tokens into the layer's `notes` prop and crashes later in `_semantic_sidecar` (`TypeError: 'Tok' object is not iterable`) — a user-facing traceback, which the gap spec's §3.3 classifies as a defect independent of the curves work. **Action:** harden note-event suffix parsing to reject unknown suffix tokens with a line-cited `DSLError` *before* the 1.10 grammar lands; this also gives Gate A its required interim behavior.

## 6. Onboarding dependency this fixture creates (F5 tie)

The catalog contains **zero guitar instruments** today, so the fixture names its minimum library requirements as the onboarding spec: instrument `"SingleCut Bridge - Sustain"` (clean DI or lightly driven bridge-pickup sustain — the fixture's FX chain supplies drive/cab, keeping timbre and rig separated per the architecture's C3); chromatic or ≤2-semitone-spaced keycenters across at least E2–E6 (the fixture's bends warp ≤2 st by design — within the AF-P1 default warp-quality envelope); ≥3 velocity layers (the `dyn()` crescendos are the point); round-robins welcome but not required; `sustain` articulation mandatory, `staccato` optional (no fixture note uses a fallback — Gate C asserts zero). The cab IR is an ordinary content-addressed sample (`convolve` discipline), onboarded by hash like any other.

## 7. Provenance and rights

The solo is an **original composition written for this fixture** in a recognizable idiom (minor-pentatonic ballad lead: slow accelerating bends with late widening vibrato, pre-bend releases, unison double-stops, slurred pentatonic runs, a held climax bend with crescendo, fall-off, long resolving vibrato). Style and technique are not protected subject matter; no melody, phrase, or solo from any recording was transcribed or approximated note-for-note. The instrument/library names are fictional placeholders chosen to avoid trademarked product names.

## 8. Why these specific gestures (the fixture's coverage argument)

Each phrase exists to pin one contract clause: **P1** — the AF-P1 motivating example end-to-end (acceleration `pow:k`, hold, sampled-vibrato envelope, partial release, note-scope dynamic). **P2** — pre-bend (curve starting above zero: the normative "0 = written base pitch" rule made audible) and delayed vibrato on a tail. **P3** — two simultaneous notes with independent pitch curves: the polyphonic case channel-wide pitch bend cannot express and per-note curves get for free. **P4** — proof the *existing* 1.9 surface (motifs, slur-joined plays, phrasing, humanize) composes under the new sugar rather than being replaced by it. **P5** — a single 4.5-beat note whose pitch, vibrato depth, and dynamic all evolve independently, ending in a fall-off dive: the stress test for curve summing, sampler time-varying crossfades, and the time-varying resampler. **P6** — the quiet case: late slow vibrato and a decrescendo, where lowering artifacts (interpolation flutter, crossfade zipper) would be most audible. A fixture that only stressed the loud cases would pass while the quiet ones regressed.
