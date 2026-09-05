import pytest

from audioforge.dsl import (
    DSLError,
    _apply_expressive_lowering,
    lower_note_curve_escape_hatch,
    lower_technique,
    position_timbre_curve,
    resolve_string_fret_event,
)


def _note(**extra):
    return {"note": "A4", "start_beat": 0.0, "dur_beats": 1.0, **extra}


def _curve_targets(ev):
    return [c["target"] for c in ev.get("curves", [])]


def test_curve_escape_hatches_lower_to_note_scope_targets():
    assert lower_note_curve_escape_hatch("cutoff", 2500.0)["target"] == "cutoff_hz"
    assert lower_note_curve_escape_hatch("level", -3.0)["target"] == "gain_db"
    assert lower_note_curve_escape_hatch("scan", 0.75)["target"] == "scan"


@pytest.mark.parametrize("name", [
    "palm_mute",
    "dead_note",
    "let_ring",
    "accent",
    "tenuto",
    "staccatissimo",
    "harmonic",
    "sul_ponticello",
    "sul_tasto",
])
def test_lower_technique_emits_explicit_ir_for_every_synth_technique(name):
    params = {"partial": 3} if name == "harmonic" else {}
    result = lower_technique(name, params, voice="synth", note=_note(), bpm=120)
    ev = result["note"]

    assert "technique" not in ev
    assert "tech" not in ev
    if name == "palm_mute":
        assert ev["dur_beats"] == 0.6
        assert _curve_targets(ev) == ["gain_db", "cutoff_hz"]
    elif name == "dead_note":
        assert ev["dur_beats"] == 0.16
        assert _curve_targets(ev) == ["gain_db", "cutoff_hz"]
    elif name == "let_ring":
        assert ev["release_s_add"] == 0.6
    elif name == "accent":
        assert ev["attack_scale"] == 0.75
        assert ev["curves"][0]["target"] == "dynamic"
    elif name == "tenuto":
        assert ev["art"] == "legato"
    elif name == "staccatissimo":
        assert ev["dur_beats"] == 0.12
    elif name == "harmonic":
        assert ev["harmonic_partial"] == 3
        assert ev["curves"][0]["points"][0][0] == 0.0
        assert ev["curves"][0]["points"][0][1] == pytest.approx(1200 * __import__("math").log2(3), abs=1e-6)
        assert result["layer_fx"][0]["type"] == "peak"
    elif name == "sul_ponticello":
        assert ev["curves"][0]["points"] == [[0.0, 8500.0]]
    elif name == "sul_tasto":
        assert ev["curves"][0]["points"] == [[0.0, 1800.0]]


def test_sampled_fallback_and_reject_paths_are_explicit():
    palm = lower_technique("palm_mute", voice="sampled", note=_note(), bpm=120)
    assert _curve_targets(palm["note"]) == ["gain_db"]
    assert "technique_fallback" in palm["diagnostics"][0]

    dead = lower_technique("dead_note", voice="sampled", note=_note(), bpm=120)
    assert _curve_targets(dead["note"]) == ["gain_db"]
    assert "technique_fallback" in dead["diagnostics"][0]

    with pytest.raises(DSLError, match="technique_unsupported_voice"):
        lower_technique("sul_tasto", voice="sampled", note=_note(), bpm=120)
    with pytest.raises(DSLError, match="technique_param_out_of_range"):
        lower_technique("harmonic", {"partial": 5}, voice="synth",
                        note=_note(), bpm=120)


@pytest.mark.parametrize("name", [
    "accent",
    "let_ring",
    "tenuto",
    "staccatissimo",
])
def test_sampled_supported_technique_cells_lower_without_fallback(name):
    result = lower_technique(name, voice="sampled", note=_note(), bpm=120)

    assert result["diagnostics"] == []
    assert "technique" not in result["note"]


@pytest.mark.parametrize("name", [
    "harmonic",
    "sul_ponticello",
    "sul_tasto",
])
def test_sampled_rejected_technique_cells_use_canonical_diagnostic(name):
    with pytest.raises(DSLError, match="technique_unsupported_voice"):
        lower_technique(name, voice="sampled", note=_note(), bpm=120)


@pytest.mark.parametrize("name", [
    "palm_mute",
    "dead_note",
    "let_ring",
    "accent",
    "tenuto",
    "staccatissimo",
    "harmonic",
    "sul_ponticello",
    "sul_tasto",
])
def test_physical_model_technique_cells_reject_with_canonical_diagnostic(name):
    with pytest.raises(DSLError, match="technique_unsupported_voice"):
        lower_technique(name, voice="physical", note=_note(), bpm=120)


def test_string_fret_resolver_derives_pitch_authoritatively():
    ev = {
        "string": 2,
        "fret": 3,
        "start_beat": 0.0,
        "dur_beats": 1.0,
    }

    resolved = resolve_string_fret_event(ev, ["E2", "A2", "D3"])

    assert resolved["note"] == "C3"
    assert resolved["string"] == 2
    assert resolved["fret"] == 3


def test_muted_string_lowers_to_dead_note_on_open_string_pitch():
    resolved = resolve_string_fret_event(
        {"string": 1, "fret": "x", "start_beat": 0.0, "dur_beats": 1.0},
        ["E2", "A2"],
    )

    assert resolved["note"] == "E2"
    assert resolved["technique"] == "dead_note"


def test_position_timbre_curve_uses_pinned_constants():
    low_e = position_timbre_curve({"string": 1, "fret": 0}, ["E2", "A2"])
    a_string = position_timbre_curve({"string": 2, "fret": 5}, ["E2", "A2"])

    assert low_e["target"] == "cutoff_hz"
    assert low_e["points"] == [[0.0, 1500.0]]
    assert a_string["points"] == [[0.0, 1802.259781]]


def test_apply_expressive_lowering_compiles_ir_side_authored_fields():
    spec = {
        "id": "lowering_demo",
        "kind": "cue",
        "duration_s": 2.0,
        "bpm": 120,
        "layers": [{
            "name": "lead",
            "type": "notes",
            "osc": "sine",
            "tuning": ["E2", "A2"],
            "notes": [{
                "string": 2,
                "fret": 3,
                "start_beat": 0.0,
                "dur_beats": 1.0,
                "technique": "palm_mute",
                "curve_mods": [{"name": "level", "value": -1.5}],
            }],
        }],
    }
    diags = []

    _apply_expressive_lowering(spec, diags)

    ev = spec["layers"][0]["notes"][0]
    assert ev["note"] == "C3"
    assert "technique" not in ev
    assert _curve_targets(ev) == ["gain_db", "gain_db", "cutoff_hz"]


def test_sampled_position_timbre_records_info_without_curve():
    spec = {
        "id": "sampled_position",
        "kind": "cue",
        "duration_s": 2.0,
        "bpm": 120,
        "layers": [{
            "name": "guitar",
            "type": "instrument",
            "instrument": "guitar",
            "tuning": ["E2", "A2"],
            "notes": [{"string": 1, "fret": 0, "start_beat": 0.0, "dur_beats": 1.0}],
        }],
    }
    diags = []

    _apply_expressive_lowering(spec, diags)

    assert spec["layers"][0]["notes"][0]["note"] == "E2"
    assert "curves" not in spec["layers"][0]["notes"][0]
    assert "position_timbre_unsupported" in diags[0]
