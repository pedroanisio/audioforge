"""Programmatic composition via the Composer builder (no DSL text)."""
import sys
import wave
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from audioforge import Catalog, Composer, hall  # noqa: E402
from audioforge.library import generate_manifest  # noqa: E402
from audioforge.schema import SpecError  # noqa: E402


def test_synth_composition_validates_and_reproduces(tmp_path):
    c = (Composer("synth", tempo=96, key="C major")
         .tone("pad", osc="sine",
               events=[("C3", 0, 8), ("G3", 0, 8), ("E4", 0, 8)],
               env={"a": 0.2, "d": 0.3, "s": 0.7, "r": 1.0}, gain_db=-10)
         .tone("lead", osc="triangle",
               events=[("C5", 0, 1), ("E5", 1, 1), ("G5", 2, 2, 1.0)])
         .marker("hook", 1.25)
         .master(peak_db=-1.0))
    asset = c.asset()
    assert not [d for d in asset.validate() if d.severity == "error"]
    assert asset.spec["duration_s"] > 0          # auto-derived from notes
    m1 = c.export(tmp_path / "a")
    m2 = c.export(tmp_path / "b")
    assert m1["output_sha256"] == m2["output_sha256"]
    print("PASS  composer: pure-synth composition validates and re-renders "
          "byte-identically")


def test_expression_controls_build_valid_spec(tmp_path):
    c = (Composer("expr", tempo=54, key="C major", swing=0.04)
         .tempo_map([(0, 54), (8, 50)])
         .tone("p", osc="sine", events=[("C4", 0, 1), ("E4", 1, 1)],
               humanize=(0.012, 0.06),
               dynamic=[(0, 0.4), (4, 0.6)],
               fx=[hall(rt60=2.0, mix=0.25)])
         .master(peak_db=-1.0))
    spec = c.to_dsl_spec()
    assert spec["tempo_map"][0] == [0.0, 54.0] and spec["swing"] == 0.04
    L = spec["layers"][0]
    assert L["humanize"] == {"timing_s": 0.012, "vel": 0.06}
    assert L["dynamic"] == [[0.0, 0.4], [4.0, 0.6]]
    assert L["fx"][0]["type"] == "hall"
    assert not [d for d in c.asset().validate() if d.severity == "error"]
    s1, _, _ = c.render()
    assert s1.shape[0] > 0
    # tempo_map must start at beat 0
    try:
        Composer("bad").tempo_map([(2, 60), (4, 50)])
        raise AssertionError("expected SpecError")
    except SpecError:
        pass
    print("PASS  composer: humanize/dynamic/tempo_map/swing/fx build a valid, "
          "renderable spec")


def test_instrument_layer_requires_library():
    try:
        Composer("needs_lib").instrument("v", instrument="x",
                                         events=[("C4", 0, 1)])
        raise AssertionError("expected SpecError")
    except SpecError as e:
        assert "library" in str(e)
    print("PASS  composer: instrument layer without a library is refused")


def _tiny_library(base: Path) -> Catalog:
    lib = base / "tinyinst"
    sdir = lib / "samples"
    sdir.mkdir(parents=True)
    with wave.open(str(sdir / "k_c4.wav"), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(44100)
        w.writeframes((np.zeros(8820) + 0.2 * 32767).astype("<i2").tobytes())
    (lib / "keys.sfz").write_text(
        "<region> sample=samples/k_c4.wav lokey=0 hikey=127 "
        "pitch_keycenter=60\n")
    generate_manifest(lib, name="tinyinst", version="1.0.0",
                      license_str="CC0-1.0")
    return Catalog.build(base)


def test_compose_from_catalog_renders(tmp_path):
    cat = _tiny_library(tmp_path)
    inst = cat.instrument("keys")
    assert inst.renderable and cat.pin("tinyinst")
    c = (Composer("from_cat", tempo=100)
         .from_catalog("kbd", cat, "keys",
                       events=[("C4", 0, 1), ("E4", 1, 1), ("G4", 2, 2)])
         .master(peak_db=-1.0))
    spec = c.to_dsl_spec()
    assert spec["library"]["name"] == "tinyinst"
    assert spec["layers"][0]["type"] == "instrument"
    s, sr, _ = c.render()
    assert s.shape[0] > 0 and sr > 0
    print("PASS  composer: instrument layer resolved from the catalog renders")


if __name__ == "__main__":
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        test_synth_composition_validates_and_reproduces(Path(td))
    test_instrument_layer_requires_library()
    with tempfile.TemporaryDirectory() as td:
        test_compose_from_catalog_renders(Path(td))
    print("\nAll composer SDK tests passed.")
