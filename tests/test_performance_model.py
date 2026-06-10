"""Performance model (P3) tests: legato joins, ensemble multiplication,
phrasing. Measured, not assumed: join continuity via boundary-window RMS,
attack suppression via onset slope, the pitch ramp via short-window f0
tracking through the join, ensemble width via fundamental-peak bandwidth."""
import sys
import tempfile
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from audioforge import AudioForge  # noqa: E402
from audioforge import library as libmod  # noqa: E402
from audioforge.determinism import rng_for  # noqa: E402
from audioforge.sampler import (render_instrument_track,  # noqa: E402
                                render_section)
from audioforge.sequencer import TempoMap  # noqa: E402
from test_dynamics import build_p2_library  # noqa: E402

SR = 48000
AF = AudioForge()
TM = TempoMap([[0.0, 120.0]])


def _render(lib, notes, dur_s=6.0, **extra):
    track = {"name": "v", "type": "instrument", "instrument": "testviolin",
             "notes": notes, **extra}
    n = int(dur_s * SR)
    return render_instrument_track(
        track, n, SR, TM, lambda s: rng_for("p3", "t", s), lib)


def _two_notes(slur):
    evs = [{"note": "C4", "start_beat": 0.0, "dur_beats": 4.0,
            "vel": 0.4},
           {"note": "D4", "start_beat": 4.0, "dur_beats": 4.0,
            "vel": 0.4}]
    if slur:
        for e in evs:
            e["slur"] = 1
    return evs


def test_slur_dsl():
    res = AF.compile("""
asset s { kind: cue
  duration: 8s
  tempo: 120bpm
  key: C major
  motif m { C4 @ 0b for 1b
            E4 @ 1b for 1b }
  layer v : notes { osc: sine
    notes: slur( C4 @ 0b for 1b, D4 @ 1b for 1b ), E4 @ 3b for 1b,
           slur( G4 @ 4b for 1b, A4 @ 5b for 1b )
    play m @ 6b legato
  }
  master { peak: -1db }
}""")
    assert res.ok, [d.message for d in res.diagnostics]
    sl = [e.get("slur") for e in res.assets[0].spec["layers"][0]["notes"]]
    assert sl[0] == sl[1] and sl[0] is not None      # first group
    assert sl[2] is None                              # lone note
    assert sl[3] == sl[4] and sl[3] != sl[0]          # second group
    assert sl[5] == sl[6] and sl[5] not in (sl[0], sl[3])  # play legato
    print("PASS  slur DSL: groups get distinct ids, lone notes none, "
          "play+legato makes the motif one group")


def test_legato_join_continuity(lib):
    """At the note boundary, the joined version must not dip and must not
    re-attack. Detached: release + fresh attack = an energy valley and a
    sharp onset. Joined: held crossfade + suppressed attack."""
    det = _render(lib, _two_notes(False))
    leg = _render(lib, _two_notes(True), legato_s=0.06)
    j = int(2.0 * SR)                                  # boundary at 2 s

    def dip(x):
        around = np.sqrt(np.mean(x[j - SR // 2:j + SR // 2] ** 2))
        at = np.sqrt(np.mean(x[j - 1200:j + 1200] ** 2))
        return at / around
    assert dip(leg) > 0.8, dip(leg)                    # continuous

    def c4_hold(x):
        """C4 fundamental 20-50 ms past the boundary: legato holds the
        outgoing note through the crossfade; detached is in release."""
        seg = x[j + int(0.02 * SR):j + int(0.05 * SR)]
        s = np.abs(np.fft.rfft(seg * np.hanning(seg.size), n=8 * seg.size))
        f = np.fft.rfftfreq(8 * seg.size, 1 / SR)
        return s[(f > 255) & (f < 270)].max()
    # modest by design: the detached release (0.12 s) is itself slower
    # than the 60 ms join, so it retains C4 too — direction is what counts
    assert c4_hold(leg) > 1.15 * c4_hold(det), \
        (c4_hold(leg), c4_hold(det))

    def attack_hf(x):
        """HF energy right after the boundary: the recorded attack scrape.
        Legato skips 60 ms into the sample — past the scrape."""
        from audioforge.fx import filter_fx
        seg = filter_fx(x[j:j + int(0.05 * SR)], SR, "highpass", 2500.0)
        return np.sqrt(np.mean(seg ** 2))
    assert attack_hf(det) > 2.0 * attack_hf(leg), \
        (attack_hf(det), attack_hf(leg))
    leg2 = _render(lib, _two_notes(True), legato_s=0.06)
    assert np.array_equal(leg, leg2)
    print(f"PASS  legato join: continuous (RMS ratio {dip(leg):.2f}); "
          f"outgoing C4 held {c4_hold(leg)/c4_hold(det):.1f}x stronger "
          f"through the join; attack scrape suppressed "
          f"{attack_hf(det)/attack_hf(leg):.1f}x; byte-stable")


def test_legato_pitch_ramp(lib):
    """f0 tracked in 15 ms hops through the join must pass through
    intermediate values (a real glide), not jump C4 -> E4."""
    leg = _render(lib, _two_notes(True), legato_s=0.06)
    j = int(2.0 * SR)
    hop, win = int(0.005 * SR), int(0.015 * SR)
    f0s = []
    for k in range(-2, 10):
        seg = leg[j + k * hop:j + k * hop + win]
        s = np.abs(np.fft.rfft(seg * np.hanning(win), n=8 * win))
        f = np.fft.rfftfreq(8 * win, 1 / SR)
        band = (f > 200) & (f < 400)
        f0s.append(f[band][np.argmax(s[band])])
    mid = [f0 for f0 in f0s if 268 < f0 < 288]         # between C4 and D4
    assert mid, f0s
    assert any(f0 <= 268 for f0 in f0s) and any(f0 >= 288 for f0 in f0s)
    print(f"PASS  pitch ramp: f0 through the join passes intermediate "
          f"values ({min(mid):.0f}..{max(mid):.0f} Hz between 262 and 294)")


def test_section_multiplication(lib):
    layer = {"name": "v", "type": "instrument", "instrument": "testviolin",
             "section": {"size": 6, "spread": 0.8, "detune_c": 9.0,
                         "timing_s": 0.01},
             "notes": [{"note": "C4", "start_beat": 0.0, "dur_beats": 8.0,
                        "vel": 0.4}]}
    n = int(4 * SR)
    st = render_section(layer, n, SR, TM,
                        lambda s: rng_for("p3", "sec", s), lib)
    assert st.shape == (n, 2)
    assert not np.array_equal(st[:, 0], st[:, 1])
    st2 = render_section(layer, n, SR, TM,
                         lambda s: rng_for("p3", "sec", s), lib)
    assert np.array_equal(st, st2)
    solo = _render(lib, [layer["notes"][0]], 4.0)

    def beating(x):
        """Envelope fluctuation over the held tone: detuned unison beats
        (the section 'shimmer'); one steady player doesn't. Coefficient of
        variation of 50 ms RMS blocks over 2 s."""
        seg = x[SR:3 * SR]
        env = np.sqrt((seg.reshape(-1, int(0.05 * SR)) ** 2).mean(axis=1))
        return env.std() / env.mean()
    assert beating(st.mean(axis=1)) > 2.0 * beating(solo), \
        (beating(solo), beating(st.mean(axis=1)))
    print(f"PASS  section: stereo, deterministic; envelope beating "
          f"{beating(solo):.3f} -> {beating(st.mean(axis=1)):.3f} with 6 "
          f"detuned players (the shimmer)")


def test_phrasing_arch(lib):
    rise = [{"note": nm, "start_beat": float(b), "dur_beats": 1.0, "slur": 1}
            for b, nm in enumerate(["C4", "D4", "Eb4", "D4", "C4"])]
    flat = _render(lib, [dict(e) for e in rise], 4.0)
    shaped = _render(lib, [dict(e) for e in rise], 4.0, phrasing=1.0)

    def note_rms(x, i):
        a = int(i * 0.5 * SR)
        return np.sqrt(np.mean(x[a + 2400:a + int(0.45 * SR)] ** 2))
    # the arch: peak note gains relative to the first, vs the flat render
    ratio_flat = note_rms(flat, 2) / note_rms(flat, 0)
    ratio_shaped = note_rms(shaped, 2) / note_rms(shaped, 0)
    assert ratio_shaped > 1.25 * ratio_flat, (ratio_flat, ratio_shaped)
    # end lift: last note eases
    end_flat = note_rms(flat, 4) / note_rms(flat, 2)
    end_shaped = note_rms(shaped, 4) / note_rms(shaped, 2)
    assert end_shaped < end_flat, (end_flat, end_shaped)
    print(f"PASS  phrasing: peak/first RMS {ratio_flat:.2f} -> "
          f"{ratio_shaped:.2f} with the arch; last note eases "
          f"({end_flat:.2f} -> {end_shaped:.2f})")


if __name__ == "__main__":
    test_slur_dsl()
    with tempfile.TemporaryDirectory() as td:
        root = Path(td) / "minilib2"
        pin = build_p2_library(root)
        lib = libmod.load_library(f"minilib2@{pin}")
        test_legato_join_continuity(lib)
        test_legato_pitch_ramp(lib)
        test_section_multiplication(lib)
        test_phrasing_arch(lib)
    print("\nAll performance-model (P3) tests passed.")
