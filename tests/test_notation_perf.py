"""Notation budgets (HARNESS-NPERF-001…004; roadmap-notation RN-Q-001).

Budgets are the harness values on the reference machine. They are generous on purpose:
a budget test guards against order-of-magnitude regressions, not jitter. The LilyPond
budget needs the `engrave` extra and skips loudly without it.
"""
import time
from pathlib import Path

import pytest

from audioforge import interop
from audioforge.musicxml import TPQ

BEATS_PER_BAR = 4
MEASURES = 116
NAMES = ["C", "D", "E", "F", "G", "A", "B"]


def _big_spec(layers: int = 7, measures: int = MEASURES) -> dict:
    """~3 000 notes over 116 measures of 4/4 at 120 bpm (one note per beat per layer)."""
    beats = measures * BEATS_PER_BAR
    spec = {"id": "perf_orchestral", "kind": "cue", "duration_s": beats * 0.5, "bpm": 120.0,
            "key": "C major", "score": {"meter": {"beats": BEATS_PER_BAR, "unit": 4}},
            "tempo_map": [[0, 120], [beats / 2, 96], [beats, 120]],
            "layers": []}
    for li in range(layers):
        notes = [{"note": f"{NAMES[(b + li) % 7]}{3 + (li % 3)}", "start_beat": float(b), "dur_beats": 1.0,
                  "vel": 0.5 + 0.4 * ((b + li) % 3) / 2, **({"art": "staccato"} if b % 5 == 0 else {})}
                 for b in range(beats)]
        spec["layers"].append({"name": f"v{li}", "type": "notes", "osc": "sine", "notes": notes,
                               "dynamic": [[0.0, 0.35], [beats / 2, 0.87], [float(beats), 0.22]]})
    return spec


def _chorale_xml() -> str:
    """A four-part, ten-measure chorale-shaped score (our own notated export)."""
    spec = {"id": "chorale", "kind": "cue", "duration_s": 20.0, "bpm": 120.0, "key": "G major",
            "score": {"meter": {"beats": 4, "unit": 4}}, "layers": []}
    for li, octave in enumerate((5, 4, 4, 3)):
        spec["layers"].append({"name": f"p{li}", "type": "notes", "osc": "sine", "notes": [
            {"note": f"{NAMES[(b * (li + 1)) % 7]}{octave}", "start_beat": float(b), "dur_beats": 1.0}
            for b in range(40)]})
    return interop.export_notated_musicxml(spec)


def _timed(fn, *args):
    t0 = time.perf_counter()
    out = fn(*args)
    return out, time.perf_counter() - t0


def test_export_budgets_notated_musicxml_and_midi():
    spec = _big_spec()
    assert sum(len(l["notes"]) for l in spec["layers"]) >= 3000
    xml, dt_xml = _timed(interop.export_notated_musicxml, spec)
    assert dt_xml <= 1.0, f"notated export took {dt_xml:.2f}s (budget 1.0s)"
    midi, dt_midi = _timed(interop.export_midi_bytes, spec)
    assert dt_midi <= 0.5, f"MIDI export took {dt_midi:.2f}s (budget 0.5s)"
    assert xml.count("<measure ") == MEASURES * len(spec["layers"]) and midi.startswith(b"MThd")


def test_import_budget_four_part_chorale():
    xml = _chorale_xml()
    spec, dt = _timed(interop.import_musicxml, xml)
    assert dt <= 1.0, f"import took {dt:.2f}s (budget 1.0s)"
    assert len(spec["layers"]) == 4 and sum(len(l["notes"]) for l in spec["layers"]) == 160


def test_proof_sheet_budget_116_measures(tmp_path):
    from audioforge.score import score_pdf
    out = tmp_path / "perf.pdf"
    _, dt = _timed(score_pdf, _big_spec(), out)
    assert dt <= 15.0, f"proof sheet took {dt:.2f}s (budget 15s)"
    assert out.stat().st_size > 0


def test_lilypond_budget_116_measures(tmp_path):
    pytest.importorskip("lilypond", reason="install the engrave extra")
    from audioforge.lilypond import engrave
    spec = _big_spec(layers=4)
    result, dt = _timed(engrave, spec, tmp_path / "perf.pdf")
    assert dt <= 30.0, f"musicxml2ly + lilypond took {dt:.1f}s (budget 30s)"
    assert result.pdf.exists() and result.pdf.stat().st_size > 0
    assert Path(result.pdf).suffix == ".pdf"
