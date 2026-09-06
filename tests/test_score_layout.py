"""Regression tests for score title-page layout robustness.

Drawing a dense, long-header orchestral proof sheet
(``docs/examples/orchestral/fable-symphony-orchestral-v2/fable_symphony_orchestral_v2.af``) surfaced two title-page

pollution bugs:

  1. the program-notes blurb overran its column and overprinted the footer
     caption (``Proportional notation — …``);
  2. stage seat labels for sources at near-identical azimuth/distance
     overprinted each other (``Trumpet``/``Tuba``, ``Contrabass``/
     ``Contrabass Pizz``, ``Violins``/``Harp``).

These lock the two pure layout helpers that fix both, plus an end-to-end smoke
test that the exact conditions which polluted the page now draw a valid PDF.
"""
import pytest

pytest.importorskip("matplotlib")
from audioforge import score  # noqa: E402


# --------------------------------------------------------- program clamp ----

def test_clamp_lines_passthrough():
    lines = ["alpha", "beta", "gamma"]
    assert score._clamp_lines(lines, 10) == lines


def test_clamp_lines_truncates_with_ellipsis():
    lines = [f"line {i}" for i in range(40)]
    out = score._clamp_lines(lines, 10)
    assert len(out) == 10
    assert out[-1].endswith("…")
    assert out[:9] == lines[:9]          # earlier lines untouched


def test_clamp_lines_strips_trailing_punctuation_before_ellipsis():
    out = score._clamp_lines(["a", "b. ", "c", "d"], 2)
    assert out[-1] == "b …"              # no doubled ". …"


def test_clamp_lines_nonpositive_budget_is_empty():
    assert score._clamp_lines(["x", "y"], 0) == []


# ------------------------------------------------------- label declutter ----

def test_declutter_enforces_min_gap():
    ys = [1.00, 1.02, 1.03, 5.00]        # first three collide
    out = score._declutter(ys, 0.10)
    ordered = sorted(out)
    assert all(b - a >= 0.10 - 1e-9 for a, b in zip(ordered, ordered[1:]))
    assert len(out) == len(ys)


def test_declutter_preserves_centroid():
    ys = [1.00, 1.01, 1.02]
    out = score._declutter(ys, 0.10)
    assert abs(sum(out) / len(out) - sum(ys) / len(ys)) < 1e-9


def test_declutter_already_spaced_is_unchanged():
    ys = [1.0, 2.0, 3.0]
    assert score._declutter(ys, 0.10) == ys


def test_declutter_singleton_and_empty():
    assert score._declutter([2.5], 0.10) == [2.5]
    assert score._declutter([], 0.10) == []


# ----------------------------------------------------- end-to-end smoke -----

def test_family_classification():
    assert score._family_of({"source": "ViolinEnsSusVib", "name": "violins"}) == "Strings"
    assert score._family_of({"source": "ContrabassPizz", "name": "cb_pizz"}) == "Strings"
    assert score._family_of({"source": "FluteSusVib", "name": "flute"}) == "Woodwinds"
    assert score._family_of({"source": "BassoonSus", "name": "bassoon"}) == "Woodwinds"
    assert score._family_of({"source": "TrumpetSus", "name": "trumpet"}) == "Brass"
    assert score._family_of({"source": "FHornSus", "name": "horns"}) == "Brass"
    assert score._family_of({"source": "TubaSus", "name": "tuba"}) == "Brass"
    assert score._family_of({"source": "Timpani", "name": "timpani"}) == "Percussion"
    assert score._family_of({"source": "Harp", "name": "harp"}) == "Percussion"


def test_group_families_order_and_nonempty():
    staves = [
        {"source": "Harp", "name": "harp"},
        {"source": "ViolinEnsSusVib", "name": "violins"},
        {"source": "TrumpetSus", "name": "trumpet"},
        {"source": "CelloEnsSusVib", "name": "cellos"},
    ]
    groups = score._group_families(staves)
    names = [g[0] for g in groups]
    assert names == ["Strings", "Brass", "Percussion"]   # Woodwinds absent → skipped
    # spec order preserved within a family
    assert [s["name"] for s in dict(groups)["Strings"]] == ["violins", "cellos"]


def test_family_geo_is_roomier_than_packed_floor():
    """A 4-staff family page gives each staff a lane far taller than the 0.40in
    floor that produced the merged 17-staff grid."""
    packed = score._layout(17, 8)["block"]
    roomy = score._family_geo(4, 8)["block"]
    assert packed <= 0.40 + 1e-9
    assert roomy >= 0.58
    assert roomy > packed * 1.4


def test_long_header_dense_seating_draws(tmp_path):
    """Reproduce the pollution conditions: a very long program blurb plus many
    sources at an identical seat. Must produce a valid PDF without raising."""
    spec = {
        "id": "stress_layout",
        "kind": "soundtrack",
        "duration_s": 8.0,
        "bpm": 120.0,
        "key": "C major",
        "library": {"name": "m", "manifest_sha256": "a" * 64},
        "stage": {
            "dims": [20.0, 30.0, 12.0],
            "mics": {"tree": 0.6, "close": 0.2},
            "hall_file": "h.wav",
            "hall_sha256": "b" * 64,
        },
        "emotion": {"awe": 0.6, "calm": 0.3},
        "layers": [
            {
                "name": f"section_{i}",
                "type": "instrument",
                "instrument": "violin",
                "seat": {"az_deg": 30.0, "dist_m": 7.0},   # all identical
                "notes": [
                    {"note": "C4", "start_beat": 0.0, "dur_beats": 1.0,
                     "vel": 0.6},
                ],
            }
            for i in range(6)
        ],
    }
    program = "Very long header sentence that repeats. " * 120
    out = tmp_path / "stress.pdf"
    score.score_pdf(spec, str(out), title="Stress", program=program)
    data = out.read_bytes()
    assert data[:4] == b"%PDF" and len(data) > 1000


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-q"]))
