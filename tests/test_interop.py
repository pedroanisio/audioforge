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
