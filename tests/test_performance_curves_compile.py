import copy

from audioforge import AudioForge, spec_hash


def _compile_performance_spec():
    src = """
asset curve_lowering {
  kind: cue
  duration: 3s
  tempo: 120bpm
  layer lead : notes {
    osc: sine
    env: a=0.01s d=0.1s s=0.7 r=0.1s
    glide: 0.12s
    vibrato: rate=5hz depth=20c delay=0.05s
    dynamic: 0b=mp, 2b=f
    notes: A4 @ 0b for 1b, B4 @ 1b for 1b
  }
}
"""
    result = AudioForge().compile(src)
    assert result.ok, [d.message for d in result.diagnostics]
    return result.assets[0].spec


def test_compile_legacy_performance_fields_to_explicit_curves():
    spec = _compile_performance_spec()
    layer = spec["layers"][0]

    assert {"target": "dynamic", "time_basis": "layer_beats",
            "points": [[0.0, 0.48], [2.0, 0.74]]} in layer["automation"]
    assert layer["dynamic"] == [[0.0, 0.48], [2.0, 0.74]]

    first, second = layer["notes"]
    first_targets = [curve["target"] for curve in first["curves"]]
    second_targets = [curve["target"] for curve in second["curves"]]
    assert first_targets == ["pitch_cents"]
    assert second_targets == ["pitch_cents", "pitch_cents"]

    vibrato = first["curves"][0]
    assert vibrato["source"] == "vibrato"
    assert vibrato["time_basis"] == "note_seconds"
    assert vibrato["rate_hz"] == 250.0
    assert len(vibrato["values"]) > 10

    glide = second["curves"][0]
    assert glide["source"] == "glide_s"
    assert glide["points"][0][1] < 0.0
    assert glide["points"][-1] == [0.12, 0.0]

    authored = spec["_meta"]["semantic"]["authored_expression"]
    assert {entry["field"] for entry in authored} == {"dynamic", "glide_s", "vibrato"}


def test_compile_curve_values_are_hash_included_but_semantic_sidecar_is_not():
    spec = _compile_performance_spec()

    changed_curve = copy.deepcopy(spec)
    changed_curve["layers"][0]["notes"][0]["curves"][0]["values"][3] += 1.0
    assert spec_hash(spec) != spec_hash(changed_curve)

    changed_semantic = copy.deepcopy(spec)
    changed_semantic["_meta"]["semantic"]["authored_expression"][0]["source"] = (
        "rewritten source text"
    )
    assert spec_hash(spec) == spec_hash(changed_semantic)
