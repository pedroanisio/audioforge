"""AI-agent DSL surface: manifest, grammar, smart sugar, analysis, decompile."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from audioforge import AudioForge  # noqa: E402
from audioforge.analysis import analyze_audio  # noqa: E402
from audioforge.capabilities import capability_manifest  # noqa: E402
from audioforge.decompile import spec_to_dsl  # noqa: E402
from audioforge.grammar import dsl_ebnf, dsl_gbnf  # noqa: E402
from audioforge.cli import main as cli_main  # noqa: E402


SMART_SRC = """
asset agent_ready {
  kind: cue
  duration: 4s
  tempo: 96bpm
  key: C major
  style: cinematic
  perform: style=cinematic expressivity=0.8
  ensemble: synth size=5 spread=0.45 octaves=1
  voicing: richness=0.7 extensions=7,9
  space: hall=studio depth=0.5
  marker hit @ 2s

  motif hook {
    C4 @ 0b for 1b
    E4 @ 1b for 1b
    G4 @ 2b for 2b
  }
  layer pad : notes {
    osc: saw
    gain: -12db
    env: a=0.05s d=0.2s s=0.7 r=0.3s
    notes: C3maj7 @ 0b for 8b voicing drop2
    play hook @ 0b legato
  }
  master { peak: -1db }
}
"""


def test_capability_manifest_is_machine_readable_and_current():
    cap = capability_manifest()
    assert cap["engine_version"] and cap["dsl_version"]
    assert "notes" in cap["layer_types"]
    assert "osc" in cap["layer_types"]["notes"]["properties"]
    assert "lowpass" in cap["fx"]
    assert "trill" in cap["articulations"]
    assert "style" in cap["smart_directives"]
    assert cap["examples"]["smart_directives"].startswith("style:")
    assert cap["repair_hints"]["unknown_property"]
    assert cap["incompatibilities"]["seat_with_bus"]
    json.dumps(cap, sort_keys=True)


def test_grammar_artifacts_expose_constrained_generation_surface():
    ebnf = dsl_ebnf()
    gbnf = dsl_gbnf()
    assert "asset" in ebnf and "layer" in ebnf and "smart_directive" in ebnf
    assert "root ::=" in gbnf and "asset" in gbnf and "smart-directive" in gbnf


def test_smart_directives_compile_to_explicit_ir():
    res = AudioForge().compile(SMART_SRC)
    assert res.ok, [d.message for d in res.diagnostics]
    spec = res.assets[0].spec
    assert spec["intent"]["style"] == "cinematic"
    assert spec["intent"]["perform"]["expressivity"] == 0.8
    assert spec["intent"]["ensemble"]["size"] == 5
    assert spec["intent"]["voicing"]["extensions"] == [7, 9]
    assert spec["intent"]["space"]["hall"] == "studio"
    assert spec["layers"][0]["humanize"]["timing_s"] > 0
    assert spec["layers"][0]["phrasing"] > 0
    assert spec["layers"][0]["unison"] >= 5
    assert spec["layers"][0]["spread_cents"] > 0
    assert any(fx["type"] in {"hall", "saturate", "comp"}
               for fx in spec["master"]["fx"])
    assert any("smart directives" in d.message for d in res.diagnostics)
    assert not [d for d in res.assets[0].validate() if d.severity == "error"]


def test_voicing_directive_adds_explicit_extensions_to_chord_stacks():
    src = """
asset voiced {
  kind: cue
  duration: 2s
  tempo: 90bpm
  voicing: richness=1 extensions=7,9
  layer keys : notes {
    osc: sine
    env: a=0.01s d=0.1s s=0.8 r=0.1s
    notes: C3 @ 0b for 2b, E3 @ 0b for 2b, G3 @ 0b for 2b
  }
  master { peak: -1db }
}
"""
    res = AudioForge().compile(src)
    assert res.ok, [d.message for d in res.diagnostics]
    notes = [e["note"] for e in res.assets[0].spec["layers"][0]["notes"]]
    assert "A#3" in notes
    assert "D4" in notes


def test_render_analysis_is_structured_and_written_to_manifest(tmp_path):
    res = AudioForge().compile(SMART_SRC)
    asset = res.assets[0]
    stereo, sr, _meta = asset.render()
    report = analyze_audio(stereo, sr)
    assert report["duration_s"] > 0
    assert report["peak_dbfs"] <= 0.1
    assert report["spectral_centroid_hz"] > 0
    assert 0.0 <= report["stereo_width"] <= 2.0
    meta = asset.export(tmp_path, analyze=True)
    assert "analysis" in meta
    on_disk = json.loads((tmp_path / f"{asset.id}.manifest.json").read_text())
    assert on_disk["analysis"]["spectral_centroid_hz"] == meta["analysis"]["spectral_centroid_hz"]


def test_ir_decompiles_to_render_equivalent_dsl():
    res = AudioForge().compile(SMART_SRC)
    spec = res.assets[0].spec
    dsl = spec_to_dsl(spec)
    assert "asset agent_ready" in dsl
    assert "layer pad : notes" in dsl
    assert "notes:" in dsl
    again = AudioForge().compile(dsl)
    assert again.ok, [d.message for d in again.diagnostics]
    assert again.assets[0].spec["duration_s"] == spec["duration_s"]
    assert again.assets[0].spec["layers"][0]["notes"] == spec["layers"][0]["notes"]


def test_cli_exposes_agent_surfaces(tmp_path, capsys):
    src = tmp_path / "smart.af"
    src.write_text(SMART_SRC)
    assert cli_main(["capabilities"]) == 0
    cap_out = capsys.readouterr().out
    assert '"smart_directives"' in cap_out
    assert cli_main(["grammar", "--format", "gbnf"]) == 0
    grammar_out = capsys.readouterr().out
    assert "root ::=" in grammar_out
    assert cli_main(["decompile", str(src)]) == 0
    dsl_out = capsys.readouterr().out
    assert "asset agent_ready" in dsl_out
    assert cli_main(["render", str(src), "-o", str(tmp_path / "out"),
                     "--analyze"]) == 0
    render_out = capsys.readouterr().out
    assert '"analysis"' in render_out


def test_perform_directive_adds_phrase_analysis_and_musical_performance_ir():
    src = """
asset phrased {
  kind: cue
  duration: 6s
  tempo: 90bpm
  perform: style=romantic expressivity=0.9
  layer melody : notes {
    osc: sine
    env: a=0.01s d=0.1s s=0.8 r=0.2s
    notes: C4 @ 0b for 1b, D4 @ 1b for 1b, E4 @ 2b for 1b, G4 @ 3b for 2b,
           C4 @ 7b for 1b, B3 @ 8b for 1b, C4 @ 9b for 2b
  }
  master { peak: -1db }
}
"""
    spec = AudioForge().compile(src).assets[0].spec
    phrases = spec["intent"]["analysis"]["phrases"]
    assert len(phrases) == 2
    assert phrases[0]["peak_note"] == "G4"
    layer = spec["layers"][0]
    assert layer["dynamic"][0][1] < max(v for _b, v in layer["dynamic"])
    assert layer["vibrato"]["depth_cents"] > 0
    assert layer["notes"][0]["slur"] == layer["notes"][1]["slur"]
    assert layer["notes"][3]["dur_beats"] > 2.0  # phrase peak agogic lengthening


def test_voicing_directive_voice_leads_and_adds_passing_or_suspension_tones():
    src = """
asset voicelead {
  kind: cue
  duration: 4s
  tempo: 80bpm
  voicing: richness=1 extensions=7,9
  layer harmony : notes {
    osc: sine
    env: a=0.01s d=0.1s s=0.8 r=0.2s
    notes: C3 @ 0b for 2b, E3 @ 0b for 2b, G3 @ 0b for 2b,
           G3 @ 2b for 2b, B3 @ 2b for 2b, D4 @ 2b for 2b
  }
  master { peak: -1db }
}
"""
    spec = AudioForge().compile(src).assets[0].spec
    notes = spec["layers"][0]["notes"]
    assert any(e.get("generated") == "voice_leading" for e in notes)
    assert any(e.get("generated") in {"passing_tone", "suspension"} for e in notes)
    assert "voice_leading" in spec["intent"]["voicing"]


def test_ensemble_and_space_create_role_buses_and_route_layers():
    src = """
asset arranged {
  kind: cue
  duration: 4s
  tempo: 100bpm
  ensemble: cinematic size=4 spread=0.6 octaves=1
  space: hall=studio depth=0.6
  layer bass_line : notes {
    osc: sine
    env: a=0.01s d=0.1s s=0.8 r=0.2s
    notes: C2 @ 0b for 4b
  }
  layer lead_theme : notes {
    osc: triangle
    env: a=0.01s d=0.1s s=0.8 r=0.2s
    notes: C5 @ 0b for 1b, E5 @ 1b for 1b, G5 @ 2b for 2b
  }
  master { peak: -1db }
}
"""
    spec = AudioForge().compile(src).assets[0].spec
    bus_names = {b["name"] for b in spec["buses"]}
    assert {"af_bass", "af_melody", "af_space"}.issubset(bus_names)
    routes = {l["name"]: l.get("bus") for l in spec["layers"]}
    assert routes["bass_line"] == "af_bass"
    assert routes["lead_theme"] == "af_melody"
    assert any(b["name"] == "af_space" and b.get("fx") for b in spec["buses"])
    assert not [d for d in AudioForge().load_spec(spec).validate()
                if d.severity == "error"]


def test_analysis_returns_actionable_recommendations():
    import numpy as np

    sr = 48000
    t = np.arange(sr) / sr
    mono_bright = 0.05 * np.sin(2 * np.pi * 9000 * t)
    stereo = np.stack([mono_bright, mono_bright], axis=1)
    report = analyze_audio(stereo, sr)
    recs = {r["code"] for r in report["recommendations"]}
    assert {"low_foundation_weak", "mono_image", "very_bright"}.issubset(recs)


def test_decompiler_preserves_buses_automation_dynamic_and_smart_render_ir():
    res = AudioForge().compile(SMART_SRC)
    spec = res.assets[0].spec
    spec["layers"][0].setdefault("automation", []).append(
        {"target": "gain_db", "points": [[0, -12], [2, -6]]})
    dsl = spec_to_dsl(spec)
    assert "bus af_" in dsl
    assert "auto gain:" in dsl
    assert "dynamic:" in dsl
    again = AudioForge().compile(dsl)
    assert again.ok, [d.message for d in again.diagnostics]
