import struct
import xml.etree.ElementTree as ET

import pytest

from audioforge import interop


def _interop_spec() -> dict:
    return {
        "id": "interop_depth",
        "kind": "cue",
        "duration_s": 4.0,
        "bpm": 90.0,
        "key": "D minor",
        "score": {"meter": {"beats": 3, "unit": 4}},
        "layers": [
            {
                "name": "lead",
                "type": "notes",
                "notes": [
                    {"note": "C#4", "start_beat": 0.0, "dur_beats": 1.5, "vel": 0.0},
                    {"note": "E4", "start_beat": 2.0, "dur_beats": 0.5, "vel": 2.0},
                    {"note": "G4", "start_beat": 2.0, "dur_beats": 0.5, "vel": 0.8},
                    {"note": "A4", "start_beat": 2.75, "dur_beats": 2.0, "vel": 0.7},
                ],
            },
            {
                "name": "bass",
                "type": "notes",
                "notes": [
                    {"note": "D2", "start_beat": 0.5, "dur_beats": 3.0, "vel": 0.6},
                ],
            },
            {"name": "noise", "type": "noise"},
        ],
    }


def test_vlq_round_trip_and_midi_rejects_invalid_or_unsupported_events():
    encoded = interop._vlq(0x2000)
    assert interop._read_vlq(encoded, 0) == (0x2000, len(encoded))

    with pytest.raises(ValueError, match="not a MIDI file"):
        interop.import_midi_bytes(b"not-midi")

    track = interop._vlq(0) + bytes([0xC0, 0x00])
    data = (
        b"MThd" + struct.pack(">IHHH", 6, 0, 1, interop.TPQ)
        + b"MTrk" + struct.pack(">I", len(track)) + track
    )
    with pytest.raises(ValueError, match="unsupported MIDI event 0xc0"):
        interop.import_midi_bytes(data)


def test_midi_export_import_clamps_velocity_and_preserves_tempo():
    midi = interop.export_midi_bytes(_interop_spec())
    assert midi.startswith(b"MThd")

    imported = interop.import_midi_bytes(midi, asset_id="from_midi")
    notes = imported["layers"][0]["notes"]

    assert imported["id"] == "from_midi"
    assert imported["bpm"] == pytest.approx(90.0, abs=0.0001)
    by_note = {n["note"]: n for n in notes}
    assert set(by_note) == {"C#4", "D2", "E4", "G4", "A4"}
    assert by_note["C#4"]["vel"] == round(1 / 127.0, 4)
    assert by_note["E4"]["vel"] == 1.0
    assert by_note["D2"]["start_beat"] == 0.5


def test_interop_diagnostics_report_unprojected_performance_curves():
    spec = _interop_spec()
    spec["layers"][0]["notes"][0]["curves"] = [{
        "target": "pitch_cents",
        "time_basis": "note_seconds",
        "points": [[0.0, 0.0], [0.5, 200.0]],
    }]
    spec["layers"][0]["notes"][1]["curves"] = [{
        "target": "dynamic",
        "time_basis": "note_seconds",
        "points": [[0.0, 0.2], [0.5, 0.9]],
    }]

    midi_codes = {d["code"] for d in interop.interop_diagnostics(spec, "midi")}
    xml_codes = {d["code"] for d in interop.interop_diagnostics(spec, "musicxml")}

    assert {"lossy_pitch_curve", "lossy_dynamic_curve"} <= midi_codes
    assert {"lossy_pitch_curve", "lossy_dynamic_curve"} <= xml_codes


def test_midi_pitch_bend_imports_layer_pitch_cents_curve():
    track = bytearray()
    track.extend(interop._vlq(0) + bytes([0xB0, 101, 0]))  # RPN MSB
    track.extend(interop._vlq(0) + bytes([0xB0, 100, 0]))  # RPN LSB
    track.extend(interop._vlq(0) + bytes([0xB0, 6, 12]))   # +/- 12 st
    track.extend(interop._vlq(0) + bytes([0x90, 60, 96]))
    track.extend(interop._vlq(0) + bytes([0xE0, 127, 127]))
    track.extend(interop._vlq(interop.TPQ) + bytes([0x80, 60, 0]))
    track.extend(interop._vlq(0) + b"\xff\x2f\x00")
    data = (
        b"MThd" + struct.pack(">IHHH", 6, 0, 1, interop.TPQ)
        + b"MTrk" + struct.pack(">I", len(track)) + bytes(track)
    )

    imported = interop.import_midi_bytes(data, asset_id="bent")
    automation = imported["layers"][0]["automation"]

    assert imported["id"] == "bent"
    assert automation == [{
        "target": "pitch_cents",
        "time_basis": "layer_beats",
        "points": [[0.0, 1200.0]],
    }]


def test_exact_musicxml_exports_rests_meter_accidentals_and_imports_them():
    xml = interop.export_musicxml(_interop_spec())
    root = ET.fromstring(xml)

    assert root.findtext(".//part-name") == "interop_depth"
    assert root.findtext(".//time/beats") == "3"
    assert root.findtext(".//time/beat-type") == "4"
    assert root.find(".//rest") is not None
    assert root.findtext(".//pitch[step='C']/alter") == "1"

    imported = interop.import_musicxml(xml, asset_id="from_xml")
    notes = imported["layers"][0]["notes"]
    assert imported["id"] == "from_xml"
    assert imported["bpm"] == 90.0
    assert notes[0] == {"note": "C#4", "start_beat": 0.0, "dur_beats": 1.5}
    assert any(n["note"] == "D2" for n in notes)


def test_musicxml_bend_import_expands_to_pitch_curve():
    xml = """<score-partwise version="3.1">
  <part-list><score-part id="P1"><part-name>bends</part-name></score-part></part-list>
  <part id="P1"><measure number="1">
    <attributes><divisions>480</divisions></attributes>
    <sound tempo="120"/>
    <note>
      <pitch><step>C</step><octave>4</octave></pitch>
      <duration>960</duration>
      <notations><technical><bend><bend-alter>2</bend-alter></bend></technical></notations>
    </note>
  </measure></part>
</score-partwise>"""

    imported = interop.import_musicxml(xml, asset_id="xml_bend")
    note = imported["layers"][0]["notes"][0]

    assert note["curves"] == [{
        "target": "pitch_cents",
        "time_basis": "note_beats",
        "points": [[0.0, 0.0], [2.0, 200.0]],
    }]


def test_notated_musicxml_quantizes_chords_rests_ties_and_clefs():
    xml = interop.export_notated_musicxml(_interop_spec(), beats_per_bar=3,
                                          grid=0.25)
    root = ET.fromstring(xml.split("\n", 1)[1])

    assert root.findtext(".//work-title") == "interop_depth"
    assert [p.text for p in root.findall(".//part-name")] == ["lead", "bass"]
    assert root.find(".//chord") is not None
    assert root.find(".//tie[@type='start']") is not None
    assert root.find(".//tied[@type='stop']") is not None
    assert root.find(".//rest") is not None
    assert {sign.text for sign in root.findall(".//clef/sign")} == {"G", "F"}
    assert root.findtext(".//key/fifths") == "-1"

    with pytest.raises(ValueError, match="no pitched layers"):
        interop.export_notated_musicxml({"layers": [{"type": "noise"}]})
