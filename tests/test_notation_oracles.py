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
            assert {n["start_beat"] for n in imp["notes"]} == \
                {round(g["on"] / TPQ, 6) for g in _notated_events(spec, layer, NOTATED_GRID)}, name
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
            xml_part = root.findall("part")[pi]
            dyn = [d.value for d in part.recurse().getElementsByClass(m21.dynamics.Dynamic)]
            assert dyn == [d[0].tag for d in xml_part.findall(".//direction-type/dynamics")], name
            assert len(part.recurse().getElementsByClass(m21.dynamics.DynamicWedge)) == \
                len([w for w in xml_part.findall(".//wedge") if w.get("type") != "stop"]), name
            assert sum(len(n.articulations) for n in part.recurse().notes) == \
                len([c for a in xml_part.findall(".//articulations") for c in a]), name
            assert len(part.recurse().getElementsByClass(m21.spanner.Slur)) == \
                len(xml_part.findall(".//slur[@type='start']")), name
            assert sum(1 for n in part.recurse().notesAndRests
                       if any(isinstance(e, m21.expressions.Fermata) for e in n.expressions)) == \
                len(xml_part.findall(".//fermata")), name
            assert sum(1 for n in part.recurse().notes if n.duration.tuplets) == \
                len(xml_part.findall(".//time-modification")), name
            assert sum(1 for n in part.recurse().notes if n.lyric) == len(xml_part.findall(".//lyric")), name
            if xml_part.find(".//repeat") is not None:
                expanded = m21.repeat.Expander(part).process()
                assert float(expanded.highestTime) == exp["expected_duration_beats"], name
        assert len(score.parts[0].recurse().getElementsByClass(m21.expressions.RehearsalMark)) == \
            len(root.findall("part")[0].findall(".//rehearsal")), name
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


# -------------------------------------------------------------- T3: notation marks ----
from audioforge.musicxml import _notated_events, _note_name  # noqa: E402
from audioforge.interop import FORMATS  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def _codes(spec, fmt):
    return {d["code"] for d in interop.interop_diagnostics(spec, fmt)}


def test_dynamics_export_as_marks_and_hairpins_and_import_back():
    spec = _spec("dynamics_articulations_slurs")
    xml = interop.export_notated_musicxml(spec)
    root = _xml(xml)
    marks = [d[0].tag for d in root.findall(".//direction-type/dynamics")]
    assert marks == _expected("dynamics_articulations_slurs")["dynamics"] == ["pp", "ff"]
    assert [w.get("type") for w in root.findall(".//wedge")] == ["crescendo", "stop"]
    back = interop.import_musicxml(xml)
    assert back["layers"][0]["dynamic"] == spec["layers"][0]["dynamic"]
    assert "lossy_dynamic_curve" not in _codes(spec, "musicxml_notated")
    assert "lossy_dynamic_curve" in _codes(spec, "midi") and "lossy_dynamic_curve" in _codes(spec, "musicxml")


def test_articulations_and_slurs_export_and_import_back():
    spec = _spec("dynamics_articulations_slurs")
    xml = interop.export_notated_musicxml(spec)
    root = _xml(xml)
    arts = [child.tag for a in root.findall(".//articulations") for child in a]
    assert arts == ["staccato", "strong-accent", "staccato"]
    assert [(s.get("type"), s.get("number")) for s in root.findall(".//slur")] == [("start", "1"), ("stop", "1")]
    back = interop.import_musicxml(xml)
    got = [(n["note"], n.get("art"), n.get("slur")) for n in back["layers"][0]["notes"]]
    want = [(e["note"], e.get("art"), e.get("slur")) for e in spec["layers"][0]["notes"]]
    assert got == want
    assert "lossy_articulation" in _codes(spec, "midi") and "lossy_slur" in _codes(spec, "musicxml")
    assert not {"lossy_articulation", "lossy_slur"} & _codes(spec, "musicxml_notated")

    # legato runs become slurs; tremolo an ornament; pizzicato a pizz./arco direction pair
    spec2 = {"id": "arts", "kind": "cue", "duration_s": 4.0, "bpm": 120.0, "layers": [{
        "name": "v", "type": "notes", "notes": [
            {"note": "C4", "start_beat": 0.0, "dur_beats": 1.0, "art": "legato"},
            {"note": "D4", "start_beat": 1.0, "dur_beats": 1.0, "art": "legato"},
            {"note": "E4", "start_beat": 2.0, "dur_beats": 1.0, "art": "tremolo"},
            {"note": "F4", "start_beat": 3.0, "dur_beats": 0.5, "art": "pizzicato"},
            {"note": "G4", "start_beat": 3.5, "dur_beats": 0.5}]}]}
    root2 = _xml(interop.export_notated_musicxml(spec2))
    assert [s.get("type") for s in root2.findall(".//slur")] == ["start", "stop"]
    assert root2.find(".//ornaments/tremolo").text == "3"
    assert [w.text for w in root2.findall(".//words")] == ["pizz.", "arco"]
    assert [s.get("pizzicato") for s in root2.findall(".//direction/sound") if s.get("pizzicato")] == ["yes", "no"]
    back2 = interop.import_musicxml(interop.export_notated_musicxml(spec2))
    assert [n.get("art") for n in back2["layers"][0]["notes"]] == [None, None, "tremolo", "pizzicato", None]
    assert back2["layers"][0]["notes"][0]["slur"] == back2["layers"][0]["notes"][1]["slur"]


def test_fermata_and_rehearsal_marks_export_with_repeat_barlines_and_import_back():
    spec = _spec("tempo_changes_fermata")
    xml = interop.export_notated_musicxml(spec)
    root = _xml(xml)
    with_fermata = [n for n in root.iter("note") if n.find("notations/fermata") is not None]
    assert len(with_fermata) == _expected("tempo_changes_fermata")["holds"] == 1
    assert with_fermata[0].findtext("pitch/step") == "A"          # the note ending at the hold
    back = interop.import_musicxml(xml)
    assert back["holds"] == [{"beat": 8.0, "duration_s": 1.0}]      # a fermata holds the note's own length
    assert "lossy_hold" in _codes(spec, "midi") and "lossy_hold" not in _codes(spec, "musicxml_notated")

    spec2 = _spec("form_sections_repeat")
    xml2 = interop.export_notated_musicxml(spec2)
    root2 = _xml(xml2)
    assert [r.text for r in root2.findall(".//rehearsal")] == ["intro", "verse", "outro"]
    assert [(r.get("direction"), r.get("times")) for r in root2.findall(".//repeat")] == \
        [("forward", None), ("backward", "2")]
    back2 = interop.import_musicxml(xml2)
    assert [s["name"] for s in back2["score"]["sections"]] == ["intro", "verse", "outro"]
    assert back2["score"]["repeats"] == [{"section": "verse", "count": 2}]
    assert "lossy_repeat" not in _codes(spec2, "musicxml_notated")
    # MIDI and the exact-tick export carry the performed (expanded) form: 24 beats
    perf = interop.import_midi_bytes(interop.export_midi_bytes(spec2))
    assert max(n["start_beat"] + n["dur_beats"] for l in perf["layers"] for n in l["notes"]) == \
        _expected("form_sections_repeat")["expected_duration_beats"] == 24.0
    exact = ET.fromstring(interop.export_musicxml(spec2))
    assert sum(int(n.findtext("duration")) for n in exact.iter("note") if n.find("rest") is None) == 24 * TPQ
    # the performed form names sections per pass (compile_repeats): intro, verse ×2, outro
    assert [r.text.split("__")[0] for r in exact.findall(".//rehearsal")] == ["intro", "verse", "verse", "outro"]
    fmt, _, tracks = interop._split_tracks(interop.export_midi_bytes(spec2))
    assert tracks[0].count(b"\xff\x06") == 4                       # intro, verse__1, verse__2, outro
    # a repeat that does not sit on barlines is reported, not written
    import copy
    spec3 = copy.deepcopy(spec2)
    spec3["score"]["sections"][1].update({"start_beat": 5.0, "dur_beats": 7.0, "end_beat": 12.0})
    assert "lossy_repeat" in _codes(spec3, "musicxml_notated")
    assert _xml(interop.export_notated_musicxml(spec3)).find(".//repeat") is None


def test_tuplets_and_lyrics_project_and_import_back():
    spec = _spec("tuplet_lyrics")
    xml = interop.export_notated_musicxml(spec)
    root = _xml(xml)
    tms = root.findall(".//time-modification")
    assert len(tms) == 3 and all((t.findtext("actual-notes"), t.findtext("normal-notes")) == ("3", "2") for t in tms)
    trip = [n for n in root.iter("note") if n.find("time-modification") is not None]
    assert [int(n.findtext("duration")) for n in trip] == [320, 320, 320]
    assert [n.findtext("type") for n in trip] == ["quarter"] * 3
    assert [t.get("type") for t in root.findall(".//notations/tuplet")] == ["start", "stop"]
    assert [l.findtext("text") for l in root.findall(".//lyric")] == ["la", "la", "la"]
    back = interop.import_musicxml(xml)
    assert back["notation"]["tuplets"] == [{"layer": "v", "start_beat": 0.0, "dur_beats": 2.0, "ratio": [3, 2]}]
    assert back["notation"]["lyrics"] == [{"layer": "v", "start_beat": 0.0, "text": "la la la"}]
    assert "lossy_lyrics" in _codes(spec, "musicxml") and "lossy_lyrics" not in _codes(spec, "musicxml_notated")
    fmt, _, tracks = interop._split_tracks(interop.export_midi_bytes(spec))
    assert tracks[1].count(b"\xff\x05") == 3                       # one lyric event per syllable


def test_lossy_registry_codes_are_registered_and_emitted_for_every_dropped_construct():
    from audioforge.capabilities import capability_manifest
    from audioforge.tools.gen_interop import INTEROP, render
    codes = set(capability_manifest()["diagnostic_codes"])
    for row in interop.coverage():
        for fmt in FORMATS:
            cell = row[fmt]
            assert cell["status"] in interop.STATUSES, (row["construct"], fmt)
            if cell["status"] in ("lossy", "unsupported", "conditional"):
                assert cell["code"] in codes, (row["construct"], fmt, cell["code"])
    for name in FIXTURES:
        spec = _spec(name)
        for fmt in FORMATS:
            rows = interop.coverage(spec)
            expected = {r[fmt]["code"] for r in rows
                        if r["present"] and r[fmt]["status"] in ("lossy", "unsupported")}
            assert _codes(spec, fmt) == expected, (name, fmt)
    assert render() == INTEROP.read_text(), "docs/INTEROP.md is stale: run gen_interop --write"
    with pytest.raises(ValueError, match="unknown interop format"):
        interop.interop_diagnostics(_spec("polymeter"), "abc")


def test_score_layer_projection_defined_for_every_format():
    rows = {row["construct"]: row for row in interop.coverage()}
    for construct in ("meter", "pickup", "polymeter", "sections", "repeats", "key", "tempo",
                      "holds", "tuplets", "lyrics", "tuning", "dynamic_marks", "articulations", "slurs"):
        assert construct in rows, construct
        for fmt in FORMATS:
            cell = rows[construct][fmt]
            assert cell["status"] in interop.STATUSES
            assert cell["status"] in ("preserved",) or cell["note"], (construct, fmt)
    poly = _spec("polymeter")
    assert {"lossy_polymeter"} == _codes(poly, "midi") == _codes(poly, "musicxml")
    assert not _codes(poly, "musicxml_notated")
    pick = _spec("meter_6_8_pickup")
    assert "lossy_pickup" in _codes(pick, "musicxml") and "lossy_pickup" not in _codes(pick, "midi")
    fmt, _, tracks = interop._split_tracks(interop.export_midi_bytes(pick))
    assert tracks[0].count(b"\xff\x58\x04") == 2                   # 1/4 anacrusis, then 6/8


def test_ambiguity_set_matches_documentation():
    from audioforge.harmony import identify_chord
    from audioforge.theory import CHORD_QUALITIES
    ambiguous = Counter()
    for root in range(12):
        for quality, intervals in CHORD_QUALITIES.items():
            result = identify_chord([{"note": _note_name(60 + root + iv)} for iv in intervals])
            assert result["status"] != "unrecognized", (root, quality)
            if result["status"] == "ambiguous":
                assert len(result["candidates"]) >= 2
                ambiguous[quality] += 1
    assert set(ambiguous) == {"dim7", "aug", "min7", "m7", "6", "min7b5", "m7b5", "m6", "sus2", "sus4"}
    assert sum(ambiguous.values()) == 120 and len(CHORD_QUALITIES) * 12 == 300
    doc = (ROOT / "docs" / "MIGRATION_3.md").read_text()
    for token in ("`dim7`", "`aug`", "`min7`", "`m7b5`", "`m6`", "`sus2`", "`sus4`", "120 of the 300"):
        assert token in doc, token


_LETTERS = "CDEFGAB"
_NATURAL = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}


def _degree(semis: int, quality: str) -> int:
    """Scale degree a chord-tone interval spells as (thirds stack plus sus/add tones)."""
    if semis == 0:
        return 1
    if semis <= 2:
        return 2
    if semis <= 4:
        return 3
    if semis == 5:
        return 4
    if semis == 6:
        return 5
    if semis <= 8:
        return 5
    if semis == 9:
        return 7 if quality == "dim7" else 6
    if semis <= 11:
        return 7
    if semis == 14:
        return 9
    return 11


def _spelled(root: str, semis: int, quality: str) -> str:
    """Chord tone `semis` above `root` (music21 spelling: '-' flat) with its proper letter."""
    letter, alter = root[0], root[1:].count("#") - root[1:].count("-")
    degree = _degree(semis, quality)
    li = (_LETTERS.index(letter) + degree - 1)
    target = _LETTERS[li % 7]
    natural = _NATURAL[target] + 12 * (li // 7) - _NATURAL[letter]
    acc = alter + semis - natural
    return f"{target}{'#' * acc if acc > 0 else '-' * -acc}{4 + li // 7}"


def test_chord_parity_with_music21():
    _m21()
    from music21 import chord as m21chord, pitch
    from audioforge.harmony import identify_chord
    from audioforge.theory import CHORD_QUALITIES
    disputes = {"7sus4", "dom7sus4"}   # music21 names the quartal tetramirror from the fourth
    agree = total = 0
    ambiguous = 0
    for root in ("C", "C#", "D", "E-", "E", "F", "F#", "G", "A-", "A", "B-", "B"):
        for quality, intervals in CHORD_QUALITIES.items():
            ps = [pitch.Pitch(_spelled(root, iv, quality)) for iv in intervals]
            assert [p.midi for p in ps] == [pitch.Pitch(root + "4").midi + iv for iv in intervals]
            ours = identify_chord([{"note": _note_name(p.midi)} for p in ps])
            if ours["status"] == "ambiguous":
                ambiguous += 1
                continue
            assert ours["status"] == "resolved"
            if quality in disputes:
                continue
            total += 1
            agree += ours["root_pc"] == m21chord.Chord(ps).root().pitchClass
    assert ambiguous == 120
    assert agree / total >= 0.95, (agree, total)


def test_corpus_round_trip_bach_chorale(tmp_path):
    m21 = _m21()
    from music21 import corpus
    from audioforge import AudioForge
    score = corpus.parse("bach/bwv66.6")
    path = tmp_path / "bwv66.6.musicxml"
    score.write("musicxml", fp=str(path))
    spec = interop.import_musicxml(path.read_text(), asset_id="bwv66_6")
    assert len(spec["layers"]) == len(score.parts) == 4
    for part, layer in zip(score.parts, spec["layers"]):
        starts = _m21_notes(part)
        assert len(layer["notes"]) == len(starts), layer["name"]
        assert sorted({n["start_beat"] for n in layer["notes"]}) == \
            sorted({round(float(n.getOffsetInHierarchy(part)), 6) for n in starts}), layer["name"]
    ours = max(n["start_beat"] + n["dur_beats"] for l in spec["layers"] for n in l["notes"])
    assert ours == pytest.approx(float(score.highestTime), abs=1e-6)
    import math
    seconds = float(score.seconds)
    if math.isnan(seconds):
        # no MetronomeMark in the stream: music21's writer still declares a playback tempo
        # (<sound tempo>), which is what the import honours; fall back to 120 like both sides do
        declared = _xml(path.read_text()).find(".//sound[@tempo]")
        bpm = float(declared.get("tempo")) if declared is not None else 120.0
        seconds = float(score.highestTime) * 60.0 / bpm
    # fermatas import as holds of the note's own length; the timeline underneath matches music21
    fermatas = {round(float(n.getOffsetInHierarchy(score.parts[0])) + float(n.duration.quarterLength), 6)
                for n in score.parts[0].recurse().notesAndRests
                if any(isinstance(e, m21.expressions.Fermata) for e in n.expressions)}
    assert {h["beat"] for h in spec.get("holds", [])} >= fermatas and fermatas
    held = sum(h["duration_s"] for h in spec.get("holds", []))
    assert spec["duration_s"] - held == pytest.approx(seconds, rel=0.01)
    asset = AudioForge().load_spec(spec)                 # validates the parser's claim
    assert not [d for d in asset.validate() if d.severity == "error"]
    audio, sample_rate, _meta = asset.render()          # (stereo array, rate, meta)
    assert audio.shape[0] == pytest.approx(spec["duration_s"] * sample_rate, rel=0.05) and audio.shape[1] == 2


def test_lilypond_zero_warnings_for_every_fixture(tmp_path):
    lilypond = pytest.importorskip("lilypond", reason="install the oracles extra")
    import subprocess
    exe = Path(lilypond.executable())
    musicxml2ly = exe.parent / "musicxml2ly"
    for name in FIXTURES:
        xml_path = tmp_path / f"{name}.musicxml"
        xml_path.write_text(interop.export_notated_musicxml(_spec(name)))
        ly = tmp_path / f"{name}.ly"
        r1 = subprocess.run([str(musicxml2ly), "-o", str(ly), str(xml_path)],
                            capture_output=True, text=True, timeout=300)
        assert r1.returncode == 0, (name, r1.stderr[-800:])
        r2 = subprocess.run([str(exe), "-dno-point-and-click", "-o", str(tmp_path / name), str(ly)],
                            capture_output=True, text=True, timeout=600)
        assert r2.returncode == 0 and (tmp_path / f"{name}.pdf").exists(), (name, r2.stderr[-800:])
        import re
        noise = [l for l in (r1.stderr + r2.stderr).splitlines()
                 if re.search(r"\b(warning|error)\b\s*:", l, re.IGNORECASE)]
        if "polymeter" in _expected(name):
            # musicxml2ly assumes one timing for the score; genuine per-part meters need
            # LilyPond's per-staff Timing_translator, which it does not emit. The export is
            # schema-valid and engraves; the bar-check warning is the recorded limitation.
            noise = [l for l in noise if "bar check failed" not in l]
        assert not noise, (name, noise[:6])
