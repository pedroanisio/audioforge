"""Machine-readable AudioForge capability manifest for AI agents."""
from __future__ import annotations

from . import interop
from .dsl import (ARTICULATIONS, DSL_VERSION, DYNAMIC_MARKS, EMOTIONS,
                  GROOVE_TEMPLATES)
from .schema import (AUTO_TARGETS, BIT_DEPTHS, FX_TYPES, KINDS, LAYER_TYPES,
                     NATIVE_FX_TYPES, NATIVE_OSC_SHAPES, NOISE_COLORS,
                     OSC_SHAPES)
from .styles import list_style_packs
from .version import ENGINE_VERSION, version_contract
from .ir_schema import IR_SCHEMA_VERSION, ir_schema_metadata
from .curves import (
    CURVE_SHAPES,
    CURVE_UNSUPPORTED_VOICE_CODE,
    LAYER_TIME_BASES,
    NOTE_TIME_BASES,
    PERFORMANCE_CURVE_TARGETS,
    PHYSICAL_MODEL_OSCILLATORS,
    PITCH_CENTS_DEFAULT_LIMIT,
    PITCH_CENTS_HARD_LIMIT,
)
from .analysis import ANALYSIS_DIAGNOSTIC_CODES, LOOP_BOUNDARY_CODE
from .harmony import HARMONY_DIAGNOSTIC_CODES
from .plan import (PLAN_DIAGNOSTIC_CODES, RENDER_PLAN_ROUTES,
                   RENDER_PLAN_SCHEMA_VERSION)
from .schema import (
    EXPRESSIVE_DIAGNOSTIC_CODES,
    NOTE_SCOPE_SUPPORT,
    NOTE_SCOPE_TARGETS,
    NOTE_SCOPE_TARGET_RANGES,
    NOTE_SCOPE_TIMBRE_TARGETS,
    ROUTING_FALLBACK_MODES,
    TECHNIQUES,
)
from .sample_catalog.constants import (
    ANALYSIS_SCHEMA,
    CANDIDATE_SCHEMA,
    LICENSE_BUNDLE_SCHEMA,
    LICENSE_EVIDENCE_SCHEMA,
    SAMPLE_CATALOG_COMMANDS,
    SAMPLE_CATALOG_BUILDER_VERSION,
)
from .sample_catalog.licenses import ACCEPTED_LICENSES
from .sample_catalog.sfz import GENERATED_SFZ_OPCODES
from .sample_catalog.sources import SOURCE_ADAPTERS, SOURCE_ADAPTER_CLI_NAMES


CAPABILITY_SCHEMA_VERSION = "audioforge.capabilities/1"

CURVE_SUPPORT_MATRIX = {
    "notes:synth": {
        "pitch_cents": "full",
        "dynamic": "level_time_varying_brightness_onset_sampled",
        "gain_db": "full",
        "cutoff_hz": "full",
        "scan": "morph_only",
    },
    "instrument:sampled": {
        "pitch_cents": "full",
        "dynamic": "full",
        "gain_db": "full",
        "cutoff_hz": "unsupported_no_per_voice_filter",
        "scan": "unsupported_no_morph_voice",
    },
    "physical_models": {
        "voices": sorted(PHYSICAL_MODEL_OSCILLATORS),
        "pitch_cents": "unsupported_until_staged",
        "dynamic": "full",
        "gain_db": "full",
        "cutoff_hz": "unsupported_until_staged",
        "scan": "unsupported_until_staged",
        "diagnostic": CURVE_UNSUPPORTED_VOICE_CODE,
        "initial_pitch_bound_cents": 400,
    },
}

CLI_COMMANDS = [
    "batch",
    "campaign",
    "capabilities",
    "compile",
    "decompile",
    "export-midi",
    "export-musicxml",
    "grammar",
    "import-midi",
    "import-musicxml",
    "ingest",
    "libgen",
    "pack",
    "plan",
    "render",
    "repair",
    "sample-catalog",
    "score",
    "validate",
    "verify",
]


def _param(kind: str, *, unit: str | None = None, default=None,
           minimum=None, maximum=None, enum=None, description: str = ""):
    out = {"type": kind}
    if unit:
        out["unit"] = unit
    if default is not None:
        out["default"] = default
    if minimum is not None:
        out["min"] = minimum
    if maximum is not None:
        out["max"] = maximum
    if enum is not None:
        out["enum"] = sorted(enum)
    if description:
        out["description"] = description
    return out


COMMON_LAYER_PROPS = {
    "gain": _param("number", unit="db", default=0.0),
    "pan": _param("number", minimum=-1.0, maximum=1.0, default=0.0),
    "start": _param("number", unit="s", default=0.0),
    "duration": _param("number", unit="s"),
    "env": _param("adsr"),
    "fx": _param("fx_chain"),
    "auto": _param("automation", enum=AUTO_TARGETS),
    "bus": _param("string"),
}


def _capability_statuses() -> dict:
    """Per-capability lifecycle status, derived by predicate (AF-R07) — not hand-listed.

    stable       = pure-Python, always available.
    experimental = requires the native C-kernel toolchain (fails loudly if the
                   compiler is absent), so its availability is environment-dependent.
    A new voice inherits its status from *where it is registered*: a pure-Python
    oscillator is `stable`; a native kernel is `experimental` until it too is
    pure-Python — no manifest edit required, so the field cannot rot.
    """

    def _status(name: str, native: set) -> str:
        return "experimental" if name in native else "stable"

    return {
        "predicate": (
            "stable = pure-Python, always available; experimental = requires the "
            "native C-kernel toolchain (fails loudly if the compiler is absent)"
        ),
        "by_capability": {
            "oscillators": {
                n: _status(n, NATIVE_OSC_SHAPES) for n in sorted(OSC_SHAPES | NATIVE_OSC_SHAPES)
            },
            "fx_types": {
                n: _status(n, NATIVE_FX_TYPES) for n in sorted(FX_TYPES | NATIVE_FX_TYPES)
            },
        },
    }


def capability_manifest() -> dict:
    """Return a deterministic, JSON-serializable descriptor of the DSL.

    This is intentionally explicit rather than prose-derived: agents can use it
    to choose valid layer types, properties, units, ranges, and enums without
    scraping the Markdown spec.
    """
    layer_specific = {
        "tone": {
            "osc": _param("enum", enum=OSC_SHAPES, default="sine"),
            "note": _param("pitch"),
            "freq": _param("number", unit="hz"),
            "detune": _param("number", unit="c", default=0.0),
        },
        "notes": {
            "osc": _param("enum", enum=OSC_SHAPES, default="sine"),
            "notes": _param("note_events"),
            "play": _param("motif_expansion"),
            "loop": _param("number", unit="b"),
            "arp": _param("arpeggiator",
                          enum={"up", "down", "updown", "downup", "random"}),
            "humanize": _param("number|object", minimum=0.0, maximum=1.0),
            "dynamic": _param("dynamic_curve", enum=DYNAMIC_MARKS),
            "phrasing": _param("number", minimum=0.0, maximum=1.0),
        },
        "sweep": {
            "shape": _param("enum", enum=OSC_SHAPES, default="sine"),
            "from": _param("number", unit="hz"),
            "to": _param("number", unit="hz"),
            "curve": _param("enum", enum={"lin", "exp"}, default="exp"),
        },
        "noise": {"color": _param("enum", enum=NOISE_COLORS)},
        "drums": {
            "voice": _param("enum", enum={"kick", "snare", "hat", "open_hat",
                                           "clap", "tom"}),
            "pattern": _param("pattern"),
        },
        "grain": {
            "source": _param("enum", enum=set(OSC_SHAPES) | set(NOISE_COLORS)),
            "grainsize": _param("number", unit="s"),
            "density": _param("number"),
            "pitchspread": _param("number", unit="c"),
        },
        "sample": {
            "file": _param("string"),
            "sha256": _param("sha256"),
            "pitch": _param("number", unit="st", default=0.0),
        },
        "foley": {"model": _param("enum", enum={"rain", "wind", "fire", "surf"})},
        "instrument": {
            "instrument": _param("string"),
            "articulation": _param("enum", enum=ARTICULATIONS,
                                   default="sustain"),
            "section": _param("object"),
            "seat": _param("stage_position"),
        },
    }
    layers = {
        name: {
            "properties": {**COMMON_LAYER_PROPS, **layer_specific.get(name, {})}
        }
        for name in sorted(LAYER_TYPES)
    }
    layers["audio"] = {
        "compiles_to": "sample",
        "properties": {
            **COMMON_LAYER_PROPS,
            "file": _param("string"),
            "sha256": _param("sha256"),
            "preserve": _param("enum", enum={"mono", "stereo", "channels"},
                               default="mono"),
        },
    }
    for name, entry in layers.items():
        entry["properties"]["automation_ir"] = _param("json_string", description="Canonical automation list, including shaped or mapped curves")
        if name in {"notes", "instrument"}:
            entry["properties"]["notes_ir"] = _param("json_string", description="Canonical note events with stable IDs, voices and mapped curves")
        if name not in {"notes", "instrument"}:
            entry["properties"].update({
                "clip_source": _param("json_string", description="Compiled repeat source timing; paired with clip_map"),
                "clip_map": _param("json_string", description="Compiled [source_start_s, source_end_s, destination_s] windows"),
            })
    return {
        "schema": CAPABILITY_SCHEMA_VERSION,
        "engine_version": ENGINE_VERSION,
        "dsl_version": DSL_VERSION,
        "version_contract": version_contract(),
        "ir_schema": {
            "version": IR_SCHEMA_VERSION,
            "path": "docs/ir.schema.json",
            "metadata": ir_schema_metadata(),
        },
        "kinds": sorted(KINDS),
        "layer_types": layers,
        "oscillators": sorted(OSC_SHAPES),
        "fx": {name: {"type": name} for name in sorted(FX_TYPES | {
            "lowpass", "highpass", "bandpass"
        })},
        "articulations": sorted(ARTICULATIONS),
        "dynamic_marks": dict(sorted(DYNAMIC_MARKS.items())),
        "grooves": sorted(GROOVE_TEMPLATES),
        "emotions": sorted(EMOTIONS),
        "audio_semantics": {
            "performance_seed": {"type": "integer", "min": 0, "max": 2**64-1, "default": 0,
                                 "dsl": "seed: N", "scope": "take identity independent of mix edits"},
            "master_normalization": {"enum": ["none", "peak"], "default": "none", "dsl": "normalize: none|peak",
                                     "peak": "true-peak ceiling", "lufs": "explicit loudness normalization"},
            "note_duration": "gate time followed by release; fixed-window tone/noise envelopes retain window semantics",
            "sample_resampling": "rate-adaptive antialias filtering; loop_sustain exits at note-off",
            "loop_safe": "whole beats under the actual tempo/hold map plus measured premaster and delivered seam and tail checks",
            "emotion_scope": "production presets only; sadness and urgency are metadata",
            "analysis": "observations separate from context-dependent recommendations; no musical-quality score",
            "acceptance": "python -m audioforge.tools.musical_acceptance --out DIR [--baseline-root CHECKOUT]",
        },
        "automation_targets": sorted(AUTO_TARGETS),
        "performance_curves": {
            "time_offset": "Input-clock shift in the curve time basis; preserves cropped note shape",
            "time_map": "Contiguous [source_start, source_end, destination] windows in the curve time basis",
            "canonical_ir": "automation_ir JSON strings on layers/buses/master; notes_ir JSON strings on note layers",
            "targets": {
                "pitch_cents": {
                    "unit": "cents",
                    "reference": "relative_to_base_pitch",
                    "default_limit": PITCH_CENTS_DEFAULT_LIMIT,
                    "hard_limit": PITCH_CENTS_HARD_LIMIT,
                    "combination": "sum_in_cents",
                },
                "dynamic": {
                    "unit": "normalized",
                    "range": [0.0, 1.0],
                    "combination": "one_per_scope",
                },
                "cutoff_hz": {
                    "unit": "hz",
                    "range": list(NOTE_SCOPE_TARGET_RANGES["cutoff_hz"]),
                    "combination": "one_per_note",
                },
                "gain_db": {
                    "unit": "db",
                    "range": list(NOTE_SCOPE_TARGET_RANGES["gain_db"]),
                    "combination": "one_per_note_additive",
                },
                "scan": {
                    "unit": "normalized",
                    "range": list(NOTE_SCOPE_TARGET_RANGES["scan"]),
                    "combination": "one_per_note",
                },
            },
            "note_scope_targets": sorted(NOTE_SCOPE_TARGETS),
            "note_scope_timbre_targets": sorted(NOTE_SCOPE_TIMBRE_TARGETS),
            "curve_shapes": sorted(CURVE_SHAPES),
            "time_bases": sorted(NOTE_TIME_BASES | LAYER_TIME_BASES),
            "support_matrix": CURVE_SUPPORT_MATRIX,
        },
        "note_scope_targets": {
            "targets": sorted(NOTE_SCOPE_TARGETS),
            "timbre_targets": sorted(NOTE_SCOPE_TIMBRE_TARGETS),
            "ranges": {
                name: list(bounds)
                for name, bounds in sorted(NOTE_SCOPE_TARGET_RANGES.items())
            },
            "support": NOTE_SCOPE_SUPPORT,
        },
        "techniques": {
            name: {
                "lowers_to": list(entry["lowers_to"]),
                "params": entry["params"],
                "support": entry["support"],
                "doc": entry["doc"],
                "fidelity": entry["fidelity"],
            }
            for name, entry in sorted(TECHNIQUES.items())
        },
        "render_plan": {
            "schema": RENDER_PLAN_SCHEMA_VERSION,
            "routes": sorted(RENDER_PLAN_ROUTES),
            "policy": {
                "fallbacks": {
                    "enum": sorted(ROUTING_FALLBACK_MODES),
                    "default": "allow",
                },
                "stretch_warn_semitones": {
                    "type": "number",
                    "minimum": 0,
                    "default": None,
                },
            },
            "diagnostic_codes": sorted(PLAN_DIAGNOSTIC_CODES),
            "artifact": {
                "extension": ".plan.json",
                "hash": "sha256(canonical_plan_json_without_plan_hash_field)",
            },
        },
        "sample_catalog": {
            "builder_version": SAMPLE_CATALOG_BUILDER_VERSION,
            "artifact_schemas": {
                "analysis": ANALYSIS_SCHEMA,
                "candidate": CANDIDATE_SCHEMA,
                "license_bundle": LICENSE_BUNDLE_SCHEMA,
                "license_evidence": LICENSE_EVIDENCE_SCHEMA,
                "library_manifest_builder": SAMPLE_CATALOG_BUILDER_VERSION,
            },
            "accepted_licenses": sorted(ACCEPTED_LICENSES),
            "commands": list(SAMPLE_CATALOG_COMMANDS),
            "source_adapters": sorted(SOURCE_ADAPTERS),
            "cli_sources": sorted(SOURCE_ADAPTER_CLI_NAMES),
            "storage_root": "_catalog",
            "approved_layout": "_catalog/approved/<instrument>/<version>/",
            "generated_sfz_subset": {
                "validator": "audioforge.sampler.parse_sfz",
                "opcodes": sorted(GENERATED_SFZ_OPCODES),
                "forbidden": ["#include", "$define", "filters", "lfo", "cc"],
            },
            "review_gate": {
                "candidate_state": "candidate",
                "approved_state": "approved",
                "required_for_approval": [
                    "LICENSES.json",
                    "license_evidence_hash",
                    "review.status=approved",
                    "review.reviewer",
                    "manifest_sha256",
                ],
            },
        },
        "bit_depths": sorted(BIT_DEPTHS),
        "timing": {
            "tempo_map": "piecewise-linear [beat, bpm] points integrated exactly",
            "fermata": "fermata: BEATb=DURATIONs inserts absolute seconds",
            "hold": "alias for fermata with identical IR under spec.holds",
        },
        "style_packs": list_style_packs(),
        "generated_from": {
            "layer_types": "audioforge.schema.LAYER_TYPES",
            "fx": "audioforge.schema.FX_TYPES",
            "styles": "audioforge.styles.STYLE_PACKS",
        },
        "smart_directives": {
            "style": {"enum": list_style_packs()},
            "perform": {
                "properties": ["style", "expressivity", "rubato", "amount",
                               "segment"],
                "rubato": {
                    "enum": ["arch", "push_pull", "ritard", "accelerando"],
                    "compiles_to": "dense tempo_map points",
                    "coordination": "one conductor curve from authored form or merged activity spans",
                },
                "phrasing": "authored form/slurs or rest-delimited spans; neutral midpoint arch unless dynamics are authored",
                "cadences": "conservative dominant-to-tonic candidates require chord, key and downbeat evidence",
            },
            "ensemble": {"properties": ["family", "size", "spread", "octaves"]},
            "voicing": {"properties": ["richness", "extensions", "voice_leading"],
                        "ambiguity": "preserve pitch collection and emit diagnostic",
                        "voice_leading": "opt-in register search preserving pitch classes, onsets and gates"},
            "space": {"properties": ["hall", "depth"]},
        },
        "intent_blocks": {
            "render_affecting": {
                "density": {
                    "enum": ["balanced", "dense", "sparse"],
                    "expands_to": "layer gain_db deltas",
                },
                "contour": {
                    "enum": ["arch", "fall", "flat", "rise"],
                    "expands_to": "master gain automation",
                },
                "texture": {
                    "enum": ["airy", "bright", "neutral", "smooth", "warm"],
                    "expands_to": "master fx",
                },
            },
            "metadata": {
                "affect": {"type": "string"},
                "avoid": {"type": "string[]"},
                "repair": {"type": "string"},
                "style_text": {"type": "string"},
            },
            "conflicts": [
                "density=sparse with ensemble.size > 6 emits a warning",
                "avoid=clipping with master peak > -0.5 dBFS emits a warning",
            ],
        },
        "score_layer": {
            "properties": {
                "meter": "meter: BEATS UNIT",
                "pickup": "pickup: N b",
                "form": "form: section STARTb for DURb, ...",
                "repeat": "repeat: section xN",
                "polymeter": "polymeter: layer BEATS UNIT",
            },
            "semantics": {
                "repeat": "count includes first pass; lowers to expanded events/clip windows and extends duration",
                "meter": "quarter-note beat units; local bar resets groove phase",
                "pickup": "beat zero begins pickup; first full downbeat is pickup_beats",
                "polymeter": "per-part groove/bar phase without rescaling explicit timestamps",
            },
        },
        "interop": {
            "exports": ["midi", "musicxml"],
            "imports": ["midi", "musicxml"],
            "cli": ["export-midi", "export-musicxml",
                    "import-midi", "import-musicxml"],
            # ADR-0009: the construct × format matrix the exporters, the lossy
            # diagnostics and docs/INTEROP.md all read from (audioforge.interop.COVERAGE).
            "formats": list(interop.FORMATS),
            "coverage": interop.coverage(),
        },
        "notation": {
            # Directives that compile to `spec.notation`; `rendering` says what the
            # renderer does with them today (HARNESS-NTUN-003 / NSEM-002).
            "directives": {
                "tuning": {"ir": "notation.tuning", "rendering": "metadata_only",
                           "diagnostic": "tuning_not_rendered",
                           "roadmap": "RN-T-002 (n-EDO resolver), RN-T-003 (microtonal interop)"},
                "tuplet": {"ir": "notation.tuplets", "rendering": "authored_durations",
                           "note": "groups notes whose durations are already explicit; "
                                   "notation only, no change in sound"},
                "lyrics": {"ir": "notation.lyrics", "rendering": "metadata_only"},
            },
        },
        "cli": {
            "commands": list(CLI_COMMANDS),
        },
        "examples": {
            "smart_directives": (
                "style: cinematic\n"
                "perform: style=cinematic expressivity=0.8 rubato=arch\n"
                "ensemble: synth size=5 spread=0.45 octaves=1\n"
                "voicing: richness=0.7 extensions=7,9\n"
                "space: hall=studio depth=0.5"
            ),
            "intent_block": (
                "intent {\n"
                "  density: sparse\n"
                "  contour: arch\n"
                "  texture: smooth\n"
                "  affect: tense\n"
                "  avoid: clipping, noise\n"
                "  repair: \"make the melody less rough\"\n"
                "}"
            ),
            "notes_layer": (
                "layer lead : notes { osc: sine env: a=0.01s d=0.1s "
                "s=0.8 r=0.2s notes: C4 @ 0b for 1b }"
            ),
            "score_layer": (
                "meter: 7 8\npickup: 1b\n"
                "form: intro 0b for 7b, verse 7b for 14b\n"
                "repeat: verse x2"
            ),
            "audio_layer": (
                "layer vocal : audio { file: \"take.wav\" "
                "sha256: \"...64 hex...\" preserve: stereo }"
            ),
        },
        "repair_hints": {
            "unknown_property": (
                "Remove the property or replace it with one listed for the "
                "asset/layer/master scope in this manifest."
            ),
            "notes_first_event": (
                "Put the first notes: event on the same line, or write play "
                "as a separate layer-body statement."
            ),
            "resource_pin": (
                "Replace placeholder hashes with content-addressed sample, IR, "
                "or library manifest SHA-256 values."
            ),
            "validate_render_ready": (
                "Run validate without --no-resolve before render; clean "
                "validation is the render-ready predicate."
            ),
            "invalid_curve": (
                "Use a supported curve target, time basis, point encoding, "
                "and interpolation shape from performance_curves."
            ),
            "note_curve_unsupported_target": (
                "Use one of the published note_scope_targets or move the "
                "automation to layer/master scope."
            ),
            "note_curve_unsupported_voice": (
                "Move the note curve to a voice that supports the target, or "
                "use an equivalent layer/master automation where available."
            ),
            "scan_requires_morph_osc": (
                "Use osc=morph for note-scope scan curves, or remove the scan "
                "curve from this note."
            ),
            "duplicate_note_timbre_curve": (
                "Keep at most one cutoff_hz, gain_db, or scan curve per note."
            ),
            "technique_unknown": (
                "Use a technique listed in capability_manifest()['techniques']."
            ),
            "technique_unsupported_voice": (
                "Choose a supported voice for the technique or use an explicit "
                "lower-level curve/articulation form."
            ),
            "technique_param_out_of_range": (
                "Adjust technique parameters to the manifest ranges/enums."
            ),
            "technique_layer_override": (
                "Per-note technique overrides the layer default; remove one if "
                "that was not intentional."
            ),
            "technique_fallback": (
                "A reduced technique lowering was used; inspect render manifest "
                "fallback records before accepting the render."
            ),
            "tuning_required_for_string_fret": (
                "Add layer.tuning before using note string/fret fields."
            ),
            "string_out_of_tuning": (
                "Use a 1-based string index present in layer.tuning."
            ),
            "fret_out_of_range": (
                "Use a fret inside 0..max_fret or the muted string value 'x'."
            ),
            "string_fret_pitch_conflict": (
                "Remove the explicit pitch or make it match the pitch derived "
                "from tuning, string, and fret."
            ),
            "position_timbre_unsupported": (
                "Position timbre is synth-only until sampled/physical voices "
                "grow a documented per-voice timbre primitive."
            ),
            "curve_unsupported_voice": (
                "Move the curve to a supported voice, remove it, or wait for "
                "the physical-model kernel stage advertised in the support matrix."
            ),
            "render_plan_stale": (
                "Regenerate the plan from the current spec, engine version, "
                "library pin, catalog facts, and routing policy before rendering."
            ),
            "render_plan_policy": (
                "Adjust spec.routing or choose sampled articulations that satisfy "
                "the active render-plan policy."
            ),
        },
        "diagnostic_codes": {
            "unknown_property": {"repair_hint": "unknown_property"},
            "notes_first_event": {"repair_hint": "notes_first_event"},
            "resource_pin": {"repair_hint": "resource_pin"},
            "validate_render_ready": {"repair_hint": "validate_render_ready"},
            "invalid_curve": {"repair_hint": "invalid_curve"},
            **{
                code: {"repair_hint": code}
                for code in sorted(EXPRESSIVE_DIAGNOSTIC_CODES)
                if code != CURVE_UNSUPPORTED_VOICE_CODE
            },
            CURVE_UNSUPPORTED_VOICE_CODE: {
                "repair_hint": "curve_unsupported_voice"
            },
            "render_plan_stale": {"repair_hint": "render_plan_stale"},
            "render_plan_schema": {"repair_hint": "render_plan_stale"},
            "render_plan_missing_evidence": {
                "repair_hint": "render_plan_stale"
            },
            "render_plan_policy_fallback_forbid": {
                "repair_hint": "render_plan_policy"
            },
            "render_plan_policy_fallback_warn": {
                "repair_hint": "render_plan_policy"
            },
            "render_plan_stretch_warn": {
                "repair_hint": "render_plan_policy"
            },
            "render_plan_inpaint_unavailable": {
                "repair_hint": "Inpainting is reserved and cannot be routed until F3 lands."
            },
            "lossy_articulation": {
                "repair_hint": "Use MusicXML for notation metadata or accept MIDI loss."
            },
            "intent_conflict": {
                "repair_hint": "Review typed intent fields against explicit render settings."
            },
            # Render-plan codes not listed individually above (RM-E-001 follow-up):
            "render_plan_approximation": {
                "repair_hint": "The plan declares an approximate technique, sampled legato join or "
                               "section multiplication; accept it, or set routing: fallbacks=forbid "
                               "and use recorded material for the gesture."
            },
            "render_plan_sustain_gap": {
                "repair_hint": "A held sampled note outlasts its recording without a usable loop; "
                               "shorten the note, pick a region with a sustain loop, or accept the gap."
            },
            # Interop coverage (ADR-0009): codes the registry in audioforge.interop may emit.
            "lossy_lyrics": {
                "repair_hint": "Lyrics survive in MIDI (lyric events) and the notated MusicXML export; the exact-tick view drops them."
            },
            "lossy_pitch_curve": {
                "repair_hint": "Arbitrary pitch_cents curves are not projected by any export; bake them into notes or accept the loss."
            },
            "lossy_dynamic_curve": {
                "repair_hint": "Layer dynamic marks survive only in the notated MusicXML export; through-note dynamic curves are not projected."
            },
            "lossy_slur": {
                "repair_hint": "Slurs survive only in the notated MusicXML export; use `--notated` or accept the loss."
            },
            "lossy_hold": {
                "repair_hint": "Fermata lengths are not written; the notated MusicXML export keeps the sign."
            },
            "lossy_polymeter": {
                "repair_hint": "Only the notated MusicXML export writes per-part meters; other formats keep the score meter."
            },
            "lossy_pickup": {
                "repair_hint": "Declare a pickup that is a whole number of 64ths for MIDI, or use the notated MusicXML export."
            },
            "lossy_meter_unit": {
                "repair_hint": "MIDI time signatures need a power-of-two unit; change the meter or use MusicXML."
            },
            "lossy_repeat": {
                "repair_hint": "Start and end repeated sections on barlines so the notated export can write repeat signs, or export the performed form (MIDI, exact-tick)."
            },
            "lossy_key_change": {
                "repair_hint": "Key changes need the notated MusicXML export or MIDI; the exact-tick view keeps the initial key."
            },
            "lossy_tuning": {
                "repair_hint": "Non-12-EDO tuning is metadata until the resolver lands (RN-T-002/003); exports carry 12-TET pitches."
            },
            "lossy_string_fret": {
                "repair_hint": "String and fret fields are not projected by any export yet."
            },
            "lossy_marker": {
                "repair_hint": "Markers live in real seconds and are not written by the exports; use sections for beat-based labels."
            },
            "unsupported_layer_type": {
                "repair_hint": "Only layers with note events export; render other layers to audio or leave them out of the interchange."
            },
            # Notation (ADR-0009): the tuning directive is metadata until the resolver lands.
            "tuning_not_rendered": {
                "repair_hint": "The tuning directive is stored but the renderer stays 12-TET; "
                               "remove it, or wait for the n-EDO resolver (engine 3.1 line) "
                               "that applies it and proves the frequencies by FFT."
            },
            # Harmony (RM-E-001): unresolved pitch collections are preserved and reported.
            "ambiguous_harmony": {
                "repair_hint": "Author an explicit chord symbol (for example C3maj7) so root and "
                               "quality are not inferred from an ambiguous collection such as C6/Am7."
            },
            "unrecognized_harmony": {
                "repair_hint": "The pitch collection matches no known chord quality; notes are kept "
                               "unchanged. Author a chord symbol or leave the cluster as written."
            },
            # Loop safety: measured seam and tail failure raised at render.
            LOOP_BOUNDARY_CODE: {
                "repair_hint": "Shorten gates or releases so tails end before the loop boundary, or "
                               "drop loopsafe; the JSON in the message names the measured seam jump "
                               "and tail energy."
            },
            # Audio analysis observations/recommendations (context-aware since 3.0).
            "low_foundation_weak": {
                "repair_hint": "Check the declared bass part, its register, gain and filtering, or "
                               "declare expect_bass=false when the piece has no bass by design."
            },
            "mono_image": {
                "repair_hint": "Increase space depth, width, unison spread or pan layers, or declare "
                               "stereo=mono when a mono image is intended."
            },
            "very_bright": {
                "repair_hint": "Lower oscillator brightness, add lowpass automation, or rebalance "
                               "low layers."
            },
            "high_crest": {
                "repair_hint": "Use bus compression, saturation, or lower transient layers."
            },
            "near_ceiling": {
                "repair_hint": "Use a lower master peak target for delivery headroom."
            },
            "dead_air": {
                "repair_hint": "Fill or trim silent stretches; pass the spec as analysis context so "
                               "authored rests are not reported as missing audio."
            },
        },
        "incompatibilities": {
            "seat_with_bus": "A staged layer cannot also set bus; the stage is its route.",
            "instrument_without_library": "Instrument layers require a spec-level library pin.",
            "cutoff_auto_without_filter": "cutoff automation requires a filter fx at the target index.",
            "loopsafe_without_bpm": "loopsafe requires tempo/bpm so whole-beat duration can be checked.",
        },
        "statuses": _capability_statuses(),
    }


def capability_manifest_schema() -> dict:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://audioforge.local/schemas/capabilities.schema.json",
        "title": "AudioForge Capability Manifest",
        "type": "object",
        "required": ["schema", "engine_version", "dsl_version"],
        "properties": {
            "schema": {"const": CAPABILITY_SCHEMA_VERSION},
            "engine_version": {"type": "string"},
            "dsl_version": {"type": "string"},
            "layer_types": {"type": "object"},
            "fx": {"type": "object"},
            "smart_directives": {"type": "object"},
            "intent_blocks": {"type": "object"},
            "repair_hints": {"type": "object"},
            "diagnostic_codes": {"type": "object"},
            "cli": {"type": "object"},
            "performance_curves": {"type": "object"},
            "note_scope_targets": {"type": "object"},
            "techniques": {"type": "object"},
            "render_plan": {"type": "object"},
        },
        "additionalProperties": True,
    }
