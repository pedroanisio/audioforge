"""Published Universal Music IR schema for AudioForge specs."""
from __future__ import annotations

import copy
from typing import Any

from .schema import (
    AUTO_TARGETS,
    BIT_DEPTHS,
    BPM_MAX,
    BPM_MIN,
    FX_TYPES,
    KINDS,
    LAYER_TYPES,
    NOTE_SCOPE_TARGETS,
    NOISE_COLORS,
    OSC_SHAPES,
    ROUTING_FALLBACK_MODES,
    validate_spec,
)
from .curves import (
    CURVE_SHAPES,
    LAYER_TIME_BASES,
    NOTE_TIME_BASES,
)
from .version import ENGINE_VERSION

IR_SCHEMA_VERSION = "1.2"

SEMANTIC_FIELDS = [
    "intent",
    "emotion",
    "intensity_curve",
    "score",
    "key",
    "key_map",
    "tempo_map",
    "holds",
    "markers",
    "cutdowns",
    "stage",
    "library",
    "routing",
    "notation",
]

RENDER_FIELDS = [
    "id",
    "kind",
    "duration_s",
    "sample_rate",
    "bit_depth",
    "bpm",
    # `swing` and `groove` shape per-16th timing and accents — they change the
    # rendered audio (and therefore the render hash), so they are render-layer
    # fields, not semantic sugar (audit finding F7).
    "swing",
    "groove",
    "loop_safe",
    "layers",
    "buses",
    "master",
    "variant",
    "intensity_scale",
]

PROVENANCE_FIELDS = ["_meta"]
HASH_EXCLUDED_TOP_LEVEL = ["_meta", "intent", "notation"]

INTENT_RENDER_ENUMS = {
    "density": ["balanced", "dense", "sparse"],
    "contour": ["arch", "fall", "flat", "rise"],
    "texture": ["airy", "bright", "neutral", "smooth", "warm"],
}


def ir_schema_metadata() -> dict[str, Any]:
    """Return versioning and ownership metadata for the published IR schema."""
    return {
        "version": IR_SCHEMA_VERSION,
        "engine_version": ENGINE_VERSION,
        "field_layers": {
            "semantic": list(SEMANTIC_FIELDS),
            "render": list(RENDER_FIELDS),
            "provenance": list(PROVENANCE_FIELDS),
        },
        "hash_excluded_top_level": list(HASH_EXCLUDED_TOP_LEVEL),
        "migration": {
            "current": IR_SCHEMA_VERSION,
            "supported_from": ["0.9", "1.0"],
            "policy": "additive-compatible",
            "notes": (
                "IR schema 1.2 extends note-scope curves with timbre targets "
                "and adds hash-included fretted/stringed instrument mechanics. "
                "No migration is required for valid 1.0/1.1 specs; curves and "
                "string/fret/tuning fields are render data and therefore "
                "hash-included, while provenance-only metadata changes remain "
                "hash-excluded."
            ),
        },
        "curves": {
            "targets": sorted(NOTE_SCOPE_TARGETS),
            "shapes": sorted(CURVE_SHAPES),
            "time_bases": sorted(NOTE_TIME_BASES | LAYER_TIME_BASES),
            "hash_policy": "expanded curve data is render data",
        },
        "render_plan": {
            "schema": "audioforge.render-plan/1",
            "policy_field": "routing",
            "hash_policy": "routing policy is render data; derived route "
                           "decisions live outside the IR",
        },
    }


def migrate_ir_spec(spec: dict, from_version: str) -> dict:
    """Return a copy of ``spec`` migrated to the current IR schema version.

    The only legacy boundary currently supported is 0.9 -> 1.0, where
    provenance previously appeared under ``metadata`` in experimental fixtures.
    The migration moves that sidecar to ``_meta`` and records the current schema
    version without changing render-affecting fields.
    """
    if from_version not in ir_schema_metadata()["migration"]["supported_from"]:
        raise ValueError(f"unsupported IR schema migration from {from_version}")
    out = copy.deepcopy(spec)
    if from_version == "0.9":
        legacy = out.pop("metadata", None)
        if isinstance(legacy, dict):
            out.setdefault("_meta", {}).update(legacy)
    out.setdefault("_meta", {})["ir_schema_version"] = IR_SCHEMA_VERSION
    return out


def _number(*, minimum: float | None = None, maximum: float | None = None) -> dict:
    out: dict[str, Any] = {"type": "number"}
    if minimum is not None:
        out["minimum"] = minimum
    if maximum is not None:
        out["maximum"] = maximum
    return out


def _string_enum(values) -> dict:
    return {"type": "string", "enum": sorted(values)}


def _array_items(item_schema: dict, *, min_items: int | None = None) -> dict:
    out: dict[str, Any] = {"type": "array", "items": item_schema}
    if min_items is not None:
        out["minItems"] = min_items
    return out


def ir_json_schema() -> dict[str, Any]:
    """Return the JSON Schema artifact published in ``docs/ir.schema.json``."""
    layer_ref = {"$ref": "#/$defs/layer"}
    point2 = {
        "type": "array",
        "prefixItems": [{"type": "number"}, {"type": "number"}],
        "minItems": 2,
        "maxItems": 2,
    }
    point3 = {
        "type": "array",
        "prefixItems": [
            {"type": "number"},
            {"type": "number"},
            {"type": "string"},
        ],
        "minItems": 3,
        "maxItems": 3,
    }
    curve = {
        "type": "object",
        "required": ["target"],
        "properties": {
            "target": _string_enum(AUTO_TARGETS),
            "points": _array_items(
                {"oneOf": [point2, point3]},
                min_items=1,
            ),
            "time_basis": _string_enum(NOTE_TIME_BASES | LAYER_TIME_BASES),
            "t0": _number(),
            "rate_hz": _number(minimum=1e-9),
            "values": _array_items({"type": "number"}, min_items=1),
            "fx_index": {"type": "integer", "minimum": 0},
        },
        "additionalProperties": True,
    }
    automation = curve
    note_event = {
        "type": "object",
        "properties": {
            "note": {"type": "string"},
            "freq_hz": _number(minimum=1),
            "start_beat": _number(minimum=0),
            "dur_beats": _number(minimum=0),
            "vel": _number(minimum=0, maximum=1),
            "art": {"type": "string"},
            "slur": {"type": "integer", "minimum": 1},
            "generated": {"type": "string"},
            "curves": _array_items({"$ref": "#/$defs/curve"}),
            "string": {"type": "integer", "minimum": 1},
            "fret": {
                "oneOf": [
                    {"type": "integer", "minimum": 0},
                    {"const": "x"},
                ],
            },
        },
        "required": ["start_beat", "dur_beats"],
        "additionalProperties": True,
    }
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": (
            "https://audioforge.local/schemas/"
            f"audioforge-ir-{IR_SCHEMA_VERSION}.schema.json"
        ),
        "title": "AudioForge Universal Music IR",
        "type": "object",
        "required": ["id", "kind", "duration_s", "layers"],
        "additionalProperties": True,
        "properties": {
            "id": {"type": "string", "minLength": 1},
            "kind": _string_enum(KINDS),
            "duration_s": _number(minimum=0.05, maximum=600.0),
            "sample_rate": {"type": "integer", "minimum": 8000, "maximum": 192000},
            "bit_depth": {"type": "integer", "enum": sorted(BIT_DEPTHS)},
            # Base tempo bounds single-sourced from the validator (audit F3); the
            # time-varying `tempo_map` keeps its own, looser ceiling.
            "bpm": _number(minimum=float(BPM_MIN), maximum=float(BPM_MAX)),
            "swing": _number(minimum=0.0, maximum=0.5),
            "layers": _array_items(layer_ref, min_items=1),
            "buses": _array_items({"$ref": "#/$defs/bus"}),
            "master": {"$ref": "#/$defs/master"},
            "intent": {
                "type": "object",
                "properties": {"structured": {"$ref": "#/$defs/structured_intent"}},
                "additionalProperties": True,
            },
            "emotion": {
                "type": "object",
                "additionalProperties": _number(minimum=0.0, maximum=1.0),
            },
            "intensity_curve": _array_items({"$ref": "#/$defs/point"}),
            "score": {"$ref": "#/$defs/score"},
            "key": {"type": "string"},
            "key_map": _array_items({"type": "array", "minItems": 3}),
            "tempo_map": _array_items({"$ref": "#/$defs/point"}),
            "holds": _array_items({"$ref": "#/$defs/hold"}),
            "groove": {"type": "object", "additionalProperties": True},
            "markers": _array_items({"$ref": "#/$defs/marker"}),
            "cutdowns": _array_items({"type": "object", "additionalProperties": True}),
            "stage": {"type": "object", "additionalProperties": True},
            "library": {"type": "object", "additionalProperties": True},
            "routing": {
                "type": "object",
                "properties": {
                    "fallbacks": _string_enum(ROUTING_FALLBACK_MODES),
                    "stretch_warn_semitones": _number(minimum=0.0),
                },
                "additionalProperties": False,
            },
            "notation": {"type": "object", "additionalProperties": True},
            "loop_safe": {"type": "boolean"},
            "variant": {"type": ["string", "integer"]},
            "intensity_scale": _number(minimum=0.0, maximum=1.5),
            "_meta": {
                "type": "object",
                "properties": {
                    "dsl_version": {"type": "string"},
                    "engine_version": {"type": "string"},
                    "lines": {"type": "object", "additionalProperties": True},
                    "semantic": {"type": "object", "additionalProperties": True},
                },
                "additionalProperties": True,
            },
        },
        "$defs": {
            "point": {
                "type": "array",
                "items": {"type": "number"},
                "minItems": 2,
                "maxItems": 2,
            },
            "curve_point": {"oneOf": [point2, point3]},
            "curve": curve,
            "marker": {
                "type": "object",
                "required": ["name", "time_s"],
                "properties": {
                    "name": {"type": "string"},
                    "time_s": _number(minimum=0.0),
                },
                "additionalProperties": True,
            },
            "hold": {
                "type": "object",
                "required": ["beat", "duration_s"],
                "properties": {
                    "beat": _number(minimum=0.0),
                    "duration_s": _number(minimum=0.0),
                },
                "additionalProperties": False,
            },
            "score": {
                "type": "object",
                "properties": {
                    "meter": {
                        "type": "object",
                        "required": ["beats", "unit"],
                        "properties": {
                            "beats": {"type": "integer", "minimum": 1},
                            "unit": {"type": "integer", "minimum": 1},
                        },
                        "additionalProperties": True,
                    },
                    "pickup_beats": _number(minimum=0.0),
                    "sections": _array_items(
                        {"type": "object", "additionalProperties": True}
                    ),
                    "repeats": _array_items(
                        {"type": "object", "additionalProperties": True}
                    ),
                    "polymeter": {"type": "object", "additionalProperties": True},
                },
                "additionalProperties": True,
            },
            "structured_intent": {
                "type": "object",
                "properties": {
                    "render_affecting": {
                        "type": "object",
                        "properties": {
                            key: _string_enum(values)
                            for key, values in INTENT_RENDER_ENUMS.items()
                        },
                        "additionalProperties": False,
                    },
                    "metadata": {
                        "type": "object",
                        "properties": {
                            "affect": {"type": "string"},
                            "avoid": _array_items({"type": "string"}),
                            "repair": {"type": "string"},
                            "style_text": {"type": "string"},
                        },
                        "additionalProperties": False,
                    },
                    "expansions": _array_items(
                        {"type": "object", "additionalProperties": True}
                    ),
                    "authored": _array_items(
                        {"type": "object", "additionalProperties": True}
                    ),
                },
                "additionalProperties": False,
            },
            "layer": {
                "type": "object",
                "required": ["type"],
                "properties": {
                    "name": {"type": "string"},
                    "type": _string_enum(LAYER_TYPES),
                    "osc": _string_enum(OSC_SHAPES),
                    "color": _string_enum(NOISE_COLORS),
                    "freq_hz": _number(minimum=1),
                    "note": {"type": "string"},
                    "notes": _array_items(note_event),
                    "env": {"$ref": "#/$defs/env"},
                    "fx": _array_items({"$ref": "#/$defs/fx"}),
                    "automation": _array_items(automation),
                    "bus": {"type": "string"},
                    "pan": _number(minimum=-1, maximum=1),
                    "gain_db": _number(minimum=-120, maximum=24),
                    "start_s": _number(minimum=0),
                    "duration_s": _number(minimum=0),
                    "file": {"type": "string"},
                    "sha256": {"type": "string"},
                    "instrument": {"type": "string"},
                    "articulation": {"type": "string"},
                    "tuning": _array_items({"type": "string"}, min_items=1),
                    "max_fret": {"type": "integer", "minimum": 0},
                    "seat": {"type": "object", "additionalProperties": True},
                    "section": {"type": "object", "additionalProperties": True},
                    "role": {"type": "string"},
                    "source_kind": {"type": "string"},
                },
                "additionalProperties": True,
            },
            "env": {
                "type": "object",
                "required": ["attack", "decay", "sustain", "release"],
                "properties": {
                    "attack": _number(minimum=0, maximum=60),
                    "decay": _number(minimum=0, maximum=60),
                    "sustain": _number(minimum=0, maximum=1),  # level, not time (F4)
                    "release": _number(minimum=0, maximum=60),
                },
                "additionalProperties": True,
            },
            "fx": {
                # The engine has no `lowpass`/`highpass`/`bandpass` fx *types* —
                # filters are `{"type":"filter","mode":...}`. The published schema
                # used to list those bare names, accepting IR the validator
                # rejects (audit finding F2). The real filter shape is documented
                # here instead via `mode`/`cutoff_hz`.
                "type": "object",
                "required": ["type"],
                "properties": {
                    "type": _string_enum(FX_TYPES),
                    "mode": _string_enum({"lowpass", "highpass", "bandpass"}),
                    "cutoff_hz": _number(minimum=10, maximum=24000),
                },
                "additionalProperties": True,
            },
            "bus": {
                "type": "object",
                "required": ["name"],
                "properties": {
                    "name": {"type": "string"},
                    "gain_db": _number(minimum=-60, maximum=12),
                    "fx": _array_items({"$ref": "#/$defs/fx"}),
                    "automation": _array_items(automation),
                    "duck": {"type": "object", "additionalProperties": True},
                },
                "additionalProperties": True,
            },
            "master": {
                "type": "object",
                "properties": {
                    "fx": _array_items({"$ref": "#/$defs/fx"}),
                    "automation": _array_items(automation),
                    "target_peak_dbfs": _number(minimum=-40, maximum=0),
                    "target_lufs": _number(minimum=-40, maximum=-5),
                    "stereo_width": _number(minimum=0, maximum=1),
                    "fade_in_s": _number(minimum=0),
                    "fade_out_s": _number(minimum=0),
                },
                "additionalProperties": True,
            },
        },
        "x-audioforge": ir_schema_metadata(),
    }


def _check_str(value: Any, path: str, errors: list[str]) -> None:
    if not isinstance(value, str):
        errors.append(f"{path}: expected string")


def _check_object(value: Any, path: str, errors: list[str]) -> None:
    if not isinstance(value, dict):
        errors.append(f"{path}: expected object")


def _check_array(value: Any, path: str, errors: list[str]) -> None:
    if not isinstance(value, list):
        errors.append(f"{path}: expected array")


def _validate_structured_intent(intent: dict, errors: list[str]) -> None:
    structured = intent.get("structured")
    if structured is None:
        return
    if not isinstance(structured, dict):
        errors.append("intent.structured: expected object")
        return
    render = structured.get("render_affecting", {})
    if not isinstance(render, dict):
        errors.append("intent.structured.render_affecting: expected object")
    else:
        for field, allowed in INTENT_RENDER_ENUMS.items():
            if field not in render:
                continue
            if render[field] not in allowed:
                errors.append(
                    "intent.structured.render_affecting."
                    f"{field}: expected one of {allowed}"
                )
    metadata = structured.get("metadata", {})
    if not isinstance(metadata, dict):
        errors.append("intent.structured.metadata: expected object")
    else:
        for field in ("affect", "repair", "style_text"):
            if field in metadata:
                _check_str(metadata[field],
                           f"intent.structured.metadata.{field}", errors)
        if "avoid" in metadata:
            _check_array(metadata["avoid"],
                         "intent.structured.metadata.avoid", errors)
            if isinstance(metadata["avoid"], list):
                for idx, item in enumerate(metadata["avoid"]):
                    _check_str(item,
                               f"intent.structured.metadata.avoid[{idx}]",
                               errors)
    for field in ("expansions", "authored"):
        if field in structured:
            _check_array(structured[field],
                         f"intent.structured.{field}", errors)


def validate_ir_schema(spec: dict) -> list[str]:
    """Validate a compiled IR spec against the published schema contract.

    The JSON Schema is the published structural artifact; this helper adds a
    dependency-free runtime validator for CI. It performs boundary checks for
    schema-owned metadata, then delegates render-contract validation to
    ``audioforge.schema.validate_spec``.
    """
    errors: list[str] = []
    if not isinstance(spec, dict):
        return ["spec: expected object"]

    layers = spec.get("layers")
    if isinstance(layers, list):
        for i, layer in enumerate(layers):
            if isinstance(layer, dict) and "type" not in layer:
                errors.append(f"layers[{i}].type: missing required field")

    meta = spec.get("_meta")
    if meta is not None:
        if not isinstance(meta, dict):
            errors.append("_meta: expected object")
        else:
            for key in ("dsl_version", "engine_version"):
                if key in meta:
                    _check_str(meta[key], f"_meta.{key}", errors)

    if "intent" in spec:
        _check_object(spec["intent"], "intent", errors)
        if isinstance(spec["intent"], dict):
            _validate_structured_intent(spec["intent"], errors)
    if "score" in spec:
        _check_object(spec["score"], "score", errors)

    render_spec = copy.deepcopy(spec)
    render_spec.pop("_meta", None)
    try:
        validate_spec(render_spec)
    except Exception as exc:  # validate_spec raises SpecError; keep loose here.
        errors.append(str(exc))
    return errors
