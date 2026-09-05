"""validate_spec and the agent facade never rewrite the caller's spec (RM-E-004, HARNESS-CON-004)."""
import copy

from audioforge import AudioForge
from audioforge.agent_tools import run_tool
from audioforge.schema import validate_spec


def _spec_with_repeats():
    return {"id": "r", "kind": "cue", "duration_s": 2.0, "sample_rate": 48000, "bpm": 120,
            "score": {"sections": [{"name": "verse", "start_beat": 0, "dur_beats": 4}],
                      "repeats": [{"section": "verse", "count": 2}]},
            "layers": [{"name": "m", "type": "notes", "osc": "sine",
                        "notes": [{"note": "C4", "start_beat": 0, "dur_beats": 0.5}]}],
            "master": {"target_peak_dbfs": -1}}


def test_validate_spec_returns_expanded_ir_and_leaves_input_untouched():
    raw = _spec_with_repeats()
    before = copy.deepcopy(raw)
    out = validate_spec(raw)
    assert raw == before
    assert out is not raw
    assert out["duration_s"] == 4.0 and not out["score"].get("repeats")
    assert validate_spec(copy.deepcopy(out)) == out


def test_agent_validate_does_not_mutate_the_request():
    raw = _spec_with_repeats()
    before = copy.deepcopy(raw)
    response = run_tool("validate", {"spec": raw})
    assert response["ok"], response["diagnostics"]
    assert raw == before


def test_compiled_assets_and_mutations_carry_expanded_ir():
    source = """asset r { kind: cue
      duration: 2s
      tempo: 120bpm
      form: verse 0b for 2b
      repeat: verse x2
      layer m : notes { osc: sine
        notes: C4 @ 0b for 0.5b }
    }"""
    result = AudioForge().compile(source)
    assert result.ok, result.diagnostics
    asset = result.assets[0]
    assert asset.spec["duration_s"] == 3.0
    asset.set("layers.0.gain_db", -6)
    assert asset.spec["duration_s"] == 3.0 and asset.spec["layers"][0]["gain_db"] == -6
    loaded = AudioForge().load_spec(_spec_with_repeats())
    assert loaded.spec["duration_s"] == 4.0
    assert not [d for d in loaded.validate(resolve=False) if d.severity == "error"]
