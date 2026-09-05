"""Every diagnostic code the engine emits is in the capability manifest (RM-E-001, HARNESS-CON-001)."""
import re

import pytest

from audioforge import AudioForge
from audioforge.analysis import ANALYSIS_DIAGNOSTIC_CODES, LOOP_BOUNDARY_CODE, _recommend
from audioforge.capabilities import capability_manifest
from audioforge.harmony import HARMONY_DIAGNOSTIC_CODES
from audioforge.render import render
from audioforge.schema import SpecError

REGISTERED = set(capability_manifest()["diagnostic_codes"])


def test_code_families_are_registered():
    assert HARMONY_DIAGNOSTIC_CODES <= REGISTERED
    assert ANALYSIS_DIAGNOSTIC_CODES <= REGISTERED
    assert LOOP_BOUNDARY_CODE in REGISTERED


def test_recommend_only_emits_registered_codes():
    extreme = {"low_band_share": 0.0, "stereo_width": 0.0, "spectral_centroid_hz": 9000.0,
               "crest_db": 30.0, "peak_dbfs": 0.0, "longest_silence_s": 10.0, "silence_share": 0.5}
    emitted = {item["code"] for item in _recommend(extreme)}
    assert emitted == ANALYSIS_DIAGNOSTIC_CODES


def test_harmony_diagnostics_lead_with_a_registered_code():
    result = AudioForge().compile("""asset h { kind: cue
      duration: 4s
      tempo: 120bpm
      voicing: richness=1 extensions=7
      layer chords : notes { osc: sine
        notes: C3 @ 0b for 2b, E3 @ 0b for 2b, G3 @ 0b for 2b, A3 @ 0b for 2b }
    }""")
    assert result.ok, result.diagnostics
    # Messages are prefixed with the asset id ("h: ambiguous_harmony: ..."); the code is the token.
    codes = {re.search(r"\b(\w+_harmony)\b", d.message).group(1)
             for d in result.diagnostics if "_harmony" in d.message}
    assert codes == {"ambiguous_harmony"}


def test_loop_failure_leads_with_a_registered_code():
    spec = {"id": "loop", "kind": "cue", "duration_s": 1.0, "sample_rate": 48000, "bpm": 120,
            "loop_safe": True,
            "layers": [{"name": "lead", "type": "notes", "osc": "sine", "gain_db": -12,
                        "env": {"attack": 0.001, "decay": 0, "sustain": 1, "release": 0.2},
                        "notes": [{"note": "C4", "start_beat": 0, "dur_beats": 2}]}],
            "master": {"target_peak_dbfs": -1, "fade_out_s": 0}}
    with pytest.raises(SpecError) as info:
        render(spec)
    assert str(info.value).split(":")[0] == LOOP_BOUNDARY_CODE


def test_diagnostic_infers_registered_code_from_message():
    from audioforge.sdk import Diagnostic, infer_diagnostic_code
    assert Diagnostic("warning", "h: ambiguous_harmony: layer 'x' at 0b; preserved").code == "ambiguous_harmony"
    assert Diagnostic("error", "loop_boundary_tail: unsafe loop seam: {}").code == LOOP_BOUNDARY_CODE
    assert Diagnostic("error", "spec.layers[0].gain_db: must be a number").code is None
    assert Diagnostic("warning", "free text", code="dead_air").code == "dead_air"
    assert infer_diagnostic_code("") is None
    assert "code" in Diagnostic("warning", "x").as_dict()


def test_sdk_agent_and_plan_diagnostics_carry_codes():
    from audioforge.agent_tools import run_tool
    spec = {"id": "loop", "kind": "cue", "duration_s": 1.0, "sample_rate": 48000, "bpm": 120,
            "loop_safe": True,
            "layers": [{"name": "lead", "type": "notes", "osc": "sine", "gain_db": -12,
                        "env": {"attack": 0.001, "decay": 0, "sustain": 1, "release": 0.2},
                        "notes": [{"note": "C4", "start_beat": 0, "dur_beats": 2}]}],
            "master": {"target_peak_dbfs": -1, "fade_out_s": 0}}
    sdk_codes = {d.code for d in AudioForge().load_spec(spec).validate()}
    assert LOOP_BOUNDARY_CODE in sdk_codes
    response = run_tool("validate", {"spec": spec})
    assert not response["ok"]
    assert all("code" in d for d in response["diagnostics"])
    assert LOOP_BOUNDARY_CODE in {d["code"] for d in response["diagnostics"]}
    result = AudioForge().compile("""asset t { kind: cue
      duration: 1s
      tempo: 120bpm
      routing: fallbacks=warn
      layer p : notes { osc: sine
        notes: C4 @ 0b for 1b tech harmonic(partial=3) }
    }""")
    assert result.ok, result.diagnostics
    plan_codes = {d.code for d in result.assets[0].validate()}
    assert "render_plan_approximation" in plan_codes
