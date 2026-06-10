"""Tier S (P1) tests: SFZ-subset interpreter, orchestra manifests, the
instrument layer. The mini-library is built in-test with measurable design:
velocity layers have distinct spectra, round-robins carry marker partials,
sources are 44.1k against a 48k engine so resampling is always exercised."""
import io
import sys
import tempfile
import wave
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from audioforge import AudioForge  # noqa: E402
from audioforge import library as libmod, sampler  # noqa: E402
from audioforge.determinism import rng_for, spec_hash  # noqa: E402

SRC_SR = 44100
ENG_SR = 48000
AF = AudioForge()


def _tone(freq, dur, partials=((1, 1.0),), sr=SRC_SR):
    t = np.arange(int(dur * sr)) / sr
    x = sum(a * np.sin(2 * np.pi * freq * k * t) for k, a in partials)
    x *= np.exp(-t * 0.2)                       # gentle natural decay
    return x / np.abs(x).max() * 0.8


def _write(path, x, sr=SRC_SR):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((x * 30000).astype("<i2").tobytes())


SFZ = """
// test violin — exercises inheritance, key shorthand, vel layers, RR, loops
<control> default_path=wavs/
<global> ampeg_attack=0.01 ampeg_release=0.12 unknown_opcode=7
<group> lokey=55 hikey=63 pitch_keycenter=60
<region> sample=c4_soft.wav lovel=1 hivel=63
<region> sample=c4_loud_rr1.wav lovel=64 hivel=127 seq_length=2 seq_position=1
<region> sample=c4_loud_rr2.wav lovel=64 hivel=127 seq_length=2 seq_position=2
<group>
<region> key=g4 sample=g4_sus.wav lovel=1 hivel=127
         loop_mode=loop_continuous loop_start=4410 loop_end=39690
         loop_crossfade=0.02
"""


def build_library(root: Path) -> str:
    """3-key mini violin: C4 soft (pure sine), C4 loud rr1 (odd harmonics),
    C4 loud rr2 (same + 13th-partial marker), G4 looped sustain."""
    (root / "wavs").mkdir(parents=True)
    c4, g4 = 261.626, 391.995
    _write(root / "wavs/c4_soft.wav", _tone(c4, 2.0))
    _write(root / "wavs/c4_loud_rr1.wav",
           _tone(c4, 2.0, ((1, 1.0), (3, 0.5), (5, 0.3))))
    _write(root / "wavs/c4_loud_rr2.wav",
           _tone(c4, 2.0, ((1, 1.0), (3, 0.5), (5, 0.3), (13, 0.35))))
    _write(root / "wavs/g4_sus.wav", _tone(g4, 1.0))   # 1 s; loop extends it
    (root / "testviolin.sfz").write_text(SFZ)
    m = libmod.generate_manifest(root, name="minilib", version="1.0.0",
                                 license_str="CC0-1.0")
    libmod.add_library_path(root.parent)
    return m["manifest_sha256"]


def _f0(x, sr=ENG_SR, lo=200, hi=500):
    s = np.abs(np.fft.rfft(x * np.hanning(x.size)))
    f = np.fft.rfftfreq(x.size, 1 / sr)
    band = (f > lo) & (f < hi)
    return f[band][np.argmax(s[band])]


def _partial(x, freq, sr=ENG_SR, width=15):
    s = np.abs(np.fft.rfft(x * np.hanning(x.size)))
    f = np.fft.rfftfreq(x.size, 1 / sr)
    return s[(f > freq - width) & (f < freq + width)].max()


def test_parse_and_inheritance():
    regions, ignored = sampler.parse_sfz(SFZ)
    assert len(regions) == 4
    assert all(r.ampeg_release == 0.12 for r in regions)   # <global> inherited
    assert regions[0].sample == "wavs/c4_soft.wav"          # default_path
    g = regions[3]
    assert (g.lokey, g.hikey, g.pitch_keycenter) == (67, 67, 67)  # key=g4
    assert g.loop_mode == "loop_continuous" and g.loop_end == 39690
    assert "unknown_opcode" in ignored                      # loud, not silent
    print("PASS  sfz: inheritance, default_path, key shorthand, loop "
          "opcodes, unknown opcodes reported")


def test_manifest_pin_and_tamper(tmp: Path, pin: str):
    lib = libmod.load_library(f"minilib@{pin}")
    x, sr = lib.audio("wavs/c4_soft.wav")
    assert sr == SRC_SR and x.size > SRC_SR
    # tamper one byte of a sample -> refusal naming both hashes
    p = tmp / "wavs/c4_soft.wav"
    raw = bytearray(p.read_bytes())
    raw[5000] ^= 0xFF
    p.write_bytes(bytes(raw))
    fresh = libmod.load_library(f"minilib@{pin}")
    try:
        fresh.audio("wavs/c4_soft.wav")
        raise AssertionError("tampered sample not refused")
    except ValueError as e:
        assert "hash mismatch" in str(e) and "pinned" in str(e)
    raw[5000] ^= 0xFF                                       # restore
    p.write_bytes(bytes(raw))
    # editing the manifest without regenerating -> self-hash refusal
    mp = tmp / "library.manifest.json"
    txt = mp.read_text().replace('"version": "1.0.0"', '"version": "9.9.9"')
    mp.write_text(txt)
    try:
        libmod.load_library(f"minilib@{pin}")
        raise AssertionError("edited manifest not refused")
    except ValueError as e:
        assert "self-hash" in str(e)
    mp.write_text(txt.replace('"version": "9.9.9"', '"version": "1.0.0"'))
    print("PASS  manifest: pin loads; tampered sample and edited manifest "
          "both refuse loudly")


def _render_dsl(pin, notes, vel="", variant=None, dur=6):
    src = f"""
asset p1test {{
  kind: cue
  duration: {dur}s
  tempo: 120bpm
  library: "minilib@{pin}"
  layer vln : instrument {{
    instrument: testviolin
    gain: -3db
    notes: {notes}
  }}
  master {{ peak: -1db
           fadeout: 0.05s }}
}}
"""
    res = AF.compile(src, variant=variant)
    assert res.ok, [d.message for d in res.diagnostics]
    st, sr, meta = res.assets[0].render()
    return st.mean(axis=1), sr, res.assets[0]


def test_pitch_and_resampling(pin):
    x, sr, _ = _render_dsl(pin, "D4 @ 0b for 4b vel 0.4")
    f0 = _f0(x[sr // 4:sr * 2])
    cents = 1200 * np.log2(f0 / 293.665)
    assert abs(cents) < 8, f"{f0:.2f} Hz ({cents:+.1f}c)"
    print(f"PASS  pitch: C4 sample played at D4 through 44.1k->48k "
          f"resampling lands {cents:+.1f} cents from nominal")


def test_velocity_layers(pin):
    soft, sr, _ = _render_dsl(pin, "C4 @ 0b for 4b vel 0.3")
    loud, _, _ = _render_dsl(pin, "C4 @ 0b for 4b vel 0.9")
    c4 = 261.626
    r_soft = _partial(soft[:sr * 2], c4 * 3) / _partial(soft[:sr * 2], c4)
    r_loud = _partial(loud[:sr * 2], c4 * 3) / _partial(loud[:sr * 2], c4)
    assert r_soft < 0.05 and r_loud > 0.2, (r_soft, r_loud)
    print(f"PASS  velocity layers: H3/H1 {r_soft:.3f} soft (pure-sine "
          f"layer) vs {r_loud:.2f} loud (harmonic layer)")


def test_round_robin_seeded(pin):
    notes = ", ".join(f"C4 @ {b}b for 0.9b vel 0.9" for b in range(8))
    marker = 261.626 * 13

    def rr_pattern(variant=None):
        x, sr, _ = _render_dsl(pin, notes, variant=variant)
        out = []
        for b in range(8):
            seg = x[int(b * 0.5 * sr):int((b * 0.5 + 0.42) * sr)]
            out.append(_partial(seg, marker) / max(_partial(seg, 261.626),
                                                   1e-9) > 0.05)
        return tuple(out)

    p1, p1b = rr_pattern(), rr_pattern()
    variants = [rr_pattern(v) for v in ("alt", "alt2", "bravo")]
    assert len(set(p1)) == 2          # both RRs actually appear
    assert p1 == p1b                  # re-render identical
    # an 8-pick pattern collides with one variant ~1/256 per engine bump
    # (hit at 2.14.0) — require only that variants are not ALL the base
    assert any(p != p1 for p in variants)
    print(f"PASS  round-robin: seeded picks {''.join('2' if v else '1' for v in p1)}, "
          f"re-render identical, variant tag re-realizes")


def test_loop_extension(pin):
    x, sr, _ = _render_dsl(pin, "G4 @ 0b for 8b vel 0.6", dur=5)
    # source is 1 s; the note holds 4 s — RMS must persist well past 1 s
    early = np.sqrt(np.mean(x[int(0.3 * sr):int(0.8 * sr)] ** 2))
    late = np.sqrt(np.mean(x[int(3.0 * sr):int(3.6 * sr)] ** 2))
    assert late > 0.25 * early, (early, late)
    f0 = _f0(x[sr * 2:sr * 3], lo=300, hi=500)
    assert abs(1200 * np.log2(f0 / 391.995)) < 10
    print(f"PASS  loop: 1 s source sustains a 4 s note (late/early RMS "
          f"{late/early:.2f}), pitch held through the loop")


def test_hash_discipline(pin):
    _, _, asset = _render_dsl(pin, "C4 @ 0b for 2b")
    other = dict(asset.spec)
    other["library"] = {**other["library"],
                        "manifest_sha256": "f" * 64}
    assert spec_hash(asset.spec) != spec_hash(other)
    res = AF.compile(f"""
asset nolib {{ kind: cue
  duration: 2s
  tempo: 120bpm
  layer v : instrument {{ instrument: testviolin
    notes: C4 @ 0b for 1b }}
  master {{ peak: -1db }}
}}""")
    assert not res.ok and any("library" in d.message
                              for d in res.diagnostics)
    print("PASS  hashing: library pin folds into spec hash; instrument "
          "layer without a library is a compile error")


if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as td:
        root = Path(td) / "minilib"
        pin = build_library(root)
        test_parse_and_inheritance()
        test_manifest_pin_and_tamper(root, pin)
        test_pitch_and_resampling(pin)
        test_velocity_layers(pin)
        test_round_robin_seeded(pin)
        test_loop_extension(pin)
        test_hash_discipline(pin)
    print("\nAll Tier S (P1) tests passed.")
