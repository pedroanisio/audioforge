from pathlib import Path

import pytest

from audioforge import AudioForge


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "static" / "fixtures"


def _compile_fixture(path: Path):
    result = AudioForge().compile(path.read_text())
    return result


def _note_targets(note: dict) -> list[str]:
    return [curve["target"] for curve in note.get("curves", [])]


def test_expressive_techniques_acceptance_fixture_golden_ir_snapshot():
    result = _compile_fixture(FIXTURES / "expressive_techniques.af")

    assert result.ok, [d.message for d in result.diagnostics]
    spec = result.assets[0].spec
    layer = spec["layers"][0]
    snapshot = {
        "id": spec["id"],
        "tuning": layer["tuning"],
        "max_fret": layer["max_fret"],
        "notes": [
            {
                "note": note["note"],
                "string": note["string"],
                "fret": note["fret"],
                "targets": _note_targets(note),
            }
            for note in layer["notes"]
        ],
    }

    assert snapshot == {
        "id": "expressive_techniques",
        "tuning": ["E2", "A2", "D3", "G3", "B3", "E4"],
        "max_fret": 24,
        "notes": [
            {
                "note": "E2",
                "string": 1,
                "fret": 0,
                "targets": ["gain_db", "cutoff_hz"],
            },
            {
                "note": "A2",
                "string": 2,
                "fret": 0,
                "targets": ["cutoff_hz", "gain_db"],
            },
            {
                "note": "E4",
                "string": 6,
                "fret": 0,
                "targets": ["scan", "dynamic", "cutoff_hz"],
            },
            {
                "note": "E4",
                "string": 6,
                "fret": "x",
                "targets": ["gain_db", "cutoff_hz"],
            },
        ],
    }


def test_physical_pitch_curve_fixture_now_compiles():
    """Physical-model pitch curves are staged (varispeed realisation)."""
    result = _compile_fixture(FIXTURES / "expressive_physical_pitch_curve.af")
    assert result.ok, [d.message for d in result.diagnostics]
    note = result.assets[0].spec["layers"][0]["notes"][0]
    assert any(c["target"] == "pitch_cents" for c in note.get("curves", []))


@pytest.mark.parametrize(("filename", "code"), [
    ("expressive_scan_non_morph.af", "scan_requires_morph_osc"),
    ("expressive_duplicate_cutoff.af", "duplicate_note_timbre_curve"),
])
def test_expressive_techniques_rejection_fixtures_fail_with_codes(filename, code):
    result = _compile_fixture(FIXTURES / "rejections" / filename)

    assert not result.ok
    assert any(code in diagnostic.message for diagnostic in result.diagnostics)
