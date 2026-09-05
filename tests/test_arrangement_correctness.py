"""Executable arrangement acceptance at the public compiler/render boundary."""
import copy

import numpy as np
import pytest

from audioforge import AudioForge
from audioforge.decompile import spec_to_dsl
from audioforge.sequencer import TempoMap

SOURCE = """asset repeat_me { kind: cue
  duration: 2s
  tempo: 120bpm
  form: verse 0b for 2b, ending 2b for 2b
  repeat: verse x2
  layer melody : notes { osc: sine
    gain: -15db
    env: a=0.001s d=0s s=1 r=0.1s
    notes: C4 @ 0b for 0.5b, D4 @ 2b for 0.5b
  }
  master { peak: -1db
    fadeout: 0s
  }
}"""


def compile_spec(source=SOURCE):
    result = AudioForge().compile(source)
    assert result.ok, result.diagnostics
    return result.assets[0].spec


def test_repeat_expands_notes_duration_and_continuation_in_ir_and_audio():
    spec = compile_spec()
    assert spec["duration_s"] == pytest.approx(3)
    assert [e["start_beat"] for e in spec["layers"][0]["notes"]] == [0, 2, 4]
    audio, sr, meta = AudioForge().load_spec(spec).render()
    assert audio.shape[0] == 3 * sr
    for second in [0, 1, 2]:
        assert np.sqrt(np.mean(audio[int((second + .05) * sr):int((second + .2) * sr)]**2)) > .01
    assert meta["duration_s"] == 3
    again = compile_spec(spec_to_dsl(spec))
    assert np.array_equal(AudioForge().load_spec(again).render()[0], audio)


def test_repeat_replays_tempo_automation_and_markers_without_stale_coordinates():
    from audioforge.schema import validate_spec
    spec = compile_spec(SOURCE.replace('  repeat: verse x2\n', ''))
    spec["tempo_map"] = [[0, 90], [2, 150], [4, 90]]
    tm = TempoMap(spec["tempo_map"])
    spec["duration_s"] = tm.sec(4)
    spec["score"]["repeats"] = [{"section": "verse", "count": 2}]
    spec["markers"] = [{"name": "start", "time_s": 0}, {"name": "end", "time_s": tm.sec(2)}]
    spec["layers"][0]["automation"] = [{"target": "gain_db", "points": [[0, -8], [tm.sec(2), 0], [tm.sec(4), -4]]}]
    resolved = validate_spec(copy.deepcopy(spec))
    assert resolved["duration_s"] == pytest.approx(tm.sec(4) + tm.sec(2))
    out_tm = TempoMap(resolved["tempo_map"])
    assert out_tm.sec(2) == pytest.approx(tm.sec(2))
    assert out_tm.sec(4) - out_tm.sec(2) == pytest.approx(tm.sec(2))
    assert out_tm.sec(6) == pytest.approx(resolved["duration_s"])
    assert [m["time_s"] for m in resolved["markers"]] == pytest.approx([0, tm.sec(2), 2 * tm.sec(2)])
    points = resolved["layers"][0]["automation"][0]["points"]
    assert any(t == pytest.approx(tm.sec(2)) and v == -8 for t, v in points)
    assert points[-1][0] == pytest.approx(resolved["duration_s"])


def test_repeat_rejects_unknown_sections_and_fractional_counts():
    for directive in ('missing x2', 'verse x0', 'verse x2.5'):
        result = AudioForge().compile(SOURCE.replace('verse x2', directive))
        assert not result.ok


def test_meter_and_pickup_define_groove_bar_phase():
    from audioforge.performance import groove_slot
    score = {"meter": {"beats": 3, "unit": 4}, "pickup_beats": 1,
             "polymeter": {"cross": {"beats": 5, "unit": 8}}}
    assert groove_slot(1, "main", score, 16) == 0
    assert groove_slot(4, "main", score, 16) == 0
    assert groove_slot(3.5, "cross", score, 16) == 0
    assert groove_slot(3.5, "main", score, 16) == 10


@pytest.mark.parametrize('kind,properties', [
    ('noise', 'color: pink'), ('tone', 'osc: sine\n note: A3'),
    ('drums', 'voice: hat\n pattern: x...x...'),
])
def test_repeat_dry_generators_before_effects_and_survives_decompilation(kind, properties):
    source = f'''asset clips {{ kind: cue
      duration: 2s
      tempo: 120bpm
      form: verse 0b for 2b
      repeat: verse x2
      layer bed : {kind} {{ {properties}
        gain: -18db
        env: a=0.01s d=0s s=1 r=0.1s
        fx: delay(time=0.1s, feedback=0.3, mix=0.2)
      }}
      master {{ peak: -1db
        fadeout: 0s
      }}
    }}'''
    spec = compile_spec(source)
    audio, sr, _ = AudioForge().load_spec(spec).render()
    assert audio.shape[0] == 3 * sr
    again = compile_spec(spec_to_dsl(spec))
    assert np.array_equal(AudioForge().load_spec(again).render()[0], audio)


def test_repeat_with_smart_dynamics_and_rubato_remains_renderable():
    spec = compile_spec(SOURCE.replace('tempo: 120bpm', 'tempo: 120bpm\n  perform: expressivity=0.6 rubato=arch amount=0.05'))
    audio = AudioForge().load_spec(spec).render()[0]
    assert np.isfinite(audio).all() and np.max(abs(audio)) > .01
    again = compile_spec(spec_to_dsl(spec))
    assert np.allclose(AudioForge().load_spec(again).render()[0], audio, atol=1e-10, rtol=0)


def test_repeat_preserves_tempo_holds_inside_sections():
    source = SOURCE.replace('duration: 2s', 'duration: 2.2s').replace('tempo: 120bpm', 'tempo: 120bpm\n fermata: 1b=0.2s')
    spec = compile_spec(source)
    assert spec["duration_s"] == pytest.approx(3.4)
    assert spec["holds"] == [{"beat": 1., "duration_s": .2}, {"beat": 3., "duration_s": .2}]
    audio, sr, _ = AudioForge().load_spec(spec).render()
    assert audio.shape[0] == int(spec["duration_s"] * sr)


def test_clip_contract_rejects_invalid_window_bounds():
    from audioforge.schema import SpecError
    spec = compile_spec(SOURCE.replace('  repeat: verse x2\n', ''))
    spec["layers"][0]["clip_map"] = [[-1, 10000, 0]]
    spec["layers"][0]["clip_source"] = {"duration_s": 10000}
    with pytest.raises(SpecError, match="clip"):
        AudioForge().load_spec(spec)


def test_repeat_preserves_shaped_automation_with_layer_offset_and_roundtrip():
    from audioforge.schema import validate_spec
    from audioforge.render import _automation_envs
    from audioforge.curves import evaluate_curve
    spec = compile_spec(SOURCE.replace('  repeat: verse x2\n', ''))
    layer = spec['layers'][0]
    layer['start_s'] = .25
    curve = {'target': 'gain_db', 'points': [[0, -30], [2, 0, 'pow:2']]}
    layer['automation'] = [curve]
    spec['score']['repeats'] = [{'section': 'verse', 'count': 2}]
    resolved = validate_spec(spec)
    env = _automation_envs(resolved['layers'][0], 3000, 1000, TempoMap([[0, 120]]))[0]
    for dest, source in [(0.5, .5), (1.5, .5), (2.5, 1.5)]:
        expected = 10**(evaluate_curve(curve, [source-.25])[0]/20)
        assert env[int(dest*1000)] == pytest.approx(expected)
    rebuilt = compile_spec(spec_to_dsl(resolved))
    assert rebuilt['layers'][0]['automation'] == resolved['layers'][0]['automation']
    assert np.array_equal(AudioForge().load_spec(rebuilt).render()[0],
                          AudioForge().load_spec(resolved).render()[0])


def test_cropped_note_curve_retains_its_original_shape():
    from audioforge.schema import validate_spec
    from audioforge.curves import evaluate_curve
    spec = compile_spec(SOURCE.replace('  repeat: verse x2\n', ''))
    spec['layers'][0]['notes'] = [{'note': 'C4', 'start_beat': 0, 'dur_beats': 4,
         'curves': [{'target': 'pitch_cents', 'time_basis': 'note_beats',
                     'points': [[0, 0], [4, 100, 'pow:2']]}]}]
    spec['score']['sections'] = [{'name': 'middle', 'start_beat': 1, 'dur_beats': 1}]
    spec['score']['repeats'] = [{'section': 'middle', 'count': 2}]
    out = validate_spec(spec)
    event = next(e for e in out['layers'][0]['notes'] if e['start_beat'] == 2)
    assert evaluate_curve(event['curves'][0], [.5])[0] == pytest.approx(100*(1.5/4)**2)
    rebuilt = compile_spec(spec_to_dsl(out))
    assert rebuilt['layers'][0]['notes'] == out['layers'][0]['notes']


@pytest.mark.parametrize('hold', [.2, .5])
def test_repeat_preserves_a_terminal_hold_even_when_the_source_ends_inside_it(hold):
    source = SOURCE.replace('duration: 2s', 'duration: 2.2s').replace(
        'tempo: 120bpm', f'tempo: 120bpm\n fermata: 4b={hold}s')
    spec = compile_spec(source)
    assert spec['duration_s'] == pytest.approx(3.2)
    assert spec['holds'] == [{'beat': 6., 'duration_s': pytest.approx(.2)}]


def test_repeating_an_expanded_shaped_curve_composes_its_existing_clock():
    from audioforge.schema import validate_spec
    from audioforge.curves import evaluate_curve
    spec = compile_spec(SOURCE.replace('  repeat: verse x2\n', ''))
    spec['layers'][0]['automation'] = [{'target': 'gain_db',
        'points': [[0, -30], [2, 0, 'pow:2']]}]
    spec['score']['repeats'] = [{'section': 'verse', 'count': 2}]
    first = validate_spec(spec)
    original_curve = copy.deepcopy(first['layers'][0]['automation'][0])
    first['score']['sections'] = [{'name': 'whole', 'start_beat': 0, 'dur_beats': 6}]
    first['score']['repeats'] = [{'section': 'whole', 'count': 2}]
    second = validate_spec(first)
    curve = second['layers'][0]['automation'][0]
    assert evaluate_curve(curve, [3.5, 4.5, 5.5]).tolist() == pytest.approx(
        evaluate_curve(original_curve, [.5, 1.5, 2.5]).tolist())


def test_repeat_validates_generated_note_gates_before_claiming_success():
    source = SOURCE.replace('C4 @ 0b for 0.5b', 'C4 @ 1.9995b for 0.001b')
    result = AudioForge().compile(source)
    assert not result.ok
    assert any('dur_beats' in d.message for d in result.diagnostics)


def test_expanded_loop_and_form_repeats_keep_event_ids_unique():
    from audioforge.schema import validate_spec
    spec = compile_spec(SOURCE.replace('  repeat: verse x2\n', ''))
    layer = spec['layers'][0]
    layer['notes'] = [{**layer['notes'][0], 'id': 'one'}]
    layer['loop_beats'] = 1
    spec['score']['repeats'] = [{'section': 'verse', 'count': 2}]
    expanded = validate_spec(spec)
    ids = [e['id'] for e in expanded['layers'][0]['notes']]
    assert len(ids) == len(set(ids)) == 6
    assert compile_spec(spec_to_dsl(expanded))['layers'][0]['notes'] == expanded['layers'][0]['notes']
