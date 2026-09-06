"""The five electronic-production tracks compile, validate, and use every construct
ADR-0015 added (docs/ELECTRONIC_TRACKS.md). Rendering them is a documented manual
step (minutes); compiling is the cheap, standing proof that the specs stay valid."""
from pathlib import Path

import pytest

from audioforge import AudioForge
from audioforge.dsl import compile_dsl

ROOT = Path(__file__).resolve().parent.parent
HOUSE = ROOT / "docs" / "examples" / "electronic"
TRACKS = sorted(HOUSE.glob("house-0[1-5]-*/house_0[1-5]_*.af"))


def _fx_types(spec):
    out = set()
    for holder in list(spec["layers"]) + list(spec.get("buses", [])) + [spec.get("master", {})]:
        out |= {f["type"] for f in holder.get("fx", [])}
    return out


def test_five_tracks_exist_and_validate_render_ready():
    assert len(TRACKS) == 5, [p.name for p in TRACKS]
    for path in TRACKS:
        res = AudioForge().compile(path.read_text())
        assert res.ok, (path.name, [d.message for d in res.diagnostics if d.severity == "error"])
        assert not [d for d in res.assets[0].validate() if d.severity == "error"], path.name


def test_tracks_cover_every_new_construct():
    specs = {p.stem: compile_dsl(p.read_text())[0][0] for p in TRACKS}
    fx = {name: _fx_types(s) for name, s in specs.items()}
    assert {"phaser", "flanger", "chorus", "bitcrush"} <= fx["house_04_phase"]
    assert "chorus" in fx["house_01_filter"] and "bitcrush" in fx["house_03_chop"]
    assert any("vocoder" in b for b in specs["house_02_robot"]["buses"])
    assert any("duck" in b for b in specs["house_01_filter"]["buses"])
    chop = {l["name"]: l for l in specs["house_03_chop"]["layers"] if l["type"] == "sample"}
    assert chop["chops"]["slices"] == 16 and chop["stutter"]["offset_s"] > 0 and chop["stutter"]["length_s"] > 0
    assert chop["reverse_swell"]["reverse"] is True and chop["reverse_swell"]["stretch"] == 2.0
    assert chop["halftime"]["pitch_st"] == -12.0
    full = specs["house_05_full"]
    assert {"phaser", "flanger", "chorus", "bitcrush"} <= fx["house_05_full"]
    assert any("vocoder" in b for b in full["buses"]) and full.get("key_map") and full.get("tempo_map")
    assert len(full["score"]["sections"]) == 7
    assert all(l["sha256"] == chop["chops"]["sha256"] for l in full["layers"] if l["type"] == "sample")


def test_source_loop_sample_is_the_pinned_one():
    import hashlib
    wav = ROOT / "samples" / "house_source_loop.wav"
    chop = compile_dsl((HOUSE / "house-03-chop" / "house_03_chop.af").read_text())[0][0]
    pinned = {l["sha256"] for l in chop["layers"] if l["type"] == "sample"}
    assert pinned == {hashlib.sha256(wav.read_bytes()).hexdigest()}
    src = AudioForge().compile((HOUSE / "house-00-source-loop" / "house_00_source_loop.af").read_text())
    assert src.ok, src.diagnostics
