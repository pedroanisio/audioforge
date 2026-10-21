"""`audioforge score --engrave` (ADR-0011 D4; HARNESS-NENG-002).

Without the `engrave` extra the verb exits 3 with the install hint and never touches the
proof sheet; with it (oracle interpreter) LilyPond produces the PDF and the CLI says so.
"""
import builtins
import sys
from pathlib import Path

import pytest

from audioforge import cli
from audioforge.lilypond import EXIT_OPTIONAL_DEPENDENCY_MISSING, INSTALL_HINT, EngraverUnavailable

FIXTURE = Path(__file__).parent / "fixtures" / "notation" / "meter_3_4_two_parts.af"


def _without_lilypond(monkeypatch):
    real_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "lilypond" and level == 0:          # the wheel, not audioforge.lilypond
            raise ImportError("no module named lilypond")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    monkeypatch.delitem(sys.modules, "lilypond", raising=False)


def test_score_help_documents_engrave():
    import subprocess
    out = subprocess.run([sys.executable, "-m", "audioforge.cli", "score", "--help"],
                         capture_output=True, text=True)
    import re
    assert "--engrave" in out.stdout and re.search(r"exit\s+3", out.stdout)   # argparse wraps lines


def test_engrave_without_the_extra_exits_3_with_the_hint(tmp_path, monkeypatch, capsys):
    _without_lilypond(monkeypatch)
    out = tmp_path / "score.pdf"
    code = cli.main(["score", str(FIXTURE), "-o", str(out), "--engrave"])
    assert code == EXIT_OPTIONAL_DEPENDENCY_MISSING == 3
    assert INSTALL_HINT in capsys.readouterr().err
    assert not out.exists()
    from audioforge.lilypond import executables
    with pytest.raises(EngraverUnavailable):
        executables()


def test_proof_sheet_path_is_unchanged_by_the_flag_being_absent(tmp_path):
    out = tmp_path / "sheet.pdf"
    assert cli.main(["score", str(FIXTURE), "-o", str(out)]) == 0
    assert out.stat().st_size > 0


def test_engrave_with_the_extra_produces_a_lilypond_pdf(tmp_path, capsys):
    pytest.importorskip("lilypond", reason="install the engrave extra")
    out = tmp_path / "engraved.pdf"
    assert cli.main(["score", str(FIXTURE), "-o", str(out), "--engrave"]) == 0
    assert out.read_bytes().startswith(b"%PDF")
    text = capsys.readouterr().out
    assert "engraved by LilyPond" in text
    from audioforge.lilypond import engrave
    result = engrave(__import__("audioforge.dsl", fromlist=["compile_dsl"]).compile_dsl(FIXTURE.read_text())[0][0],
                     tmp_path / "again.pdf", keep_ly=True)
    assert result.ly is not None and result.ly.exists() and not result.warnings


MICROTONAL = Path(__file__).parent / "fixtures" / "notation" / "microtonal_19edo.af"


def _spec(path: Path) -> dict:
    from audioforge.dsl import compile_dsl
    return compile_dsl(path.read_text())[0][0]


def test_engraving_input_spells_a_non_12_tuning_in_written_pitches():
    """LilyPond spells only half- and quarter-tone alterations and truncates the rest
    (a 19-EDO C#5, alter 0.789, would engrave as C natural), so the engraving input
    carries the written spelling; the sounding offsets stay in the MusicXML export."""
    import xml.etree.ElementTree as ET
    from audioforge.lilypond import engraving_musicxml, tuning_note
    xml = engraving_musicxml(_spec(MICROTONAL))
    root = ET.fromstring(xml.split("\n", 1)[1] if xml.startswith("<?xml") else xml)
    alters = {(p.findtext("step"), p.findtext("octave")): p.findtext("alter")
              for p in root.iter("pitch")}
    assert alters == {("A", "4"): None, ("B", "4"): None, ("C", "5"): "1", ("E", "5"): None}
    assert root.find(".//accidental") is None
    assert "19-EDO" in tuning_note(_spec(MICROTONAL))


def test_engraving_input_is_the_notated_export_under_12_tet():
    from audioforge.interop import export_notated_musicxml
    from audioforge.lilypond import engraving_musicxml, tuning_note
    spec = _spec(FIXTURE)
    assert engraving_musicxml(spec) == export_notated_musicxml(spec)
    assert tuning_note(spec) is None


def test_engrave_a_19_edo_score_in_its_written_spelling(tmp_path, capsys):
    pytest.importorskip("lilypond", reason="install the engrave extra")
    from audioforge.lilypond import engrave
    result = engrave(_spec(MICROTONAL), tmp_path / "edo.pdf", keep_ly=True)
    assert not result.warnings, result.warnings
    ly = " ".join(result.ly.read_text().split())
    assert "\\relative a' {" in ly and "a2 b2 | % 2 cis2 e2 }" in ly   # C#5 stays sharp, not truncated
    assert result.tuning_note and "19-EDO" in result.tuning_note
    assert cli.main(["score", str(MICROTONAL), "-o", str(tmp_path / "cli.pdf"), "--engrave"]) == 0
    assert "19-EDO" in capsys.readouterr().out
