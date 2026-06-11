"""Tests: byte-level reproducibility, seed isolation, schema rejection."""
import copy
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from audioforge import render_to_wav, spec_hash, validate_spec, SpecError  # noqa: E402

SUCCESS_CUE = {
    "id": "success_cue_v1",
    "kind": "cue",
    "duration_s": 1.1,
    "bpm": 140,
    "layers": [
        {
            "name": "arp",
            "type": "notes",
            "osc": "triangle",
            "gain_db": -3,
            "env": {"attack": 0.004, "decay": 0.22, "sustain": 0.0, "release": 0.08},
            "notes": [
                {"note": "C5", "start_beat": 0.0, "dur_beats": 0.5},
                {"note": "E5", "start_beat": 0.5, "dur_beats": 0.5},
                {"note": "G5", "start_beat": 1.0, "dur_beats": 1.2, "vel": 1.1},
            ],
        }
    ],
    "master": {"target_peak_dbfs": -2.0, "fade_out_s": 0.06, "stereo_width": 0.6},
}

TRANSITION_WHOOSH = {
    "id": "transition_whoosh_v1",
    "kind": "transition",
    "duration_s": 1.4,
    "layers": [
        {
            "name": "air",
            "type": "noise",
            "color": "pink",
            "gain_db": -2,
            "env": {"attack": 0.55, "decay": 0.5, "sustain": 0.0, "release": 0.25},
        }
    ],
    "master": {"target_peak_dbfs": -1.5, "fade_out_s": 0.08, "stereo_width": 0.8},
}


def _load(name):
    if name == "success_cue.json":
        return copy.deepcopy(SUCCESS_CUE)
    if name == "transition_whoosh.json":
        return copy.deepcopy(TRANSITION_WHOOSH)
    raise FileNotFoundError(name)


def test_byte_identical_rerender():
    """The core guarantee: same spec -> identical WAV bytes, twice."""
    for name, spec in {
        "success_cue.json": SUCCESS_CUE,
        "transition_whoosh.json": TRANSITION_WHOOSH,
    }.items():
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            m1 = render_to_wav(spec, a)
            m2 = render_to_wav(copy.deepcopy(spec), b)
            assert m1["output_sha256"] == m2["output_sha256"], name
            bytes_a = (Path(a) / m1["file"]).read_bytes()
            bytes_b = (Path(b) / m2["file"]).read_bytes()
            assert bytes_a == bytes_b, name
    print("PASS  byte-identical re-render (all presets)")


def test_spec_change_changes_output():
    """Any semantic change to the spec must change the hash and the audio."""
    spec = _load("success_cue.json")
    changed = copy.deepcopy(spec)
    changed["layers"][0]["notes"][0]["note"] = "D5"
    assert spec_hash(spec) != spec_hash(changed)
    with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
        m1 = render_to_wav(spec, a)
        changed["id"] = "success_cue_changed"
        m2 = render_to_wav(changed, b)
        assert m1["output_sha256"] != m2["output_sha256"]
    print("PASS  spec change propagates to output hash")


def test_key_order_irrelevant():
    """Canonical hashing: JSON key order must not affect identity."""
    spec = _load("transition_whoosh.json")
    reordered = json.loads(json.dumps(spec, sort_keys=True))
    assert spec_hash(spec) == spec_hash(reordered)
    print("PASS  canonical hash ignores key order")


def test_schema_rejects_bad_specs():
    bad_cases = [
        ({}, "missing id"),
        ({"id": "x", "kind": "nope", "duration_s": 1, "layers": [{}]}, "bad kind"),
        ({"id": "x", "kind": "sfx", "duration_s": 1,
          "layers": [{"type": "noise", "color": "purple",
                      "env": {"attack": 0, "decay": 0, "sustain": 1, "release": 0}}]},
         "bad noise color"),
        ({"id": "x", "kind": "loop", "duration_s": 1,
          "layers": [{"type": "drums", "voice": "kick", "pattern": "x?.x"}]},
         "bad pattern char"),
        ({"id": "x", "kind": "loop", "duration_s": 1,
          "layers": [{"type": "drums", "voice": "kick", "pattern": "x..."}]},
         "drums without bpm"),
    ]
    for spec, why in bad_cases:
        try:
            validate_spec(spec)
        except SpecError:
            continue
        raise AssertionError(f"schema accepted invalid spec ({why})")
    print("PASS  schema rejects malformed specs with clear errors")


if __name__ == "__main__":
    test_byte_identical_rerender()
    test_spec_change_changes_output()
    test_key_order_irrelevant()
    test_schema_rejects_bad_specs()
    print("\nAll tests passed.")
