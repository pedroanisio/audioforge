"""Variation-at-scale tests (v2.8): seeded variants, vary() choice sets,
intensity scaling, campaign cutdowns, pack export."""
import json
import sys
import tempfile
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from audioforge import AudioForge  # noqa: E402

AF = AudioForge()

SRC = """
asset vtest {
  kind: cue
  duration: 24s
  tempo: 100bpm
  key: D minor
  intensity: 0s=0.2, 12s=0.9, 24s=0.3

  cutdowns {
    12s: keep 0s to 6s, keep 17.5s to 24s, fade 0.5s
    6s: keep 18s to 24s
  }

  layer texture : grain {
    source: pad
    note: D4
    srcdur: 1.5s
    grainsize: vary(0.06s, 0.12s)
    duration: 24s
    gain: -16db
    env: a=1s d=1s s=0.8 r=2s
  }
  layer beat : drums {
    voice: kick
    pattern: vary(X...x...X...x..., X..x..x.X...x..., X.....x.X..x....)
    gain: -7db
    humanize: 0.4
  }
  layer line : notes {
    osc: triangle
    gain: -12db
    humanize: 0.5
    env: a=0.02s d=0.3s s=0.6 r=0.4s
    notes: D4 @ 0b for 2b, F4 @ 4b for 2b, A4 @ 8b for 4b,
           D4 @ 16b for 2b, A3 @ 20b for 4b
  }
  master { lufs: -16
           peak: -1db
           fadeout: 1s }
}
"""


def test_variants_reproducible_and_distinct():
    a1 = AF.compile(SRC, variant="v1").assets[0]
    a1b = AF.compile(SRC, variant="v1").assets[0]
    a2 = AF.compile(SRC, variant="v2").assets[0]
    s1, _, _ = a1.render()
    s1b, _, _ = a1b.render()
    s2, _, _ = a2.render()
    assert np.array_equal(s1, s1b)
    assert not np.array_equal(s1, s2)
    assert a1.hash != a2.hash
    # the composition survives: identical note IR across variants
    assert a1.spec["layers"][2]["notes"] == a2.spec["layers"][2]["notes"]
    print("PASS  variants: same tag byte-identical, tags distinct, "
          "composition IR preserved")


def test_vary_choices_stable_and_explicit():
    picks = {}
    for tag in ("v1", "v2", "v3", "v4", "v5", "v6"):
        spec = AF.compile(SRC, variant=tag).assets[0].spec
        picks[tag] = (spec["layers"][0]["grain_s"], spec["layers"][1]["pattern"])
        again = AF.compile(SRC, variant=tag).assets[0].spec
        assert picks[tag] == (again["layers"][0]["grain_s"],
                              again["layers"][1]["pattern"])
    assert len(set(picks.values())) >= 2     # alternatives actually explored
    canonical = AF.compile(SRC).assets[0].spec
    assert canonical["layers"][0]["grain_s"] == 0.06   # variant None -> alt 0
    print(f"PASS  vary(): {len(set(picks.values()))} distinct choice combos "
          f"over 6 tags, all compile-stable; no-variant = canonical")


def test_intensity_scaling():
    base = AF.compile(SRC).assets[0]
    quiet = base.with_intensity(0.3)
    s_full, sr, _ = base.render()
    s_q, _, _ = quiet.render()

    def arc(s):
        x = s.mean(axis=1)
        lo = np.sqrt(np.mean(x[:int(4 * sr)] ** 2))
        hi = np.sqrt(np.mean(x[int(10 * sr):int(14 * sr)] ** 2))
        return 20 * np.log10(hi / lo)
    swing_full, swing_q = arc(s_full), arc(s_q)
    assert swing_q < swing_full - 1.0, (swing_full, swing_q)
    assert base.hash != quiet.hash
    print(f"PASS  intensity: dramatic swing {swing_full:.1f} dB at 1.0 vs "
          f"{swing_q:.1f} dB at 0.3, hash-tracked")


def test_cutdowns_length_content_loudness():
    a = AF.compile(SRC).assets[0]
    full, sr, _ = a.render()
    with tempfile.TemporaryDirectory() as td:
        metas = a.export_cutdowns(td)
        assert {m["cutdown"]["length_s"] for m in metas} == {12.0, 6.0}
        for m in metas:
            assert abs(m["duration_s"] - m["cutdown"]["length_s"]) <= 1.0
            assert abs(m["loudness"]["final_lufs"] + 16) < 0.4
            assert m["cutdown"]["parent_spec_hash"] == a.hash
        # 6s cut content matches the source window (correlation, pre-loudness
        # shapes differ only by gain): compare normalized envelopes
        import wave
        with wave.open(str(Path(td) / "vtest_6s.wav")) as w:
            raw = w.readframes(w.getnframes())
        b = np.frombuffer(raw, dtype=np.uint8).reshape(-1, 3)
        v = (b[:, 0].astype(np.int32) | (b[:, 1].astype(np.int32) << 8)
             | (b[:, 2].astype(np.int32) << 16))
        v = ((v - ((v >> 23) & 1) * (1 << 24)) / float(1 << 23))
        cut = v.reshape(-1, 2).mean(axis=1)
        src_win = full[int(18 * sr):int(24 * sr)].mean(axis=1)
        n = min(cut.size, src_win.size)
        e1 = np.abs(cut[:n]).reshape(-1, 4800).mean(axis=1)
        e2 = np.abs(src_win[:n]).reshape(-1, 4800).mean(axis=1)
        r = np.corrcoef(e1, e2)[0, 1]
        assert r > 0.97, r
    print(f"PASS  cutdowns: lengths/loudness/lineage correct; 6s cut "
          f"envelope correlates {r:.3f} with the source window")


def test_pack_export():
    with tempfile.TemporaryDirectory() as td:
        pack = AF.export_pack(SRC, td, n=4)
        assert len(pack["variants"]) == 4
        hashes = {v["output_sha256"] for v in pack["variants"]}
        assert len(hashes) == 4
        assert (Path(td) / "pack.manifest.json").exists()
        for v in pack["variants"]:
            assert (Path(td) / v["file"]).exists()
    print("PASS  pack: 4 variants, 4 distinct output hashes, manifest + "
          "files on disk")


if __name__ == "__main__":
    test_variants_reproducible_and_distinct()
    test_vary_choices_stable_and_explicit()
    test_intensity_scaling()
    test_cutdowns_length_content_loudness()
    test_pack_export()
    print("\nAll variation-at-scale tests passed.")
