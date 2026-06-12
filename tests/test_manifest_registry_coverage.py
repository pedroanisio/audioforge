"""Drift-map Finding #7 — the capability manifest must cover registries.

`capability_manifest()` is the canonical agent-facing contract. It is built
from the schema/dsl/styles registries, but the report flagged that nothing
guards the manifest against drifting from them (a new oscillator, kind, style
pack, or layer type could be added to the engine yet never surface to agents).

These tests enumerate the source registries and assert the manifest reflects
every member — equality for plain enums, and registry-⊆-manifest for fields the
manifest deliberately extends (`fx` adds filter aliases, `layer_types` adds the
`audio` file-layer alias).
"""
import json
import re
from pathlib import Path

import pytest

pytest.importorskip("numpy")

from audioforge import capability_manifest  # noqa: E402
from audioforge.capabilities import capability_manifest_schema  # noqa: E402
from audioforge.schema import (AUTO_TARGETS, BIT_DEPTHS, FX_TYPES, KINDS,  # noqa: E402
                               LAYER_TYPES, OSC_SHAPES)
from audioforge.dsl import (ARTICULATIONS, DYNAMIC_MARKS, EMOTIONS,  # noqa: E402
                            GROOVE_TEMPLATES, INTENT_METADATA_FIELDS,
                            INTENT_RENDER_FIELDS)
from audioforge.styles import list_style_packs  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
M = capability_manifest()


def _keys(field):
    return set(field.keys()) if isinstance(field, dict) else set(field)


@pytest.mark.parametrize("manifest_key, registry", [
    ("kinds", KINDS),
    ("oscillators", OSC_SHAPES),
    ("articulations", ARTICULATIONS),
    ("dynamic_marks", DYNAMIC_MARKS),
    ("grooves", GROOVE_TEMPLATES),
    ("emotions", EMOTIONS),
    ("automation_targets", AUTO_TARGETS),
    ("bit_depths", BIT_DEPTHS),
])
def test_manifest_enum_equals_registry(manifest_key, registry):
    assert _keys(M[manifest_key]) == set(registry), (
        f"capability_manifest()['{manifest_key}'] drifted from its registry "
        f"(Finding #7)"
    )


def test_manifest_style_packs_match():
    assert set(M["style_packs"]) == set(list_style_packs())


def test_manifest_fx_covers_registry():
    # the manifest adds filter aliases (lowpass/highpass/bandpass) on top.
    assert set(FX_TYPES) <= _keys(M["fx"]), (
        f"manifest fx is missing registry types: "
        f"{sorted(set(FX_TYPES) - _keys(M['fx']))}"
    )


def test_manifest_layer_types_cover_registry():
    # the manifest may add aliases (e.g. 'audio'); every schema layer type
    # must still be present.
    assert set(LAYER_TYPES) <= _keys(M["layer_types"]), (
        f"manifest layer_types is missing schema types: "
        f"{sorted(set(LAYER_TYPES) - _keys(M['layer_types']))}"
    )


def test_published_capability_schema_matches_runtime_source():
    published = json.loads((ROOT / "docs" / "capability.schema.json").read_text())
    assert published == capability_manifest_schema(), (
        "docs/capability.schema.json drifted from capability_manifest_schema() "
        "(Finding #7)"
    )


def test_manifest_diagnostic_codes_have_repair_hints():
    codes = M["diagnostic_codes"]
    hints = M["repair_hints"]
    assert codes, "capability manifest must expose diagnostic_codes"
    for code, payload in codes.items():
        hint = payload.get("repair_hint")
        assert hint, f"diagnostic code {code!r} has no repair_hint"
        if hint in hints:
            continue
        assert isinstance(hint, str) and len(hint) > 20, (
            f"diagnostic code {code!r} points at neither a manifest repair_hints "
            "entry nor an inline actionable hint"
        )


def test_manifest_intent_blocks_cover_parser_fields():
    render_fields = set(M["intent_blocks"]["render_affecting"])
    metadata_fields = set(M["intent_blocks"]["metadata"])
    assert render_fields == set(INTENT_RENDER_FIELDS), (
        "manifest intent_blocks.render_affecting drifted from dsl parser "
        f"fields: {sorted(render_fields ^ set(INTENT_RENDER_FIELDS))}"
    )
    assert metadata_fields == set(INTENT_METADATA_FIELDS), (
        "manifest intent_blocks.metadata drifted from dsl parser fields: "
        f"{sorted(metadata_fields ^ set(INTENT_METADATA_FIELDS))}"
    )


def test_manifest_cli_commands_cover_cli_parser():
    cli_src = (ROOT / "audioforge" / "cli.py").read_text()
    parser_cmds = set(re.findall(r'add_parser\(\s*"([a-z0-9][a-z0-9-]*)"', cli_src))
    manifest_cmds = set(M["cli"]["commands"])
    assert parser_cmds == manifest_cmds, (
        "capability_manifest()['cli']['commands'] drifted from cli.py parser: "
        f"missing={sorted(parser_cmds - manifest_cmds)} "
        f"phantom={sorted(manifest_cmds - parser_cmds)}"
    )


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-q"]))
