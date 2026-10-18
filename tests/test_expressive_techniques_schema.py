import copy

import pytest

from audioforge.schema import (
    EXPRESSIVE_DIAGNOSTIC_CODES,
    NOTE_SCOPE_TARGETS,
    NOTE_SCOPE_TIMBRE_TARGETS,
    TECHNIQUES,
    SpecError,
    validate_spec,
)


def _notes_spec(*, osc="morph", note=None, curves=None, tuning=None,
                max_fret=None):
    layer = {
        "type": "notes",
        "osc": osc,
        "env": {"attack": 0.01, "decay": 0.1, "sustain": 0.7, "release": 0.1},
        "notes": [
            note or {
                "note": "A4",
                "start_beat": 0.0,
                "dur_beats": 1.0,
                "curves": curves or [],
            }
        ],
    }
    if tuning is not None:
        layer["tuning"] = tuning
    if max_fret is not None:
        layer["max_fret"] = max_fret
    return {
        "id": "expressive_schema",
        "kind": "cue",
        "duration_s": 2.0,
        "bpm": 120,
        "layers": [layer],
    }


def _instrument_spec(curves):
    return {
        "id": "sampled_note_scope",
        "kind": "cue",
        "duration_s": 2.0,
        "bpm": 120,
        "library": {"name": "test", "manifest_sha256": "a" * 64},
        "layers": [{
            "type": "instrument",
            "instrument": "guitar",
            "notes": [{
                "note": "A4",
                "start_beat": 0.0,
                "dur_beats": 1.0,
                "curves": curves,
            }],
        }],
    }


def test_note_scope_targets_extend_performance_curves():
    assert NOTE_SCOPE_TIMBRE_TARGETS == {"cutoff_hz", "gain_db", "scan"}
    assert NOTE_SCOPE_TARGETS == {
        "pitch_cents",
        "dynamic",
        "cutoff_hz",
        "gain_db",
        "scan",
    }


def test_validate_spec_accepts_new_note_scope_timbre_curves_on_synth():
    spec = _notes_spec(curves=[
        {
            "target": "cutoff_hz",
            "time_basis": "note_beats",
            "points": [[0.0, 1800.0], [1.0, 6400.0]],
        },
        {
            "target": "gain_db",
            "time_basis": "note_beats",
            "points": [[0.0, -3.0], [1.0, 0.0]],
        },
        {
            "target": "scan",
            "time_basis": "note_beats",
            "points": [[0.0, 0.0], [1.0, 1.0]],
        },
    ])

    assert validate_spec(spec)["id"] == "expressive_schema"


@pytest.mark.parametrize(("curve", "code"), [
    ({"target": "wobble", "points": [[0.0, 0.0]]},
     "note_curve_unsupported_target"),
    ({"target": "cutoff_hz", "points": [[0.0, 1000.0], [0.5, 2000.0]]},
     "duplicate_note_timbre_curve"),
    ({"target": "scan", "points": [[0.0, 0.5]]},
     "scan_requires_morph_osc"),
    ({"target": "cutoff_hz", "points": [[0.0, 25000.0]]},
     "cutoff_hz value 25000.0 outside 10..24000"),
])
def test_validate_spec_rejects_bad_note_scope_timbre_curves(curve, code):
    curves = [curve]
    if code == "duplicate_note_timbre_curve":
        curves.append(copy.deepcopy(curve))
    spec = _notes_spec(osc="sine", curves=curves)

    with pytest.raises(SpecError, match=code):
        validate_spec(spec)


def test_validate_spec_rejects_sampled_note_scope_filter_targets():
    spec = _instrument_spec([{
        "target": "cutoff_hz",
        "points": [[0.0, 1200.0]],
    }])

    with pytest.raises(SpecError, match="note_curve_unsupported_voice"):
        validate_spec(spec)


@pytest.mark.parametrize(("target", "value"), [
    ("pitch_cents", 25.0),
    ("dynamic", 0.5),
    ("gain_db", -3.0),
])
def test_sampled_supported_note_scope_curve_cells_accept(target, value):
    spec = _instrument_spec([{
        "target": target,
        "points": [[0.0, value]],
    }])

    assert validate_spec(spec)["id"] == "sampled_note_scope"


@pytest.mark.parametrize("target", ["cutoff_hz", "scan"])
def test_sampled_unsupported_note_scope_curve_cells_reject(target):
    value = 1000.0 if target == "cutoff_hz" else 0.5
    spec = _instrument_spec([{
        "target": target,
        "points": [[0.0, value]],
    }])

    with pytest.raises(SpecError, match="note_curve_unsupported_voice"):
        validate_spec(spec)


@pytest.mark.parametrize(("target", "value"), [
    ("dynamic", 0.5),
    ("gain_db", -3.0),
])
def test_physical_model_supported_note_scope_curve_cells_accept(target, value):
    spec = _notes_spec(osc="struck", curves=[{
        "target": target,
        "points": [[0.0, value]],
    }])

    assert validate_spec(spec)["id"] == "expressive_schema"


def test_physical_model_pitch_curve_cell_accepts():
    """pitch_cents on physical models is supported via varispeed."""
    spec = _notes_spec(osc="struck", curves=[{
        "target": "pitch_cents",
        "points": [[0.0, 0.0], [1.0, 25.0]],
    }])
    assert validate_spec(spec)["id"] == "expressive_schema"


@pytest.mark.parametrize(("target", "value", "code"), [
    ("cutoff_hz", 1000.0, "note_curve_unsupported_voice"),
    ("scan", 0.5, "note_curve_unsupported_voice"),
])
def test_physical_model_unsupported_note_scope_curve_cells_reject(target, value, code):
    spec = _notes_spec(osc="struck", curves=[{
        "target": target,
        "points": [[0.0, value]],
    }])

    with pytest.raises(SpecError, match=code):
        validate_spec(spec)


def test_technique_registry_shape_is_single_source_ready():
    assert set(TECHNIQUES) == {
        "accent",
        "dead_note",
        "harmonic",
        "let_ring",
        "palm_mute",
        "staccatissimo",
        "sul_ponticello",
        "sul_tasto",
        "tenuto",
    }
    for name, entry in TECHNIQUES.items():
        assert name == name.lower()
        assert entry["lowers_to"]
        assert set(entry["support"]) == {"synth", "sampled", "physical"}
        assert isinstance(entry["doc"], str) and entry["doc"]
        assert isinstance(entry["params"], dict)


def test_expressive_diagnostic_codes_match_contract_set():
    assert EXPRESSIVE_DIAGNOSTIC_CODES == {
        "note_curve_unsupported_target",
        "note_curve_unsupported_voice",
        "scan_requires_morph_osc",
        "duplicate_note_timbre_curve",
        "curve_unsupported_voice",
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
    }


def test_validate_spec_accepts_matching_string_fret_annotation():
    note = {
        "note": "A4",
        "string": 1,
        "fret": 0,
        "start_beat": 0.0,
        "dur_beats": 1.0,
    }
    spec = _notes_spec(note=note, tuning=["A4", "E5"], max_fret=24)

    assert validate_spec(spec)["layers"][0]["notes"][0]["string"] == 1


@pytest.mark.parametrize(("note", "code"), [
    ({"note": "A4", "string": 1, "fret": 0}, "tuning_required_for_string_fret"),
    ({"note": "A4", "string": 3, "fret": 0}, "string_out_of_tuning"),
    ({"note": "A4", "string": 1, "fret": 25}, "fret_out_of_range"),
    ({"note": "B4", "string": 1, "fret": 0}, "string_fret_pitch_conflict"),
])
def test_validate_spec_rejects_invalid_string_fret_annotations(note, code):
    note = {**note, "start_beat": 0.0, "dur_beats": 1.0}
    tuning = None if code == "tuning_required_for_string_fret" else ["A4", "E5"]
    spec = _notes_spec(note=note, tuning=tuning, max_fret=24)

    with pytest.raises(SpecError, match=code):
        validate_spec(spec)
