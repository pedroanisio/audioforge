import copy

import pytest

from audioforge.schema import SpecError, validate_spec


def _base_spec():
    return {
        "id": "schema_edges",
        "kind": "cue",
        "duration_s": 2.0,
        "layers": [{
            "type": "tone",
            "freq_hz": 440,
            "env": {"attack": 0.01, "decay": 0.1, "sustain": 0.7, "release": 0.1},
        }],
        "master": {"target_peak_dbfs": -1.0},
    }


@pytest.mark.parametrize(("mutate", "message"), [
    (lambda s: s.update({"bit_depth": 20}), "bit_depth"),
    (lambda s: s.update({"layers": []}), "layers"),
    (lambda s: s["layers"][0].update({"type": "unknown"}), "type"),
    (lambda s: s["layers"][0].update({"osc": "missing"}), "osc"),
    (lambda s: s["layers"][0].pop("freq_hz"), "tone needs"),
    (lambda s: s["layers"][0].update({"pan": True}), "expected a number"),
    (lambda s: s["layers"][0].update({"unison": 99}), "unison"),
    (lambda s: s["layers"][0].update({
        "automation": {"target": "gain_db"},
    }), "automation must be a list"),
    (lambda s: s["layers"][0].update({
        "automation": [{"target": "pitch", "points": [[0, 0], [1, 1]]}],
    }), "target"),
    (lambda s: s["layers"][0].update({
        "automation": [{"target": "gain_db", "points": [[0, 0]]}],
    }), "at least 2"),
    (lambda s: s["layers"][0].update({
        "automation": [{"target": "cutoff_hz", "points": [[0, 100], [1, 200]]}],
    }), "requires an fx chain"),
    (lambda s: s.update({"buses": {"name": "main"}}), "buses"),
    (lambda s: s.update({"stage": {"hall_file": "hall.wav", "hall_sha256": "x"}}),
     "stage"),
    (lambda s: s.update({"variant": []}), "variant"),
    (lambda s: s.update({"tempo_map": [[1, 120]]}), "first point"),
    (lambda s: s.update({"groove": []}), "groove"),
    (lambda s: s.update({"markers": [{"name": 1, "time_s": 0.5}]}), "name"),
    (lambda s: s.update({"emotion": []}), "emotion"),
    (lambda s: s.update({"emotion": {"joy": 2.0}}), "joy"),
])
def test_validate_spec_rejects_edge_cases_with_pathful_errors(mutate, message):
    spec = _base_spec()
    mutate(spec)

    with pytest.raises(SpecError, match=message):
        validate_spec(spec)


def test_validate_spec_accepts_full_optional_cross_references():
    spec = _base_spec()
    spec["layers"][0].update({
        "name": "lead",
        "fx": [{"type": "filter", "mode": "lowpass", "cutoff_hz": 1200}],
        "automation": [{"target": "cutoff_hz", "points": [[0, 600], [1, 1200]]}],
        "bus": "music",
    })
    spec["buses"] = [{"name": "music", "duck": {"source": "lead"}}]
    spec["tempo_map"] = [[0.0, 120.0], [4.0, 130.0]]
    spec["groove"] = {"timing": [0.0] * 16, "accent": [1.0] * 16}

    assert validate_spec(copy.deepcopy(spec))["id"] == "schema_edges"
