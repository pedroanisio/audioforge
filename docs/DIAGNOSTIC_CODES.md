---
disclaimer:
  notice: >-
    No information within this document should be taken for granted. Any statement
    or premise not backed by a real logical definition or verifiable reference may
    be invalid, erroneous, or a hallucination.
  generated_by: "audioforge.tools.gen_capability (from capability_manifest)"
  date: "2026-07-04"
---

# AudioForge Diagnostic Codes

<!-- GENERATED — do not hand-edit. Run `python -m audioforge.tools.gen_capability --write`. -->

Every diagnostic code the engine can emit, with its repair hint. Generated from
`capability_manifest()["diagnostic_codes"]` and gated by `gen_capability.py --check`
(`make manifest-check`), so a new code cannot land undocumented.

There are **55** diagnostic codes.

| Code | Repair hint |
|------|-------------|
| `ambiguous_harmony` | _(see repair_hints in the manifest)_ |
| `curve_unsupported_voice` | Move the curve to a supported voice, remove it, or wait for the physical-model kernel stage advertised in the support matrix. |
| `dead_air` | _(see repair_hints in the manifest)_ |
| `duplicate_note_timbre_curve` | Keep at most one cutoff_hz, gain_db, or scan curve per note. |
| `fret_out_of_range` | Use a fret inside 0..max_fret or the muted string value 'x'. |
| `high_crest` | _(see repair_hints in the manifest)_ |
| `intent_conflict` | _(see repair_hints in the manifest)_ |
| `invalid_curve` | Use a supported curve target, time basis, point encoding, and interpolation shape from performance_curves. |
| `loop_boundary_tail` | _(see repair_hints in the manifest)_ |
| `lossy_articulation` | _(see repair_hints in the manifest)_ |
| `lossy_dynamic_curve` | _(see repair_hints in the manifest)_ |
| `lossy_hold` | _(see repair_hints in the manifest)_ |
| `lossy_key_change` | _(see repair_hints in the manifest)_ |
| `lossy_lyrics` | _(see repair_hints in the manifest)_ |
| `lossy_marker` | _(see repair_hints in the manifest)_ |
| `lossy_meter_unit` | _(see repair_hints in the manifest)_ |
| `lossy_pickup` | _(see repair_hints in the manifest)_ |
| `lossy_pitch_curve` | _(see repair_hints in the manifest)_ |
| `lossy_polymeter` | _(see repair_hints in the manifest)_ |
| `lossy_repeat` | _(see repair_hints in the manifest)_ |
| `lossy_slur` | _(see repair_hints in the manifest)_ |
| `lossy_string_fret` | _(see repair_hints in the manifest)_ |
| `lossy_tuning` | _(see repair_hints in the manifest)_ |
| `low_foundation_weak` | _(see repair_hints in the manifest)_ |
| `mono_image` | _(see repair_hints in the manifest)_ |
| `near_ceiling` | _(see repair_hints in the manifest)_ |
| `note_curve_unsupported_target` | Use one of the published note_scope_targets or move the automation to layer/master scope. |
| `note_curve_unsupported_voice` | Move the note curve to a voice that supports the target, or use an equivalent layer/master automation where available. |
| `notes_first_event` | Put the first notes: event on the same line, or write play as a separate layer-body statement. |
| `position_timbre_unsupported` | Position timbre is synth-only until sampled/physical voices grow a documented per-voice timbre primitive. |
| `render_plan_approximation` | _(see repair_hints in the manifest)_ |
| `render_plan_inpaint_unavailable` | _(see repair_hints in the manifest)_ |
| `render_plan_missing_evidence` | Regenerate the plan from the current spec, engine version, library pin, catalog facts, and routing policy before rendering. |
| `render_plan_policy_fallback_forbid` | Adjust spec.routing or choose sampled articulations that satisfy the active render-plan policy. |
| `render_plan_policy_fallback_warn` | Adjust spec.routing or choose sampled articulations that satisfy the active render-plan policy. |
| `render_plan_schema` | Regenerate the plan from the current spec, engine version, library pin, catalog facts, and routing policy before rendering. |
| `render_plan_stale` | Regenerate the plan from the current spec, engine version, library pin, catalog facts, and routing policy before rendering. |
| `render_plan_stretch_warn` | Adjust spec.routing or choose sampled articulations that satisfy the active render-plan policy. |
| `render_plan_sustain_gap` | _(see repair_hints in the manifest)_ |
| `resource_pin` | Replace placeholder hashes with content-addressed sample, IR, or library manifest SHA-256 values. |
| `scan_requires_morph_osc` | Use osc=morph for note-scope scan curves, or remove the scan curve from this note. |
| `string_fret_pitch_conflict` | Remove the explicit pitch or make it match the pitch derived from tuning, string, and fret. |
| `string_out_of_tuning` | Use a 1-based string index present in layer.tuning. |
| `technique_fallback` | A reduced technique lowering was used; inspect render manifest fallback records before accepting the render. |
| `technique_layer_override` | Per-note technique overrides the layer default; remove one if that was not intentional. |
| `technique_param_out_of_range` | Adjust technique parameters to the manifest ranges/enums. |
| `technique_unknown` | Use a technique listed in capability_manifest()['techniques']. |
| `technique_unsupported_voice` | Choose a supported voice for the technique or use an explicit lower-level curve/articulation form. |
| `tuning_not_rendered` | _(see repair_hints in the manifest)_ |
| `tuning_required_for_string_fret` | Add layer.tuning before using note string/fret fields. |
| `unknown_property` | Remove the property or replace it with one listed for the asset/layer/master scope in this manifest. |
| `unrecognized_harmony` | _(see repair_hints in the manifest)_ |
| `unsupported_layer_type` | _(see repair_hints in the manifest)_ |
| `validate_render_ready` | Run validate without --no-resolve before render; clean validation is the render-ready predicate. |
| `very_bright` | _(see repair_hints in the manifest)_ |
