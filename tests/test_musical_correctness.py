"""Musical acceptance cases assert authored and audible meaning."""
from __future__ import annotations

import pytest

from audioforge import AudioForge
from audioforge.theory import note_to_semis


def compile_chord(notes: str, directives: str = "", key: str = "C major"):
    source = f"""asset harmony {{
      kind: cue
      duration: 4s
      tempo: 120bpm
      {f'key: {key}' if key else ''}
      voicing: richness=1 extensions=7 {directives}
      layer chords : notes {{
        osc: sine
        notes: {notes}
      }}
      master {{ peak: -1db }}
    }}"""
    result = AudioForge().compile(source)
    assert result.ok, [diagnostic.message for diagnostic in result.diagnostics]
    return result


@pytest.mark.parametrize("notes,expected", [
    ("C3 @ 0b for 2b, E3 @ 0b for 2b, G3 @ 0b for 2b, B3 @ 0b for 2b", {0, 4, 7, 11}),
    ("E3 @ 0b for 2b, G3 @ 0b for 2b, C4 @ 0b for 2b", {0, 4, 7, 11}),
    ("G3 @ 0b for 2b, C4 @ 0b for 2b, E4 @ 0b for 2b", {0, 4, 7, 11}),
    ("F3 @ 0b for 2b, G3 @ 0b for 2b, B3 @ 0b for 2b, D4 @ 0b for 2b", {2, 5, 7, 11}),
    ("F3 @ 0b for 2b, A3 @ 0b for 2b, D4 @ 0b for 2b", {0, 2, 5, 9}),
])
def test_chord_extensions_respect_root_quality_and_inversion(notes, expected):
    result = compile_chord(notes)
    events = result.assets[0].spec["layers"][0]["notes"]
    assert {note_to_semis(event["note"]) % 12 for event in events} == expected


def test_explicit_chord_quality_survives_expansion_and_inversion():
    result = compile_chord("C3maj7 @ 0b for 2b voicing inv2")
    events = result.assets[0].spec["layers"][0]["notes"]
    assert {note_to_semis(event["note"]) % 12 for event in events} == {0, 4, 7, 11}
    assert all(event["harmony"]["root_pc"] == 0 for event in events)
    assert all(event["harmony"]["quality"] == "maj7" for event in events)


def test_ambiguous_harmony_is_preserved_and_reported():
    # C6 and Am7 share a pitch collection; bass alone cannot settle intent.
    result = compile_chord(
        "C3 @ 0b for 2b, E3 @ 0b for 2b, G3 @ 0b for 2b, A3 @ 0b for 2b",
        key="")
    events = result.assets[0].spec["layers"][0]["notes"]
    assert {note_to_semis(event["note"]) % 12 for event in events} == {0, 4, 7, 9}
    assert any("ambiguous_harmony" in diagnostic.message for diagnostic in result.diagnostics)


def test_unknown_cluster_is_not_given_an_invented_root():
    result = compile_chord("C3 @ 0b for 2b, C#3 @ 0b for 2b, D3 @ 0b for 2b")
    assert len(result.assets[0].spec["layers"][0]["notes"]) == 3
    assert any("unrecognized_harmony" in diagnostic.message for diagnostic in result.diagnostics)


def test_extensions_follow_modulation_at_each_chord_onset():
    result = compile_chord("C3maj @ 0b for 1b, C3maj @ 4b for 1b",
                           key="C major, 4b=F major")
    events = result.assets[0].spec["layers"][0]["notes"]
    assert {note_to_semis(e["note"]) % 12 for e in events if e["start_beat"] == 0} == {0, 4, 7, 11}
    assert {note_to_semis(e["note"]) % 12 for e in events if e["start_beat"] == 4} == {0, 4, 7, 10}


def test_voice_leading_preserves_chord_tones_and_reduces_motion():
    result = compile_chord("C3maj @ 0b for 2b, F4maj @ 2b for 2b",
                           directives="voice_leading=on")
    events = result.assets[0].spec["layers"][0]["notes"]
    assert {event["start_beat"] for event in events} == {0, 2}
    first = sorted(note_to_semis(event["note"]) for event in events if event["start_beat"] == 0)
    second = sorted(note_to_semis(event["note"]) for event in events if event["start_beat"] == 2)
    assert {pitch % 12 for pitch in second} == {0, 4, 5, 9}
    assert max(abs(a - b) for a, b in zip(first, second)) <= 5


def test_phrase_analysis_does_not_fabricate_cadences_or_pitch_peaks():
    from audioforge.dsl import _analyze_layer_phrases

    layer = {"type": "notes", "notes": [
        {"note": pitch, "start_beat": beat, "dur_beats": 1}
        for beat, pitch in enumerate(["C5", "D4", "E4", "F#4"])]}
    phrase = _analyze_layer_phrases(layer)[0]
    assert "cadence_beat" not in phrase
    assert "peak_beat" not in phrase
    assert phrase["boundary_evidence"] == "activity_span"


def test_expressivity_preserves_polyphonic_gates_and_authored_slurs():
    from audioforge import AudioForge

    source = """asset phrase { kind: cue
      duration: 4s
      tempo: 120bpm
      perform: expressivity=0.8
      layer p : notes { osc: sine
        notes: C3maj @ 0b for 2b, F3maj @ 2b for 2b
      }
    }"""
    result = AudioForge().compile(source)
    assert result.ok, result.diagnostics
    notes = result.assets[0].spec["layers"][0]["notes"]
    assert all(note["dur_beats"] == 2 for note in notes)
    assert all("slur" not in note for note in notes)
    assert not any(fx["type"] == "comp" for fx in result.assets[0].spec.get("master", {}).get("fx", []))


def test_chord_humanization_keeps_simultaneous_onsets_coordinated():
    from audioforge.performance import schedule_notes
    from audioforge.determinism import rng_for
    from audioforge.sequencer import TempoMap

    layer = {"humanize": {"timing_s": .02, "vel": .1}, "notes": [
        {"note": pitch, "start_beat": 1, "dur_beats": 1}
        for pitch in ["C4", "E4", "G4"]]}
    schedule = schedule_notes(layer, 48000, 48000, TempoMap([[0, 120]]),
                              lambda path: rng_for("take", path))
    assert len({note["start"] for note in schedule}) == 1


def test_emotion_reports_production_scope_and_inactive_tags():
    from audioforge import AudioForge

    result = AudioForge().compile("""asset e { kind: cue
      duration: 1s
      tempo: 120bpm
      emotion: sadness=0.8 tension=0.5
      layer p : notes { osc: sine
        notes: C4 @ 0b for 1b
      }
    }""")
    assert result.ok, result.diagnostics
    messages = " ".join(d.message for d in result.diagnostics)
    assert "production" in messages
    assert "sadness" in messages and "metadata" in messages


def test_full_uint64_seed_survives_dsl_round_trip():
    from audioforge import AudioForge
    from audioforge.decompile import spec_to_dsl

    result = AudioForge().compile("""asset s { kind: cue
      duration: 1s
      tempo: 120bpm
      seed: 18446744073709551615
      layer p : notes { osc: sine
        notes: C4 @ 0b for 1b
      }
    }""")
    assert result.ok, result.diagnostics
    assert result.assets[0].spec["performance_seed"] == 2**64 - 1
    again = AudioForge().compile(spec_to_dsl(result.assets[0].spec))
    assert again.ok, again.diagnostics
    assert again.assets[0].spec["performance_seed"] == 2**64 - 1


def test_legato_requires_contiguous_monophonic_slurs():
    from audioforge.performance import legato_links, schedule_notes
    from audioforge.determinism import rng_for
    from audioforge.sequencer import TempoMap

    events = [{"note": "C4", "start_beat": 0, "dur_beats": 1, "slur": 1},
              {"note": "D4", "start_beat": 3, "dur_beats": 1, "slur": 1}]
    def links(notes):
        schedule = schedule_notes({"notes": notes}, 144000, 48000, TempoMap([[0, 120]]),
                                  lambda path: rng_for("take", path))
        return legato_links(schedule)
    assert links(events) == [(None, None), (None, None)]
    events[1]["start_beat"] = 1
    assert links(events) == [(None, 1), (0, None)]
    events.append({"note": "E4", "start_beat": 1, "dur_beats": 1, "slur": 1})
    assert links(events) == [(None, None)] * 3


def test_technique_approximation_survives_ir_and_strict_routing_rejects_it():
    from audioforge import AudioForge
    from audioforge.schema import SpecError

    source = """asset t { kind: cue
      duration: 1s
      tempo: 120bpm
      layer p : notes { osc: sine
        notes: C4 @ 0b for 1b tech harmonic(partial=3)
      }
    }"""
    result = AudioForge().compile(source)
    assert result.ok, result.diagnostics
    asset = result.assets[0]
    evidence = asset.spec["layers"][0]["notes"][0]["technique_render"]
    assert evidence["fidelity"] == "approximate"
    assert evidence["name"] == "harmonic"
    assert asset.plan()["plan"]["segments"][0]["decision"]["technique"] == evidence
    strict = AudioForge().compile(source.replace("duration: 1s", "duration: 1s\n routing: fallbacks=forbid"))
    assert strict.ok, strict.diagnostics
    with pytest.raises(SpecError, match="approximate.*harmonic"):
        strict.assets[0].render()


def test_analysis_observations_do_not_prescribe_missing_bass_or_stereo():
    import numpy as np
    from audioforge.analysis import analyze_audio

    sr = 8000
    signal = .05 * np.sin(2 * np.pi * 2000 * np.arange(sr) / sr)
    for context in (None, {"role": "solo", "stereo": "mono", "expect_bass": False}):
        report = analyze_audio(signal, sr, context=context)
        assert not {r["code"] for r in report["recommendations"]} & {"mono_image", "low_foundation_weak"}
        assert {r["code"] for r in report["observations"]} >= {"mono_image", "low_foundation_weak"}
    report = analyze_audio(signal, sr, context={"expect_bass": True, "stereo": "stereo"})
    assert {r["code"] for r in report["recommendations"]} >= {"mono_image", "low_foundation_weak"}


def test_analysis_distinguishes_authored_rests_from_missing_notes():
    import numpy as np
    from audioforge.analysis import analyze_audio

    sr = 8000
    audio = np.zeros(sr * 12)
    audio[:sr] = .1 * np.sin(2 * np.pi * 440 * np.arange(sr) / sr)
    context = {"bpm": 60, "duration_s": 12, "layers": [
        {"name": "solo", "type": "notes", "notes": [
            {"note": "A4", "start_beat": 0, "dur_beats": 1}]}]}
    rest = analyze_audio(audio, sr, context=context)
    assert "dead_air" not in {r["code"] for r in rest["recommendations"]}
    context["layers"][0]["notes"][0]["dur_beats"] = 12
    missing = analyze_audio(audio, sr, context=context)
    assert "dead_air" in {r["code"] for r in missing["recommendations"]}


def test_cadence_candidates_require_harmonic_and_metric_evidence():
    from audioforge import AudioForge
    source = '''asset cadence { kind: cue
      duration: 4s
      tempo: 120bpm
      key: C major
      meter: 4 4
      perform: expressivity=0.5
      layer harmony : notes { osc: sine
        notes: G37 @ 0b for 4b, C3maj @ 4b for 2b
      }
    }'''
    result = AudioForge().compile(source)
    assert result.ok, result.diagnostics
    candidates = result.assets[0].spec["intent"]["analysis"]["phrases"][0]["cadence_candidates"]
    assert candidates == [{"beat": 4.0, "type": "dominant_to_tonic", "status": "candidate",
                           "evidence": ["resolved_chord_roots", "declared_key", "local_downbeat"]}]
    offbeat = AudioForge().compile(source.replace('for 4b', 'for 3b').replace('@ 4b', '@ 3b'))
    assert offbeat.ok, offbeat.diagnostics
    assert not offbeat.assets[0].spec["intent"]["analysis"]["phrases"][0].get("cadence_candidates")


def test_distinct_parts_share_timing_motion_without_becoming_identical():
    import numpy as np
    from audioforge.performance import schedule_notes
    from audioforge.determinism import performance_hash, rng_for
    from audioforge.sequencer import TempoMap
    root = performance_hash({'performance_seed': 42})
    deviations = []
    for name in ('violin', 'cello'):
        track = {'name': name, '_performance_root': root,
                 'humanize': {'timing_s': .02, 'vel': 0},
                 'notes': [{'note': 'C4', 'start_beat': beat, 'dur_beats': .1} for beat in range(1, 97)]}
        schedule = schedule_notes(track, 100000, 1000, TempoMap([[0, 60]]),
                                  lambda path: rng_for(root, name, path))
        deviations.append([event['start_time_s']-event['start_beat'] for event in schedule])
    assert np.corrcoef(deviations)[0, 1] > .7
    assert not np.array_equal(*deviations)
