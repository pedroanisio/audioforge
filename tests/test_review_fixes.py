"""Regressions for cold-cache builds, empty duck buses and scene resolution."""
from concurrent.futures import ThreadPoolExecutor
import subprocess
import threading
import xml.etree.ElementTree as ET

import numpy as np
import pytest

from audioforge import AudioForge, _native
from audioforge.render import render
from audioforge.scene import _request, resolve_scene


def test_concurrent_native_builds_publish_complete_outputs(tmp_path, monkeypatch):
    monkeypatch.setenv('AUDIOFORGE_NATIVE_CACHE', str(tmp_path))
    monkeypatch.setattr(_native.shutil, 'which', lambda name: '/fake/cc')
    barrier = threading.Barrier(8)

    def compile_kernel(args, **kwargs):
        from pathlib import Path
        output = Path(args[args.index('-o') + 1])
        barrier.wait(timeout=10)
        output.write_bytes(b'complete kernel')

    monkeypatch.setattr(_native.subprocess, 'run', compile_kernel)
    with ThreadPoolExecutor(max_workers=8) as pool:
        outputs = list(pool.map(lambda _: _native._build('upfirdn', 'test'), range(8)))
    assert len(set(outputs)) == 1
    assert outputs[0].read_bytes() == b'complete kernel'
    assert not list(tmp_path.glob('*.tmp.so'))


def test_failed_native_compile_cleans_temporary_output(tmp_path, monkeypatch):
    monkeypatch.setenv('AUDIOFORGE_NATIVE_CACHE', str(tmp_path))
    monkeypatch.setattr(_native.shutil, 'which', lambda name: '/fake/cc')

    def fail(args, **kwargs):
        raise subprocess.CalledProcessError(1, args)

    monkeypatch.setattr(_native.subprocess, 'run', fail)
    with pytest.raises(subprocess.CalledProcessError):
        _native._build('upfirdn', 'test')
    assert not list(tmp_path.iterdir())


def test_unused_duck_source_bus_matches_unducked_audio():
    forge = AudioForge()
    source = '''asset review { kind: cue
 duration: 0.5s
 tempo: 120bpm
 bus voice { gain: 0db }
 bus music { duck: source=bus:voice amount=6db }
 layer pad : notes { osc: sine
  bus: music
  notes: E4 @ 0b for 1b }
}'''
    ducked = forge.compile(source)
    plain = forge.compile(source.replace('duck: source=bus:voice amount=6db', 'gain: 0db'))
    assert ducked.ok and plain.ok
    a = render(ducked.assets[0].spec)
    b = render(plain.assets[0].spec)
    np.testing.assert_array_equal(a[0], b[0])


def test_resolve_pins_live_tag_and_preserves_commented_example(tmp_path):
    zero = '0' * 64
    comment = f'<!-- café example: <generated id="hit" cacheSha256="{zero}"/> -->'
    scene = tmp_path / 'scene.xml'
    scene.write_text(f'''<scene><project duration="12"/><assets>
{comment}
<generated id="hit" kind="sound-effect" provider="audioforge" model="ui/click"
 prompt="" cache="hit.wav" cacheSha256="{zero}"/>
</assets></scene>''')
    result = resolve_scene(scene)[0]
    assert result.status == 'rendered'
    assert ET.parse(scene).find('assets/generated').get('cacheSha256') == result.sha256
    assert comment in scene.read_text()
    assert resolve_scene(scene, check=True)[0].status == 'up-to-date'


@pytest.mark.parametrize('tracks,expected', [
    ('<audioTrack asset="bed" start="2" clipIn="4"/>', 14),
    ('<audioTrack asset="bed" start="8"/><audioTrack asset="bed" start="0"/>', 12),
    ('<audioTrack asset="bed" start="0"/><audioTrack asset="bed" start="2" clipIn="4"/>', 14),
    ('', 12),
])
def test_auto_duration_covers_all_track_source_ranges(tracks, expected):
    root = ET.fromstring(f'''<scene><project duration="12"/>
<assets><generated id="bed" model="bed/ambient-calm"/></assets>
<audioMix>{tracks}</audioMix></scene>''')
    assert _request(root, root.find('assets/generated'))[1]['duration'] == expected
