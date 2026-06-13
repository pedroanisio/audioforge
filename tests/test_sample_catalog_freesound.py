from audioforge.sample_catalog.sources import FreesoundAdapter


class FakeHttp:
    def __init__(self):
        self.calls = []

    def get_json(self, url, *, params=None, headers=None):
        self.calls.append((url, params, headers))
        if len(self.calls) == 1:
            return {
                "next": "https://freesound.org/apiv2/search/text/?page=2",
                "results": [
                    {
                        "id": 1,
                        "name": "Guitar C4.wav",
                        "url": "https://freesound.org/s/1/",
                        "download": "https://freesound.org/apiv2/sounds/1/download/",
                        "license": "https://creativecommons.org/publicdomain/zero/1.0/",
                        "username": "alice",
                        "tags": ["guitar", "c4"],
                        "type": "wav",
                        "duration": 1.2,
                        "filesize": 100,
                        "avg_rating": 4.5,
                        "num_ratings": 8,
                        "analysis": {"lowlevel": {}},
                    },
                    {
                        "id": 2,
                        "name": "By sample.wav",
                        "url": "https://freesound.org/s/2/",
                        "download": "https://freesound.org/apiv2/sounds/2/download/",
                        "license": "CC-BY",
                        "username": "bob",
                        "tags": ["guitar"],
                        "type": "wav",
                    },
                ],
            }
        return {
            "next": None,
            "results": [{
                "id": 3,
                "name": "Guitar D4.flac",
                "url": "https://freesound.org/s/3/",
                "download": "https://freesound.org/apiv2/sounds/3/download/",
                "license": "Creative Commons 0",
                "username": "cara",
                "tags": ["guitar", "d4"],
                "type": "flac",
            }],
        }


def test_freesound_search_uses_fields_filters_pagination_and_cc0_only():
    http = FakeHttp()
    adapter = FreesoundAdapter(
        http, token="tok", fetched_at="2026-06-12T00:00:00+00:00")
    candidates = adapter.search(instrument="guitar", limit=2)

    assert [c.source_id for c in candidates] == ["1", "3"]
    first_url, first_params, first_headers = http.calls[0]
    assert first_url.endswith("/search/text/")
    assert "fields" in first_params
    assert "avg_rating" in first_params["fields"]
    assert "num_ratings" in first_params["fields"]
    assert 'license:"Creative Commons 0"' in first_params["filter"]
    assert "tag:guitar" in first_params["filter"]
    assert "(type:wav OR type:aiff OR type:flac)" in first_params["filter"]
    assert "duration:[0.08 TO 12]" in first_params["filter"]
    assert "avg_rating:[3 TO *]" in first_params["filter"]
    assert "-tag:loop" in first_params["filter"]
    assert "-tag:speech" in first_params["filter"]
    assert "-tag:field-recording" in first_params["filter"]
    assert first_headers == {"Authorization": "Bearer tok"}
    assert http.calls[1][1] is None
    assert candidates[0].evidence.evidence_hash
    assert candidates[0].decision.accepted
    assert candidates[0].descriptors["avg_rating"] == 4.5
    assert candidates[0].descriptors["num_ratings"] == 8


def test_freesound_search_rate_limits_paginated_requests():
    http = FakeHttp()
    sleeps = []
    current_time = [100.0]

    adapter = FreesoundAdapter(
        http,
        min_interval_s=0.75,
        sleep=sleeps.append,
        now=lambda: current_time[0],
    )
    candidates = adapter.search(instrument="guitar", limit=2)

    assert [c.source_id for c in candidates] == ["1", "3"]
    assert sleeps == [0.75]
    assert len(http.calls) == 2


def test_freesound_search_can_include_quarantined_results_for_review():
    candidates = FreesoundAdapter(FakeHttp()).search(
        instrument="guitar", limit=3, include_quarantine=True)
    by_id = {c.source_id: c for c in candidates}
    assert by_id["2"].decision.status == "quarantine"


class UnsafeFreesoundHttp:
    def get_json(self, url, *, params=None, headers=None):
        return {
            "next": None,
            "results": [
                {
                    "id": 4,
                    "name": "No download.wav",
                    "url": "https://freesound.org/s/4/",
                    "license": "CC0",
                    "username": "dana",
                    "tags": ["guitar"],
                    "type": "wav",
                },
                {
                    "id": 5,
                    "name": "Preview only.wav",
                    "url": "https://freesound.org/s/5/",
                    "previews": {"preview-hq-mp3": "https://cdn.example/5.mp3"},
                    "license": "CC0",
                    "username": "eli",
                    "tags": ["guitar"],
                    "type": "wav",
                },
                {
                    "id": 6,
                    "name": "Compressed.mp3",
                    "url": "https://freesound.org/s/6/",
                    "download": "https://freesound.org/apiv2/sounds/6/download/",
                    "license": "CC0",
                    "username": "fern",
                    "tags": ["guitar"],
                    "type": "mp3",
                },
            ],
        }


def test_freesound_search_quarantines_missing_download_and_bad_type():
    adapter = FreesoundAdapter(UnsafeFreesoundHttp())

    assert adapter.search(instrument="guitar", limit=10) == []

    candidates = adapter.search(
        instrument="guitar", limit=10, include_quarantine=True)
    by_id = {c.source_id: c for c in candidates}
    assert by_id["4"].decision.status == "quarantine"
    assert "missing_download_url" in by_id["4"].decision.reasons
    assert by_id["5"].decision.status == "quarantine"
    assert "missing_download_url" in by_id["5"].decision.reasons
    assert by_id["5"].download_url == ""
    assert by_id["6"].decision.status == "quarantine"
    assert "unsupported_freesound_file_type" in by_id["6"].decision.reasons


class UnsuitablePitchedFreesoundHttp:
    def __init__(self):
        self.calls = []

    def get_json(self, url, *, params=None, headers=None):
        self.calls.append((url, params, headers))
        return {
            "next": None,
            "results": [
                {
                    "id": 7,
                    "name": "Guitar C4 loop.wav",
                    "url": "https://freesound.org/s/7/",
                    "download": "https://freesound.org/apiv2/sounds/7/download/",
                    "license": "CC0",
                    "username": "gwen",
                    "tags": ["guitar", "loop"],
                    "type": "wav",
                },
                {
                    "id": 8,
                    "name": "Guitar field recording.wav",
                    "url": "https://freesound.org/s/8/",
                    "download": "https://freesound.org/apiv2/sounds/8/download/",
                    "license": "CC0",
                    "username": "hani",
                    "tags": ["guitar", "field-recording"],
                    "type": "wav",
                },
            ],
        }


def test_freesound_search_quarantines_unsuitable_pitched_content():
    adapter = FreesoundAdapter(UnsuitablePitchedFreesoundHttp())

    assert adapter.search(instrument="guitar", limit=10) == []

    candidates = adapter.search(
        instrument="guitar", limit=10, include_quarantine=True)
    by_id = {c.source_id: c for c in candidates}
    assert by_id["7"].decision.status == "quarantine"
    assert "unsuitable_pitched_instrument_content" in by_id["7"].decision.reasons
    assert by_id["8"].decision.status == "quarantine"
    assert "unsuitable_pitched_instrument_content" in by_id["8"].decision.reasons


class PitchConfidenceFreesoundHttp:
    def get_json(self, url, *, params=None, headers=None):
        return {
            "next": None,
            "results": [
                {
                    "id": 10,
                    "name": "Guitar low pitch confidence.wav",
                    "url": "https://freesound.org/s/10/",
                    "download": (
                        "https://freesound.org/apiv2/sounds/10/download/"
                    ),
                    "license": "CC0",
                    "username": "jana",
                    "tags": ["guitar", "c4"],
                    "type": "wav",
                    "analysis": {
                        "tonal": {"pitch_confidence": 0.12},
                    },
                },
                {
                    "id": 11,
                    "name": "Guitar high pitch confidence.wav",
                    "url": "https://freesound.org/s/11/",
                    "download": (
                        "https://freesound.org/apiv2/sounds/11/download/"
                    ),
                    "license": "CC0",
                    "username": "kira",
                    "tags": ["guitar", "d4"],
                    "type": "wav",
                    "analysis": {
                        "pitch": {"confidence": 0.81},
                    },
                },
            ],
        }


def test_freesound_search_quarantines_low_pitch_confidence_when_available():
    adapter = FreesoundAdapter(PitchConfidenceFreesoundHttp())

    candidates = adapter.search(instrument="guitar", limit=10)
    assert [c.source_id for c in candidates] == ["11"]

    candidates = adapter.search(
        instrument="guitar", limit=10, include_quarantine=True)
    by_id = {c.source_id: c for c in candidates}
    assert by_id["10"].decision.status == "quarantine"
    assert "pitch_confidence_below_threshold" in by_id["10"].decision.reasons
    assert by_id["11"].decision.accepted


class DrumFreesoundHttp:
    def __init__(self):
        self.calls = []

    def get_json(self, url, *, params=None, headers=None):
        self.calls.append((url, params, headers))
        return {
            "next": None,
            "results": [{
                "id": 9,
                "name": "Drum beat.wav",
                "url": "https://freesound.org/s/9/",
                "download": "https://freesound.org/apiv2/sounds/9/download/",
                "license": "CC0",
                "username": "ivan",
                "tags": ["drums", "beat"],
                "type": "wav",
                "analysis": {"tonal": {"pitch_confidence": 0.02}},
            }],
        }


def test_freesound_does_not_apply_pitched_content_filter_to_drums():
    http = DrumFreesoundHttp()
    candidates = FreesoundAdapter(http).search(instrument="drums", limit=10)

    assert [c.source_id for c in candidates] == ["9"]
    assert candidates[0].decision.accepted
    assert "-tag:beat" not in http.calls[0][1]["filter"]
