import json
from pathlib import Path

import numpy as np
import pytest

from audioforge import AudioForge, spec_hash, validate_spec
from audioforge.agent_tools import run_tool, tool_schemas
from audioforge.capabilities import capability_manifest, capability_manifest_schema
from audioforge.catalog import DEFAULT_INSTRUMENT_CAPABILITIES
from audioforge.interop import export_session_bundle, interop_diagnostics
from audioforge.repair import apply_repair, plan_repair
from audioforge.schema import SpecError


def test_library_aware_orchestration_validates_ranges_and_techniques():
    assert "violin" in DEFAULT_INSTRUMENT_CAPABILITIES
    spec = {
        "id": "orch_ok",
        "kind": "cue",
        "duration_s": 2,
        "bpm": 120,  # instrument layers use the beat grid (audit F1)
        "library": {"name": "test", "manifest_sha256": "a" * 64},
        "layers": [{
            "name": "vln",
            "type": "instrument",
            "instrument": "violin",
            "articulation": "spiccato",
            "orchestration": DEFAULT_INSTRUMENT_CAPABILITIES["violin"],
            "notes": [{"note": "C5", "start_beat": 0, "dur_beats": 1}],
        }],
        "master": {"target_peak_dbfs": -1},
    }
    validate_spec(spec)

    spec["layers"][0]["notes"][0]["note"] = "C8"
    with pytest.raises(SpecError, match="outside hard range"):
        validate_spec(spec)

    spec["layers"][0]["notes"][0]["note"] = "C5"
    spec["layers"][0]["articulation"] = "pizzicato"
    with pytest.raises(SpecError, match="unavailable articulation"):
        validate_spec(spec)


def test_score_extensions_compile_to_typed_metadata_without_hashing_notation():
    src = """
asset notation_demo {
  kind: cue
  duration: 2s
  tempo: 120bpm
  tuning: edo divisions=24 base=A4 hz=440
  tuplet: lead 0b for 1b ratio=3:2
  lyrics: lead 0b "hello" phonemes=HH_AH_L_OW
  layer lead : notes {
    osc: sine
    env: a=0.01s d=0.1s s=0.8 r=0.1s
    notes: C4 @ 0b for 1b
  }
}
"""
    spec = AudioForge().compile(src).assets[0].spec
    without = AudioForge().compile("""
asset notation_demo {
  kind: cue
  duration: 2s
  tempo: 120bpm
  layer lead : notes {
    osc: sine
    env: a=0.01s d=0.1s s=0.8 r=0.1s
    notes: C4 @ 0b for 1b
  }
}
""").assets[0].spec

    assert spec["notation"]["tuning"]["system"] == "edo"
    assert spec["notation"]["tuplets"][0]["ratio"] == [3, 2]
    assert spec["notation"]["lyrics"][0]["text"] == "hello"
    assert spec_hash(spec) == spec_hash(without)


def test_repair_planner_is_deterministic_and_verifies_compile():
    src = """
asset repair_me {
  kind: cue
  duration: 1s
  tempo: 120bpm
  layer tone : tone {
    osc: saw
    note: C4
    env: a=0.01s d=0.1s s=0.8 r=0.1s
  }
  master { peak: -0.1db }
}
"""
    analysis = {"recommendations": [{"code": "very_bright"}, {"code": "clipping"}]}
    first = plan_repair({"dsl": src, "analysis": analysis, "feedback": "less rough"})
    second = plan_repair({"dsl": src, "analysis": analysis, "feedback": "less rough"})
    assert first == second
    assert first["suggestions"][0]["operation"] == "insert_master_fx"
    patched = apply_repair(src, first["suggestions"][0])
    assert AudioForge().compile(patched).ok
    assert first["trace"]["verification"]["compile_ok"] is True


def test_interop_diagnostics_and_session_bundle_manifest(tmp_path):
    spec = AudioForge().compile("""
asset interop_demo {
  kind: cue
  duration: 1s
  tempo: 120bpm
  layer lead : notes {
    osc: sine
    env: a=0.01s d=0.1s s=0.8 r=0.1s
    notes: C4 @ 0b for 1b art staccato
  }
}
""").assets[0].spec
    spec["notation"] = {"lyrics": [{"layer": "lead", "text": "hello"}]}
    spec["layers"][0]["notes"][0]["art"] = "trill"
    warnings = interop_diagnostics(spec, "midi")
    assert any(w["code"] == "lossy_articulation" for w in warnings)
    manifest = export_session_bundle(spec, tmp_path)
    assert manifest["schema"] == "audioforge.session-bundle/1"
    assert Path(manifest["files"]["spec"]).is_file()
    assert json.loads((tmp_path / "session.manifest.json").read_text()) == manifest


def test_capability_manifest_schema_and_examples_are_contractual():
    manifest = capability_manifest()
    schema = capability_manifest_schema()
    assert schema["required"] == ["schema", "engine_version", "dsl_version"]
    assert manifest["schema"] == "audioforge.capabilities/1"
    assert sorted(manifest["oscillators"])
    for example in manifest["examples"].values():
        if example.startswith("asset "):
            assert AudioForge().compile(example).ok


def test_agent_tool_facade_response_shapes(tmp_path):
    src = """
asset tool_demo {
  kind: cue
  duration: 1s
  layer tone : tone {
    osc: sine
    note: C4
    env: a=0.01s d=0.1s s=0.8 r=0.1s
  }
}
"""
    schemas = tool_schemas()
    assert "compile" in schemas and "repair" in schemas
    compiled = run_tool("compile", {"dsl": src})
    assert compiled["ok"] is True
    assert compiled["artifacts"][0]["id"] == "tool_demo"
    decompiled = run_tool("decompile", {"spec": compiled["artifacts"][0]["spec"]})
    assert "asset tool_demo" in decompiled["artifacts"][0]["dsl"]
    repaired = run_tool("repair", {"dsl": src, "analysis": {"recommendations": []}})
    assert repaired["ok"] is True
    error = run_tool("compile", {"dsl": "nope"})
    assert error["ok"] is False
    assert error["diagnostics"][0]["severity"] == "error"


def test_agent_tools_cover_validate_render_export_analyze_and_import_errors():
    src = """
asset tool_extra {
  kind: cue
  duration: 1s
  tempo: 120bpm
  layer lead : notes {
    osc: sine
    env: a=0.01s d=0.1s s=0.8 r=0.1s
    notes: C4 @ 0b for 1b
  }
}
"""
    spec = AudioForge().compile(src).assets[0].spec
    assert run_tool("validate", {"spec": spec})["ok"] is True
    assert run_tool("render", {"dsl": src})["artifacts"][0]["renderable"] is True
    assert run_tool("export", {"spec": spec, "format": "midi"})["ok"] is True
    assert run_tool("export", {"spec": spec, "format": "musicxml"})["ok"] is True
    audio = np.zeros((128, 2), dtype=float)
    assert run_tool("analyze", {"audio": audio, "sample_rate": 48000})["ok"] is True
    assert run_tool("import", {})["ok"] is False
    assert run_tool("unknown", {})["ok"] is False
    assert run_tool("validate", {"spec": {"bad": True}})["ok"] is False


def test_repair_noop_and_peak_suggestions_apply_cleanly():
    src = """
asset repair_peak {
  kind: cue
  duration: 1s
  layer tone : tone {
    osc: sine
    note: C4
    env: a=0.01s d=0.1s s=0.8 r=0.1s
  }
}
"""
    noop = plan_repair({"dsl": src, "analysis": {"recommendations": []}})
    assert noop["suggestions"][0]["operation"] == "noop"
    clipping = plan_repair({
        "dsl": src,
        "analysis": {"recommendations": [{"code": "clipping"}]},
    })
    patched = apply_repair(src, clipping["suggestions"][0])
    assert "peak: -1db" in patched
    assert AudioForge().compile(patched).ok
