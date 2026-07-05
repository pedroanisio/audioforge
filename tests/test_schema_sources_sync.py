"""AF-R08 Phase A — the generated JSON Schema derives its enums from schema.py's
registries (one source of truth), gated so it cannot silently drift back to
hand-restated literals. See ADR-0005.
"""
from __future__ import annotations

import audioforge.ir_schema as irs
from audioforge.ir_schema import ir_json_schema
from audioforge.schema import (
    AUTO_TARGETS,
    FILTER_MODES,
    FX_TYPES,
    KINDS,
    LAYER_TYPES,
    NOISE_COLORS,
    OSC_SHAPES,
)

_REGISTRIES = {
    "OSC_SHAPES": OSC_SHAPES,
    "FX_TYPES": FX_TYPES,
    "KINDS": KINDS,
    "LAYER_TYPES": LAYER_TYPES,
    "AUTO_TARGETS": AUTO_TARGETS,
    "NOISE_COLORS": NOISE_COLORS,
    "FILTER_MODES": FILTER_MODES,
}


def _all_enums(node):
    if isinstance(node, dict):
        if isinstance(node.get("enum"), list):
            yield node["enum"]
        for v in node.values():
            yield from _all_enums(v)
    elif isinstance(node, list):
        for v in node:
            yield from _all_enums(v)


def test_every_ir_registry_is_reflected_verbatim_as_a_generated_enum():
    enums = {tuple(e) for e in _all_enums(ir_json_schema())}
    for name, reg in _REGISTRIES.items():
        assert tuple(sorted(reg)) in enums, (
            f"schema.py registry {name} is not reflected verbatim in the generated JSON "
            "Schema — it was hand-restated and can now drift (AF-R08 / ADR-0005)"
        )


def test_filter_modes_is_single_sourced():
    # the exact literal that used to be duplicated in schema.py and ir_schema.py
    assert FILTER_MODES == {"lowpass", "highpass", "bandpass"}
    enums = {tuple(e) for e in _all_enums(ir_json_schema())}
    assert tuple(sorted(FILTER_MODES)) in enums


def test_derivation_is_live_not_hardcoded(monkeypatch):
    """A new osc shape added to the registry must flow into the generated schema —
    proving the enum is derived, not a frozen literal."""
    monkeypatch.setattr(irs, "OSC_SHAPES", set(OSC_SHAPES) | {"__probe_shape__"})
    enums = {tuple(e) for e in _all_enums(ir_json_schema())}
    assert any("__probe_shape__" in e for e in enums), (
        "OSC_SHAPES is not derived into the generated schema — it is hardcoded somewhere"
    )
