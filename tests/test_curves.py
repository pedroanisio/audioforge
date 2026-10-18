import numpy as np
import pytest

from audioforge.curves import evaluate_curve, sampled_to_points
from audioforge.schema import SpecError, validate_spec


def test_evaluate_curve_linear_hold_pow_and_edges():
    curve = {
        "target": "pitch_cents",
        "points": [
            [0.0, 0.0],
            [1.0, 10.0],
            [2.0, 20.0, "hold"],
            [3.0, 30.0, "pow:2"],
        ],
    }

    out = evaluate_curve(curve, np.array([-1.0, 0.5, 1.5, 2.5, 4.0]))

    assert np.allclose(out, [0.0, 5.0, 10.0, 22.5, 30.0])


def test_evaluate_curve_sampled_encoding_matches_linear_breakpoints():
    sampled = {
        "target": "dynamic",
        "t0": 0.25,
        "rate_hz": 4.0,
        "values": [0.0, 0.5, 1.0],
    }
    points = sampled_to_points(sampled)

    assert points == [[0.25, 0.0], [0.5, 0.5], [0.75, 1.0]]
    assert np.allclose(
        evaluate_curve(sampled, np.array([0.25, 0.375, 0.75])),
        evaluate_curve({"target": "dynamic", "points": points},
                       np.array([0.25, 0.375, 0.75])),
    )


def test_validate_spec_accepts_note_scoped_pitch_and_dynamic_curves():
    spec = {
        "id": "curve_contract",
        "kind": "cue",
        "duration_s": 2.0,
        "bpm": 120,
        "layers": [{
            "type": "notes",
            "osc": "sine",
            "env": {"attack": 0.01, "decay": 0.1, "sustain": 0.7, "release": 0.1},
            "notes": [{
                "note": "A4",
                "start_beat": 0.0,
                "dur_beats": 2.0,
                "curves": [
                    {
                        "target": "pitch_cents",
                        "time_basis": "note_beats",
                        "points": [[0.0, 0.0], [0.8, 200.0, "pow:2.5"], [2.0, 0.0]],
                    },
                    {
                        "target": "dynamic",
                        "time_basis": "note_beats",
                        "points": [[0.0, 0.3], [2.0, 0.8]],
                    },
                ],
            }],
        }],
    }

    assert validate_spec(spec)["id"] == "curve_contract"


@pytest.mark.parametrize(("curve", "message"), [
    ({"target": "pitch_cents", "points": [[1.0, 0.0], [0.0, 1.0]]}, "ascending"),
    ({"target": "pitch_cents", "points": [[0.0, 0.0, "hold"]]}, "first point"),
    ({"target": "pitch_cents", "points": [[0.0, 0.0], [1.0, 1.0, "spline"]]}, "shape"),
    ({"target": "dynamic", "points": [[0.0, -0.1], [1.0, 0.5]]}, "dynamic"),
    ({"target": "pitch_cents", "points": [[0.0, 0.0], [1.0, 5000.0]]}, "pitch_cents"),
    ({"target": "dynamic", "t0": 0.0, "rate_hz": 0.0, "values": [0.0]}, "rate_hz"),
])
def test_validate_spec_rejects_invalid_note_curves_with_pathful_errors(curve, message):
    spec = {
        "id": "bad_curve",
        "kind": "cue",
        "duration_s": 2.0,
        "bpm": 120,
        "layers": [{
            "type": "notes",
            "osc": "sine",
            "env": {"attack": 0.01, "decay": 0.1, "sustain": 0.7, "release": 0.1},
            "notes": [{
                "note": "A4",
                "start_beat": 0.0,
                "dur_beats": 1.0,
                "curves": [curve],
            }],
        }],
    }

    with pytest.raises(SpecError, match=message):
        validate_spec(spec)


def test_validate_spec_accepts_physical_model_pitch_curve():
    spec = {
        "id": "unsupported_curve",
        "kind": "cue",
        "duration_s": 2.0,
        "bpm": 120,
        "layers": [{
            "type": "notes",
            "osc": "bowed",
            "env": {"attack": 0.01, "decay": 0.1, "sustain": 0.7, "release": 0.1},
            "notes": [{
                "note": "A4",
                "start_beat": 0.0,
                "dur_beats": 1.0,
                "curves": [{"target": "pitch_cents", "points": [[0.0, 0.0], [1.0, 10.0]]}],
            }],
        }],
    }

    assert validate_spec(spec)["id"] == "unsupported_curve"
