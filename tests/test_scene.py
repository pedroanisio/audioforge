"""scene-render integration: resolve <generated provider="audioforge"> and scene add."""
import json
import xml.etree.ElementTree as ET

import pytest

from audioforge.cli import main
from audioforge.cues import sidecar_path
from audioforge.scene import (SceneError, add_cue, generated_snippet, resolve_scene)

ZERO = "0" * 64

SCENE = f"""<?xml version="1.0" encoding="UTF-8"?>
<!-- hand-written comment that must survive -->
<scene version="1.1">
  <project width="640" height="360" fps="24" duration="12" seed="1"/>
  <assets>
    <audio id="vo" src="vo.wav" duration="3"/>
    <generated id="bed" kind="music" provider="audioforge"
               model="bed/ambient-calm" prompt="duration=auto intensity=0.2"
               seed="4" cache="gen/bed.wav" cacheSha256="{ZERO}"/>
    <generated id="hit" kind="sound-effect" provider="audioforge" model="ui/click"
               cache="gen/hit.wav" cacheSha256="{ZERO}"/>
    <generated id="tts" kind="speech" provider="elsewhere" model="x" cache="t.wav" cacheSha256="{ZERO}"/>
  </assets>
  <audioMix sampleRate="48000" channels="2" bitDepth="16">
    <audioTrack id="t-bed" asset="bed" role="music" start="2"/>
  </audioMix>
</scene>
"""


def _attr(path, aid, name):
    root = ET.parse(path).getroot()
    return next(el for el in root.iter("generated") if el.get("id") == aid).get(name)


@pytest.fixture()
def scene(tmp_path):
    p = tmp_path / "scene.xml"
    p.write_text(SCENE)
    return p


def test_resolve_renders_pins_and_preserves_document(scene):
    res = {r.asset_id: r for r in resolve_scene(scene)}
    assert set(res) == {"bed", "hit"}                      # other providers untouched
    assert res["bed"].status == res["hit"].status == "rendered"
    assert res["bed"].params["duration"] == 10.0           # auto: 12 s project - 2 s start
    assert res["bed"].params["seed"] == 4
    text = scene.read_text()
    assert "hand-written comment that must survive" in text
    assert _attr(scene, "tts", "cacheSha256") == ZERO
    for aid in ("bed", "hit"):
        sha = _attr(scene, aid, "cacheSha256")
        assert sha == res[aid].sha256 and sha != ZERO
    side = json.loads(sidecar_path(scene.parent / "gen/bed.wav").read_text())
    assert side["bit_depth"] == 16 and side["duration_s"] == 10.0


def test_resolve_is_incremental_and_check_detects_staleness(scene):
    resolve_scene(scene)
    assert {r.status for r in resolve_scene(scene)} == {"up-to-date"}
    assert {r.status for r in resolve_scene(scene, check=True)} == {"up-to-date"}
    scene.write_text(scene.read_text().replace("intensity=0.2", "intensity=0.9"))
    before = scene.read_text()
    res = {r.asset_id: r.status for r in resolve_scene(scene, check=True)}
    assert res == {"bed": "stale", "hit": "up-to-date"}
    assert scene.read_text() == before                     # check never writes
    assert {r.status for r in resolve_scene(scene)} == {"rendered", "up-to-date"}


def test_attribute_only_drift_is_repinned_without_rendering(scene):
    resolve_scene(scene)
    good = _attr(scene, "hit", "cacheSha256")
    scene.write_text(scene.read_text().replace(good, ZERO))
    res = {r.asset_id: r.status for r in resolve_scene(scene)}
    assert res["hit"] == "pinned" and _attr(scene, "hit", "cacheSha256") == good


def test_errors_are_reported_per_asset(scene):
    scene.write_text(scene.read_text().replace('model="ui/click"', 'model="ui/nope"'))
    res = {r.asset_id: r for r in resolve_scene(scene)}
    assert res["hit"].status == "error" and "unknown cue" in res["hit"].message
    assert res["bed"].status == "rendered"


def test_add_cue_inserts_asset_and_track(tmp_path):
    p = tmp_path / "scene.xml"
    p.write_text(SCENE)
    add_cue(p, "transition/whoosh", "duration=0.5", asset_id="swoosh", start=4.25,
            gain_db=-6, bus=None, resolve=False)
    root = ET.parse(p).getroot()
    gen = next(el for el in root.iter("generated") if el.get("id") == "swoosh")
    assert gen.get("model") == "transition/whoosh" and gen.get("prompt") == "duration=0.5"
    trk = next(el for el in root.iter("audioTrack") if el.get("asset") == "swoosh")
    assert trk.get("start") == "4.25" and trk.get("gain") == "-6.0" and trk.get("role") == "effects"
    assert "    <generated id=\"swoosh\"" in p.read_text()          # indented like siblings
    with pytest.raises(SceneError, match="already exists"):
        add_cue(p, "transition/whoosh", asset_id="swoosh", resolve=False)


def test_add_cue_creates_audiomix_and_resolves(tmp_path):
    p = tmp_path / "scene.xml"
    p.write_text('<scene version="1.1">\n  <project duration="6"/>\n  <assets>\n  </assets>\n</scene>\n')
    res = add_cue(p, "bed/news-pulse", "intensity=0.3", asset_id="m")
    assert res[0].status == "rendered" and res[0].params["duration"] == 6.0
    root = ET.parse(p).getroot()
    assert root.find("audioMix/audioTrack").get("asset") == "m"


def test_generated_snippet_defaults():
    s = generated_snippet("bed/cinematic-epic", "key='E minor' seed=3", asset_id="m")
    el = ET.fromstring(s)
    assert el.get("provider") == "audioforge" and el.get("kind") == "music"
    assert el.get("prompt") == "key='E minor' duration=auto" and el.get("seed") == "3"
    assert el.get("cacheSha256") == ZERO


def test_cli_cue_and_scene(scene, tmp_path, capsys):
    assert main(["cue", "list", "--category", "sting"]) == 0
    assert "sting/logo" in capsys.readouterr().out
    assert main(["cue", "show", "ui/click"]) == 0
    assert json.loads(capsys.readouterr().out)["id"] == "ui/click"
    assert main(["cue", "dsl", "ui/pop", "pitch=1200"]) == 0
    assert "from: 1200.0hz" in capsys.readouterr().out
    wav = tmp_path / "c.wav"
    assert main(["cue", "render", "ui/click", "-o", str(wav), "--snippet", "audio", "--id", "clk"]) == 0
    out = capsys.readouterr().out
    assert wav.is_file() and '<audio id="clk"' in out and "<audioTrack" in out
    assert main(["scene", "resolve", "--check", str(scene)]) == 3      # stale -> 3
    assert main(["scene", "resolve", str(scene)]) == 0
    assert main(["scene", "resolve", "--check", str(scene)]) == 0
    assert main(["cue", "render", "ui/nope", "-o", str(wav)]) == 1


def test_cli_cue_gallery(tmp_path, capsys):
    assert main(["cue", "gallery", "-o", str(tmp_path / "g"), "--category", "ui"]) == 0
    page = (tmp_path / "g" / "index.html").read_text()
    assert "ui/click" in page and "ui__pop.wav" in page
    assert (tmp_path / "g" / "ui__click.wav").is_file()
