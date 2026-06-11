import math

import pytest

from audioforge import AudioForge
from audioforge.decompile import spec_to_dsl
from audioforge.schema import SpecError, validate_spec
from audioforge.sequencer import TempoMap, TimelineMap


def _compile(src: str) -> dict:
    res = AudioForge().compile(src)
    assert res.ok, [d.message for d in res.diagnostics]
    return res.assets[0].spec


def test_fermata_compiles_to_first_class_hold_and_shifts_timeline():
    spec = _compile("""
asset held_phrase {
  kind: cue
  duration: 6s
  tempo: 120bpm
  fermata: 2b=1.25s
  layer lead : notes {
    osc: sine
    env: a=0.01s d=0.1s s=0.8 r=0.1s
    notes: C4 @ 0b for 2b, E4 @ 2b for 1b
  }
  master { peak: -1db }
}
""")

    assert spec["holds"] == [{"beat": 2.0, "duration_s": 1.25}]
    base = TempoMap([[0.0, spec["bpm"]]])
    timeline = TimelineMap(base, spec["holds"])

    assert timeline.sec(1.0) == pytest.approx(base.sec(1.0))
    assert timeline.sec(2.0) == pytest.approx(base.sec(2.0) + 1.25)
    assert timeline.sec(3.0) == pytest.approx(base.sec(3.0) + 1.25)
    assert timeline.beat_at(base.sec(2.0) + 0.6) == pytest.approx(2.0)


def test_fermata_timeline_is_used_by_render_scheduler():
    res = AudioForge().compile("""
asset rendered_hold {
  kind: cue
  duration: 3s
  samplerate: 8000
  tempo: 120bpm
  fermata: 1b=0.25s
  layer lead : notes {
    osc: sine
    env: a=0.001s d=0.01s s=0.5 r=0.01s
    notes: C4 @ 0b for 1b, E4 @ 1b for 0.5b
  }
  master { peak: -1db }
}
""")
    assert res.ok, [d.message for d in res.diagnostics]

    audio, sr, meta = res.assets[0].render()

    assert sr == 8000
    assert audio.shape == (24000, 2)
    assert meta["duration_s"] == pytest.approx(3.0)
    assert res.assets[0].spec["holds"] == [{"beat": 1.0, "duration_s": 0.25}]


def test_fermata_dsl_rejects_malformed_hold_pairs():
    res = AudioForge().compile("""
asset bad_hold {
  kind: cue
  duration: 3s
  tempo: 120bpm
  fermata: 1s=0.25s
  layer lead : tone {
    freq: 440hz
    env: a=0.01s d=0.1s s=0.7 r=0.1s
  }
}
""")

    assert not res.ok
    assert "fermata beat must use beats" in res.diagnostics[0].message


def test_hold_schema_rejects_non_positive_or_unordered_events():
    spec = {
        "id": "bad_hold",
        "kind": "cue",
        "duration_s": 3.0,
        "bpm": 120.0,
        "holds": [{"beat": 2.0, "duration_s": 0.5},
                  {"beat": 1.0, "duration_s": 0.5}],
        "layers": [{"type": "tone", "freq_hz": 440.0,
                    "env": {"attack": 0.01, "decay": 0.1,
                            "sustain": 0.7, "release": 0.1}}],
    }

    with pytest.raises(SpecError, match="holds.*ascend"):
        validate_spec(spec)

    spec["holds"] = [{"beat": 1.0, "duration_s": 0.0}]
    with pytest.raises(SpecError, match="duration_s"):
        validate_spec(spec)


def test_perform_rubato_lowers_phrase_curve_to_dense_tempo_map():
    spec = _compile("""
asset rubato_phrase {
  kind: cue
  duration: 8s
  tempo: 90bpm
  perform: rubato=arch amount=0.16 segment=0.25b
  layer melody : notes {
    osc: sine
    env: a=0.01s d=0.1s s=0.8 r=0.1s
    notes: C4 @ 0b for 1b, E4 @ 1b for 1b, G4 @ 2b for 1b, C5 @ 3b for 2b
  }
  master { peak: -1db }
}
""")

    points = spec["tempo_map"]
    rubato = spec["intent"]["perform"]["rubato_compiled"]
    assert spec["bpm"] == 90.0
    assert spec["intent"]["perform"]["rubato"] == "arch"
    assert rubato["target"] == "tempo_map"
    assert rubato["max_segment_error_s"] <= 0.002
    assert rubato["point_count"] == len(points)
    assert len(points) > 10
    assert min(v for _b, v in points) < 90.0
    assert max(v for _b, v in points) > 90.0
    assert [b for b, _v in points] == sorted({b for b, _v in points})


def test_rubato_decompiles_as_macro_not_expanded_tempo_blob():
    spec = _compile("""
asset roundtrip_rubato {
  kind: cue
  duration: 8s
  tempo: 96bpm
  perform: rubato=arch amount=0.12 segment=0.5b expressivity=0.4
  layer melody : notes {
    osc: sine
    env: a=0.01s d=0.1s s=0.8 r=0.1s
    notes: C4 @ 0b for 1b, E4 @ 1b for 1b, G4 @ 2b for 1b, C5 @ 3b for 1b
  }
  master { peak: -1db }
}
""")

    dsl = spec_to_dsl(spec)

    assert "tempo: 96bpm" in dsl
    assert "perform: rubato=arch amount=0.12 segment=0.5b expressivity=0.4" in dsl
    assert "tempo:" not in "\n".join(
        line for line in dsl.splitlines() if "perform:" in line
    )
    again = _compile(dsl)
    assert again["intent"]["perform"]["rubato"] == "arch"
    assert math.isclose(
        again["intent"]["perform"]["rubato_compiled"]["max_segment_error_s"],
        spec["intent"]["perform"]["rubato_compiled"]["max_segment_error_s"],
    )
