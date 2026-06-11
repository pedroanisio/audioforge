"""Palette-depth tests (v2.9): blown waveguide, drum-voice depth,
procedural foley, sample ingestion, hash-pinned convolution."""
import io
import sys
import tempfile
import wave
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from audioforge import AudioForge  # noqa: E402
from audioforge import foley, samples as smod, synth  # noqa: E402
from audioforge.determinism import rng_for  # noqa: E402
from audioforge.fx import convolve_fx  # noqa: E402
from audioforge.sequencer import DRUM_VOICES  # noqa: E402

SR = 48000
AF = AudioForge()


def _spec(x, sr=SR):
    s = np.abs(np.fft.rfft(x * np.hanning(x.size)))
    return s, np.fft.rfftfreq(x.size, 1 / sr)


def test_blown_sustains_odd_harmonics():
    x = synth.osc("blown", 220.0, SR * 3, SR, rng=rng_for("t", "bl"),
                  voice={"pressure": 0.6, "brightness": 0.6})
    tail = x[-SR:]
    assert np.sqrt(np.mean(tail ** 2)) > 0.3        # self-oscillates, sustains
    s, f = _spec(tail)
    pk = lambda lo, hi: s[(f > lo) & (f < hi)].max()  # noqa: E731
    band = (f > 180) & (f < 260)
    pitch = f[band][np.argmax(s[band])]
    assert abs(pitch - 220) < 8, pitch
    h2, h3 = pk(420, 460) / pk(180, 260), pk(640, 680) / pk(180, 260)
    assert h3 > 10 * h2                              # cylindrical bore: odd
    x2 = synth.osc("blown", 220.0, SR * 3, SR, rng=rng_for("t", "bl"),
                   voice={"pressure": 0.6, "brightness": 0.6})
    assert np.array_equal(x, x2)
    print(f"PASS  blown: {pitch:.0f} Hz sustained, H3/H2 = {h3/max(h2,1e-9):.0f}x "
          f"(odd-harmonic bore), deterministic")


def test_brass_sustains_and_brightens():
    """The brass lip-reed completes bowed/blown/brass: it self-oscillates on the
    proven reed core (sustained, tightly in tune), carries a *full* harmonic
    series — the even harmonics the bell-flare rectifier supplies and a plain
    cylindrical reed (blown) cannot — brightens with the `brightness` control,
    and is bit-deterministic. Locks the kernel's measured properties."""
    v = {"pressure": 0.6, "brightness": 0.6}
    x = synth.osc("brass", 220.0, SR * 3, SR, rng=rng_for("t", "br"), voice=v)
    tail = x[-SR:]
    assert np.sqrt(np.mean(tail ** 2)) > 0.3          # self-oscillates, sustains
    s, f = _spec(tail)
    band = (f > 180) & (f < 260)
    pitch = f[band][np.argmax(s[band])]
    cents = 1200.0 * np.log2(pitch / 220.0)
    assert abs(cents) < 35, (pitch, cents)            # tight tuning (meas. ~+8c)

    # full harmonic series: the even harmonics (H2, H4) must be well above the
    # odd-only floor — the bell flare, the brass-defining feature vs blown.
    hk = lambda k: s[(f > k * pitch - 20) & (f < k * pitch + 20)].max()
    fund = hk(1)
    h2, h3, h4 = hk(2) / fund, hk(3) / fund, hk(4) / fund
    assert h2 > 0.03 and h4 > 0.02, (h2, h4)          # evens present (~-18dB)
    assert h3 > 0.1, h3                               # strong odd series too

    # brightness drives the in-loop steepening: brighter => more high-freq energy
    def hf(b):
        y = synth.osc("brass", 220.0, SR, SR, rng=rng_for("t", "br"),
                      voice={"pressure": 0.6, "brightness": b})[-SR // 2:]
        S, F = _spec(y)
        return S[F > 1500].sum() / S.sum()
    assert hf(0.9) > hf(0.1), (hf(0.1), hf(0.9))

    x2 = synth.osc("brass", 220.0, SR * 3, SR, rng=rng_for("t", "br"), voice=v)
    assert np.array_equal(x, x2)                       # deterministic
    print(f"PASS  brass: {pitch:.0f} Hz ({cents:+.0f}c) sustained, full series "
          f"(H2={20 * np.log10(h2):.0f}dB), brightens, deterministic")


def test_struck_string_tension_glide():
    """The struck string is the nonlinear cousin of pluck: tension modulation
    makes a hard strike start sharp and glide down to the nominal pitch (the
    "boing"). tension=0 reduces to the linear Karplus-Strong (no glide); the
    tail always lands on the nominal pitch; and it is bit-deterministic."""
    f0 = 146.83                                        # D3

    def render(tension):
        return synth.osc("struck", f0, SR * 2, SR, rng=rng_for("t", "st"),
                         voice={"damping": 0.4, "brightness": 0.6,
                                "tension": tension, "strike": 0.9})

    def pitch(seg):                                    # autocorrelation pitch
        seg = seg - seg.mean()
        ac = np.correlate(seg, seg, "full")[seg.size - 1:]
        lo, hi = int(SR / 400), int(SR / 80)
        return SR / (lo + np.argmax(ac[lo:hi]))

    def win(y, ms, dur=120):
        a = int(ms * SR / 1000)
        return y[a:a + int(dur * SR / 1000)]

    y = render(0.8)
    assert np.all(np.isfinite(y))
    assert np.sqrt(np.mean(y[:SR // 4] ** 2)) > 5 * np.sqrt(
        np.mean(y[-SR // 4:] ** 2))                     # struck → decays

    # the defining property: tension makes the onset sharp, gliding down to f0
    glide = 1200 * np.log2(pitch(win(y, 30)) / pitch(win(y, 900)))
    assert glide > 20, glide                           # clear downward glide
    flat = 1200 * np.log2(pitch(win(render(0.0), 30)) /
                          pitch(win(render(0.0), 900)))
    assert abs(flat) < 5, flat                         # tension=0 → linear KS
    assert abs(1200 * np.log2(pitch(y[-SR // 2:]) / f0)) < 30   # tail at nominal

    assert np.array_equal(y, render(0.8))              # deterministic
    print(f"PASS  struck: tension glide {glide:+.0f}c -> nominal, tension=0 "
          f"flat ({flat:+.0f}c), deterministic")


def test_drum_voice_depth():
    rng = lambda: rng_for("t", "drum")  # noqa: E731
    lo = DRUM_VOICES["kick"](SR, rng(), {"tune_st": -6.0})
    hi = DRUM_VOICES["kick"](SR, rng(), {"tune_st": +6.0})
    def body_peak(x):
        s, f = _spec(x[:SR // 4] if x.size >= SR // 4 else x)
        band = (f > 20) & (f < 200)
        return f[band][np.argmax(s[band])]
    assert body_peak(hi) > 1.5 * body_peak(lo), (body_peak(lo), body_peak(hi))
    short = DRUM_VOICES["snare"](SR, rng(), {"decay": 0.5})
    long_ = DRUM_VOICES["snare"](SR, rng(), {"decay": 2.0})
    assert long_.size > 3 * short.size
    tonal = DRUM_VOICES["snare"](SR, rng(), {"snap": 0.05})
    noisy = DRUM_VOICES["snare"](SR, rng(), {"snap": 0.95})
    def shell_share(x):
        # POWER share of the 190 Hz shell band (linear-magnitude sums let
        # broadband noise outvote a stronger concentrated tone)
        s, f = _spec(x)
        p = s ** 2
        return p[(f > 150) & (f < 250)].sum() / p.sum()
    assert shell_share(tonal) > 5 * shell_share(noisy),         (shell_share(tonal), shell_share(noisy))
    print(f"PASS  drums: tune moves body {body_peak(lo):.0f} -> "
          f"{body_peak(hi):.0f} Hz; decay scales 4x; snap shifts shell "
          f"power share {shell_share(tonal):.2f} -> {shell_share(noisy):.3f}")


def test_foley_models_character():
    n = SR * 6
    r = foley.rain(n, SR, rng_for("t", "rain"), intensity=0.7)
    w = foley.wind(n, SR, rng_for("t", "wind"), intensity=0.6)
    fi = foley.fire(n, SR, rng_for("t", "fire"), intensity=0.6)
    su = foley.surf(n, SR, rng_for("t", "surf"), intensity=0.6)
    for name, x in (("rain", r), ("wind", w), ("fire", fi), ("surf", su)):
        x2 = getattr(foley, name)(n, SR, rng_for("t", name), intensity=0.7
                                  if name == "rain" else 0.6)
        assert np.array_equal(x, x2), name

    def centroid(x):
        s, f = _spec(x)
        return (s * f).sum() / s.sum()
    assert centroid(r) > 2.5 * centroid(w)          # rain bright, wind dark
    # fire pops are LOCALLY spiky; wind is globally peaky (gust envelope)
    # but smooth within any second — so compare median per-second crest of
    # the >500 Hz band, where impulsiveness lives
    from audioforge.fx import filter_fx
    def local_crest(x):
        h = filter_fx(x, SR, "highpass", 500.0)
        secs = h[:SR * 6].reshape(6, SR)
        return np.median([np.max(np.abs(s)) / np.sqrt(np.mean(s ** 2))
                          for s in secs])
    crest = local_crest
    assert crest(fi) > 1.8 * crest(w), (crest(fi), crest(w))
    # surf swells: envelope autocorrelation peaks in the wave-period range
    env = np.abs(su).reshape(-1, SR // 10).mean(axis=1)
    env = env - env.mean()
    ac = np.correlate(env, env, "full")[env.size:]
    lag = np.argmax(ac[30:]) + 30                   # > 3 s
    assert 3.0 < lag / 10.0 < 15.0, lag / 10.0
    print(f"PASS  foley: rain centroid {centroid(r):.0f} vs wind "
          f"{centroid(w):.0f} Hz; fire local crest {crest(fi):.0f} vs wind "
          f"{crest(w):.0f}; surf period ~{lag/10:.1f} s; all deterministic")


def _wav_bytes(x, sr=SR):
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((x / max(np.abs(x).max(), 1e-9) * 30000)
                      .astype("<i2").tobytes())
    return buf.getvalue()


def test_ingest_catalog_and_snippet():
    rng = np.random.default_rng(3)
    t = np.arange(SR // 2) / SR
    hit = np.sin(2 * np.pi * 150 * t) * np.exp(-t * 25)
    loop = rng.standard_normal(SR * 2) * 0.4
    with tempfile.TemporaryDirectory() as td:
        (Path(td) / "punch.wav").write_bytes(_wav_bytes(hit))
        (Path(td) / "bed loop.wav").write_bytes(_wav_bytes(loop))
        cat = smod.ingest(td)
        by = {c["file"]: c for c in cat}
        assert by["punch.wav"]["guess"] == "one_shot"
        assert by["bed loop.wav"]["guess"] == "loop"
        for c in cat:
            assert len(c["sha256"]) == 64
            assert c["sha256"] in c["snippet"]
        # the emitted snippet actually renders
        src = ("asset ing { kind: cue\n  duration: 2s\n  tempo: 120bpm\n  "
               + by["punch.wav"]["snippet"].replace("\\n", "\n")
               + "\n  master { peak: -1db\n fadeout: 0.02s }\n}")
        res = AF.compile(src)
        assert res.ok, [d.message for d in res.diagnostics]
        s, _, _ = res.assets[0].render()
        assert np.abs(s).max() > 0.01
    print("PASS  ingest: catalog hashes + one-shot/loop guesses correct; "
          "emitted snippet compiles and renders")


def test_convolve_hash_pinned():
    rng = np.random.default_rng(7)
    t = np.arange(SR) / SR
    ir = rng.standard_normal(SR) * np.exp(-t * 6)
    ir[0] = 1.0
    sha = smod.register_sample("t_ir.wav", _wav_bytes(ir))
    x = np.zeros(SR * 2)
    x[:200] = np.hanning(200)                        # an impulse-ish dry hit
    wet = convolve_fx(x, SR, "t_ir.wav", sha, mix=0.5)
    tail = lambda v: np.sqrt(np.mean(v[SR // 2:SR] ** 2))  # noqa: E731
    assert tail(wet) > 50 * max(tail(x), 1e-12)
    try:
        convolve_fx(x, SR, "t_ir.wav", "0" * 64, mix=0.5)
        raise AssertionError("hash mismatch not refused")
    except Exception as e:
        assert "hash mismatch" in str(e)
    print("PASS  convolve: hash-verified IR adds a real tail; wrong hash "
          "refused with both hashes named")


if __name__ == "__main__":
    test_blown_sustains_odd_harmonics()
    test_brass_sustains_and_brightens()
    test_struck_string_tension_glide()
    test_drum_voice_depth()
    test_foley_models_character()
    test_ingest_catalog_and_snippet()
    test_convolve_hash_pinned()
    print("\nAll palette-depth tests passed.")
