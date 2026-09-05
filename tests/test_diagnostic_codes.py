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
