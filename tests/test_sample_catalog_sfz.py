from audioforge.sampler import parse_sfz
from audioforge.sample_catalog.sfz import build_region_sets, build_regions, write_sfz


def test_generated_sfz_is_stable_and_parseable_subset(tmp_path):
    analyses = [
        {"path": str(tmp_path / "D4.wav"), "status": "accepted", "midi_note": 62},
        {"path": str(tmp_path / "C4.wav"), "status": "accepted", "midi_note": 60},
    ]
    regions = build_regions(analyses)
    path = write_sfz(regions, tmp_path / "instrument.sfz")
    text = path.read_text()

    assert text.index("sample=samples/C4.wav") < text.index("sample=samples/D4.wav")
    parsed, ignored = parse_sfz(text)
    assert ignored == set()
    assert [r.pitch_keycenter for r in parsed] == [60, 62]
    assert parsed[0].lokey == 60
    assert parsed[0].hikey == 61


def test_generated_sfz_uses_explicit_velocity_round_robin_and_articulation(tmp_path):
    analyses = [
        {
            "path": str(tmp_path / "C4_soft_rr1.wav"),
            "status": "accepted",
            "midi_note": 60,
            "velocity_layer": "soft",
            "round_robin_group": "c4_soft",
            "articulation": "staccato",
        },
        {
            "path": str(tmp_path / "C4_soft_rr2.wav"),
            "status": "accepted",
            "midi_note": 60,
            "velocity_layer": "soft",
            "round_robin_group": "c4_soft",
            "articulation": "staccato",
        },
        {
            "path": str(tmp_path / "C4_loud.wav"),
            "status": "accepted",
            "midi_note": 60,
            "velocity_layer": "loud",
            "articulation": "sustain",
        },
    ]

    sets = build_region_sets(analyses)
    assert sorted(sets) == ["staccato", "sustain"]
    stac = sets["staccato"]
    assert [r.lovel for r in stac] == [1, 1]
    assert [r.hivel for r in stac] == [63, 63]
    assert [r.seq_length for r in stac] == [2, 2]
    assert [r.seq_position for r in stac] == [1, 2]
    assert sets["sustain"][0].lovel == 64
    assert sets["sustain"][0].hivel == 127

    path = write_sfz(stac, tmp_path / "staccato.sfz")
    text = path.read_text()
    assert "seq_length=2" in text
    assert "seq_position=1" in text
    assert "seq_position=2" in text
    parsed, ignored = parse_sfz(text)
    assert ignored == set()
    assert [r.seq_position for r in parsed] == [1, 2]


def test_generated_sfz_does_not_round_robin_unrelated_same_pitch_samples(tmp_path):
    analyses = [
        {
            "path": str(tmp_path / "C4_a.wav"),
            "status": "accepted",
            "midi_note": 60,
            "source_id": "source-a",
        },
        {
            "path": str(tmp_path / "C4_b.wav"),
            "status": "accepted",
            "midi_note": 60,
            "source_id": "source-b",
        },
    ]

    regions = build_regions(analyses)

    assert len(regions) == 2
    assert [r.seq_length for r in regions] == [None, None]
    assert [r.seq_position for r in regions] == [None, None]


def test_generated_sfz_uses_same_pack_as_implicit_round_robin_group(tmp_path):
    analyses = [
        {
            "path": str(tmp_path / "C4_pack_rr1.wav"),
            "status": "accepted",
            "midi_note": 60,
            "descriptors": {"pack": "clean-guitar-pack"},
        },
        {
            "path": str(tmp_path / "C4_pack_rr2.wav"),
            "status": "accepted",
            "midi_note": 60,
            "descriptors": {"pack": "clean-guitar-pack"},
        },
    ]

    regions = build_regions(analyses)

    assert [r.seq_length for r in regions] == [2, 2]
    assert [r.seq_position for r in regions] == [1, 2]
