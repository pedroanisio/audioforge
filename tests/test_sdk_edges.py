import json
import importlib

import pytest

from audioforge import sdk
from audioforge.schema import SpecError


def _spec(asset_id="sdk_asset") -> dict:
    return {
        "id": asset_id,
        "kind": "cue",
        "duration_s": 1.0,
        "layers": [{
            "name": "tone",
            "type": "tone",
            "freq_hz": 440.0,
            "env": {"attack": 0.01, "decay": 0.1, "sustain": 0.8, "release": 0.1},
        }],
        "master": {"target_peak_dbfs": -1.0},
    }


def _notes_spec(asset_id="sdk_notes") -> dict:
    spec = _spec(asset_id)
    spec["layers"] = [{
        "name": "notes",
        "type": "notes",
        "osc": "sine",
        "env": {"attack": 0.01, "decay": 0.1, "sustain": 0.8, "release": 0.1},
        "notes": [{"note": "C4", "start_beat": 0.0, "dur_beats": 1.0}],
    }]
    return spec


def test_diagnostic_and_asset_mutation_helpers():
    diag = sdk.Diagnostic("warning", "careful", "layers.0")
    assert diag.as_dict() == {
        "severity": "warning", "message": "careful", "path": "layers.0", "code": None,
    }   # `code` is part of the envelope since ADR-0008

    asset = sdk.AudioAsset(_spec())
    assert asset.id == "sdk_asset"
    assert asset.variant("b").spec["variant"] == "b"
    assert asset.with_intensity("0.7").spec["intensity_scale"] == 0.7
    assert asset.set("layers.0.gain_db", -6).spec["layers"][0]["gain_db"] == -6
    clone = asset.mutated("layers.0.pan", 0.25, new_id="clone")
    assert clone.id == "clone"
    assert asset.id == "sdk_asset"

    assert json.loads(asset.to_json())["id"] == "sdk_asset"
    assert "asset sdk_asset" in asset.to_dsl()
    assert asset.to_midi().startswith(b"MThd")
    assert "<score-partwise" in asset.to_musicxml()
    assert sdk.AudioAsset.from_json(asset.to_json()).id == "sdk_asset"


def test_asset_validation_and_resolve_errors_are_structured():
    invalid = sdk.AudioAsset({"id": "bad"})
    errors = invalid.validate()
    assert errors[0].severity == "error"
    assert "kind" in errors[0].message

    unresolved = _spec("unresolved")
    unresolved["layers"] = [{
        "name": "sample",
        "type": "sample",
        "file": "missing.wav",
        "sha256": "a" * 64,
    }]
    asset = sdk.AudioAsset(unresolved)
    with pytest.raises(SpecError, match="unresolved resources"):
        asset.render()


def test_export_preview_analyze_and_plugin_exporters(monkeypatch, tmp_path):
    calls = []

    def fake_render_to_wav(spec, out_dir, stems=False):
        calls.append((spec["id"], stems))
        manifest = tmp_path / f"{spec['id']}.manifest.json"
        manifest.write_text("{}")
        return {"id": spec["id"], "file": f"{spec['id']}.wav", "spec_hash": "h"}

    def fake_render(spec, return_stems=False):
        return [[0.0, 0.0]], 48000, {}

    monkeypatch.setattr(sdk, "render_to_wav", fake_render_to_wav)
    monkeypatch.setattr(sdk, "render", fake_render)
    monkeypatch.setattr("audioforge.analysis.analyze_audio", lambda stereo, sr, context=None: {"peak_dbfs": -3})
    monkeypatch.setattr(sdk, "EXPORTERS", {
        "sidecar": lambda spec, meta, out: str(out / f"{spec['id']}.sidecar"),
    })

    asset = sdk.AudioAsset(_spec())
    meta = asset.export(tmp_path, preset="social_video", stems=True, analyze=True)
    assert meta["id"] == "sdk_asset__social_video"
    assert meta["analysis"] == {"peak_dbfs": -3}
    assert "sidecar" in meta["extra_exports"]
    assert json.loads((tmp_path / "sdk_asset__social_video.manifest.json").read_text())[
        "analysis"
    ] == {"peak_dbfs": -3}

    preview = asset.preview(tmp_path)
    assert preview["id"] == "sdk_asset__preview"
    assert calls[-1] == ("sdk_asset__preview", False)

    with pytest.raises(SpecError, match="unknown export preset"):
        asset.export(tmp_path, preset="nope")


def test_export_cutdowns_uses_presets_and_writes_manifests(monkeypatch, tmp_path):
    def fake_render_cutdowns(spec):
        assert spec["sample_rate"] == 48000
        assert spec["bit_depth"] == 16
        assert spec["master"]["target_lufs"] == -14.0
        yield 15.0, [[0.0, 0.0]], 48000, {
            "id": spec["id"], "bit_depth": 16, "spec_hash": "hash", "performance_hash": "take",
            "cutdown": {"length_s": 15},
        }

    def fake_write_wav(path, stereo, sr, bit_depth, spec_hash, seed):
        path.write_bytes(b"RIFF")
        return "b" * 64

    render_module = importlib.import_module("audioforge.render")
    monkeypatch.setattr(render_module, "render_cutdowns", fake_render_cutdowns)
    monkeypatch.setattr(render_module, "_write_wav", fake_write_wav)

    metas = sdk.AudioAsset(_spec()).export_cutdowns(tmp_path, preset="social_video")
    assert metas[0]["file"] == "sdk_asset_15s.wav"
    assert (tmp_path / "sdk_asset_15s.manifest.json").exists()

    with pytest.raises(SpecError, match="unknown export preset"):
        sdk.AudioAsset(_spec()).export_cutdowns(tmp_path, preset="nope")


def test_audioforge_load_import_catalog_and_pack_edges(monkeypatch, tmp_path):
    forge = sdk.AudioForge()
    src = """
asset loaded {
  kind: cue
  duration: 1s
  layer t : tone {
    note: A4
    env: a=0.01s d=0.1s s=0.8 r=0.1s
  }
  master { peak: -1db }
}
"""
    af = tmp_path / "loaded.af"
    af.write_text(src)
    assert forge.load_file(af).assets[0].id == "loaded"

    js = tmp_path / "loaded.json"
    js.write_text(json.dumps(_spec("json_loaded")))
    assert forge.load_file(js).assets[0].id == "json_loaded"

    assert forge.load_spec(_spec("direct")).id == "direct"
    assert forge.catalog(tmp_path).root == tmp_path

    midi_asset = sdk.AudioAsset(_notes_spec())
    midi = midi_asset.to_midi()
    assert forge.import_midi(midi, asset_id="midi_loaded").id == "midi_loaded"
    xml = midi_asset.to_musicxml()
    assert forge.import_musicxml(xml, asset_id="xml_loaded").id == "xml_loaded"

    with pytest.raises(SpecError, match="variant v1"):
        forge.export_pack("not dsl", tmp_path, n=1)

    monkeypatch.setattr(sdk.AudioAsset, "export", lambda self, out, preset=None, id_suffix=None: {
        "spec_hash": "s", "output_sha256": "o", "file": f"{self.id}{id_suffix}.wav",
    })
    pack = forge.export_pack(src, tmp_path, tags=["a", "b"], preset="web_preview")
    assert [v["variant"] for v in pack["variants"]] == ["a", "b"]
    assert json.loads((tmp_path / "pack.manifest.json").read_text())["preset"] == "web_preview"
