"""Drift-map Finding #12 — content-addressed library pins must hold the line.

A `library.manifest.json` pins every byte (samples + SFZ) and the instrument
mapping under `manifest_sha256`; specs reference `library: "name@pin"`, and the
pin folds into the spec hash. `test_sampler.py::test_manifest_pin_and_tamper`
already covers a tampered *sample byte* and an *edited manifest*. This locks the
remaining sub-couplings the report names ("library bytes/SFZ ↔ manifest ↔ spec
pins"):

  * a spec pin that does not match the manifest hash is rejected;
  * a file present on disk but absent from the manifest is refused (every byte
    that can affect output must be pinned);
  * the manifest hash is a deterministic, order-independent codegen — so the
    same library always produces the same pin.

#12 is rated LOW precisely because these are loud runtime errors; these tests
keep them that way.
"""
import hashlib
import wave
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("numpy")
from audioforge import library as lib  # noqa: E402

SR = 44100
NAME = "pinlib"          # distinct from test_sampler's "minilib"


def _write_wav(path: Path, freq: float, dur: float = 0.5) -> None:
    t = np.arange(int(dur * SR)) / SR
    x = np.sin(2 * np.pi * freq * t) * 0.6
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((x * 30000).astype("<i2").tobytes())


def _build(root: Path) -> dict:
    (root / "wavs").mkdir(parents=True)
    _write_wav(root / "wavs/c4.wav", 261.626)
    (root / "inst.sfz").write_text(
        "<control> default_path=wavs/\n"
        "<group> lokey=48 hikey=72 pitch_keycenter=60\n"
        "<region> sample=c4.wav lovel=1 hivel=127\n"
    )
    m = lib.generate_manifest(root, name=NAME, version="1.0.0",
                              license_str="CC0-1.0")
    lib.add_library_path(root.parent)
    return m


@pytest.fixture
def manifest(tmp_path: Path) -> dict:
    return _build(tmp_path / NAME)


# --------------------------------------------------------------- spec pin ----

def test_correct_pin_loads_and_reads(manifest):
    loaded = lib.load_library(f"{NAME}@{manifest['manifest_sha256']}")
    x, sr = loaded.audio("wavs/c4.wav")
    assert sr == SR and x.size > 0


def test_wrong_pin_is_rejected(manifest):
    """A spec pin that doesn't match the manifest hash must not resolve."""
    wrong = "0" * 64
    assert wrong != manifest["manifest_sha256"]
    with pytest.raises(ValueError) as e:
        lib.load_library(f"{NAME}@{wrong}")
    assert "not found" in str(e.value)


def test_short_prefix_pin_still_matches(manifest):
    """Short pins are allowed as long as they prefix the real hash."""
    short = manifest["manifest_sha256"][:12]
    loaded = lib.load_library(f"{NAME}@{short}")
    assert loaded.manifest["name"] == NAME


# ----------------------------------------------------------- byte pinning ----

def test_unpinned_file_is_refused(tmp_path, manifest):
    """A file on disk but absent from the manifest must be refused — every
    output-affecting byte has to be pinned."""
    root = tmp_path / NAME
    (root / "wavs/rogue.wav").write_bytes(b"")          # never pinned
    loaded = lib.Library(root, manifest)
    with pytest.raises(ValueError) as e:
        loaded.audio("wavs/rogue.wav")
    assert "not in the manifest" in str(e.value)


def test_tampered_sample_is_refused(tmp_path, manifest):
    root = tmp_path / NAME
    p = root / "wavs/c4.wav"
    raw = bytearray(p.read_bytes())
    raw[200] ^= 0xFF
    p.write_bytes(bytes(raw))
    loaded = lib.Library(root, manifest)
    with pytest.raises(ValueError) as e:
        loaded.audio("wavs/c4.wav")
    assert "hash mismatch" in str(e.value)


# ------------------------------------------------------- canonical codegen ---

def test_manifest_hash_is_order_independent(manifest):
    reordered = dict(manifest)
    reordered["files"] = list(reversed(manifest["files"]))
    assert (lib._canonical_manifest_hash(reordered)
            == lib._canonical_manifest_hash(manifest)
            == manifest["manifest_sha256"]), (
        "manifest hash must not depend on file ordering (Finding #12 codegen)"
    )


def test_regeneration_is_deterministic(tmp_path, manifest):
    """Regenerating the manifest over unchanged bytes yields the same pin."""
    root = tmp_path / NAME
    again = lib.generate_manifest(root, name=NAME, version="1.0.0",
                                  license_str="CC0-1.0")
    assert again["manifest_sha256"] == manifest["manifest_sha256"]


def test_remapping_an_instrument_changes_the_pin(tmp_path, manifest):
    """Pointing an instrument at a different SFZ changes rendered audio, so it
    must change the hash (the doctrine the manifest extends)."""
    remapped = {
        **manifest,
        "instruments": {"inst": {"sfz": "inst.sfz",
                                 "articulations": {"sustain": "other.sfz"}}},
    }
    assert (lib._canonical_manifest_hash(remapped)
            != manifest["manifest_sha256"])


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-q"]))
