"""Timeline warnings must describe the conductor clock used in the render."""
from audioforge.sdk import _timeline_warnings


def _spec(tempo, start=12, duration=2, seconds=10, offset=0, holds=None):
    return {"bpm": tempo[0][1], "tempo_map": tempo, "duration_s": seconds,
            "holds": holds or [], "layers": [{"type": "notes", "name": "voice",
                "start_s": offset, "notes": [{"note": "A4", "start_beat": start,
                                              "dur_beats": duration}]}]}


def test_accelerating_score_notes_fit_even_when_opening_tempo_would_overrun():
    assert _timeline_warnings(_spec([[0, 60], [4, 120]])) == []


def test_ritardando_can_overrun_even_when_opening_tempo_would_fit():
    warnings = _timeline_warnings(_spec([[0, 120], [4, 60]]))
    assert len(warnings) == 1
    assert warnings[0].path == "layers.0.notes.0"


def test_fermata_and_layer_offset_are_part_of_the_clock():
    spec = _spec([[0, 120]], start=8, duration=2, seconds=7, offset=1,
                 holds=[{"beat": 4, "duration_s": 2}])
    assert len(_timeline_warnings(spec)) == 1
    spec["duration_s"] = 8
    assert _timeline_warnings(spec) == []
