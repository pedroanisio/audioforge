"""Musical invariants for interchange, independent of XML serialization details."""
import xml.etree.ElementTree as ET

import pytest

from audioforge import interop


def piece(notes=None, **extra):
    return dict(id="notation", kind="cue", bpm=120, duration_s=4,
                key="C major", score={"meter": {"beats": 7, "unit": 8}},
                layers=[dict(name="upper", type="notes", osc="sine", notes=notes or [
                    dict(note="C4", start_beat=0, dur_beats=5),
                    dict(note="E4", start_beat=0, dur_beats=1),
                    dict(note="G4", start_beat=1, dur_beats=2),
                ]), dict(name="lower", type="notes", osc="sine", notes=[
                    dict(note="C2", start_beat=0, dur_beats=7),
                ])], **extra)


def signature(spec):
    return [[(n["note"], round(n["start_beat"], 5), round(n["dur_beats"], 5))
             for n in sorted(p["notes"], key=lambda n: (n["start_beat"], n["note"]))]
            for p in spec["layers"] if p.get("notes")]


@pytest.mark.parametrize("export", [interop.export_musicxml, interop.export_notated_musicxml])
def test_polyphony_roundtrip_preserves_parts_onsets_and_independent_durations(export):
    spec = piece()
    xml = export(spec)
    root = ET.fromstring(xml)
    assert len(root.findall("part")) == 2
    assert root.findtext(".//time/beat-type") == "8"
    assert root.find(".//backup") is not None
    assert signature(interop.import_musicxml(xml)) == signature(spec)


def test_pickup_key_and_tempo_changes_have_correct_offsets():
    spec = piece(tempo_map=[[0, 120], [3.5, 90]],
                 key_map=[[0, "C", "major"], [3.5, "F", "major"]])
    spec["score"]["pickup_beats"] = .5
    root = ET.fromstring(interop.export_notated_musicxml(spec))
    assert root.find("part/measure").get("implicit") == "yes"
    assert [e.text for e in root.findall("part[1]//key/fifths")] == ["0", "-1"]
    imported = interop.import_musicxml(ET.tostring(root, encoding="unicode"))
    assert imported["key_map"] == spec["key_map"]
    assert len(root.findall("part[1]//sound[@tempo]")) == 2


def test_expression_is_projected_and_unknown_art_is_diagnosed():
    spec = piece(holds=[dict(beat=5, duration_s=1)], notation={
        "lyrics": [dict(layer="upper", start_beat=0, text="Light")],
    })
    spec["score"]["sections"] = [dict(name="A", start_beat=0),
                                                 dict(name="B", start_beat=3.5)]
    spec["layers"][0]["dynamic"] = [[0, .2], [3, .8]]
    spec["layers"][0]["notes"][0].update(art="staccato", slur=1)
    spec["layers"][0]["notes"][2].update(slur=1)
    spec["layers"][1]["notes"][0]["art"] = "unrepresentable"
    root = ET.fromstring(interop.export_notated_musicxml(spec))
    for path in [".//dynamics", ".//wedge", ".//staccato", ".//fermata", ".//rehearsal", ".//lyric"]:
        assert root.find(path) is not None, path
    assert len(root.findall(".//slur")) == 2
    codes = {d["code"] for d in interop.interop_diagnostics(spec, "musicxml_notated")}
    assert "lossy_articulation" in codes
    assert "lossy_lyrics" not in codes


def test_midi_has_conductor_and_independent_part_tracks():
    spec = piece(tempo_map=[[0, 120], [3.5, 90]])
    data = interop.export_midi_bytes(spec)
    assert int.from_bytes(data[8:10], "big") == 1
    assert int.from_bytes(data[10:12], "big") == 3
    assert data.count(b"\xff\x51\x03") == 2
    assert signature(interop.import_midi_bytes(data)) == signature(spec)


def test_duplicate_pitch_events_and_invalid_notation_grids():
    spec = piece(notes=[dict(note="C4", start_beat=0, dur_beats=1),
                        dict(note="C4", start_beat=0, dur_beats=1)])
    back = interop.import_musicxml(interop.export_notated_musicxml(spec))
    assert signature(back) == signature(spec)
    for grid in (0, -1, float("nan"), .1):
        with pytest.raises(ValueError, match="grid"):
            interop.export_notated_musicxml(spec, grid=grid)


def test_notated_score_includes_declared_silence_and_rejects_invalid_bars():
    spec = piece()
    spec["duration_s"] = 7  # 14 quarter beats, four 7/8 bars.
    root = ET.fromstring(interop.export_notated_musicxml(spec))
    assert [len(part.findall("measure")) for part in root.findall("part")] == [4, 4]
    for beats in (0, -1):
        with pytest.raises(ValueError, match="meter"):
            interop.export_notated_musicxml(spec, beats_per_bar=beats)


def test_midi_assigns_a_new_port_after_fifteen_pitched_parts():
    spec = piece()
    spec["layers"] = [dict(spec["layers"][0], name=f"part{i}") for i in range(18)]
    _, _, tracks = interop._split_tracks(interop.export_midi_bytes(spec))
    assert b"\xff\x21\x01\x00" in tracks[1]
    assert b"\xff\x21\x01\x01" in tracks[16]


def test_multiple_holds_split_notes_and_rests_at_their_positions():
    spec = piece(notes=[dict(note="C4", start_beat=0, dur_beats=6)])
    spec["score"]["meter"] = {"beats": 4, "unit": 4}
    spec["duration_s"] = 6
    spec["holds"] = [dict(beat=b, duration_s=.25) for b in (2, 6, 7, 8)]
    xml = interop.export_notated_musicxml(spec)
    root = ET.fromstring(xml)
    divisions = int(root.findtext(".//divisions"))
    cursor = 0
    positions = []
    for note in root.findall("part[1]/measure/note"):
        if note.find("chord") is None:
            cursor += int(note.findtext("duration")) / divisions
        if note.find("notations/fermata") is not None:
            positions.append(cursor)
    assert positions == [2, 6, 7, 8]
