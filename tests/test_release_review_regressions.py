"""Regressions found by the engine 3.0 release review (PR #1) and fixed before merge."""
import copy

import numpy as np
import pytest

from audioforge import AudioForge
from audioforge.decompile import spec_to_dsl
from audioforge.render import render
from audioforge.schema import SpecError, validate_spec


def test_intent_contour_round_trip_is_idempotent():
    """Decompiling an asset with a structured intent block must not also emit the master
    automation that block regenerates; otherwise every cycle doubles the contour."""
    source = """asset c { kind: cue
      duration: 4s
      tempo: 120bpm
      intent { contour: arch }
      layer p : notes { osc: sine
        notes: C4 @ 0b for 8b }
    }"""
    first = AudioForge().compile(source)
    assert first.ok, first.diagnostics
    spec1 = first.assets[0].spec
    second = AudioForge().compile(spec_to_dsl(spec1))
    assert second.ok, second.diagnostics
    spec2 = second.assets[0].spec
    assert len(spec2["master"]["automation"]) == len(spec1["master"]["automation"]) == 1
    assert np.array_equal(render(spec1)[0], render(spec2)[0])


ENV = {"attack": 0.01, "decay": 0.01, "sustain": 0.5, "release": 0.05}


def _two_beds(second_name):
    return {"id": "dup", "kind": "cue", "duration_s": 1.0, "sample_rate": 48000, "bpm": 120,
            "layers": [{"name": "bed", "type": "noise", "color": "white", "gain_db": -12, "env": ENV},
                       {"name": second_name, "type": "noise", "color": "white", "gain_db": -12, "env": ENV}],
            "master": {"target_peak_dbfs": -1, "fade_out_s": 0}}


def test_duplicate_layer_names_are_rejected():
    with pytest.raises(SpecError, match=r"layers\[1\]\.name: duplicate layer name 'bed'"):
        validate_spec(_two_beds("bed"))
    result = AudioForge().compile("""asset d { kind: cue
      duration: 1s
      tempo: 120bpm
      layer bed : noise { color: white
        env: a=0.01s d=0.01s s=0.5 r=0.05s }
      layer bed : noise { color: white
        env: a=0.01s d=0.01s s=0.5 r=0.05s }
    }""")
    assert not result.ok
    assert any("duplicate layer name" in d.message for d in result.diagnostics)


def test_distinct_layers_draw_independent_randomness():
    spec = _two_beds("bed2")
    one = render({**copy.deepcopy(spec), "layers": [copy.deepcopy(spec["layers"][0])]})[0]
    both = render(copy.deepcopy(spec))[0]
    assert not np.allclose(both, 2 * one)
