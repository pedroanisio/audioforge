"""Dynamics & articulation (P2) tests. The mini-library's velocity layers
are spectrally disjoint (pure sine vs strong harmonics), so crossfade
behavior is directly measurable: H3/H1 tracks which layer is sounding."""
import json
import sys
import tempfile
import numpy as np  # noqa: F811
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from audioforge import AudioForge  # noqa: E402
from audioforge import library as libmod  # noqa: E402
from audioforge.determinism import rng_for  # noqa: E402
from audioforge.sampler import render_instrument_track  # noqa: E402
from audioforge.sequencer import TempoMap, render_note_track  # noqa: E402
from test_sampler import build_library, _partial, _f0  # noqa: E402

ENG_SR = 48000
AF = AudioForge()
C4 = 261.626


def build_p2_library(root: Path) -> str:
    """The P1 mini-library plus a real sampled 'spiccato' articulation, so
    both sampled-articulation selection and fallback synthesis are tested."""
    build_library(root)
    # give the soft C4 a recorded-style attack transient (30 ms scrape):
    # the legato attack-skip mechanism needs something real to skip
    rng = np.random.default_rng(11)
    sr0 = 44100
    t = np.arange(int(2.0 * sr0)) / sr0
    body = np.sin(2 * np.pi * 261.626 * t) * np.exp(-t * 0.2) * 0.8
    burst_n = int(0.03 * sr0)
    body[:burst_n] += rng.standard_normal(burst_n) * \
        np.linspace(1.0, 0.0, burst_n) * 0.5
    body = np.clip(body, -0.95, 0.95)   # body level matches the original
                                        # soft layer; no int16 wrap
    import wave as _w
    with _w.open(str(root / "wavs/c4_soft.wav"), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr0)
        w.writeframes((body * 30000).astype("<i2").tobytes())
    # a looped sustain map: held notes outlive the 2 s recordings, and the
    # time-varying crossfade is exercised through loop extension
    (root / "testviolin_sus.sfz").write_text("""
<global> ampeg_attack=0.01 ampeg_release=0.12
        loop_mode=loop_continuous loop_start=8820 loop_end=79380
        loop_crossfade=0.05
<group> lokey=55 hikey=63 pitch_keycenter=60
<region> sample=wavs/c4_soft.wav lovel=1 hivel=63
<region> sample=wavs/c4_loud_rr1.wav lovel=64 hivel=127 seq_length=2 seq_position=1
<region> sample=wavs/c4_loud_rr2.wav lovel=64 hivel=127 seq_length=2 seq_position=2
""")
    (root / "testviolin_spic.sfz").write_text("""
<global> ampeg_attack=0.001 ampeg_release=0.05
<group> lokey=55 hikey=63 pitch_keycenter=60
<region> sample=wavs/c4_soft.wav lovel=1 hivel=127
""")
    m = libmod.generate_manifest(
        root, name="minilib2", version="1.0.0", license_str="CC0-1.0",
        instruments={"testviolin": {
            "sfz": "testviolin_sus.sfz",
            "articulations": {"sustain": "testviolin_sus.sfz",
                              "spiccato": "testviolin_spic.sfz"}}})
    return m["manifest_sha256"]


def _track(notes, dynamic=None, art=None, gain_db=0.0):
    t = {"name": "v", "type": "instrument", "instrument": "testviolin",
         "notes": notes, "gain_db": gain_db}
    if dynamic:
        t["dynamic"] = dynamic
    if art:
        t["articulation"] = art
    return t


def _render_track(lib, track, dur_s=8.0, bpm=120):
    tm = TempoMap([[0.0, bpm]])
    n = int(dur_s * ENG_SR)
    report = {}
    sig = render_instrument_track(
        track, n, ENG_SR, tm,
        lambda sub: rng_for("t", "dyn", sub), lib, report=report)
    return sig, report


def test_dynamic_marks_compile():
    res = AF.compile("""
asset m { kind: cue
  duration: 4s
  tempo: 120bpm
  key: C major
  layer v : notes { osc: sine
    dynamic: 0b=ppp, 2b=mf, 4b=0.66
    notes: C4 @ 0b for 4b }
  master { peak: -1db }
}""")
    assert res.ok
    assert res.assets[0].spec["layers"][0]["dynamic"] == \
        [[0.0, 0.10], [2.0, 0.60], [4.0, 0.66]]
    print("PASS  marks: ppp/mf and raw values compile to the documented "
          "0..1 points, explicit in IR")


def test_static_crossfade(lib):
    h31 = {}
    for v in (0.15, 0.5, 0.95):
        sig, _ = _render_track(
            lib, _track([{"note": "C4", "start_beat": 0.0,
                          "dur_beats": 8.0}], dynamic=[[0.0, v]]), 5.0)
        seg = sig[ENG_SR // 2:ENG_SR * 2]
        h31[v] = _partial(seg, C4 * 3) / _partial(seg, C4)
    assert h31[0.15] < 0.05, h31
    assert h31[0.95] > 0.3, h31
    assert h31[0.15] * 3 < h31[0.5] < h31[0.95] * 0.9, h31
    print(f"PASS  crossfade (static): H3/H1 {h31[0.15]:.3f} at pp, "
          f"{h31[0.5]:.2f} blended at mid, {h31[0.95]:.2f} at ff")


def test_time_varying_crossfade(lib):
    """The leaning-in test: ONE held note under a pp->fff hairpin must move
    from the soft layer's spectrum to the loud layer's."""
    sig, _ = _render_track(
        lib, _track([{"note": "C4", "start_beat": 0.0, "dur_beats": 14.0}],
                    dynamic=[[0.0, 0.05], [14.0, 1.0]]), 7.0)
    early = sig[int(0.3 * ENG_SR):int(1.3 * ENG_SR)]
    late = sig[int(5.5 * ENG_SR):int(6.5 * ENG_SR)]
    r_e = _partial(early, C4 * 3) / _partial(early, C4)
    r_l = _partial(late, C4 * 3) / _partial(late, C4)
    assert r_e < 0.05 and r_l > 0.3, (r_e, r_l)
    sig2, _ = _render_track(
        lib, _track([{"note": "C4", "start_beat": 0.0, "dur_beats": 14.0}],
                    dynamic=[[0.0, 0.05], [14.0, 1.0]]), 7.0)
    assert np.array_equal(sig, sig2)
    print(f"PASS  crossfade (time-varying): one held note under a hairpin "
          f"moves H3/H1 {r_e:.3f} -> {r_l:.2f}; byte-stable")


def test_dynamic_gain_term(lib):
    rms = {}
    for v in (0.1, 1.0):
        sig, _ = _render_track(
            lib, _track([{"note": "C4", "start_beat": 0.0,
                          "dur_beats": 6.0}], dynamic=[[0.0, v]]), 4.0)
        rms[v] = np.sqrt(np.mean(sig[ENG_SR // 2:ENG_SR * 3] ** 2))
    db = 20 * np.log10(rms[1.0] / rms[0.1])
    assert 4.0 < db < 16.0, db   # -9 dB term + recorded-layer loudness
    print(f"PASS  gain term: pp vs fff level difference {db:.1f} dB — "
          f"present but timbre carries the dynamics")


def test_synth_notes_dynamic():
    tm = TempoMap([[0.0, 120.0]])
    track = {"name": "s", "type": "notes", "osc": "saw",
             "dynamic": [[0.0, 0.1], [8.0, 1.0]],
             "env": {"attack": 0.01, "decay": 0.1, "sustain": 0.8,
                     "release": 0.1},
             "notes": [{"note": "A3", "start_beat": 0.0, "dur_beats": 1.5},
                       {"note": "A3", "start_beat": 6.5, "dur_beats": 1.5}]}
    n = int(4.5 * ENG_SR)
    sig = render_note_track(track, n, ENG_SR, tm,
                            rng_factory=lambda s: rng_for("t", "sd", s))

    def centroid(x):
        s = np.abs(np.fft.rfft(x * np.hanning(x.size))) ** 2
        f = np.fft.rfftfreq(x.size, 1 / ENG_SR)
        return (s * f).sum() / s.sum()
    early = sig[int(0.1 * ENG_SR):int(0.7 * ENG_SR)]
    late = sig[int(3.35 * ENG_SR):int(3.95 * ENG_SR)]
    assert centroid(late) > 1.6 * centroid(early), \
        (centroid(early), centroid(late))
    print(f"PASS  synth dynamics: same saw note at pp vs ff centroid "
          f"{centroid(early):.0f} -> {centroid(late):.0f} Hz "
          f"(curve-driven brightness)")


def test_articulation_fallbacks_and_sampled(lib):
    # sampled articulation -> no fallback recorded
    _, rep = _render_track(lib, _track(
        [{"note": "C4", "start_beat": 0.0, "dur_beats": 1.0}],
        art="spiccato"), 2.0)
    assert "articulation_fallbacks" not in rep
    # unsampled -> documented fallback, recorded
    sig, rep = _render_track(lib, _track(
        [{"note": "C4", "start_beat": 0.0, "dur_beats": 4.0,
          "art": "staccato"}]), 4.0)
    fb = rep["articulation_fallbacks"]["v/testviolin"]["staccato"]
    assert "0.18 s clamp" in fb
    # the clamp is audible: note dies long before its written duration
    tail = np.sqrt(np.mean(sig[ENG_SR:2 * ENG_SR] ** 2))
    head = np.sqrt(np.mean(sig[:ENG_SR // 3] ** 2))
    assert tail < 0.05 * head
    print("PASS  articulations: sampled spiccato selects silently; "
          "staccato falls back with manifest record and a real clamp")


def test_tremolo_retrigger(lib):
    sig, rep = _render_track(lib, _track(
        [{"note": "C4", "start_beat": 0.0, "dur_beats": 4.0,
          "art": "tremolo"}]), 3.0)
    assert "tremolo" in rep["articulation_fallbacks"]["v/testviolin"]
    env = np.abs(sig[:2 * ENG_SR]).reshape(-1, ENG_SR // 100).mean(axis=1)
    onsets = int(np.sum((env[1:-1] > env[:-2]) & (env[1:-1] > env[2:])
                        & (env[1:-1] > 0.15 * env.max())))
    assert 12 <= onsets <= 40, onsets
    sig2, _ = _render_track(lib, _track(
        [{"note": "C4", "start_beat": 0.0, "dur_beats": 4.0,
          "art": "tremolo"}]), 3.0)
    assert np.array_equal(sig, sig2)
    print(f"PASS  tremolo fallback: {onsets} seeded re-triggers over 2 s, "
          f"byte-stable")


def test_trill_key_aware():
    res = AF.compile("""
asset tr { kind: cue
  duration: 4s
  tempo: 84bpm
  key: A minor
  layer v : notes { osc: sine
    notes: B4 @ 0b for 1b art trill, E4 @ 2b for 1b art trill }
  master { peak: -1db }
}""")
    assert res.ok
    notes = res.assets[0].spec["layers"][0]["notes"]
    names = [e["note"] for e in notes]
    assert names[:2] == ["B4", "C5"]        # half step in A natural minor
    assert "F4" in names and "F#4" not in names   # E4 trills with F4
    print("PASS  trill: compile-time expansion picks key-aware neighbors "
          "(B4~C5, E4~F4 in A minor)")


if __name__ == "__main__":
    test_dynamic_marks_compile()
    with tempfile.TemporaryDirectory() as td:
        root = Path(td) / "minilib2"
        pin = build_p2_library(root)
        lib = libmod.load_library(f"minilib2@{pin}")
        test_static_crossfade(lib)
        test_time_varying_crossfade(lib)
        test_dynamic_gain_term(lib)
        test_synth_notes_dynamic()
        test_articulation_fallbacks_and_sampled(lib)
        test_tremolo_retrigger(lib)
    test_trill_key_aware()
    print("\nAll dynamics & articulation (P2) tests passed.")
