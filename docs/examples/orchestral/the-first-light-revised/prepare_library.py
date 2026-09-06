"""Assemble pinned local recordings for the revised demonstration.

Download the author's educational archive separately; never fabricate intervals
or distribute these recordings as a newly licensed sample library.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import zipfile

from audioforge.library import generate_manifest

ROOT = Path(__file__).resolve().parents[4]
NAME = 'FirstLight-Orchestra'
DEST = ROOT / 'libraries' / NAME


def prepare(archive):
    original = ROOT / 'libraries/VSCO-2-CE-1.1.0'
    base = json.loads((original/'library.manifest.json').read_text())
    DEST.mkdir(exist_ok=True)
    # Link only immutable, independently pinned source files. No original is edited.
    for item in base['files']:
        source, target = original/item['path'], DEST/item['path']
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            os.link(source, target)
    prefix = 'SFZ Viola True Legato Demo/Samples/'
    with zipfile.ZipFile(archive) as z:
        for name in z.namelist():
            if name.startswith(prefix) and name.endswith('.wav'):
                dest = DEST/'Hilowitz'/Path(name).name
                dest.parent.mkdir(exist_ok=True)
                data = z.read(name)
                if dest.exists():
                    assert dest.read_bytes() == data
                else:
                    dest.write_bytes(data)
    notes = [('D3', 50), ('E3', 52), ('F3', 53), ('G3', 55), ('A3', 57)]
    sfz = '\n'.join(f'<region> sample=Hilowitz/LV_Sustain_{n}.wav key={m} ampeg_attack=0.01 ampeg_release=0.18'
                    for n, m in notes)
    (DEST/'ViolaRecorded.sfz').write_text(sfz+'\n')
    transitions = []
    # Offsets and arrival anchors were checked on the original stereo waveforms
    # and spectrograms. Unlike the tutorial's single offset, these follow each take.
    for (n0, m0), (n1, m1), trim, arrival in zip(notes, notes[1:], [.96,.90,1.04,.90], [1.09,1.06,1.13,1.00]):
        transitions.append(dict(from_midi=m0, to_midi=m1,
            sample=f'Hilowitz/LV_Legato_{n0}_{n1}.wav', offset_frames=round(trim*48000),
            lead_s=round(arrival-trim, 5), crossfade_s=.025, release_s=.18,
            provenance=dict(source_url='https://www.youtube.com/watch?v=j9OfaBw4n0c',
                description=f'David Hilowitz, SFZ Viola True Legato Demo (2021): recorded {n0} to {n1}, including destination sustain.',
                archive_url='https://www.dropbox.com/s/e205qd88tpx3atp/SFZ%20Viola%20True%20Legato%20Demo.zip?dl=1',
                archive_sha256=hashlib.sha256(Path(archive).read_bytes()).hexdigest())))
    instruments = dict(base['instruments'])
    instruments['ViolaRecorded'] = dict(sfz='ViolaRecorded.sfz', articulations={'sustain':'ViolaRecorded.sfz'}, recorded_transitions=transitions)
    manifest = generate_manifest(DEST, name=NAME, version='1.0.0',
        license_str='Mixed: VSCO recordings CC0-1.0; Hilowitz publicly distributed educational demo, no separate redistribution license supplied',
        instruments=instruments)
    print(json.dumps(dict(name=NAME, pin=manifest['manifest_sha256'], transition_intervals=4),indent=2))
    return manifest


if __name__ == '__main__':
    prepare(sys.argv[1])
