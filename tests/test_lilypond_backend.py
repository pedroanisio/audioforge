"""`audioforge score --engrave` (ADR-0009 D4; HARNESS-NENG-002).

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
