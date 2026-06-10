"""Performance realism tests (v2.4): humanize, groove, vel-brightness,
glide, vibrato — each verified in the rendered audio, not just the IR."""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from audioforge import AudioForge  # noqa: E402

SR = 48000
F = AudioForge()


def _mono(src):
    res = F.compile(src)
    assert res.ok, [d.message for d in res.diagnostics]
    s, sr, _ = res.assets[0].render()
    return s.mean(axis=1), sr


def _onsets(x, sr, thresh=0.02):
    env = np.abs(x)
    k = sr // 200
    env = env[:env.size // k * k].reshape(-1, k).max(axis=1)
    d = np.diff(env)
    idx = np.where((d[:-1] > thresh) & (d[1:] <= thresh))[0]
    keep = [int(i) for i in idx if not [j for j in idx if 0 < i - j < 10]]
    return np.array(keep) * k / sr


HAT = """
asset g_{name} {{
  kind: loop
  duration: 4s
  tempo: 120bpm
  {groove}
  layer h : drums {{
    voice: hat
    pattern: xxxxxxxxxxxxxxxx
    gain: -3db
    {hum}
  }}
  master {{ peak: -1db
           fadeout: 0.01s }}
}}
"""


def test_humanize_shifts_onsets_deterministically():
    quant, sr = _mono(HAT.format(name="q", groove="", hum=""))
    hum1, _ = _mono(HAT.format(name="h", groove="",
                               hum="humanize: time=0.012s vel=0.1"))
    hum2, _ = _mono(HAT.format(name="h", groove="",
                               hum="humanize: time=0.012s vel=0.1"))
    assert np.array_equal(hum1, hum2)
    # ground truth per grid slot: hit onset = first crossing of 25% of the
    # local window peak (reseed-robust; no cross-render onset pairing)
    step = 60 / 120 / 4
    devs = []
    for i in range(1, 28):
        g = i * step
        w = hum1[int((g - 0.03) * sr):int((g + 0.03) * sr)]
        if w.size == 0 or np.abs(w).max() < 1e-4:
            continue
        onset = np.argmax(np.abs(w) > 0.25 * np.abs(w).max())
        devs.append(abs(onset / sr - 0.03))
    dev = np.array(devs)
    assert dev.max() > 0.003, dev.max()      # jitter is real (>3 ms somewhere)
    assert dev.max() < 0.014                 # bounded by the 12 ms spec
    print(f"PASS  humanize: onsets deviate up to {dev.max()*1000:.1f} ms, "
          f"byte-deterministic")


def test_groove_swing_delays_offbeats():
    straight, sr = _mono(HAT.format(name="s", groove="", hum=""))
    swung, _ = _mono(HAT.format(name="w", groove="groove: swing16 1", hum=""))
    os_, ow = _onsets(straight, sr), _onsets(swung, sr)
    step = 60.0 / 120 / 4
    # classify by grid slot (robust to detector dropouts), pair by nearest
    late, on = [], []
    for t in os_[:16]:
        slot = int(round(t / step))
        if slot == 0:        # boundary hit sits under the master fade-in;
            continue         # its detectability is reseed-sensitive
        shift = ow[np.argmin(np.abs(ow - t))] - t
        (late if slot % 2 == 1 else on).append(shift)
    assert np.mean(late) > 0.25 * step, np.mean(late)   # odd 16ths pushed late
    assert np.mean(np.abs(on)) < 0.02 * step + 0.002    # downbeats untouched
    print(f"PASS  groove swing16: offbeats late by "
          f"{np.mean(late)*1000:.0f} ms, downbeats on the grid")


def _centroid(x, sr):
    spec = np.abs(np.fft.rfft(x * np.hanning(x.size)))
    freqs = np.fft.rfftfreq(x.size, 1 / sr)
    return (spec * freqs).sum() / spec.sum()


VB = """
asset vb {{
  kind: cue
  duration: 2s
  tempo: 60bpm
  layer l : notes {{
    osc: saw
    gain: -6db
    velbright: 1
    env: a=0.01s d=0.2s s=0.6 r=0.2s
    notes: A2 @ 0b for 2b vel {vel}
  }}
  master {{ peak: -1db
           fadeout: 0.05s }}
}}
"""


def test_velocity_to_brightness():
    soft, sr = _mono(VB.format(vel=0.3))
    hard, _ = _mono(VB.format(vel=1.0))
    cs, ch = _centroid(soft, sr), _centroid(hard, sr)
    assert ch > cs * 1.6, (cs, ch)
    print(f"PASS  vel->brightness: centroid {cs:.0f} Hz at vel 0.3 vs "
          f"{ch:.0f} Hz at vel 1.0")


def _pitch_track(x, sr, t0, t1):
    seg = x[int(t0 * sr):int(t1 * sr)]
    seg = seg * np.hanning(seg.size)
    spec = np.abs(np.fft.rfft(seg))
    return np.argmax(spec) * sr / seg.size


GLIDE = """
asset gl {
  kind: cue
  duration: 3s
  tempo: 60bpm
  layer l : notes {
    osc: sine
    gain: -6db
    glide: 0.25s
    env: a=0.005s d=0.1s s=0.9 r=0.1s
    notes: A3 @ 0b for 1b, A4 @ 1b for 2b
  }
  master { peak: -1db
           fadeout: 0.05s }
}
"""


def test_glide_slides_pitch():
    x, sr = _mono(GLIDE)
    early = _pitch_track(x, sr, 1.02, 1.10)   # just after the second onset
    late = _pitch_track(x, sr, 1.6, 2.4)      # settled
    assert early < 330.0, early               # still rising from A3 (220)
    assert abs(late - 440.0) < 12.0, late     # lands on A4
    print(f"PASS  glide: pitch {early:.0f} Hz just after onset -> "
          f"{late:.0f} Hz settled")


VIB = """
asset vb2 {{
  kind: cue
  duration: 3s
  tempo: 60bpm
  layer l : notes {{
    osc: sine
    gain: -6db
    {vib}
    env: a=0.01s d=0.2s s=0.9 r=0.2s
    notes: A4 @ 0b for 3b
  }}
  master {{ peak: -1db
           fadeout: 0.05s }}
}}
"""


def _inst_freq_swing(x, sr):
    """Zero-crossing instantaneous frequency: min/max over 100 ms windows
    (FFT-bin pitch tracking can't resolve cents-deep vibrato)."""
    seg = x[int(1.0 * sr):int(2.5 * sr)]
    zc = np.where(np.diff(np.signbit(seg)))[0]
    f_inst = 1.0 / (np.diff(zc) * 2 / sr)
    wins = [f_inst[(zc[:-1] > i * sr // 10)
                   & (zc[:-1] < (i + 1) * sr // 10)].mean()
            for i in range(14)]
    return min(wins), max(wins)


def test_vibrato_modulates_pitch():
    plain, sr = _mono(VIB.format(vib=""))
    vibed, _ = _mono(VIB.format(vib="vibrato: rate=5 depth=40c delay=0.3s"))
    lo_p, hi_p = _inst_freq_swing(plain, sr)
    lo_v, hi_v = _inst_freq_swing(vibed, sr)
    assert hi_p - lo_p < 1.0, (lo_p, hi_p)        # static note is static
    assert hi_v - lo_v > 8.0, (lo_v, hi_v)        # vibrato swings ~13 Hz
    assert lo_v < 440.0 < hi_v                    # centered on the note
    print(f"PASS  vibrato: pitch swings {lo_v:.1f}..{hi_v:.1f} Hz around 440 "
          f"(static note: {hi_p - lo_p:.2f} Hz spread)")


def test_groove_in_compiled_ir():
    res = F.compile("""
asset gz {
  kind: loop
  duration: 2s
  tempo: 120bpm
  groove: laidback 0.5
  layer h : drums {
    voice: hat
    pattern: x...x...x...x...
    gain: -3db
  }
  master { peak: -1db
           fadeout: 0.01s }
}
""")
    g = res.assets[0].spec["groove"]
    assert g["name"] == "laidback" and len(g["timing"]) == 16
    assert g["timing"][4] == round(0.12 * 0.5, 4)  # template x amount, explicit
    print("PASS  groove templates expand to explicit, inspectable IR arrays")


if __name__ == "__main__":
    test_humanize_shifts_onsets_deterministically()
    test_groove_swing_delays_offbeats()
    test_velocity_to_brightness()
    test_glide_slides_pitch()
    test_vibrato_modulates_pitch()
    test_groove_in_compiled_ir()
    print("\nAll performance-realism tests passed.")
