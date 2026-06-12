"""Machine-readable AudioForge capability manifest for AI agents."""
from __future__ import annotations

from .dsl import (ARTICULATIONS, DSL_VERSION, DYNAMIC_MARKS, EMOTIONS,
                  GROOVE_TEMPLATES)
from .schema import (AUTO_TARGETS, BIT_DEPTHS, FX_TYPES, KINDS, LAYER_TYPES,
                     NOISE_COLORS, OSC_SHAPES)
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
from .plan import (PLAN_DIAGNOSTIC_CODES, RENDER_PLAN_ROUTES,
                   RENDER_PLAN_SCHEMA_VERSION)
from .schema import ROUTING_FALLBACK_MODES


CAPABILITY_SCHEMA_VERSION = "audioforge.capabilities/1"

CURVE_SUPPORT_MATRIX = {
    "notes:synth": {
        "pitch_cents": "full",
        "dynamic": "level_time_varying_brightness_onset_sampled",
    },
    "instrument:sampled": {
        "pitch_cents": "full",
        "dynamic": "full",
    },
    "physical_models": {
        "voices": sorted(PHYSICAL_MODEL_OSCILLATORS),
        "pitch_cents": "unsupported_until_staged",
        "dynamic": "unsupported_until_mapped",
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
        "automation_targets": sorted(AUTO_TARGETS),
        "performance_curves": {
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
            },
            "curve_shapes": sorted(CURVE_SHAPES),
            "time_bases": sorted(NOTE_TIME_BASES | LAYER_TIME_BASES),
            "support_matrix": CURVE_SUPPORT_MATRIX,
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
                },
            },
            "ensemble": {"properties": ["family", "size", "spread", "octaves"]},
            "voicing": {"properties": ["richness", "extensions"]},
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
            }
        },
        "interop": {
            "exports": ["midi", "musicxml"],
            "imports": ["midi", "musicxml"],
            "cli": ["export-midi", "export-musicxml",
                    "import-midi", "import-musicxml"],
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
        },
        "incompatibilities": {
            "seat_with_bus": "A staged layer cannot also set bus; the stage is its route.",
            "instrument_without_library": "Instrument layers require a spec-level library pin.",
            "cutoff_auto_without_filter": "cutoff automation requires a filter fx at the target index.",
            "loopsafe_without_bpm": "loopsafe requires tempo/bpm so whole-beat duration can be checked.",
        },
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
            "render_plan": {"type": "object"},
        },
        "additionalProperties": True,
    }
