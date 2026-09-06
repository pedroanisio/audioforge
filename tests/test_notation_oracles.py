"""Notation interchange assertions (docs/evolution/harness-notation.md: NXML, NIMP, NMIDI).

Plain tests run with the project interpreter. Oracle tests import music21 / xmlschema
inside the test body and skip when the ``oracles`` extra is absent; ``make oracle-check``
runs them with the oracles installed.
"""
import json
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

import pytest

from audioforge import interop
from audioforge.dsl import compile_dsl
from audioforge.musicxml import NOTATED_GRID, TPQ, stepped_tempo_map, tempo_marks, tempo_points

FIX = Path(__file__).parent / "fixtures" / "notation"
XSD = Path(__file__).parent / "fixtures" / "musicxml" / "xsd" / "musicxml.xsd"
FIXTURES = sorted(p.stem for p in FIX.glob("*.af"))


def _spec(name: str) -> dict:
    specs, _ = compile_dsl((FIX / f"{name}.af").read_text())
    return specs[0]


def _expected(name: str) -> dict:
    return json.loads((FIX / f"{name}.expected.json").read_text())


def _xml(text: str) -> ET.Element:
    return ET.fromstring(text.split("\n", 1)[1] if text.startswith("<?xml") else text)


def _pitched(spec: dict) -> list[dict]:
    return [l for l in spec["layers"] if any("note" in e for e in l.get("notes") or [])]


def _measures(root: ET.Element, part: int = 0) -> list[ET.Element]:
    return root.findall("part")[part].findall("measure")


def _measure_ticks(measure: ET.Element) -> int:
    """Ticks a measure occupies: durations of rests and non-chord notes."""
    return sum(int(n.findtext("duration")) for n in measure.findall("note")
               if n.find("chord") is None)


def _chord_marks(spec: dict) -> int:
    marks = 0
    for layer in _pitched(spec):
        onsets = Counter(round(e["start_beat"], 6) for e in layer["notes"] if "note" in e)
        marks += sum(n - 1 for n in onsets.values())
    return marks


def _quantized_onsets(layer: dict, grid: float = NOTATED_GRID) -> set[float]:
    return {round(round(e["start_beat"] / grid) * grid, 4) for e in layer["notes"] if "note" in e}


# ------------------------------------------------------------- notated export ----
def test_meter_unit_and_bar_length_come_from_the_spec():
    root = _xml(interop.export_notated_musicxml(_spec("meter_7_8_key_change")))
    m = _measures(root)
    assert (m[0].findtext("attributes/time/beats"),
            m[0].findtext("attributes/time/beat-type")) == ("7", "8")
    assert len(m) == _expected("meter_7_8_key_change")["measures"] == 2
    assert all(_measure_ticks(x) == 7 * TPQ // 2 for x in m)     # 7 eighths = 3.5 quarters

    poly = _xml(interop.export_notated_musicxml(_spec("polymeter")))
    sigs = [(p.findtext("measure/attributes/time/beats"),
             p.findtext("measure/attributes/time/beat-type")) for p in poly.findall("part")]
    assert sigs == [("4", "4"), ("3", "4")]                       # per-part time signatures
    assert [len(p.findall("measure")) for p in poly.findall("part")] == [3, 4]


def test_key_changes_export_as_key_signatures_at_the_barline():
    root = _xml(interop.export_notated_musicxml(_spec("meter_7_8_key_change")))
    keys = [(i, m.findtext("attributes/key/fifths")) for i, m in enumerate(_measures(root))
            if m.find("attributes/key") is not None]
    assert keys == [(0, "0"), (1, "-1")]
    assert [f for _, f in keys] == [str(f) for f in _expected("meter_7_8_key_change")["key_fifths"]]


def test_tempo_changes_export_as_metronome_directions():
    spec = _spec("tempo_changes_fermata")
    root = _xml(interop.export_notated_musicxml(spec))
    marks = root.findall(".//direction/direction-type/metronome/per-minute")
    assert [m.text for m in marks] == ["90", "120", "100"]
    assert len(marks) == len(tempo_marks(spec)) == _expected("tempo_changes_fermata")["tempo_points"]
    placed = [(i, d.findtext("offset")) for i, m in enumerate(_measures(root))
              for d in m.findall("direction")]
    assert placed == [(0, None), (1, None), (2, None)]            # beats 0, 4, 8 in 4/4
    assert [d.find("sound").get("tempo") for d in root.iter("direction")] == ["90", "120", "100"]
    # thinning: one mark per grid slot; sub-0.1 bpm wobble collapses, real steps survive
    dense = dict(spec, tempo_map=[[b / 8, 90 + (b % 3) * 0.02] for b in range(0, 65)])
    assert len(tempo_marks(dense)) == 1
    ramp = dict(spec, tempo_map=[[0, 90], [1, 100], [2, 110], [3, 120]])
    assert len(tempo_marks(ramp)) == 4
    late = dict(spec, tempo_map=[[2, 100]])
    assert tempo_marks(late) == [(0.0, 100.0)]                   # first tempo extends back to 0


def test_pickup_exports_as_an_implicit_first_measure():
    spec = _spec("meter_6_8_pickup")
    root = _xml(interop.export_notated_musicxml(spec))
    m = _measures(root)
    assert m[0].get("implicit") == "yes" and m[0].get("number") == "0"
    assert _measure_ticks(m[0]) == int(spec["score"]["pickup_beats"] * TPQ) == TPQ
    assert m[1].get("number") == "1"
    assert m[1].findtext("note/pitch/step") == "D"                # the downbeat lands on D5
    assert all(_measure_ticks(x) == 3 * TPQ for x in m[1:])       # 6/8 = 3 quarters per bar


def test_exact_tick_export_emits_parts_and_chords_and_round_trips():
    assert _chord_marks(_spec("chords_ties_rests")) > 0
    for name in ("meter_3_4_two_parts", "chords_ties_rests", "polymeter"):
        spec = _spec(name)
        root = ET.fromstring(interop.export_musicxml(spec))
        layers = _pitched(spec)
        assert len(root.findall("part")) == len(layers) == _expected(name)["parts"]
        assert [p.text for p in root.findall("part-list/score-part/part-name")] == \
            [l["name"] for l in layers]
        assert len(root.findall(".//chord")) == _chord_marks(spec)
        for part, layer in zip(root.findall("part"), layers):
            xml_ticks = sum(int(n.findtext("duration")) for n in part.iter("note")
                            if n.find("rest") is None)
            assert xml_ticks == round(sum(e["dur_beats"] for e in layer["notes"]) * TPQ)
        imported = interop.import_musicxml(interop.export_musicxml(spec))
        for layer, back in zip(layers, imported["layers"]):
            want = {(e["note"], round(e["start_beat"], 6), round(e["dur_beats"], 6))
                    for e in layer["notes"]}
            got = {(e["note"], e["start_beat"], e["dur_beats"]) for e in back["notes"]}
            assert got == want, name
        assert imported["bpm"] == spec["bpm"]


# ---------------------------------------------------------------------- import ----
def test_import_parts_one_layer_per_part():
    spec = _spec("meter_3_4_two_parts")
    imported = interop.import_musicxml(interop.export_notated_musicxml(spec))
    assert [l["name"] for l in imported["layers"]] == [l["name"] for l in _pitched(spec)]
    assert all(l["notes"] for l in imported["layers"])


CHORD_VOICES_XML = """<score-partwise version="3.1">
  <part-list><score-part id="P1"><part-name>Soprano Alto</part-name></score-part></part-list>
  <part id="P1"><measure number="1">
    <attributes><divisions>2</divisions><time><beats>4</beats><beat-type>4</beat-type></time></attributes>
    <note><pitch><step>C</step><octave>5</octave></pitch><duration>4</duration><voice>1</voice></note>
    <note><chord/><pitch><step>E</step><octave>5</octave></pitch><duration>4</duration><voice>1</voice></note>
    <note><pitch><step>D</step><octave>5</octave></pitch><duration>4</duration><voice>1</voice></note>
    <backup><duration>8</duration></backup>
    <note><pitch><step>A</step><octave>4</octave></pitch><duration>2</duration><voice>2</voice></note>
    <forward><duration>2</duration></forward>
    <note><pitch><step>G</step><octave>4</octave></pitch><duration>4</duration><voice>2</voice></note>
  </measure></part>
</score-partwise>"""


def test_import_chords_backup_forward_and_voices_keep_simultaneous_onsets():
    imported = interop.import_musicxml(CHORD_VOICES_XML, asset_id="voices")
    assert [l["name"] for l in imported["layers"]] == ["Soprano_Alto"]
    got = {(n["note"], n["start_beat"], n["dur_beats"]) for n in imported["layers"][0]["notes"]}
    assert got == {("C5", 0.0, 2.0), ("E5", 0.0, 2.0), ("D5", 2.0, 2.0),
                   ("A4", 0.0, 1.0), ("G4", 2.0, 2.0)}
    assert imported["duration_s"] == 2.0 and imported["score"]["meter"] == {"beats": 4, "unit": 4}


DIVISIONS_CHANGE_XML = """<score-partwise version="3.1">
  <part-list><score-part id="P1"><part-name>x</part-name></score-part></part-list>
  <part id="P1">
    <measure number="1">
      <attributes><divisions>1</divisions><key><fifths>2</fifths><mode>major</mode></key>
        <time><beats>1</beats><beat-type>4</beat-type></time></attributes>
      <direction><direction-type><metronome><beat-unit>quarter</beat-unit><per-minute>60</per-minute></metronome></direction-type></direction>
      <note><pitch><step>C</step><octave>4</octave></pitch><duration>1</duration></note>
    </measure>
    <measure number="2">
      <attributes><divisions>4</divisions><key><fifths>-3</fifths><mode>minor</mode></key></attributes>
      <sound tempo="90"/>
      <note><pitch><step>D</step><octave>4</octave></pitch><duration>2</duration><tie type="start"/></note>
      <note><pitch><step>D</step><octave>4</octave></pitch><duration>2</duration><tie type="stop"/></note>
    </measure>
  </part>
</score-partwise>"""


def test_import_attributes_changes_and_ties_are_honoured():
    imported = interop.import_musicxml(DIVISIONS_CHANGE_XML)
    notes = imported["layers"][0]["notes"]
    assert notes == [{"note": "C4", "start_beat": 0.0, "dur_beats": 1.0},
                     {"note": "D4", "start_beat": 1.0, "dur_beats": 1.0}]   # divisions 1 -> 4; tie merged
    assert imported["key"] == "D major"
    assert imported["key_map"] == [[0.0, "D", "major"], [1.0, "C", "minor"]]
    # metronome marks are steps; the IR interpolates, so the change is written as a step
    assert imported["bpm"] == 60.0 and imported["tempo_map"] == [[0.0, 60.0], [1.0, 60.0], [1.0, 90.0]]
    assert imported["duration_s"] == pytest.approx(60 / 60 + 60 / 90, abs=1e-3)

    # the notated export's own key / tempo changes survive the round trip
    spec = _spec("tempo_changes_fermata")
    back = interop.import_musicxml(interop.export_notated_musicxml(spec))
    assert back["tempo_map"] == stepped_tempo_map(tempo_marks(spec))
    assert back["bpm"] == spec["bpm"] and back["score"]["meter"] == spec["score"]["meter"]
    spec = _spec("meter_7_8_key_change")
    back = interop.import_musicxml(interop.export_notated_musicxml(spec))
    assert back["key"] == "C major" and back["key_map"] == [[0.0, "C", "major"], [3.5, "F", "major"]]

    # cross-barline ties merge back into the authored events
    spec = _spec("chords_ties_rests")
    xml = interop.export_notated_musicxml(spec)
    assert _xml(xml).find(".//tie[@type='start']") is not None
    back = interop.import_musicxml(xml)
    want = sorted((e["note"], round(e["start_beat"], 6), round(e["dur_beats"], 6))
                  for e in _pitched(spec)[0]["notes"])
    got = sorted((e["note"], e["start_beat"], e["dur_beats"]) for e in back["layers"][0]["notes"])
    assert got == want

    with pytest.raises(ValueError, match="score-partwise"):
        interop.import_musicxml("<score-timewise/>")


def test_self_round_trip_notated_export_import_per_fixture():
    for name in FIXTURES:
        spec = _spec(name)
        back = interop.import_musicxml(interop.export_notated_musicxml(spec))
        layers = _pitched(spec)
        assert [l["name"] for l in back["layers"]] == [l["name"] for l in layers], name
        for layer, imp in zip(layers, back["layers"]):
            assert {n["start_beat"] for n in imp["notes"]} == _quantized_onsets(layer), name
            assert Counter(n["note"] for n in imp["notes"]) == \
                Counter(e["note"] for e in layer["notes"] if "note" in e), name


# ------------------------------------------------------------------------ MIDI ----
def test_midi_tempo_map_exports_tempo_events_and_one_track_per_layer():
    spec = _spec("tempo_changes_fermata")
    fmt, division, tracks = interop._split_tracks(interop.export_midi_bytes(spec))
    assert fmt == 1 and division == TPQ and len(tracks) == 1 + len(_pitched(spec))
    assert tracks[0].count(b"\xff\x51\x03") == len(tempo_points(spec)) == 3
    assert b"\xff\x58\x04" in tracks[0] and b"\xff\x59\x02" in tracks[0]

    poly = _spec("polymeter")
    back = interop.import_midi_bytes(interop.export_midi_bytes(poly))
    assert [l["name"] for l in back["layers"]] == ["main", "waltz"]
    assert sum(len(l["notes"]) for l in back["layers"]) == sum(len(l["notes"]) for l in _pitched(poly))

    # equal pitches in different layers overlap without cutting each other
    spec = {"id": "x", "kind": "cue", "duration_s": 4.0, "bpm": 120.0, "layers": [
        {"name": "a", "type": "notes", "notes": [{"note": "C4", "start_beat": 0.0, "dur_beats": 4.0}]},
        {"name": "b", "type": "notes", "notes": [{"note": "C4", "start_beat": 1.0, "dur_beats": 1.0}]}]}
    back = interop.import_midi_bytes(interop.export_midi_bytes(spec))
    assert [(n["note"], n["start_beat"], n["dur_beats"]) for l in back["layers"] for n in l["notes"]] \
        == [("C4", 0.0, 4.0), ("C4", 1.0, 1.0)]


# --------------------------------------------------------------------- oracles ----
def _m21():
    return pytest.importorskip("music21", reason="install the oracles extra")


def _m21_notes(part):
    """Note starts only: music21 splits bar-crossing notes into tied pieces."""
    return [n for n in part.recurse().notes
            if n.tie is None or n.tie.type not in ("stop", "continue")]


def _pitch_multiset_m21(part) -> Counter:
    out = Counter()
    for n in _m21_notes(part):
        for p in n.pitches:
            out[p.nameWithOctave.replace("-", "b")] += 1
    return out


def test_xsd_valid_notated_and_exact_exports_for_every_fixture():
    xmlschema = pytest.importorskip("xmlschema", reason="install the oracles extra")
    schema = xmlschema.XMLSchema(str(XSD))
    for name in FIXTURES:
        spec = _spec(name)
        for label, xml in (("notated", interop.export_notated_musicxml(spec)),
                           ("exact", interop.export_musicxml(spec))):
            errors = list(schema.iter_errors(xml))
            assert not errors, (name, label, [str(e)[:200] for e in errors[:3]])


def test_music21_parity_per_fixture():
    m21 = _m21()
    from music21 import converter
    for name in FIXTURES:
        spec, exp = _spec(name), _expected(name)
        xml = interop.export_notated_musicxml(spec)
        root = _xml(xml)
        score = converter.parseData(xml, format="musicxml")
        layers = _pitched(spec)
        assert len(score.parts) == len(layers) == exp["parts"], name
        for pi, (part, layer) in enumerate(zip(score.parts, layers)):
            measures = part.getElementsByClass(m21.stream.Measure)
            assert len(measures) == len(_measures(root, pi)), name
            sigs = [(ts.numerator, ts.denominator) for ts in part.recurse().getElementsByClass(m21.meter.TimeSignature)]
            want = ((spec.get("score") or {}).get("polymeter") or {}).get(layer["name"]) \
                or (spec.get("score") or {}).get("meter") or {"beats": 4, "unit": 4}
            assert sigs == [(want["beats"], want["unit"])], name
            fifths = [ks.sharps for ks in part.recurse().getElementsByClass(m21.key.KeySignature)]
            assert fifths == exp.get("key_fifths", fifths), name
            assert _pitch_multiset_m21(part) == Counter(e["note"] for e in layer["notes"] if "note" in e), name
            ql = sum(float(n.duration.quarterLength) for n in part.recurse().notes)
            xml_ql = sum(int(n.findtext("duration")) for n in root.findall("part")[pi].iter("note")
                         if n.find("rest") is None and n.find("chord") is None) / TPQ
            assert ql == pytest.approx(xml_ql, abs=1e-6), name
        marks = score.parts[0].recurse().getElementsByClass(m21.tempo.MetronomeMark)
        assert len(marks) == len(tempo_marks(spec)), name
        if "measures" in exp:
            assert len(score.parts[0].getElementsByClass(m21.stream.Measure)) == exp["measures"], name
        if "pickup_beats" in exp:
            first = score.parts[0].getElementsByClass(m21.stream.Measure)[0]
            assert float(first.duration.quarterLength) == exp["pickup_beats"], name


def test_midi_export_parts_and_notes_survive_music21(tmp_path):
    m21 = _m21()
    from music21 import converter
    spec = _spec("polymeter")
    layers = _pitched(spec)
    path = tmp_path / "poly.mid"
    path.write_bytes(interop.export_midi_bytes(spec))
    score = converter.parse(str(path))
    assert len(score.parts) == len(layers)
    assert sum(len(_m21_notes(p)) for p in score.parts) == sum(len(l["notes"]) for l in layers)
    # eighteen layers striking the same pitch at once: every note survives, one part each
    big = {"id": "tutti", "kind": "cue", "duration_s": 4.0, "bpm": 120.0, "tempo_map": [[0, 120], [2, 90]],
           "layers": [{"name": f"v{i}", "type": "notes",
                       "notes": [{"note": "A4", "start_beat": 0.0, "dur_beats": 2.0 + i / 18}]}
                      for i in range(18)]}
    path.write_bytes(interop.export_midi_bytes(big))
    score = converter.parse(str(path))
    assert len(score.parts) == 18
    assert sum(len(_m21_notes(p)) for p in score.parts) == 18
    assert len(score.recurse().getElementsByClass(m21.tempo.MetronomeMark)) >= 2
