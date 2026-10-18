"""Multi-oscillator layers: `osc: a + b` renders both voices and sums them.

The IR keeps `osc` as the first shape (back-compat) and adds `osc_mix` with
the full ordered list. Two or three distinct shapes are allowed; `morph` is
excluded (its scan machinery is single-voice by design); duplicates are
rejected. The mix is summed and scaled by 1/sqrt(N) to keep headroom, and it
is deterministic.
"""
import numpy as np

from audioforge import AudioForge
from audioforge.sequencer import TempoMap, render_note_track


def _track(osc, osc_mix=None):
    track = {
        "type": "notes",
        "osc": osc,
        "env": {"attack": 0.001, "decay": 0.01, "sustain": 1.0,
                "release": 0.01},
        "notes": [{"note": "A4", "start_beat": 0.0, "dur_beats": 2.0}],
    }
    if osc_mix:
        track["osc_mix"] = osc_mix
    return track


def _compile(src):
    return AudioForge().compile(src)


def test_compile_osc_mix_two_shapes():
    src = """
asset bell_pluck {
  kind: cue
  duration: 3s
  tempo: 120bpm
  layer keys : notes {
    osc: struck + pluck
    env: a=0.002s d=0.2s s=0.4 r=0.3s
    notes: A4 @ 0b for 2b
  }
}
"""
    result = _compile(src)
    assert result.ok, [d.message for d in result.diagnostics]
    layer = result.assets[0].spec["layers"][0]
    assert layer["osc"] == "struck"
    assert layer["osc_mix"] == ["struck", "pluck"]


def test_compile_osc_mix_rejects_duplicates():
    src = """
asset dup {
  kind: cue
  duration: 2s
  tempo: 120bpm
  layer l : notes {
    osc: pluck + pluck
    env: a=0.002s d=0.2s s=0.4 r=0.3s
    notes: A4 @ 0b for 1b
  }
}
"""
    result = _compile(src)
    assert not result.ok
    assert any("osc_mix" in d.message for d in result.diagnostics)


def test_compile_osc_mix_rejects_morph():
    src = """
asset nomorph {
  kind: cue
  duration: 2s
  tempo: 120bpm
  layer l : notes {
    osc: morph + pluck
    env: a=0.002s d=0.2s s=0.4 r=0.3s
    notes: A4 @ 0b for 1b
  }
}
"""
    result = _compile(src)
    assert not result.ok
    assert any("osc_mix" in d.message for d in result.diagnostics)


def test_render_osc_mix_sums_both_voices_deterministically():
    sr = 8000
    tm = TempoMap([[0.0, 120.0]])
    struck = render_note_track(_track("struck"), sr, sr, tm)
    pluck = render_note_track(_track("pluck"), sr, sr, tm)
    mixed = render_note_track(_track("struck", ["struck", "pluck"]),
                              sr, sr, tm)
    again = render_note_track(_track("struck", ["struck", "pluck"]),
                              sr, sr, tm)
    assert np.array_equal(mixed, again)
    assert mixed.size == struck.size == pluck.size
    expected = (struck + pluck) / np.sqrt(2.0)
    assert np.allclose(mixed, expected, atol=1e-9)
    assert not np.allclose(mixed, struck)
    assert not np.allclose(mixed, pluck)
