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
    }), "out of range"),
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


def _replace_layer(spec, layer):
    spec["layers"] = [layer]


@pytest.mark.parametrize(("mutate", "message"), [
    (lambda s: s.update({"id": ""}), "non-empty string"),
    (lambda s: s.update({"kind": "album"}), "kind"),
    (lambda s: s.update({"duration_s": True}), "expected a number"),
    (lambda s: s["layers"][0].update({"fx": "filter"}), "fx must be a list"),
    (lambda s: s["layers"][0].update({"fx": [{"type": "ghost"}]}), "unknown fx"),
    (lambda s: s["layers"][0].update({
        "fx": [{"type": "filter", "mode": "notch", "cutoff_hz": 1000}],
    }), "mode"),
    (lambda s: s["layers"][0].update({
        "fx": [{"type": "delay", "time_s": 10.0}],
    }), "above maximum"),
    (lambda s: s["layers"][0].update({
        "fx": [{"type": "reverb", "mix": "wet"}],
    }), "expected a number"),
    (lambda s: s["layers"][0].update({
        "fx": [{"type": "ladder", "cutoff_hz": 10.0}],
    }), "below minimum"),
    (lambda s: s["layers"][0].update({
        "fx": [{"type": "tape", "flutter": 2.0}],
    }), "above maximum"),
    (lambda s: s["layers"][0]["env"].pop("attack"), "attack"),
    (lambda s: s["layers"][0].update({"modes": "modal"}), "modes"),
    (lambda s: s["layers"][0].update({"modes": [[0.01, 1.0, 1.0]]}), "ratio"),
    (lambda s: s["layers"][0].update({"modes": [[1.0, 3.0, 1.0]]}), "amp"),
    (lambda s: s["layers"][0].update({"modes": [[1.0, 1.0, 4.0]]}), "t60"),
    (lambda s: s["layers"][0].update({"scan": 2.0}), "scan"),
    (lambda s: s["layers"][0].update({"material": "rubber"}), "material"),
    (lambda s: _replace_layer(s, {
        "type": "tone", "note": "Cmaj7", "env": _base_spec()["layers"][0]["env"],
    }), "chord"),
    (lambda s: _replace_layer(s, {
        "type": "sweep", "f_start_hz": 0.5, "f_end_hz": 1000,
        "env": _base_spec()["layers"][0]["env"],
    }), "below minimum"),
    (lambda s: _replace_layer(s, {
        "type": "noise", "color": "violet", "env": _base_spec()["layers"][0]["env"],
    }), "color"),
    (lambda s: _replace_layer(s, {"type": "drums", "voice": "kick", "pattern": "xo"}),
     "pattern"),
    (lambda s: _replace_layer(s, {
        "type": "notes", "notes": [{"start_beat": 0, "dur_beats": 1}],
    }), "needs 'note'"),
    (lambda s: _replace_layer(s, {
        "type": "notes",
        "notes": [{"note": "C4", "start_beat": 0, "dur_beats": 1, "art": "ghost"}],
    }), "art"),
    (lambda s: _replace_layer(s, {
        "type": "notes",
        "notes": [{"note": "C4", "start_beat": 0, "dur_beats": 1, "slur": 0}],
    }), "slur"),
    (lambda s: _replace_layer(s, {
        "type": "notes",
        "notes": [{"note": "C4", "start_beat": 0, "dur_beats": 1}],
        "dynamic": [[1.0, 0.5], [0.5, 0.5]],
    }), "dynamic"),
    (lambda s: s["layers"][0].update({"humanize": 0.1}), "humanize"),
    (lambda s: s["layers"][0].update({"vibrato": {"rate_hz": 20.0}}), "vibrato"),
    (lambda s: _replace_layer(s, {
        "type": "grain", "source": "sine", "env": _base_spec()["layers"][0]["env"],
    }), "needs note"),
    (lambda s: _replace_layer(s, {"type": "grain", "source": "white"}), "needs env"),
    (lambda s: _replace_layer(s, {
        "type": "instrument", "instrument": "violin",
        "notes": [{"note": "C4", "start_beat": 0, "dur_beats": 1}],
    }), "library"),
    (lambda s: (
        s.update({"library": {"name": "mini", "manifest_sha256": "a" * 64}}),
        _replace_layer(s, {
            "type": "instrument", "instrument": "",
            "notes": [{"note": "C4", "start_beat": 0, "dur_beats": 1}],
        }),
    ), "instrument"),
    (lambda s: (
        s.update({"library": {"name": "mini", "manifest_sha256": "a" * 64}}),
        _replace_layer(s, {
            "type": "instrument", "instrument": "violin", "articulation": "ghost",
            "notes": [{"note": "C4", "start_beat": 0, "dur_beats": 1}],
        }),
    ), "articulation"),
    (lambda s: _replace_layer(s, {"type": "foley", "model": "engine"}), "model"),
    (lambda s: _replace_layer(s, {"type": "sample", "file": "", "sha256": "a" * 64}),
     "file"),
    (lambda s: _replace_layer(s, {"type": "sample", "file": "hit.wav", "sha256": "x"}),
     "sha256"),
    (lambda s: s.update({"buses": [{"name": "m"}, {"name": "m"}]}), "duplicate"),
    (lambda s: s.update({"buses": [{"name": "m", "duck": {"source": "missing"}}]}),
     "duck.source"),
    (lambda s: s.update({"stage": {
        "hall_file": "hall.wav", "hall_sha256": "a" * 64, "mics": {"bad": 1.0},
    }}), "mics.bad"),
    (lambda s: s.update({"stage": {
        "hall_file": "hall.wav", "hall_sha256": "a" * 64, "dims": [1, 2, 3],
    }}), "dims"),
    (lambda s: s.update({"library": {"name": "", "manifest_sha256": "abc"}}), "library"),
    (lambda s: s.update({"cutdowns": []}), "cutdowns"),
    (lambda s: s.update({"cutdowns": [{"length_s": 1.0, "segments": []}]}),
     "segments"),
    (lambda s: s.update({"cutdowns": [{"length_s": 1.0, "segments": [[0, 3]]}]}),
     "keep windows"),
    (lambda s: s.update({"tempo_map": [[0.0, 120.0], [1.0, 500.0]]}), "bpm"),
    (lambda s: s.update({"groove": {"timing": [0.0] * 15}}), "timing"),
    (lambda s: s.update({"master": {"target_peak_dbfs": 1.0}}), "target_peak"),
    (lambda s: s.update({"loop_safe": True}), "requires bpm"),
    (lambda s: s.update({"loop_safe": True, "bpm": 100.0}), "whole"),
])
def test_validate_spec_rejects_broad_schema_contract_edges(mutate, message):
    spec = _base_spec()
    mutate(spec)

    with pytest.raises(SpecError, match=message):
        validate_spec(spec)
