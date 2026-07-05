---
disclaimer:
  notice: >-
    No information within this document should be taken for granted. Any statement
    or premise not backed by a real logical definition or verifiable reference may
    be invalid, erroneous, or a hallucination.
  generated_by: "audioforge.tools.gen_docs"
  date: "2026-07-05"
---

<!-- GENERATED — do not hand-edit. Run `python -m audioforge.tools.gen_docs --write`. -->


# IR reference

The AudioForge IR (`https://audioforge.local/schemas/audioforge-ir-1.2.schema.json`, version 1.2) as **12** structured definitions, generated from `docs/ir.schema.json` (itself generated from `audioforge/ir_schema.py`).

| Definition | Type | Properties |
|------------|------|------------|
| `bus` | object | `automation`, `duck`, `fx`, `gain_db`, `name` |
| `curve` | object | `fx_index`, `points`, `rate_hz`, `t0`, `target`, `time_basis`, `values` |
| `curve_point` | — | — |
| `env` | object | `attack`, `decay`, `release`, `sustain` |
| `fx` | object | `cutoff_hz`, `mode`, `type` |
| `hold` | object | `beat`, `duration_s` |
| `layer` | object | `articulation`, `automation`, `bus`, `color`, `duration_s`, `env`, `file`, `freq_hz`, … |
| `marker` | object | `name`, `time_s` |
| `master` | object | `automation`, `fade_in_s`, `fade_out_s`, `fx`, `stereo_width`, `target_lufs`, … |
| `point` | array | — |
| `score` | object | `meter`, `pickup_beats`, `polymeter`, `repeats`, `sections` |
| `structured_intent` | object | `authored`, `expansions`, `metadata`, `render_affecting` |
