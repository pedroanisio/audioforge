"""Behavioral regressions for scene insertion and cache validation."""
import json
import xml.etree.ElementTree as ET

import pytest

from audioforge.cues import sidecar_path
from audioforge.scene import add_cue, resolve_scene


def test_add_cue_ignores_commented_closing_tags(tmp_path):
    comment = '<!-- café layout:\n<assets>\n</assets>\n<audioMix>\n</audioMix>\n-->'
    scene = tmp_path / 'scene.xml'
    scene.write_text(f'<scene>\n<project duration="12"/>\n<assets>\n</assets>\n'
                     f'<audioMix>\n</audioMix>\n{comment}\n</scene>')
    results = add_cue(scene, 'ui/click')
    root = ET.parse(scene).getroot()
    assert root.find('assets/generated').get('model') == 'ui/click'
    assert root.find('audioMix/audioTrack').get('asset') == 'ui-click'
    assert len(results) == 1 and results[0].status == 'rendered'
    assert comment in scene.read_text()
    assert resolve_scene(scene, check=True)[0].status == 'up-to-date'


def _shared_scene(path, second_model='ui/pop'):
    path.write_text(f'''<scene><assets>
<generated id="a" kind="sound-effect" provider="audioforge" model="ui/click" cache="shared.wav"/>
<generated id="b" kind="sound-effect" provider="audioforge" model="{second_model}" cache="./shared.wav"/>
</assets></scene>''')


@pytest.mark.parametrize('check', [False, True])
def test_conflicting_cache_paths_rejected_before_writes(tmp_path, check):
    scene = tmp_path / 'scene.xml'
    _shared_scene(scene)
    before = scene.read_bytes()
    cache = tmp_path / 'shared.wav'
    cache.write_bytes(b'original audio')
    side = sidecar_path(cache)
    side.write_text('{"original": true}')
    results = resolve_scene(scene, check=check)
    assert [r.status for r in results] == ['error', 'error']
    assert all('cache' in r.message and 'conflict' in r.message for r in results)
    assert scene.read_bytes() == before
    assert cache.read_bytes() == b'original audio'
    assert side.read_text() == '{"original": true}'


def test_identical_requests_can_share_cache(tmp_path):
    scene = tmp_path / 'scene.xml'
    _shared_scene(scene, 'ui/click')
    results = resolve_scene(scene)
    assert [r.status for r in results] == ['rendered', 'pinned']
    assert results[0].sha256 == results[1].sha256
    assert [r.status for r in resolve_scene(scene, check=True)] == ['up-to-date'] * 2


@pytest.mark.parametrize('invalid_info', [[], None, 'bad', 42, {}])
def test_invalid_sidecar_shape_is_stale_and_recoverable(tmp_path, invalid_info):
    scene = tmp_path / 'scene.xml'
    scene.write_text('<scene><assets><generated id="a" kind="sound-effect" '
                     'provider="audioforge" model="ui/click" cache="a.wav"/></assets></scene>')
    resolve_scene(scene)
    side = sidecar_path(tmp_path / 'a.wav')
    side.write_text(json.dumps(invalid_info))
    before = scene.read_bytes(), side.read_bytes()
    assert resolve_scene(scene, check=True)[0].status == 'stale'
    assert (scene.read_bytes(), side.read_bytes()) == before
    assert resolve_scene(scene)[0].status == 'rendered'
    assert resolve_scene(scene, check=True)[0].status == 'up-to-date'
