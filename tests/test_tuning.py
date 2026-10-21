"""Tuning activation (ADR-0014; HARNESS-NTUN-001/002/004).

A non-12-EDO `tuning:` directive now drives the render: note names are spelled along
the chain of fifths and land on their EDO degree (proved by FFT), the default path is
bit-for-bit 12-TET, and microtonal pitches leave the engine as decimal MusicXML alters
and per-note MIDI pitch bends.
"""
import math
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
import pytest

from audioforge import AudioForge, interop, synth
from audioforge.dsl import compile_dsl
from audioforge.tuning import Tuning, freq_for, with_tuning

FIX = Path(__file__).parent / "fixtures" / "notation"
NOTES = ["C-1", "A0", "C4", "C#4", "Db4", "F#3", "Bb2", "A4", "G9", "E5", "Cb5", "B#3"]


def test_default_tuning_is_12_tet_bit_for_bit():
    t = Tuning()
    assert t.is_default and t.fifth == 7 and t.sharp == 1 and t.sidecar() is None
    for note in NOTES:
        assert t.note_to_freq(note) == synth.note_to_freq(note), note
    assert t.steps("A4") - t.steps("C4") == 9 and t.steps("C4") == 48
    assert freq_for({"freq_hz": 432.0, "note": "A4"}, {}) == 432.0        # explicit Hz wins
    assert with_tuning({"name": "m"}, {"notation": {}}) == {"name": "m"}   # no sidecar by default


def test_19_edo_spells_along_the_chain_of_fifths():
    t = Tuning(19)
    assert t.fifth == 11 and t.sharp == 1 and t.step_cents == pytest.approx(63.158, abs=1e-3)
    c4 = t.steps("C4")
    names = ("C4", "C#4", "Db4", "D4", "D#4", "Eb4", "E4", "F4", "F#4", "Gb4", "G4",
             "G#4", "Ab4", "A4", "A#4", "Bb4", "B4", "Cb5", "C5")
    assert [t.steps(n) - c4 for n in names] == list(range(20)) [:7] + list(range(8, 20))
    assert t.note_to_freq("A4") == 440.0
    assert t.note_to_freq("C#4") == pytest.approx(440.0 * 2 ** (-13 / 19))
    assert (Tuning(31).fifth, Tuning(31).sharp) == (18, 2)
    assert (Tuning(24).fifth, Tuning(24).sharp) == (14, 2)
    assert (Tuning(17).fifth, Tuning(17).sharp) == (10, 2)
    assert Tuning(22).sharp == 3 and Tuning(7).sharp == 0
    assert Tuning(19, "C4", 261.63).note_to_freq("C4") == 261.63
    with pytest.raises(ValueError):
        Tuning(0)
    with pytest.raises(ValueError):
        Tuning.from_directive({"system": "just"})
    with pytest.raises(ValueError):
        t.steps("H4")


def _peak_hz(audio: np.ndarray, sr: int) -> float:
    mono = audio.mean(axis=1) if audio.ndim == 2 else audio
    n = len(mono)
    spectrum = np.abs(np.fft.rfft(mono * np.hanning(n)))
    k = int(np.argmax(spectrum[1:-1])) + 1
    a, b, c = (math.log(spectrum[k + d] + 1e-12) for d in (-1, 0, 1))
    delta = 0.5 * (a - c) / (a - 2 * b + c) if (a - 2 * b + c) else 0.0
    return (k + delta) * sr / n


SRC = """asset t {{ kind: cue
  duration: 2s
  tempo: 120bpm
  {tuning}
  layer m : notes {{ osc: sine
    notes: {note} @ 0b for 4b }}
}}"""


def _render(src: str):
    result = AudioForge().compile(src)
    assert result.ok, result.diagnostics
    audio, sr, _meta = result.assets[0].render()
    return audio, sr, result


def test_non_12_edo_render_places_the_fundamental_at_the_edo_degree_edo_fft():
    for note in ("C#4", "E5", "Bb3"):
        audio, sr, _ = _render(SRC.format(tuning="tuning: edo divisions=19 base=A4 hz=440", note=note))
        expected = Tuning(19).note_to_freq(note)
        cents = 1200 * math.log2(_peak_hz(audio, sr) / expected)
        assert abs(cents) <= 5, (note, cents)
        # …and that degree is audibly not the 12-TET note the name would otherwise mean
        assert abs(1200 * math.log2(expected / synth.note_to_freq(note))) > 5, note


def test_12_edo_directive_and_no_directive_render_identically_and_silently():
    a, _, _ = _render(SRC.format(tuning="", note="C#4"))
    b, _, _ = _render(SRC.format(tuning="tuning: edo divisions=12 base=A4 hz=440", note="C#4"))
    assert np.array_equal(a, b)
    _, _, result = _render(SRC.format(tuning="tuning: edo divisions=19 base=A4 hz=440", note="C#4"))
    assert not [d for d in result.diagnostics if "tuning" in d.message.lower()]
    from audioforge.capabilities import capability_manifest
    manifest = capability_manifest()
    assert "tuning_not_rendered" not in manifest["diagnostic_codes"]     # retired with ADR-0014
    assert manifest["notation"]["directives"]["tuning"]["rendering"] == "n_edo_resolver"


def test_microtonal_interop_exports_decimal_alter_and_pitch_bend():
    spec = compile_dsl((FIX / "microtonal_19edo.af").read_text())[0][0]
    t = Tuning.from_spec(spec)
    assert t.divisions == 19
    for xml in (interop.export_notated_musicxml(spec), interop.export_musicxml(spec)):
        root = ET.fromstring(xml.split("\n", 1)[1] if xml.startswith("<?xml") else xml)
        alters = {(p.findtext("step"), p.findtext("octave")): float(p.findtext("alter", "0"))
                  for p in root.iter("pitch")}
        assert alters[("C", "5")] == pytest.approx(t.xml_alter("C#5"), abs=0.01)
        assert abs(alters[("C", "5")] - 1.0) > 0.1            # a 19-EDO sharp is not a 12-TET one
        assert alters[("B", "4")] == pytest.approx(t.xml_alter("B4"), abs=0.01) and alters[("B", "4")] != 0
        assert alters[("A", "4")] == 0.0                       # the reference note is exact
        # The decimal <alter> is the sounding pitch; the written spelling travels in
        # <accidental> (music21 reads a non-half-step alter only alongside one).
        written = {(n.findtext("pitch/step"), n.findtext("pitch/octave")): n.findtext("accidental")
                   for n in root.iter("note") if n.find("pitch") is not None}
        assert written == {("A", "4"): "natural", ("B", "4"): "natural",
                           ("C", "5"): "sharp", ("E", "5"): "natural"}
    twelve = dict(spec, notation={k: v for k, v in spec["notation"].items() if k != "tuning"})
    for xml in (interop.export_notated_musicxml(twelve), interop.export_musicxml(twelve)):
        assert "<accidental" not in xml                        # 12-TET exports are unchanged
    data = interop.export_midi_bytes(spec)
    _, _, tracks = interop._split_tracks(data)
    assert b"\xb0\x65\x00" in tracks[1] and b"\xb0\x06\x02" in tracks[1]   # RPN 0 = 2 semitones
    back = interop.import_midi_bytes(data)
    curve = [a for a in back["layers"][0].get("automation", []) if a["target"] == "pitch_cents"]
    assert curve, "pitch bends must import as a pitch_cents curve"
    want = (float(synth.freq_to_midi(t.note_to_freq("C#5"))) - round(float(synth.freq_to_midi(t.note_to_freq("C#5"))))) * 100
    assert any(abs(v - want) < 1.5 for _, v in curve[0]["points"]), (want, curve[0]["points"])
    assert "lossy_tuning" not in {d["code"] for d in interop.interop_diagnostics(spec, "midi")}
    chordal = dict(spec, layers=[{"name": "c", "type": "notes", "notes": [
        {"note": "C4", "start_beat": 0.0, "dur_beats": 1.0}, {"note": "E4", "start_beat": 0.0, "dur_beats": 1.0}]}])
    assert "lossy_tuning" in {d["code"] for d in interop.interop_diagnostics(chordal, "midi")}
    assert not {d["code"] for d in interop.interop_diagnostics(chordal, "musicxml_notated")} & {"lossy_tuning"}
