"""Audio semantics verified through rendered buffers, including real libraries."""
from __future__ import annotations

import copy
import wave

import numpy as np
import pytest

from audioforge import AudioForge
from audioforge import library
from audioforge.render import render
from audioforge.sampler import Region, render_region
from audioforge.sequencer import TempoMap, render_note_track

SR = 48000


def sine_spec():
    return {
        "id": "audio_correctness", "kind": "cue", "duration_s": 1.0,
        "sample_rate": SR, "bpm": 120,
        "layers": [{
            "name": "lead", "type": "notes", "osc": "sine", "gain_db": -12,
            "env": {"attack": 0.001, "decay": 0, "sustain": 1, "release": 0.2},
            "notes": [{"note": "C4", "start_beat": 0, "dur_beats": 1}],
        }],
        "master": {"target_peak_dbfs": -1, "fade_out_s": 0},
    }


def rms(signal):
    return float(np.sqrt(np.mean(np.asarray(signal) ** 2)))


@pytest.mark.parametrize("section", [None, {"size": 3, "spread": 0.5}])
def test_instrument_gain_is_applied_once_through_full_renderer(tmp_path, monkeypatch, section):
    root = tmp_path / "gain_library"
    root.mkdir()
    t = np.arange(SR) / SR
    with wave.open(str(root / "tone.wav"), "wb") as stream:
        stream.setparams((1, 2, SR, SR, "NONE", "not compressed"))
        stream.writeframes((0.25 * np.sin(2 * np.pi * 261.626 * t) * 32767)
                           .astype("<i2").tobytes())
    (root / "solo.sfz").write_text(
        "<region> sample=tone.wav lokey=59 hikey=61 pitch_keycenter=60 "
        "ampeg_attack=0.001 ampeg_release=0.2")
    manifest = library.generate_manifest(root)
    monkeypatch.setattr(library, "_LIBRARY_PATHS", [tmp_path])
    spec = sine_spec()
    spec["library"] = {"name": root.name, "manifest_sha256": manifest["manifest_sha256"]}
    layer = spec["layers"][0]
    layer.update(type="instrument", instrument="solo", gain_db=0)
    layer.pop("osc")
    if section:
        layer["section"] = section
    before = render(spec, return_stems=True)[3]["lead"]
    layer["gain_db"] = -6
    after = render(spec, return_stems=True)[3]["lead"]
    assert 20 * np.log10(rms(after) / rms(before)) == pytest.approx(-6, abs=0.03)


def test_note_release_starts_at_note_off_for_synth_and_sampler():
    track = sine_spec()["layers"][0]
    synthetic = render_note_track(track, SR, SR, TempoMap([[0, 120]]))
    t = np.arange(SR) / SR
    sampled = render_region(
        Region(pitch_keycenter=60, ampeg_attack=0.001, ampeg_release=0.2),
        np.sin(2 * np.pi * 261.626 * t), SR, 60, SR // 2, SR)
    for signal in (synthetic, sampled):
        assert rms(signal[int(0.51 * SR):int(0.55 * SR)]) > 0.02
        assert np.flatnonzero(abs(signal) > 1e-8)[-1] / SR == pytest.approx(0.7, abs=0.002)


def test_note_off_during_attack_still_has_a_release():
    track = sine_spec()["layers"][0]
    track["env"].update(attack=0.5, release=0.2)
    track["notes"][0]["dur_beats"] = 0.1
    signal = render_note_track(track, SR, SR, TempoMap([[0, 120]]))
    assert rms(signal[int(0.06 * SR):int(0.1 * SR)]) > 0.01
    assert np.flatnonzero(abs(signal) > 1e-8)[-1] / SR == pytest.approx(0.25, abs=0.002)


@pytest.mark.parametrize("source_sr,semitones,source_hz", [
    (48000, 12, 18000), (48000, 7, 20000), (96000, 0, 36000),
])
def test_sampler_suppresses_out_of_band_content(source_sr, semitones, source_hz):
    t = np.arange(source_sr) / source_sr
    signal = render_region(
        Region(pitch_keycenter=60, ampeg_attack=0, ampeg_release=0),
        np.sin(2 * np.pi * source_hz * t), source_sr, 60 + semitones, SR // 4, SR)
    assert rms(signal[512:-512]) < 0.001


def test_sampler_preserves_in_band_tone_during_transposition():
    t = np.arange(SR) / SR
    signal = render_region(
        Region(pitch_keycenter=60, ampeg_attack=0, ampeg_release=0),
        np.sin(2 * np.pi * 2000 * t), SR, 72, SR // 4, SR)
    assert rms(signal[512:-512]) == pytest.approx(2 ** -0.5, abs=0.002)
    spectrum = abs(np.fft.rfft(signal * np.hanning(signal.size)))
    assert np.fft.rfftfreq(signal.size, 1 / SR)[np.argmax(spectrum)] == 4000


def test_default_mastering_preserves_absolute_level_below_ceiling():
    spec = sine_spec()
    before = render(spec)[0]
    quieter = copy.deepcopy(spec)
    quieter["layers"][0]["gain_db"] -= 20
    after = render(quieter)[0]
    assert 20 * np.log10(rms(after) / rms(before)) == pytest.approx(-20, abs=1e-8)


def test_peak_normalization_requires_an_explicit_request():
    spec = sine_spec()
    spec["master"]["normalization"] = "peak"
    signal = render(spec)[0]
    assert 20 * np.log10(np.max(abs(signal))) == pytest.approx(-1, abs=0.02)


def test_master_normalization_dsl_roundtrip_and_validation():
    source = """asset mastering {
      kind: cue
      duration: 1s
      tempo: 120bpm
      layer a : notes { osc: sine
        notes: C4 @ 0b for 1b }
      master { normalize: peak
        peak: -3db }
    }"""
    result = AudioForge().compile(source)
    assert result.ok
    assert result.assets[0].spec["master"]["normalization"] == "peak"
    from audioforge.decompile import spec_to_dsl
    rebuilt = AudioForge().compile(spec_to_dsl(result.assets[0].spec))
    assert rebuilt.ok
    assert rebuilt.assets[0].spec["master"]["normalization"] == "peak"
    invalid = AudioForge().compile(source.replace("normalize: peak", "normalize: mysterious"))
    assert not invalid.ok


def noise_spec():
    spec = sine_spec()
    spec["layers"].append({
        "name": "air", "type": "noise", "color": "white", "gain_db": -18,
        "env": {"attack": 0.01, "decay": 0.01, "sustain": 0.5, "release": 0.05},
    })
    return spec


@pytest.mark.parametrize("edit", ["gain", "pan", "metadata", "reorder"])
def test_mix_edits_preserve_unrelated_performance(edit):
    spec = noise_spec()
    before = render(spec, return_stems=True)[3]["air"]
    changed = copy.deepcopy(spec)
    if edit == "gain":
        changed["layers"][0]["gain_db"] -= 3
    elif edit == "pan":
        changed["layers"][0]["pan"] = 0.7
    elif edit == "metadata":
        changed.update(id="renamed", markers=[{"name": "edit", "time_s": 0.5}])
    else:
        changed["layers"].reverse()
    after = render(changed, return_stems=True)[3]["air"]
    assert np.array_equal(before, after)


def test_explicit_performance_seed_changes_take_reproducibly():
    spec = noise_spec()
    before = render(spec)[0]
    spec["performance_seed"] = 1234
    after = render(spec)[0]
    assert not np.array_equal(before, after)
    assert np.array_equal(after, render(spec)[0])


def test_inserting_an_earlier_note_preserves_existing_note_performance():
    spec = sine_spec()
    spec["duration_s"] = 3
    layer = spec["layers"][0]
    layer["osc"] = "pluck"
    layer["humanize"] = {"timing_s": 0.01, "vel": 0.1}
    layer["notes"][0]["start_beat"] = 4
    before = render(spec, return_stems=True)[3]["lead"]
    layer["notes"].insert(0, {"note": "G4", "start_beat": 0, "dur_beats": 1})
    after = render(spec, return_stems=True)[3]["lead"]
    assert np.array_equal(before[SR:], after[SR:])


def test_loop_safe_rejects_a_note_release_truncated_at_the_boundary():
    from audioforge.schema import SpecError
    spec = sine_spec()
    spec["loop_safe"] = True
    spec["layers"][0]["notes"][0]["dur_beats"] = 2
    with pytest.raises(SpecError, match="loop.*tail"):
        render(spec)


def test_loop_safe_reports_measured_boundaries_when_notes_and_tails_fit():
    spec = sine_spec()
    spec["loop_safe"] = True
    _, _, meta = render(spec)
    assert meta["loop_boundary"]["passed"] is True
    assert "jump_dbfs" in meta["loop_boundary"]


def test_normalization_ceiling_includes_intersample_peaks_and_fades():
    from scipy.signal import resample_poly
    spec = sine_spec()
    spec["layers"][0]["notes"][0] = {"freq_hz": 11025, "start_beat": 0, "dur_beats": 1.5}
    spec["master"].update(normalization="peak", fade_in_s=.2, fade_out_s=.3)
    audio = render(spec)[0]
    peak = np.max(np.abs(resample_poly(audio, 4, 1, axis=0)))
    assert 20 * np.log10(peak) <= -1 + .02


def test_variable_rate_sampler_rejects_aliases_during_glide():
    source = np.sin(2 * np.pi * 19000 * np.arange(SR) / SR)
    audio = render_region(Region(ampeg_attack=0, ampeg_release=0), source, SR, 72,
                          SR//4, SR, ramp_from_midi=69, ramp_s=.25)
    assert rms(audio[1024:-1024]) < .002


def test_sustain_loop_exits_into_recorded_tail_after_note_off():
    source = np.ones(SR//2)
    source[int(.2*SR):] = 0
    region = Region(ampeg_attack=0, ampeg_release=.3,
                    loop_mode="loop_sustain", loop_start=int(.1*SR), loop_end=int(.2*SR))
    sustain = render_region(region, source, SR, 60, int(.35*SR), SR)
    region.loop_mode = "loop_continuous"
    continuous = render_region(region, source, SR, 60, int(.35*SR), SR)
    assert rms(sustain[int(.5*SR):]) < 1e-6
    assert rms(continuous[int(.5*SR):]) > .04


def test_loudness_target_does_not_skip_peak_safety_when_already_met():
    from audioforge.dynamics import master_loudness, _true_peak_per_sample
    from audioforge.loudness import integrated_lufs
    signal = np.full((SR, 2), .01)
    signal[SR//2] = 1.5
    target = integrated_lufs(signal, SR)
    audio, report = master_loudness(signal, SR, target, -1)
    assert _true_peak_per_sample(audio).max() <= 10**(-1/20) + 1e-8
    assert report["limiter"]["limited"]


def test_loop_check_includes_the_delivered_fade_envelope():
    from audioforge.render import _finish
    from audioforge.schema import SpecError
    signal = .25 * np.cos(2 * np.pi * 100 * np.arange(SR) / SR)
    spec = sine_spec()
    spec.update(loop_safe=True, layers=[])
    with pytest.raises(SpecError, match="loop.*seam"):
        _finish(signal.copy(), signal.copy(), SR, {"fade_out_s": .1},
                spec, "identity", {}, False)


def test_render_ready_validation_reports_loop_failures_across_agent_and_sdk():
    from audioforge.agent_tools import run_tool
    spec = sine_spec()
    spec['loop_safe'] = True
    spec['layers'][0]['notes'][0]['dur_beats'] = 2
    assert any(d.severity == 'error' and 'loop' in d.message
               for d in AudioForge().load_spec(spec).validate())
    response = run_tool('validate', {'spec': spec})
    assert not response['ok']
    assert any('loop' in d['message'] for d in response['diagnostics'])
