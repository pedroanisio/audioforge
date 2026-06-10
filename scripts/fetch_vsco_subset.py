"""Fetch a small CC0 subset of VSCO 2 CE and build SFZ maps for it.
License verified at repo root: CC0 1.0 Universal (fetched 2026-06-10)."""
import urllib.request, urllib.parse, pathlib, sys, time

BASE = "https://raw.githubusercontent.com/sgossner/VSCO-2-CE/master/"
ROOT = pathlib.Path("libraries/vsco2-ce-subset")
for sub in ("susvib", "spic", "timpani"):
    (ROOT / sub).mkdir(parents=True, exist_ok=True)
NOTES = ["G2", "D3", "A3", "C4", "E4", "G4", "B4"]
MIDI = {"G2": 43, "D3": 50, "A3": 57, "C4": 60, "E4": 64, "G4": 67, "B4": 71}

jobs = []
for n in NOTES:
    for v in (1, 2):
        jobs.append((f"Strings/Violin Section/susVib/VlnEns_susVib_{n}_v{v}.wav",
                     ROOT / f"susvib/VlnEns_susVib_{n}_v{v}.wav"))
    for rr in (1, 2):
        jobs.append((f"Strings/Violin Section/Spic/VlnEns_Spic_{n}_v2_rr{rr}.wav",
                     ROOT / f"spic/VlnEns_Spic_{n}_v2_rr{rr}.wav"))
for v in (1, 3, 4):
    for rr in (1, 2):
        jobs.append((f"Percussion/Timpani/Timpani3_Hit_v{v}_rr{rr}_Sum.wav",
                     ROOT / f"timpani/Timpani3_Hit_v{v}_rr{rr}_Sum.wav"))

ok = fail = 0
for rel, dest in jobs:
    if dest.exists() and dest.stat().st_size > 1000:
        ok += 1; continue
    url = BASE + urllib.parse.quote(rel)
    try:
        with urllib.request.urlopen(url, timeout=25) as r:
            dest.write_bytes(r.read())
        ok += 1
    except Exception as e:
        print("FAIL", rel, e); fail += 1
    time.sleep(0.1)
print(f"fetched {ok}/{len(jobs)} (fail {fail})")

# --- SFZ maps from the filename convention -------------------------------
def ranges(midis):
    """key ranges as midpoints between sampled keycenters"""
    ms = sorted(midis)
    out = {}
    for i, m in enumerate(ms):
        lo = 0 if i == 0 else (ms[i-1] + m) // 2 + 1
        hi = 127 if i == len(ms)-1 else (m + ms[i+1]) // 2
        out[m] = (lo, hi)
    return out

R = ranges(MIDI.values())
def region(path, m, lovel, hivel, rr=None, seqlen=None, rel=0.25):
    ops = (f"<region> sample={path} lokey={R[m][0]} hikey={R[m][1]} "
           f"pitch_keycenter={m} lovel={lovel} hivel={hivel} "
           f"ampeg_release={rel}")
    if rr: ops += f" seq_length={seqlen} seq_position={rr}"
    return ops

sus = ["<global> ampeg_attack=0.005"]
spic = ["<global> ampeg_attack=0.001"]
for n in NOTES:
    m = MIDI[n]
    sus.append(region(f"susvib/VlnEns_susVib_{n}_v1.wav", m, 1, 63, rel=0.4))
    sus.append(region(f"susvib/VlnEns_susVib_{n}_v2.wav", m, 64, 127, rel=0.4))
    for rr in (1, 2):
        spic.append(region(f"spic/VlnEns_Spic_{n}_v2_rr{rr}.wav",
                           m, 1, 127, rr=rr, seqlen=2, rel=0.15))
timp = ["<global> ampeg_attack=0.001 lokey=0 hikey=127 pitch_keycenter=50"]
for vel, (lo, hi) in {1: (1, 50), 3: (51, 95), 4: (96, 127)}.items():
    for rr in (1, 2):
        timp.append(f"<region> sample=timpani/Timpani3_Hit_v{vel}_rr{rr}_Sum.wav "
                    f"lokey=0 hikey=127 pitch_keycenter=50 lovel={lo} "
                    f"hivel={hi} seq_length=2 seq_position={rr} "
                    f"ampeg_release=0.6")
(ROOT / "violins_sustain.sfz").write_text("\n".join(sus) + "\n")
(ROOT / "violins_spiccato.sfz").write_text("\n".join(spic) + "\n")
(ROOT / "timpani.sfz").write_text("\n".join(timp) + "\n")
print("sfz maps written")
