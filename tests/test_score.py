from pathlib import Path

import pytest

from audioforge import score


def _rich_score_spec() -> dict:
    return {
        "id": "contra_silencio_iv",
        "kind": "soundtrack",
        "duration_s": 12.0,
        "bpm": 120.0,
        "key": "C major",
        "key_map": [[0.0, "C", "major"], [8.0, "D", "minor"]],
        "library": {"name": "mini", "manifest_sha256": "a" * 64},
        "stage": {
            "dims": [15.0, 23.0, 12.0],
            "mics": {"ortf": 1.2, "room": 8.0},
            "hall_file": "hall.wav",
            "hall_sha256": "b" * 64,
        },
        "markers": [{"name": "cut_point", "time_s": 1.0}],
        "intensity_curve": [[0.0, 0.1], [0.5, 0.8], [1.0, 0.3]],
        "emotion": {"tension": 0.9, "calm": 0.2},
        "layers": [
            {
                "name": "voz",
                "type": "notes",
                "osc": "sine",
                "humanize": {"timing_s": 0.0},
                "articulation": "staccato",
                "seat": {"az_deg": -12.0, "dist_m": 4.0},
                "dynamic": [[0.0, 0.2], [4.0, 0.8]],
                "notes": [
                    {"note": "C4", "start_beat": 0.0, "dur_beats": 1.0, "vel": 0.4},
                    {"note": "F#4", "start_beat": 1.5, "dur_beats": 0.5, "vel": 0.9},
                    {"note": "Bb4", "start_beat": 4.0, "dur_beats": 2.0, "vel": 0.7},
                    {"note": "C5", "start_beat": 9.0, "dur_beats": 1.0, "vel": 0.6},
                ],
            },
            {
                "name": "peso",
                "type": "instrument",
                "instrument": "cello",
                "seat": {"az_deg": 15.0, "dist_m": 5.0},
                "notes": [
                    {"note": "C2", "start_beat": 0.0, "dur_beats": 4.0, "vel": 0.8},
                    {"freq_hz": 110.0, "start_beat": 5.0, "dur_beats": 2.0, "vel": 0.5},
                ],
            },
            {
                "name": "air",
                "type": "noise",
                "duration_s": 12.0,
            },
        ],
    }


def test_score_model_helpers_are_deterministic():
    assert score._parse_pitch("F#4") == ("F", 1, 4, 31)
    assert score._parse_pitch("bad") is None
    assert score._event_pitch({"freq_hz": 440.0}) == "A4"
    assert score._key_sig("Bb", "major")[0] == -2
    assert score._key_sig("E", "minor")[0] == 1
    assert score._dyn_mark(0.59) == "mf"
    assert score._pretty("peso_sub") == "O Peso 8vb"
    assert score._title_from_id("contra_silencio_iv") == "Contra Silencio IV"
    assert score._source({"instrument": "violin"}) == "violin"
    unison_label = score._source({"osc": "saw", "unison": 3})
    assert unison_label.startswith("saw") and unison_label.endswith("3")
    assert score._source({"type": "noise"}) == "noise"

    staves = score._staves(_rich_score_spec())
    assert [s["label"] for s in staves] == ["A Voz", "O Peso"]
    assert staves[0]["clef"] == "treble"
    assert staves[1]["clef"] == "bass"
    assert staves[0]["rigid"] is True
    assert score._layout(len(staves), bars_per_sys=2)["beats"] == 8
    assert score._y_of(staves[0]["notes"][0]["diat"], "treble", 4.0) != 4.0


def test_score_pdf_renders_rich_extended_score(tmp_path):
    out = tmp_path / "score.pdf"

    result = score.score_pdf(
        _rich_score_spec(),
        out,
        title="Contra o Silencio",
        program="CONTRA O SILENCIO - banner\nA staged proportional score.",
        bars_per_system=2,
    )

    assert result == out
    assert out.exists()
    assert out.stat().st_size > 1000


def test_score_pdf_handles_multi_asset_and_no_pitched_cases(tmp_path):
    spec = _rich_score_spec()
    no_stage = {**spec, "id": "plain_asset", "stage": {}, "layers": [spec["layers"][0]]}
    out = tmp_path / "multi.pdf"

    score.score_pdf([spec, no_stage], out, subtitle="custom", bars_per_system=4)
    assert out.stat().st_size > 1000

    with pytest.raises(ValueError, match="no pitched layers"):
        score.score_pdf({"id": "empty", "duration_s": 1.0, "layers": []},
                        tmp_path / "empty.pdf")
