"""Regression guards for the AudioForge contract audit findings (F1–F14).

Each test pins a specific fix from static/refs/audioforge-contract-audit.md so the
defect — or the silent drift it warned about — cannot return. The cross-cutting
theme is single-sourcing: a published/sibling surface must never be looser than,
or disagree with, the validator that actually gates rendering.
"""
import json
import subprocess
from pathlib import Path

import pytest

from audioforge import dsl, theory
from audioforge.schema import (
    BPM_MAX,
    BPM_MIN,
    CUTOFF_CAPABLE_FX,
    FX_TYPES,
    IR_ARTICULATIONS,
    TEMPO_MAP_BPM_MAX,
    SpecError,
    validate_spec,
)
from audioforge.ir_schema import (
    INTENT_RENDER_ENUMS,
    PROVENANCE_FIELDS,
    RENDER_FIELDS,
    SEMANTIC_FIELDS,
    ir_json_schema,
)

ROOT = Path(__file__).resolve().parents[1]


def _tone_spec() -> dict:
    return {
        "id": "t", "kind": "cue", "duration_s": 2.0,
        "layers": [{
            "name": "a", "type": "tone", "osc": "sine", "note": "C4",
            "env": {"attack": 0.01, "decay": 0.1, "sustain": 0.7, "release": 0.2},
        }],
    }


def _instrument_spec(bpm=None) -> dict:
    spec = {
        "id": "i", "kind": "cue", "duration_s": 2.0,
        "library": {"name": "x", "manifest_sha256": "a" * 64},
        "layers": [{
            "name": "v", "type": "instrument", "instrument": "violin",
            "notes": [{"note": "C5", "start_beat": 0, "dur_beats": 1}],
        }],
    }
    if bpm is not None:
        spec["bpm"] = bpm
    return spec


# --- F1: instrument layers use the grid and require a base tempo --------------
def test_f1_instrument_only_spec_without_bpm_is_rejected():
    with pytest.raises(SpecError, match="bpm"):
        validate_spec(_instrument_spec())
    validate_spec(_instrument_spec(bpm=120))  # with bpm it is accepted


# --- F2: published schema must not claim fx types the engine lacks ------------
def test_f2_published_fx_type_enum_matches_engine():
    fx_props = ir_json_schema()["$defs"]["fx"]["properties"]
    assert set(fx_props["type"]["enum"]) == set(FX_TYPES)
    for fake in ("lowpass", "highpass", "bandpass"):
        assert fake not in fx_props["type"]["enum"], (
            f"{fake} is a filter MODE, not an fx type (audit F2)")
    # the real filter shape is documented instead
    assert set(fx_props["mode"]["enum"]) == {"lowpass", "highpass", "bandpass"}
    assert "cutoff_hz" in fx_props


# --- F3: one source of truth for tempo bounds --------------------------------
def test_f3_schema_bpm_bounds_match_validator_constants():
    bpm = ir_json_schema()["properties"]["bpm"]
    assert (bpm["minimum"], bpm["maximum"]) == (float(BPM_MIN), float(BPM_MAX))
    # tempo_map may exceed the base ceiling (deliberate), but stays within bounds
    spec = _instrument_spec(bpm=120)
    spec["tempo_map"] = [[0.0, BPM_MAX + 50]]
    validate_spec(spec)  # base+50 <= TEMPO_MAP_BPM_MAX
    spec["tempo_map"] = [[0.0, TEMPO_MAP_BPM_MAX + 1]]
    with pytest.raises(SpecError, match="tempo_map"):
        validate_spec(spec)


# --- F4: env sustain is a level (0..1), not a time ---------------------------
def test_f4_env_sustain_is_a_level():
    spec = _tone_spec()
    spec["layers"][0]["env"]["sustain"] = 37
    with pytest.raises(SpecError, match="sustain"):
        validate_spec(spec)
    # attack remains a time and still admits large values
    ok = _tone_spec()
    ok["layers"][0]["env"]["attack"] = 5.0
    validate_spec(ok)
    assert ir_json_schema()["$defs"]["env"]["properties"]["sustain"]["maximum"] == 1


# --- F5: intent vocabulary single-sourced from the IR module -----------------
def test_f5_intent_enums_single_sourced():
    assert dsl.INTENT_RENDER_FIELDS == {
        k: set(v) for k, v in INTENT_RENDER_ENUMS.items()
    }


# --- F6: DSL articulations are the IR set plus authoring-only `trill` ---------
def test_f6_articulation_sets_are_structurally_related():
    assert IR_ARTICULATIONS <= dsl.ARTICULATIONS
    assert dsl.ARTICULATIONS - IR_ARTICULATIONS == {"trill"}


# --- F7: render-affecting fields classified as render; taxonomy is partitioned
def test_f7_swing_and_groove_are_render_fields():
    assert "swing" in RENDER_FIELDS and "groove" in RENDER_FIELDS
    assert "groove" not in SEMANTIC_FIELDS
    assert "swing" in ir_json_schema()["properties"]


def test_f7_field_taxonomy_is_a_partition():
    layers = [SEMANTIC_FIELDS, RENDER_FIELDS, PROVENANCE_FIELDS]
    seen: set[str] = set()
    for group in layers:
        for field in group:
            assert field not in seen, f"{field} classified in two taxonomy layers"
            seen.add(field)


# --- F8: every checked-in .af that the parser accepts parses under the grammar
def test_f8_published_ebnf_defines_its_terminals():
    import re
    from audioforge.grammar import dsl_ebnf
    ebnf = dsl_ebnf()
    for term in ("IDENT", "NUMBER", "SIGNED_NUMBER", "UNIT", "PITCH", "VALUE"):
        assert re.search(rf"^{term}\s*=", ebnf, re.M), (
            f"EBNF references {term} but no longer defines it (audit F14)")


def test_f8_all_compilable_af_fixtures_parse_under_the_grammar():
    from audioforge.lark_parser import lark_parser
    from audioforge.dsl import compile_dsl, DSLError

    checked = 0
    from af_corpus import source_paths

    for path in source_paths(ROOT):
        src = path.read_text()
        try:
            compile_dsl(src)
        except DSLError:
            continue  # intentionally-invalid fixture; not a grammar round-trip case
        lark_parser().parse(src)  # must be accepted by the published grammar
        checked += 1
    assert checked >= 6, "expected the composition corpus to be round-tripped"


# --- F12: cutoff_hz automation must point at a real cutoff-capable fx ---------
def test_f12_cutoff_automation_requires_capable_fx():
    spec = _tone_spec()
    spec["layers"][0]["automation"] = [
        {"target": "cutoff_hz", "points": [[0, 100], [1, 200]]}]
    with pytest.raises(SpecError, match="out of range"):
        validate_spec(spec)  # no fx chain at all

    spec["layers"][0]["fx"] = [{"type": "reverb"}]
    with pytest.raises(SpecError, match="no cutoff"):
        validate_spec(spec)  # fx exists but isn't cutoff-capable

    spec["layers"][0]["fx"] = [{"type": "filter", "mode": "lowpass", "cutoff_hz": 800}]
    validate_spec(spec)  # filter is cutoff-capable
    assert "filter" in CUTOFF_CAPABLE_FX


# --- F13: one pitch grammar; multi-digit octaves rejected --------------------
def test_f13_tone_pitch_uses_shared_note_regex():
    assert dsl.NOTE_RE is theory.NOTE_RE
    bad = _tone_spec()
    bad["layers"][0]["note"] = "C10"  # two octave digits
    with pytest.raises(SpecError, match="note"):
        validate_spec(bad)
    validate_spec(_tone_spec())  # single-digit octave is fine
