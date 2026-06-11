"""Four-pillar Smart DSL coverage: score, audio, style packs, interop."""
import io
import json
import sys
import wave
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from audioforge import AudioForge  # noqa: E402
from audioforge.interop import (export_midi_bytes, export_musicxml,
                                import_midi_bytes, import_musicxml)  # noqa: E402
from audioforge.samples import register_sample  # noqa: E402
from audioforge.styles import list_style_packs, style_pack  # noqa: E402


def _wav_bytes(sr=24000, seconds=0.25, stereo=False):
    t = np.arange(int(sr * seconds)) / sr
    x = 0.2 * np.sin(2 * np.pi * 330 * t)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(2 if stereo else 1)
        w.setsampwidth(2)
        w.setframerate(sr)
        if stereo:
            y = 0.2 * np.sin(2 * np.pi * 660 * t)
            pcm = np.stack([x, y], axis=1).reshape(-1)
        else:
            pcm = x
        w.writeframes((pcm * 32767).astype("<i2").tobytes())
    return buf.getvalue()


def test_universal_score_layer_compiles_form_meter_repeats_and_polymeter():
    src = """
asset score_map {
  kind: cue
  duration: 12s
  tempo: 90bpm
  meter: 7 8
  pickup: 1b
  form: intro 0b for 7b, verse 7b for 14b, refrain 21b for 7b
  repeat: verse x2
  polymeter: pulse 3 4
  layer pulse : drums {
    voice: hat
    pattern: x.x.x.x.
    gain: -18db
  }
  layer melody : notes {
    osc: sine
    env: a=0.01s d=0.1s s=0.8 r=0.1s
    notes: A4 @ 0b for 1b, B4 @ 1b for 1b, C#5 @ 2b for 2b
  }
  master { peak: -1db }
}
"""
    res = AudioForge().compile(src)
    assert res.ok, [d.message for d in res.diagnostics]
    spec = res.assets[0].spec
    assert spec["score"]["meter"] == {"beats": 7, "unit": 8}
    assert spec["score"]["pickup_beats"] == 1.0
    assert [s["name"] for s in spec["score"]["sections"]] == [
        "intro", "verse", "refrain"]
    assert spec["score"]["repeats"] == [{"section": "verse", "count": 2}]
    assert spec["score"]["polymeter"]["pulse"] == {"beats": 3, "unit": 4}


def test_universal_audio_layer_compiles_to_content_addressed_sample_and_renders(tmp_path):
    sha = register_sample("spoken_love.wav", _wav_bytes())
    src = f"""
asset audio_source {{
  kind: cue
  duration: 1s
  tempo: 80bpm
  layer spoken : audio {{
    file: "spoken_love.wav"
    sha256: "{sha}"
    start: 0s
    gain: -6db
    preserve: stereo
  }}
  master {{ peak: -1db }}
}}
"""
    res = AudioForge().compile(src)
    assert res.ok, [d.message for d in res.diagnostics]
    layer = res.assets[0].spec["layers"][0]
    assert layer["type"] == "sample"
    assert layer["source_kind"] == "audio"
    assert layer["preserve_channels"] is True
    meta = res.assets[0].export(tmp_path, analyze=True)
    assert meta["file"] == "audio_source.wav"
    assert meta["analysis"]["duration_s"] == 1.0


def test_audio_preserve_stereo_renders_distinct_left_right_channels():
    sha = register_sample("wide_take.wav", _wav_bytes(stereo=True))
    src = f"""
asset stereo_audio {{
  kind: cue
  duration: 0.5s
  tempo: 80bpm
  layer take : audio {{
    file: "wide_take.wav"
    sha256: "{sha}"
    preserve: stereo
  }}
  master {{ peak: -1db }}
}}
"""
    asset = AudioForge().compile(src).assets[0]
    stereo, _sr, _meta = asset.render()
    assert stereo.ndim == 2 and stereo.shape[1] == 2
    assert np.max(np.abs(stereo[:, 0] - stereo[:, 1])) > 1e-4


def test_style_pack_registry_is_manifested_and_expands_defaults():
    names = list_style_packs()
    assert {"cinematic", "ambient", "trap", "choral"}.issubset(names)
    pack = style_pack("trap")
    assert pack["perform"]["expressivity"] > 0
    cap = __import__("audioforge.capabilities", fromlist=["capability_manifest"]).capability_manifest()
    assert "trap" in cap["style_packs"]
    assert "audio" in cap["layer_types"]
    assert "score_layer" in cap
    assert "export-midi" in cap["interop"]["cli"]
    src = """
asset styled {
  kind: cue
  duration: 2s
  tempo: 120bpm
  style: trap
  layer lead : notes {
    osc: saw
    env: a=0.01s d=0.1s s=0.7 r=0.2s
    notes: C4 @ 0b for 1b, G4 @ 1b for 1b
  }
  master { peak: -1db }
}
"""
    spec = AudioForge().compile(src).assets[0].spec
    assert spec["intent"]["style"] == "trap"
    assert spec["intent"]["ensemble"]["family"] == "electronic"
    assert any(b["name"] == "af_space" for b in spec["buses"])


def test_midi_and_musicxml_export_import_roundtrip():
    src = """
asset interop_piece {
  kind: cue
  duration: 3s
  tempo: 120bpm
  meter: 4 4
  layer melody : notes {
    osc: sine
    env: a=0.01s d=0.1s s=0.8 r=0.1s
    notes: C4 @ 0b for 1b, E4 @ 1b for 1b, G4 @ 2b for 1b
  }
  master { peak: -1db }
}
"""
    spec = AudioForge().compile(src).assets[0].spec
    midi = export_midi_bytes(spec)
    assert midi.startswith(b"MThd")
    midi_spec = import_midi_bytes(midi, asset_id="from_midi")
    assert midi_spec["id"] == "from_midi"
    assert midi_spec["layers"][0]["notes"][1]["note"] == "E4"
    xml = export_musicxml(spec)
    assert "<score-partwise" in xml and "<step>C</step>" in xml
    xml_spec = import_musicxml(xml, asset_id="from_xml")
    assert [n["note"] for n in xml_spec["layers"][0]["notes"]] == [
        "C4", "E4", "G4"]


def test_cli_exports_interop_files(tmp_path, capsys):
    src = tmp_path / "piece.af"
    src.write_text("""
asset cli_interop {
  kind: cue
  duration: 1s
  tempo: 120bpm
  layer m : notes {
    osc: sine
    env: a=0.01s d=0.1s s=0.8 r=0.1s
    notes: C4 @ 0b for 1b
  }
  master { peak: -1db }
}
""")
    from audioforge.cli import main as cli_main
    assert cli_main(["export-midi", str(src), "-o", str(tmp_path / "p.mid")]) == 0
    assert (tmp_path / "p.mid").read_bytes().startswith(b"MThd")
    assert cli_main(["import-midi", str(tmp_path / "p.mid"), "--id", "cli_midi"]) == 0
    assert '"id": "cli_midi"' in capsys.readouterr().out
    assert cli_main(["export-musicxml", str(src), "-o", str(tmp_path / "p.musicxml")]) == 0
    assert "<score-partwise" in (tmp_path / "p.musicxml").read_text()
    assert cli_main(["import-musicxml", str(tmp_path / "p.musicxml"),
                     "--id", "cli_xml"]) == 0
    assert '"id": "cli_xml"' in capsys.readouterr().out
