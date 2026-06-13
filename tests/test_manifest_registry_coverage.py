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
                               LAYER_TYPES, NOTE_SCOPE_TARGETS, OSC_SHAPES,
                               TECHNIQUES)
from audioforge.dsl import (ARTICULATIONS, DYNAMIC_MARKS, EMOTIONS,  # noqa: E402
                            GROOVE_TEMPLATES, INTENT_METADATA_FIELDS,
                            INTENT_RENDER_FIELDS)
from audioforge.sample_catalog.licenses import ACCEPTED_LICENSES  # noqa: E402
from audioforge.sample_catalog.constants import (  # noqa: E402
    ANALYSIS_SCHEMA,
    CANDIDATE_SCHEMA,
    LICENSE_BUNDLE_SCHEMA,
    LICENSE_EVIDENCE_SCHEMA,
    SAMPLE_CATALOG_COMMANDS,
    SAMPLE_CATALOG_BUILDER_VERSION,
)
from audioforge.sample_catalog.sfz import GENERATED_SFZ_OPCODES  # noqa: E402
from audioforge.sample_catalog.sources import (  # noqa: E402
    SOURCE_ADAPTERS,
    SOURCE_ADAPTER_CLI_NAMES,
    SOURCE_ADAPTER_CLI_TO_ID,
)
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


def test_manifest_performance_curve_contract_is_published():
    curves = M["performance_curves"]
    assert set(curves["targets"]) == set(NOTE_SCOPE_TARGETS)
    assert set(curves["note_scope_targets"]) == set(NOTE_SCOPE_TARGETS)
    assert set(M["note_scope_targets"]["targets"]) == set(NOTE_SCOPE_TARGETS)
    assert set(curves["curve_shapes"]) == {"hold", "linear", "pow"}
    assert {"note_beats", "note_seconds", "layer_seconds", "layer_beats"} <= set(
        curves["time_bases"]
    )
    assert curves["targets"]["pitch_cents"]["unit"] == "cents"
    assert curves["targets"]["pitch_cents"]["combination"] == "sum_in_cents"
    assert curves["targets"]["dynamic"]["range"] == [0.0, 1.0]
    sampled = curves["support_matrix"]["instrument:sampled"]
    assert sampled["pitch_cents"] == "full"
    assert sampled["dynamic"] == "full"
    assert sampled["gain_db"] == "full"
    assert sampled["cutoff_hz"] == "unsupported_no_per_voice_filter"
    assert (
        M["diagnostic_codes"]["curve_unsupported_voice"]["repair_hint"]
        == "curve_unsupported_voice"
    )
    physical = curves["support_matrix"]["physical_models"]
    assert physical["diagnostic"] == "curve_unsupported_voice"
    assert {"bowed", "blown", "brass", "struck", "sympathetic"} <= set(
        physical["voices"]
    )


def test_manifest_expressive_techniques_match_runtime_registry():
    assert set(M["techniques"]) == set(TECHNIQUES)
    for name, entry in TECHNIQUES.items():
        manifest_entry = M["techniques"][name]
        assert manifest_entry["lowers_to"] == entry["lowers_to"]
        assert manifest_entry["params"] == entry["params"]
        assert manifest_entry["support"] == entry["support"]
        assert manifest_entry["doc"] == entry["doc"]


def test_manifest_expressive_diagnostics_are_published():
    for code in (
        "note_curve_unsupported_target",
        "note_curve_unsupported_voice",
        "scan_requires_morph_osc",
        "duplicate_note_timbre_curve",
        "technique_unknown",
        "technique_unsupported_voice",
        "technique_param_out_of_range",
        "technique_layer_override",
        "technique_fallback",
        "tuning_required_for_string_fret",
        "string_out_of_tuning",
        "fret_out_of_range",
        "string_fret_pitch_conflict",
        "position_timbre_unsupported",
    ):
        assert M["diagnostic_codes"][code]["repair_hint"] == code


def test_manifest_sample_catalog_contract_matches_runtime_registries():
    sample_catalog = M["sample_catalog"]
    assert sample_catalog["builder_version"] == SAMPLE_CATALOG_BUILDER_VERSION
    assert sample_catalog["artifact_schemas"]["analysis"] == ANALYSIS_SCHEMA
    assert sample_catalog["artifact_schemas"]["candidate"] == CANDIDATE_SCHEMA
    assert sample_catalog["artifact_schemas"]["license_bundle"] == LICENSE_BUNDLE_SCHEMA
    assert sample_catalog["artifact_schemas"]["license_evidence"] == LICENSE_EVIDENCE_SCHEMA
    assert tuple(sample_catalog["commands"]) == SAMPLE_CATALOG_COMMANDS
    assert set(sample_catalog["accepted_licenses"]) == set(ACCEPTED_LICENSES)
    assert set(sample_catalog["source_adapters"]) == set(SOURCE_ADAPTERS)
    assert set(sample_catalog["cli_sources"]) == set(SOURCE_ADAPTER_CLI_NAMES)
    assert set(sample_catalog["cli_sources"]) == set(SOURCE_ADAPTER_CLI_TO_ID)
    assert set(sample_catalog["source_adapters"]) == set(
        SOURCE_ADAPTER_CLI_TO_ID.values()
    )
    assert set(sample_catalog["generated_sfz_subset"]["opcodes"]) == set(
        GENERATED_SFZ_OPCODES
    )
    assert sample_catalog["generated_sfz_subset"]["validator"] == (
        "audioforge.sampler.parse_sfz"
    )


def test_sample_catalog_goal_map_names_public_runtime_contracts():
    text = (ROOT / "docs" / "goal.md").read_text()
    sample_catalog = M["sample_catalog"]
    required_literals = {
        SAMPLE_CATALOG_BUILDER_VERSION,
        ANALYSIS_SCHEMA,
        CANDIDATE_SCHEMA,
        LICENSE_BUNDLE_SCHEMA,
        LICENSE_EVIDENCE_SCHEMA,
        *SAMPLE_CATALOG_COMMANDS,
        *ACCEPTED_LICENSES,
        *SOURCE_ADAPTERS,
        *SOURCE_ADAPTER_CLI_NAMES,
        *GENERATED_SFZ_OPCODES,
        sample_catalog["generated_sfz_subset"]["validator"],
        sample_catalog["review_gate"]["candidate_state"],
        sample_catalog["review_gate"]["approved_state"],
        *sample_catalog["review_gate"]["required_for_approval"],
        "catalog_diagnostics",
        "render_blockers",
        "ignored_opcodes",
        "missing_samples",
    }
    missing = sorted(literal for literal in required_literals if literal not in text)
    assert not missing, (
        "docs/goal.md sample-catalog traceability map drifted from public "
        f"runtime constants: {missing}"
    )


def test_sample_catalog_goal_map_covers_af_p3_requirement_ids():
    goal = (ROOT / "docs" / "goal.md").read_text()
    source = (
        ROOT
        / "docs"
        / "doc-requirements-architecture-expressive-performance-techniques-done.md"
    ).read_text()
    match = re.search(
        r"^## AF-P3/G13 Requirement Coverage Matrix\n(?P<body>.*?)(?=^## )",
        goal,
        re.MULTILINE | re.DOTALL,
    )
    assert match, (
        "docs/goal.md must include an explicit AF-P3/G13 requirement coverage "
        "matrix for the sample-catalog builder"
    )
    matrix = match.group("body")
    required_ids = (
        *(f"FR-{i}" for i in range(1, 17)),
        *(f"NFR-{i}" for i in range(1, 6)),
        *(f"PR-{i}" for i in range(1, 5)),
        *(f"ER-{i}" for i in range(1, 6)),
        *(f"OR-{i}" for i in range(1, 5)),
        *(f"AR-{i}" for i in range(1, 7)),
    )
    missing_from_source = [req_id for req_id in required_ids if req_id not in source]
    assert not missing_from_source, (
        "AF-P3/G13 source contract no longer contains expected requirement IDs: "
        f"{missing_from_source}"
    )
    missing_from_goal = [req_id for req_id in required_ids if req_id not in matrix]
    assert not missing_from_goal, (
        "docs/goal.md AF-P3/G13 coverage matrix drifted from the binding "
        f"requirements document: {missing_from_goal}"
    )


def test_sample_catalog_cli_source_choices_match_runtime_registry():
    cli_src = (ROOT / "audioforge" / "cli.py").read_text()
    assert "SOURCE_ADAPTER_CLI_NAMES" in cli_src
    assert 'choices=SOURCE_ADAPTER_CLI_NAMES' in cli_src, (
        "sample-catalog --source choices must be derived from "
        "SOURCE_ADAPTER_CLI_NAMES, not a duplicated literal tuple"
    )


def test_sample_catalog_cli_commands_match_runtime_registry():
    cli_src = (ROOT / "audioforge" / "cli.py").read_text()
    assert "SAMPLE_CATALOG_COMMANDS" in cli_src
    assert "for command in SAMPLE_CATALOG_COMMANDS" in cli_src, (
        "sample-catalog nested subcommands must be derived from "
        "SAMPLE_CATALOG_COMMANDS, not duplicated parser literals"
    )


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-q"]))
