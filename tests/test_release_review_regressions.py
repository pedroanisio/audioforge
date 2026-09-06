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


def test_repeat_expansion_survives_inexact_beat_round_trips():
    """At 44 bpm, beat 4 -> seconds -> beat yields 3.9999999999999996; the boundary note must
    not leave a 4e-16-beat sliver in the next window (rejected by the minimum gate)."""
    spec = {"id": "r", "kind": "cue", "duration_s": 8 * 60 / 44, "sample_rate": 48000, "bpm": 44,
            "score": {"sections": [{"name": "v", "start_beat": 0, "dur_beats": 4}],
                      "repeats": [{"section": "v", "count": 2}]},
            "layers": [{"name": "m", "type": "notes", "osc": "sine",
                        "notes": [{"note": "C4", "start_beat": 0, "dur_beats": 4},
                                  {"note": "D4", "start_beat": 4, "dur_beats": 2}]}],
            "master": {"target_peak_dbfs": -1}}
    out = validate_spec(spec)
    notes = sorted((n["note"], n["start_beat"], n["dur_beats"]) for n in out["layers"][0]["notes"])
    assert notes == [("C4", 0.0, 4.0), ("C4", 4.0, 4.0), ("D4", 8.0, 2.0)]


def test_groove_slot_follows_the_notated_step_under_swing():
    """Groove accent for step i must not depend on the swing offset (round(1.5) == 2)."""
    from audioforge.determinism import rng_for
    from audioforge.sequencer import TempoMap, render_drum_track
    sr = 48000
    accent = [1.0] * 16
    accent[1] = 0.0
    groove = {"timing": [0.0] * 16, "accent": accent}
    track = {"name": "kit", "type": "drums", "voice": "hat", "pattern": "xxxx", "gain_db": 0}
    for swing in (0.0, 0.4, 0.5):
        signal = render_drum_track(track, sr, sr, TempoMap([[0, 120]]), swing, rng_for("t", "voice"),
                                   groove=groove, rng_factory=lambda path: rng_for("t", path))
        step1_on = int((0.25 + swing * 0.25) * 0.5 * sr)   # beat -> seconds at 120 bpm
        step2_on = int(0.5 * 0.5 * sr)
        assert np.max(np.abs(signal[step1_on:step2_on])) < 1e-6, f"step 1 sounded at swing={swing}"
        assert np.max(np.abs(signal[step2_on:step2_on + sr // 40])) > 1e-3


def test_analysis_treats_repeated_clip_layers_by_their_source_windows():
    """A pre-roll of authored silence before a repeated continuous layer is not dead air."""
    from audioforge.analysis import analyze_audio
    base = {"id": "tone", "kind": "cue", "duration_s": 8.0, "sample_rate": 8000, "bpm": 120,
            "layers": [{"name": "t", "type": "tone", "osc": "sine", "note": "A3", "start_s": 6.0,
                        "duration_s": 2.0, "gain_db": -12,
                        "env": {"attack": 0.01, "decay": 0.01, "sustain": 1.0, "release": 0.05}}],
            "master": {"target_peak_dbfs": -1, "fade_out_s": 0}}
    plain = validate_spec(copy.deepcopy(base))
    repeated = copy.deepcopy(base)
    repeated["score"] = {"sections": [{"name": "all", "start_beat": 0, "dur_beats": 16}],
                         "repeats": [{"section": "all", "count": 1}]}
    repeated = validate_spec(repeated)
    assert repeated["layers"][0].get("clip_map"), "count 1 must still take the clip path for this test"
    audio, sr, _ = render(plain)
    reports = [analyze_audio(audio, sr, context=ctx) for ctx in (plain, repeated)]
    assert reports[0]["unexpected_silence_share"] == reports[1]["unexpected_silence_share"] == 0.0
    assert all("dead_air" not in {r["code"] for r in rep["recommendations"]} for rep in reports)


def test_clip_source_holds_follow_the_spec_rules():
    """validate_clip once accepted zero-length holds that validate_spec rejects."""
    spec = {"id": "r", "kind": "cue", "duration_s": 2.0, "sample_rate": 48000, "bpm": 120,
            "score": {"sections": [{"name": "v", "start_beat": 0, "dur_beats": 4}],
                      "repeats": [{"section": "v", "count": 2}]},
            "layers": [{"name": "bed", "type": "noise", "color": "white", "gain_db": -12, "env": ENV}],
            "master": {"target_peak_dbfs": -1, "fade_out_s": 0}}
    expanded = validate_spec(spec)
    clip = expanded["layers"][0]
    clip["clip_source"]["holds"] = [{"beat": 1.0, "duration_s": 0.0}]
    with pytest.raises(SpecError, match=r"clip_source\.holds\[0\]\.duration_s"):
        validate_spec(expanded)


def test_every_technique_declares_fidelity():
    from audioforge.schema import TECHNIQUES
    assert all(entry.get("fidelity") in {"approximate", "control_transform"} for entry in TECHNIQUES.values())


def test_freq_to_midi_has_one_definition():
    from audioforge import performance, sampler, synth
    assert sampler.freq_to_midi is synth.freq_to_midi
    assert performance.freq_to_midi is synth.freq_to_midi
    assert synth.freq_to_midi(440.0) == 69.0


@pytest.mark.parametrize("layer", [
    {"type": "tone", "osc": "sine", "note": "A3"},
    {"type": "noise", "color": "white"},
    {"type": "notes", "osc": "sine", "notes": [{"note": "C4", "start_beat": 0, "dur_beats": 1}]},
    {"type": "drums", "voice": "hat", "pattern": "x.x.x.x."},
])
def test_layer_gain_is_applied_exactly_once_for_every_generated_layer_type(layer):
    """Gain ownership is split between _layer_signal and the track renderers; this pins
    the 'once' contract per type so the next type cannot double silently (review, altitude)."""
    def spec(gain):
        return {"id": "g", "kind": "cue", "duration_s": 1.0, "sample_rate": 48000, "bpm": 120,
                "layers": [{"name": "l", "gain_db": gain, "env": ENV, **copy.deepcopy(layer)}],
                "master": {"target_peak_dbfs": -1, "fade_out_s": 0}}
    before = render(spec(0), return_stems=True)[3]["l"]
    after = render(spec(-6), return_stems=True)[3]["l"]
    rms = lambda x: float(np.sqrt(np.mean(np.asarray(x) ** 2)))
    assert 20 * np.log10(rms(after) / rms(before)) == pytest.approx(-6, abs=0.03)


def test_frequency_pitched_tone_layer_round_trips_through_dsl():
    spec = validate_spec({"id": "t", "kind": "cue", "duration_s": 1.0, "sample_rate": 48000,
                          "layers": [{"name": "a", "type": "tone", "osc": "sine", "freq_hz": 440.0,
                                      "gain_db": -12, "env": ENV}],
                          "master": {"target_peak_dbfs": -1, "fade_out_s": 0}})
    result = AudioForge().compile(spec_to_dsl(spec))
    assert result.ok, [d.message for d in result.diagnostics]
    again = result.assets[0].spec
    assert again["layers"][0]["freq_hz"] == 440.0
    assert np.array_equal(render(spec)[0], render(again)[0])


def test_cutdowns_export_from_loop_safe_assets():
    """The loop seam gate belongs to the full loop render, not to spliced cutdowns."""
    from audioforge.render import render_cutdowns
    spec = {"id": "lp", "kind": "loop", "duration_s": 4.0, "sample_rate": 48000, "bpm": 120,
            "loop_safe": True,
            "layers": [{"name": "p", "type": "notes", "osc": "sine", "gain_db": -12,
                        "env": {"attack": 0.005, "decay": 0.01, "sustain": 0.8, "release": 0.05},
                        "notes": [{"note": n, "start_beat": b, "dur_beats": 1}
                                  for n, b in (("C4", 0), ("E4", 2), ("G4", 4), ("C5", 6))]}],
            "cutdowns": [{"length_s": 2, "segments": [[0.2, 1.2], [3.2, 4.0]]}],
            "master": {"target_peak_dbfs": -1, "fade_out_s": 0}}
    _, _, meta = render(copy.deepcopy(spec))
    assert meta["loop_boundary"]["passed"] is True
    cuts = list(render_cutdowns(copy.deepcopy(spec)))
    assert len(cuts) == 1 and cuts[0][0] == 2
    assert cuts[0][1].shape[0] == pytest.approx(1.8 * 48000, abs=48000 // 2)
