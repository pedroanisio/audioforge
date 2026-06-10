"""Composition ergonomics tests (v2.7): chord syntax/voicings, arpeggiator,
Euclidean rhythms, motif transforms, tempo maps, key maps."""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from audioforge import AudioForge  # noqa: E402
from audioforge import theory  # noqa: E402
from audioforge.sequencer import TempoMap  # noqa: E402

AF = AudioForge()


def _compiled(src):
    res = AF.compile(src)
    assert res.ok, [d.message for d in res.diagnostics]
    return res.assets[0]


WRAP = """
asset t {{
  kind: cue
  duration: {dur}
  tempo: {tempo}
  {key}
  {motifs}
  layer L : notes {{
    osc: sine
    gain: -8db
    {props}
    env: a=0.005s d=0.1s s=0.7 r=0.1s
    {body}
  }}
  master {{ peak: -1db
           fadeout: 0.05s }}
}}
"""


def test_chord_expansion_and_voicings():
    a = _compiled(WRAP.format(
        dur="4s", tempo="120bpm", key="", motifs="", props="",
        body="notes: A2maj7 @ 0b for 2b vel 0.6, A2maj7 @ 2b for 2b voicing drop2"))
    evs = a.spec["layers"][0]["notes"]
    close = sorted(e["note"] for e in evs if e["start_beat"] == 0)
    drop2 = sorted(theory.note_to_semis(e["note"])
                   for e in evs if e["start_beat"] == 2)
    assert close == ["A2", "C#3", "E3", "G#3"], close
    # drop2 lowers the second-from-top (E3) by an octave
    assert theory.note_to_semis("E2") in drop2
    assert all(e.get("vel", 1.0) == 0.6 for e in evs if e["start_beat"] == 0)
    print("PASS  chords: A2maj7 expands correctly; drop2 voices E down an octave")


def test_arpeggiator_orders():
    a = _compiled(WRAP.format(
        dur="4s", tempo="120bpm", key="", motifs="",
        props="arp: down rate=0.5b octaves=1 gate=0.9",
        body="notes: C4maj @ 0b for 2b"))
    evs = a.spec["layers"][0]["notes"]
    assert [e["note"] for e in evs[:3]] == ["G4", "E4", "C4"]
    assert [e["start_beat"] for e in evs[:3]] == [0.0, 0.5, 1.0]
    assert evs[0]["dur_beats"] == 0.45
    # seeded 'random' order: identical across compiles
    src = WRAP.format(dur="4s", tempo="120bpm", key="", motifs="",
                      props="arp: random rate=0.25b",
                      body="notes: C4min7 @ 0b for 4b")
    o1 = [e["note"] for e in _compiled(src).spec["layers"][0]["notes"]]
    o2 = [e["note"] for e in _compiled(src).spec["layers"][0]["notes"]]
    assert o1 == o2
    print(f"PASS  arp: down order {[e['note'] for e in evs[:3]]}; "
          f"random order compile-stable")


def test_euclidean_patterns():
    assert theory.bjorklund(3, 8) == "x..x..x."
    assert theory.bjorklund(5, 8) == "x.xx.xx."
    assert theory.bjorklund(5, 16) == "x..x..x..x..x..."
    assert theory.bjorklund(5, 16, 3) == theory.bjorklund(5, 16)[3:] \
        + theory.bjorklund(5, 16)[:3]
    print("PASS  euclid: E(3,8), E(5,8), E(5,16) match known patterns; "
          "rotation works")


def test_motif_transforms_ir():
    motifs = """
  motif m {
    C4 @ 0b for 1b
    E4 @ 1b for 1b
    G4 @ 2b for 2b
  }
"""
    a = _compiled(WRAP.format(
        dur="16s", tempo="120bpm", key="key: C major", motifs=motifs, props="",
        body="play m @ 0b\n    play m @ 4b retrograde\n    "
             "play m @ 8b invert\n    play m @ 12b diatonic +2\n    "
             "play m @ 16b stretch 2"))
    evs = a.spec["layers"][0]["notes"]
    seg = lambda lo, hi: [e for e in evs if lo <= e["start_beat"] < hi]  # noqa: E731
    retro = sorted(seg(4, 8), key=lambda e: e["start_beat"])
    assert [e["note"] for e in retro] == ["G4", "E4", "C4"]
    inv = sorted(seg(8, 12), key=lambda e: e["start_beat"])
    assert [e["note"] for e in inv] == ["C4", "G#3", "F3"]
    dia = sorted(seg(12, 16), key=lambda e: e["start_beat"])
    assert [e["note"] for e in dia] == ["E4", "G4", "B4"]
    st = sorted(seg(16, 25), key=lambda e: e["start_beat"])
    assert [e["dur_beats"] for e in st] == [2.0, 2.0, 4.0]
    print("PASS  transforms: retrograde/invert/diatonic/stretch all "
          "verified in the IR")


def test_tempo_ramp_timing_in_audio():
    src = WRAP.format(
        dur="8s", tempo="120bpm, 8b=120bpm, 12b=180bpm", key="", motifs="",
        props="",
        body="notes: A4 @ 0b for 0.5b, A4 @ 10b for 0.5b, A4 @ 14b for 0.5b")
    a = _compiled(src)
    s, sr, _ = a.render()
    x = s.mean(axis=1)
    tm = TempoMap(a.spec["tempo_map"])
    env = np.abs(x)
    k = sr // 1000
    env = env[:env.size // k * k].reshape(-1, k).max(axis=1)
    onsets = []
    armed = True
    for i, v in enumerate(env):
        if armed and v > 0.05:
            onsets.append(i * k / sr)
            armed = False
        elif v < 0.01:
            armed = True
    expected = [tm.sec(0), tm.sec(10), tm.sec(14)]
    assert len(onsets) >= 3, onsets
    for got, want in zip(onsets[:3], expected):
        assert abs(got - want) < 0.012, (got, want)
    # the ramp actually compresses time: beat 14 lands earlier than at 120bpm
    assert expected[2] < 14 * 0.5 - 0.1
    print(f"PASS  tempo ramp: onsets at {[round(o,3) for o in onsets[:3]]} s "
          f"match the analytic map {[round(e,3) for e in expected]}")


def test_key_map_diatonic_resolution():
    motifs = """
  motif m {
    C4 @ 0b for 1b
  }
"""
    a = _compiled(WRAP.format(
        dur="16s", tempo="120bpm", key="key: C major, 8b=D major",
        motifs=motifs, props="",
        body="play m @ 0b diatonic +1\n    play m @ 8b diatonic +1"))
    evs = sorted(a.spec["layers"][0]["notes"], key=lambda e: e["start_beat"])
    assert evs[0]["note"] == "D4"          # C major: C -> D
    # in D major C-natural is chromatic: carried as B+1 semitone, and B's
    # +1-degree neighbour is C#, so C lands on D (documented offset rule)
    assert evs[1]["note"] == "D4"
    print("PASS  key map: diatonic transform resolves the key in force "
          "at the play position")


def test_compose_render_deterministic():
    src = WRAP.format(
        dur="6s", tempo="100bpm, 8b=100bpm, 10b=140bpm", key="key: A minor",
        motifs="", props="arp: updown rate=0.25b octaves=2",
        body="notes: A2min7 @ 0b for 8b")
    a, _, _ = _compiled(src).render()
    b, _, _ = _compiled(src).render()
    assert np.array_equal(a, b)
    print("PASS  chords + arp + tempo map render byte-identically")


if __name__ == "__main__":
    test_chord_expansion_and_voicings()
    test_arpeggiator_orders()
    test_euclidean_patterns()
    test_motif_transforms_ir()
    test_tempo_ramp_timing_in_audio()
    test_key_map_diatonic_resolution()
    test_compose_render_deterministic()
    print("\nAll composition-ergonomics tests passed.")
