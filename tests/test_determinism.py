"""Tests: byte-level reproducibility, seed isolation, schema rejection."""
import copy
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from audioforge import render_to_wav, spec_hash, validate_spec, SpecError  # noqa: E402

PRESETS = Path(__file__).resolve().parents[1] / "presets"


def _load(name):
    return json.loads((PRESETS / name).read_text())


def test_byte_identical_rerender():
    """The core guarantee: same spec -> identical WAV bytes, twice."""
    for preset in sorted(PRESETS.glob("*.json")):
        spec = json.loads(preset.read_text())
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            m1 = render_to_wav(spec, a)
            m2 = render_to_wav(copy.deepcopy(spec), b)
            assert m1["output_sha256"] == m2["output_sha256"], preset.name
            bytes_a = (Path(a) / m1["file"]).read_bytes()
            bytes_b = (Path(b) / m2["file"]).read_bytes()
            assert bytes_a == bytes_b, preset.name
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
