"""Catalog SDK: discovery, renderability verdict, queries, round-trip."""
import io
import sys
import wave
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from audioforge import AudioForge, Catalog, Instrument  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def _wav(path: Path, midi_note: str = "c4"):
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(44100)
        w.writeframes((np.zeros(4410) + 0.1 * 32767).astype("<i2").tobytes())


def _make_lib(base: Path):
    """A tiny one-instrument WAV library: renderable on any platform."""
    lib = base / "tinylib"
    _wav(lib / "samples" / "piano_c4.wav")
    (lib / "piano.sfz").write_text(
        "<region> sample=samples/piano_c4.wav key=60 "
        "pitch_keycenter=60 lokey=0 hikey=127\n")
    return base


def test_build_query_and_roundtrip(tmp_path):
    cat = Catalog.build(_make_lib(tmp_path))
    assert len(cat) == 1
    inst = cat.instrument("piano")
    assert isinstance(inst, Instrument)
    assert inst.renderable and not inst.render_blockers
    assert inst.samples["formats"] == ["wav"]
    assert inst.covers(60) and not inst.covers(200)   # key range is 0..127
    # queries
    assert cat.find(renderable=True) == [inst]
    assert cat.find("piano") and not cat.find("trumpet")
    assert cat.find(covers=60) == [inst]
    # round-trip through JSON
    out = cat.save(tmp_path / "c.json")
    c2 = Catalog.load(out)
    assert len(c2) == 1 and c2.instrument("piano").renderable
    print("PASS  catalog: build, query, covers, and JSON round-trip")


def test_blockers_flagged(tmp_path):
    lib = tmp_path / "broken"
    (lib / "x").mkdir(parents=True)
    # references a sample that does not exist -> missing_samples blocker
    (lib / "ghost.sfz").write_text(
        "<region> sample=nope.wav key=60 pitch_keycenter=60\n")
    # uses #include -> uses_include blocker (engine can't follow it)
    (lib / "inc.sfz").write_text('#include "other.sfz"\n<region> sample=a.wav\n')
    cat = Catalog.build(tmp_path)
    ghost = cat.instrument("ghost")
    assert not ghost.renderable and "missing_samples" in ghost.render_blockers
    inc = cat.instrument("inc")
    assert not inc.renderable and "uses_include" in inc.render_blockers
    assert cat.find(renderable=True) == []
    print("PASS  catalog: missing-sample and #include patches flagged "
          "non-renderable")


def test_sdk_catalog_against_installed_libraries():
    """Opportunistic: only runs where libraries/ has been provisioned."""
    libdir = ROOT / "libraries"
    if not libdir.is_dir() or not any(libdir.rglob("*.sfz")):
        print("  SKIP installed-libraries check: no libraries/ present")
        return
    cat = AudioForge().catalog(libdir)
    assert len(cat) > 0
    assert all(i.renderable for i in cat.renderable())
    # every library's pin is either a 64-hex string or None (no manifest yet)
    for lib in cat.libraries:
        assert lib.pin is None or (len(lib.pin) == 64)
    print(f"PASS  catalog: {len(cat)} instruments across "
          f"{len(cat.libraries)} installed libraries, "
          f"{len(cat.renderable())} renderable")


if __name__ == "__main__":
    import tempfile
    for fn in (test_build_query_and_roundtrip, test_blockers_flagged):
        with tempfile.TemporaryDirectory() as td:
            fn(Path(td))
    test_sdk_catalog_against_installed_libraries()
    print("\nAll catalog SDK tests passed.")
