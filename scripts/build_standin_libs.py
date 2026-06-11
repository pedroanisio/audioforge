"""Build CC0-backed stand-in libraries for the test fixtures.

The fixtures (bwv949 / cancoes_sertao / unser_leben) pin three commercial
libraries that ship nothing in this repo: vstobaroque (harpsichord),
vstocello (cello) and vstochoral (the SATB voices). Those are not
downloadable. To render the fixtures *as written* — same library names,
same instrument names, real hash-verified audio — we synthesize local
stand-ins from the CC0 VSCO-2-CE violin-ensemble sustain samples that
scripts/fetch_vsco_subset.py already fetched. Timbre is borrowed strings
(pitch-shifted across each voice's range), not the real instruments, but
every byte is pinned and the render path is exercised end to end.

Run from the repo root, AFTER fetch_vsco_subset.py:
    python3 scripts/build_standin_libs.py
It prints one `name@<pin>` line per library; those pins go into the fixtures.
"""
import shutil
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from audioforge.library import generate_manifest  # noqa: E402

ROOT = Path("libraries")
VSCO = ROOT / "vsco2-ce-subset" / "susvib"

# The 7 sampled keycenters of the VSCO violin-ensemble sustain patch.
NOTES = ["G2", "D3", "A3", "C4", "E4", "G4", "B4"]
MIDI = {"G2": 43, "D3": 50, "A3": 57, "C4": 60, "E4": 64, "G4": 67, "B4": 71}


def ranges(midis):
    """Key ranges as midpoints between sampled keycenters; the extremes
    open out to 0 / 127 so every note in a fixture resolves (far notes just
    pitch-shift from the nearest sample)."""
    ms = sorted(midis)
    out = {}
    for i, m in enumerate(ms):
        lo = 0 if i == 0 else (ms[i - 1] + m) // 2 + 1
        hi = 127 if i == len(ms) - 1 else (m + ms[i + 1]) // 2
        out[m] = (lo, hi)
    return out


R = ranges(MIDI.values())


def sustain_sfz(release=0.4):
    """A sustain region map over the 7 keycenters, two velocity layers each,
    referencing the WAVs copied into this library's samples/ dir."""
    lines = ["<global> ampeg_attack=0.02"]
    for n in NOTES:
        m = MIDI[n]
        lo, hi = R[m]
        for v, (lv, hv) in ((1, (1, 63)), (2, (64, 127))):
            lines.append(
                f"<region> sample=samples/VlnEns_susVib_{n}_v{v}.wav "
                f"lokey={lo} hikey={hi} pitch_keycenter={m} "
                f"lovel={lv} hivel={hv} ampeg_release={release}")
    return "\n".join(lines) + "\n"


# library name -> {instrument: per-instrument SFZ filename}, release tuned a
# little per family just so they aren't byte-identical libraries.
LIBS = {
    "vstobaroque": ({"harpsichord": "harpsichord.sfz"}, 0.25),
    "vstocello": ({"cello": "cello.sfz"}, 0.5),
    "vstochoral": ({
        "soprano": "soprano.sfz", "mezzo_soprano": "mezzo_soprano.sfz",
        "countertenor": "countertenor.sfz", "tenor": "tenor.sfz",
        "bass": "bass.sfz"}, 0.6),
}


def build():
    if not VSCO.is_dir():
        sys.exit("run scripts/fetch_vsco_subset.py first (no VSCO susvib dir)")
    wavs = sorted(VSCO.glob("*.wav"))
    pins = {}
    for lib, (instruments, release) in LIBS.items():
        d = ROOT / lib
        samples = d / "samples"
        samples.mkdir(parents=True, exist_ok=True)
        for w in wavs:
            shutil.copy2(w, samples / w.name)
        sfz = sustain_sfz(release)
        for fname in set(instruments.values()):
            (d / fname).write_text(sfz)
        m = generate_manifest(d, name=lib, version="1.0.0",
                              license_str="CC0-1.0")
        pins[lib] = m["manifest_sha256"]
        print(f"{lib}@{m['manifest_sha256']}  "
              f"({len(m['files'])} files, {len(m['instruments'])} instruments)")
    return pins


if __name__ == "__main__":
    build()
