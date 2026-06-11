"""Machine-readable AudioForge capability manifest for AI agents."""
from __future__ import annotations

from .determinism import ENGINE_VERSION
from .dsl import (ARTICULATIONS, DSL_VERSION, DYNAMIC_MARKS, EMOTIONS,
                  GROOVE_TEMPLATES)
from .schema import (AUTO_TARGETS, BIT_DEPTHS, FX_TYPES, KINDS, LAYER_TYPES,
                     NOISE_COLORS, OSC_SHAPES)
from .styles import list_style_packs


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
    return {
        "engine_version": ENGINE_VERSION,
        "dsl_version": DSL_VERSION,
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
        "bit_depths": sorted(BIT_DEPTHS),
        "style_packs": list_style_packs(),
        "smart_directives": {
            "style": {"enum": list_style_packs()},
            "perform": {"properties": ["style", "expressivity"]},
            "ensemble": {"properties": ["family", "size", "spread", "octaves"]},
            "voicing": {"properties": ["richness", "extensions"]},
            "space": {"properties": ["hall", "depth"]},
        },
        "examples": {
            "smart_directives": (
                "style: cinematic\n"
                "perform: style=cinematic expressivity=0.8\n"
                "ensemble: synth size=5 spread=0.45 octaves=1\n"
                "voicing: richness=0.7 extensions=7,9\n"
                "space: hall=studio depth=0.5"
            ),
            "notes_layer": (
                "layer lead : notes { osc: sine env: a=0.01s d=0.1s "
                "s=0.8 r=0.2s notes: C4 @ 0b for 1b }"
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
        },
        "incompatibilities": {
            "seat_with_bus": "A staged layer cannot also set bus; the stage is its route.",
            "instrument_without_library": "Instrument layers require a spec-level library pin.",
            "cutoff_auto_without_filter": "cutoff automation requires a filter fx at the target index.",
            "loopsafe_without_bpm": "loopsafe requires tempo/bpm so whole-beat duration can be checked.",
        },
    }
