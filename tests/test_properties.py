"""Property tests for deterministic core helpers and theory transforms."""

import pytest
from hypothesis import given, settings, strategies as st

from audioforge.determinism import canonical_json, derive_seed, spec_hash
from audioforge.theory import (
    bjorklund,
    chord_semis,
    diatonic_transpose,
    invert,
    note_to_semis,
    retrograde,
    semis_to_note,
    stretch,
)


CHROMATIC_NOTE_NAMES = st.sampled_from(
    ["C", "C#", "Db", "D", "D#", "Eb", "E", "F", "F#", "Gb", "G", "G#", "Ab", "A", "A#", "Bb", "B"]
)
SCALE_NOTE_NAMES = st.sampled_from(["C", "D", "E", "F", "G", "A", "B"])
OCTAVES = st.integers(min_value=1, max_value=5)
NOTES = st.builds(lambda name, octave: f"{name}{octave}", CHROMATIC_NOTE_NAMES, OCTAVES)
SCALE_NOTES = st.builds(lambda name, octave: f"{name}{octave}", SCALE_NOTE_NAMES, OCTAVES)
EVENT_NOTES = st.builds(
    lambda name, octave: f"{name}{octave}",
    CHROMATIC_NOTE_NAMES,
    st.integers(min_value=2, max_value=4),
)


def note_events():
    return st.lists(
        st.builds(
            lambda start, dur, note: {
                "start_beat": start,
                "dur_beats": dur,
                "note": note,
            },
            st.floats(min_value=0, max_value=64, allow_nan=False, allow_infinity=False),
            st.floats(min_value=0.01, max_value=16, allow_nan=False, allow_infinity=False),
            EVENT_NOTES,
        ),
        min_size=1,
        max_size=16,
    )


@given(st.dictionaries(st.text(max_size=8), st.integers(), max_size=8))
def test_canonical_json_is_key_order_independent(data):
    reversed_items = dict(reversed(list(data.items())))

    assert canonical_json(data) == canonical_json(reversed_items)


@given(st.dictionaries(st.text(max_size=8), st.integers(), max_size=8))
def test_spec_hash_ignores_top_level_meta(data):
    spec = {"id": "prop", "data": data}

    assert spec_hash(spec) == spec_hash({**spec, "_meta": {"line": 123}})


@given(st.text(max_size=64), st.lists(st.text(max_size=16), max_size=6))
def test_derive_seed_is_uint64_and_deterministic(root_hash, path):
    seed = derive_seed(root_hash, *path)

    assert seed == derive_seed(root_hash, *path)
    assert 0 <= seed < 2**64


@given(st.integers(min_value=-12, max_value=119))
def test_note_round_trip_prefers_sharps(semitones):
    assert note_to_semis(semis_to_note(semitones)) == semitones


@given(st.integers(min_value=0, max_value=64), st.integers(min_value=1, max_value=64), st.integers())
def test_bjorklund_length_and_pulse_count(k, n, rotate):
    pattern = bjorklund(k, n, rotate)

    assert len(pattern) == n
    assert set(pattern) <= {"x", "."}
    assert pattern.count("x") == min(k, n)


@given(SCALE_NOTES, st.integers(min_value=-14, max_value=14))
def test_diatonic_transpose_zero_and_round_trip(note, degrees):
    major = [0, 2, 4, 5, 7, 9, 11]

    assert diatonic_transpose(note, 0, 0, major) == semis_to_note(note_to_semis(note))
    moved = diatonic_transpose(note, degrees, 0, major)
    restored = diatonic_transpose(moved, -degrees, 0, major)
    assert note_to_semis(restored) == note_to_semis(note)


@given(note_events())
@settings(max_examples=80)
def test_retrograde_preserves_durations_and_span(events):
    span = max(e["start_beat"] + e["dur_beats"] for e in events)
    out = retrograde(events)
    expected_starts = sorted(
        round(span - (e["start_beat"] + e["dur_beats"]), 6) for e in events
    )

    assert [e["dur_beats"] for e in sorted(out, key=lambda e: e["dur_beats"])] == [
        e["dur_beats"] for e in sorted(events, key=lambda e: e["dur_beats"])
    ]
    assert [e["start_beat"] for e in out] == expected_starts
    assert out == sorted(out, key=lambda e: e["start_beat"])


@given(note_events())
@settings(max_examples=80)
def test_invert_is_its_own_inverse_for_pitches(events):
    axis_event = min(events, key=lambda e: (e["start_beat"], note_to_semis(e["note"])))
    axis = note_to_semis(axis_event["note"])
    out = invert(events)

    assert [note_to_semis(e["note"]) for e in out] == [
        2 * axis - note_to_semis(e["note"]) for e in events
    ]
    assert [e["start_beat"] for e in out] == [e["start_beat"] for e in events]
    assert [e["dur_beats"] for e in out] == [e["dur_beats"] for e in events]


@given(note_events(), st.floats(min_value=0.01, max_value=8, allow_nan=False, allow_infinity=False))
@settings(max_examples=80)
def test_stretch_scales_start_and_duration(events, factor):
    out = stretch(events, factor)

    assert len(out) == len(events)
    for original, scaled in zip(events, out):
        assert scaled["note"] == original["note"]
        assert scaled["start_beat"] == pytest.approx(original["start_beat"] * factor, abs=1e-6)
        assert scaled["dur_beats"] == pytest.approx(original["dur_beats"] * factor, abs=1e-6)


@given(NOTES, st.sampled_from(["maj", "min", "7", "maj7", "min7"]), st.sampled_from(["close", "wide", "inv1", "inv2"]))
def test_chord_voicings_are_sorted_absolute_pitches(root, quality, voicing):
    pitches = chord_semis(root, quality, voicing)

    assert pitches == sorted(pitches)
    assert all(isinstance(pitch, int) for pitch in pitches)
