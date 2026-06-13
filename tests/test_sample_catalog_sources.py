import pytest

from audioforge.sample_catalog.constants import CANDIDATE_SCHEMA
from audioforge.sample_catalog.sources import (
    Candidate,
    FreesoundAdapter,
    InternetArchiveAdapter,
    OpenverseDiscoveryAdapter,
    SOURCE_ADAPTERS,
    SOURCE_ADAPTER_CLI_NAMES,
    SOURCE_ADAPTER_CLI_TO_ID,
    WikimediaCommonsAdapter,
)


def test_source_adapter_cli_names_are_derived_from_single_registry():
    assert SOURCE_ADAPTER_CLI_TO_ID == {
        "freesound": "freesound",
        "internet-archive": "internet_archive",
        "wikimedia-commons": "wikimedia_commons",
        "openverse": "openverse_discovery",
    }
    assert SOURCE_ADAPTER_CLI_NAMES == tuple(SOURCE_ADAPTER_CLI_TO_ID)
    assert SOURCE_ADAPTERS == tuple(SOURCE_ADAPTER_CLI_TO_ID.values())


class FakeIA:
    def __init__(self):
        self.calls = []

    def get_json(self, url, *, params=None, headers=None):
        self.calls.append((url, params))
        if url.endswith("advancedsearch.php"):
            return {"response": {"docs": [{
                "identifier": "pd-pack",
                "title": "PD Pack",
                "creator": "archive",
                "licenseurl": "https://creativecommons.org/publicdomain/zero/1.0/",
            }]}}
        return {
            "metadata": {
                "title": "PD Pack",
                "creator": "archive",
                "licenseurl": "https://creativecommons.org/publicdomain/zero/1.0/",
            },
            "files": [
                {"name": "C4.wav", "format": "WAVE", "size": "123"},
                {"name": "cover.jpg", "format": "JPEG"},
            ],
        }


def test_internet_archive_adapter_uses_metadata_and_filters_audio_files():
    http = FakeIA()
    adapter = InternetArchiveAdapter(
        http, fetched_at="2026-06-12T00:00:00+00:00")
    candidates = adapter.search(query="guitar", limit=10)
    assert len(candidates) == 1
    cand = candidates[0]
    assert cand.source == "internet_archive"
    assert cand.filename == "C4.wav"
    assert cand.decision.accepted
    assert cand.download_url == "https://archive.org/download/pd-pack/C4.wav"
    assert cand.descriptors["review_requirement"] == (
        "manual_public_domain_provenance_review"
    )
    assert cand.descriptors["source_context"]["status"] == "manual_review_required"
    assert cand.to_dict()["schema"] == CANDIDATE_SCHEMA
    search_url, search_params = http.calls[0]
    assert search_url.endswith("advancedsearch.php")
    assert search_params["q"] == "mediatype:audio AND (guitar)"
    assert search_params["fl[]"] == [
        "identifier", "title", "creator", "licenseurl", "rights"
    ]
    assert search_params["rows"] == 10
    assert search_params["output"] == "json"
    metadata_url, metadata_params = http.calls[1]
    assert metadata_url == "https://archive.org/metadata/pd-pack"
    assert metadata_params is None


class FakeIAPreferredContext:
    def get_json(self, url, *, params=None, headers=None):
        if url.endswith("advancedsearch.php"):
            return {"response": {"docs": [{
                "identifier": "institutional-notes",
                "title": "Museum guitar sample pack",
                "creator": "municipal library",
                "licenseurl": "https://creativecommons.org/publicdomain/zero/1.0/",
            }]}}
        return {
            "metadata": {
                "title": "Museum guitar sample pack",
                "creator": "municipal library",
                "subject": ["isolated notes", "guitar"],
                "licenseurl": "https://creativecommons.org/publicdomain/zero/1.0/",
            },
            "files": [{"name": "C4.wav", "format": "WAVE", "size": "123"}],
        }


def test_internet_archive_adapter_records_preferred_source_context():
    adapter = InternetArchiveAdapter(
        FakeIAPreferredContext(), fetched_at="2026-06-12T00:00:00+00:00")

    candidates = adapter.search(query="guitar", limit=10)

    assert len(candidates) == 1
    context = candidates[0].descriptors["source_context"]
    assert context["status"] == "preferred"
    assert context["matched"] == [
        "institutional_collection",
        "sample_pack_or_isolated_note",
    ]


class FakeIAAmbiguousRights:
    def get_json(self, url, *, params=None, headers=None):
        if url.endswith("advancedsearch.php"):
            return {"response": {"docs": [{
                "identifier": "cc0-conflict",
                "title": "Conflicting Rights Pack",
                "creator": "archive",
                "licenseurl": "https://creativecommons.org/publicdomain/zero/1.0/",
                "rights": "All rights reserved.",
            }]}}
        return {
            "metadata": {
                "title": "Conflicting Rights Pack",
                "creator": "archive",
                "licenseurl": "https://creativecommons.org/publicdomain/zero/1.0/",
                "rights": "All rights reserved.",
            },
            "files": [{"name": "C4.wav", "format": "WAVE", "size": "123"}],
        }


def test_internet_archive_adapter_quarantines_ambiguous_rights_with_cc0():
    adapter = InternetArchiveAdapter(
        FakeIAAmbiguousRights(), fetched_at="2026-06-12T00:00:00+00:00")

    assert adapter.search(query="guitar", limit=10) == []

    quarantined = adapter.search(
        query="guitar", limit=10, include_quarantine=True)
    assert len(quarantined) == 1
    cand = quarantined[0]
    assert cand.source == "internet_archive"
    assert cand.decision.status == "quarantine"
    assert "internet_archive_ambiguous_rights" in cand.decision.reasons


class FakeCommons:
    def __init__(self):
        self.calls = []

    def get_json(self, url, *, params=None, headers=None):
        self.calls.append((url, params, headers))
        return {"query": {"pages": {"10": {
            "pageid": 10,
            "title": "File:C4.ogg",
            "fullurl": "https://commons.wikimedia.org/wiki/File:C4.ogg",
            "imageinfo": [{
                "url": "https://upload.wikimedia.org/C4.ogg",
                "sha1": "abc",
                "mime": "audio/ogg",
                "mediatype": "AUDIO",
                "extmetadata": {
                    "LicenseShortName": {"value": "CC0"},
                    "LicenseUrl": {"value": "https://creativecommons.org/publicdomain/zero/1.0/"},
                    "UsageTerms": {"value": "Public domain"},
                    "Artist": {"value": "commons"},
                },
            }],
        }}}}


def test_wikimedia_commons_adapter_reads_imageinfo_license_evidence():
    http = FakeCommons()
    candidates = WikimediaCommonsAdapter(
        http, fetched_at="2026-06-12T00:00:00+00:00").search(
            query="guitar", limit=5)
    assert len(candidates) == 1
    cand = candidates[0]
    assert cand.source == "wikimedia_commons"
    assert cand.filename == "C4.ogg"
    assert cand.evidence.license_name == "CC0"
    assert cand.decision.accepted
    assert cand.descriptors["review_requirement"] == (
        "manual_commons_license_metadata_review"
    )
    url, params, headers = http.calls[0]
    assert url == "https://commons.wikimedia.org/w/api.php"
    assert headers is None
    assert params["action"] == "query"
    assert params["generator"] == "search"
    assert params["gsrsearch"] == "file:guitar"
    assert params["gsrnamespace"] == 6
    assert params["gsrlimit"] == 5
    assert params["prop"] == "imageinfo"
    assert params["iiprop"] == "url|sha1|mime|mediatype|extmetadata"
    assert params["format"] == "json"


class FakeUnsafeCommons:
    def get_json(self, url, *, params=None, headers=None):
        return {"query": {"pages": {
            "10": {
                "pageid": 10,
                "title": "File:NoUrl.ogg",
                "fullurl": "https://commons.wikimedia.org/wiki/File:NoUrl.ogg",
                "imageinfo": [{
                    "mime": "audio/ogg",
                    "mediatype": "AUDIO",
                    "extmetadata": {
                        "LicenseShortName": {"value": "CC0"},
                        "LicenseUrl": {"value": "https://creativecommons.org/publicdomain/zero/1.0/"},
                    },
                }],
            },
            "11": {
                "pageid": 11,
                "title": "File:Cover.jpg",
                "fullurl": "https://commons.wikimedia.org/wiki/File:Cover.jpg",
                "imageinfo": [{
                    "url": "https://upload.wikimedia.org/Cover.jpg",
                    "mime": "image/jpeg",
                    "mediatype": "AUDIO",
                    "extmetadata": {
                        "LicenseShortName": {"value": "CC0"},
                        "LicenseUrl": {"value": "https://creativecommons.org/publicdomain/zero/1.0/"},
                    },
                }],
            },
            "12": {
                "pageid": 12,
                "title": "File:Contradictory.ogg",
                "fullurl": "https://commons.wikimedia.org/wiki/File:Contradictory.ogg",
                "imageinfo": [{
                    "url": "https://upload.wikimedia.org/Contradictory.ogg",
                    "mime": "audio/ogg",
                    "mediatype": "AUDIO",
                    "extmetadata": {
                        "LicenseShortName": {"value": "CC0"},
                        "LicenseUrl": {"value": "https://creativecommons.org/publicdomain/zero/1.0/"},
                        "UsageTerms": {"value": "All rights reserved."},
                    },
                }],
            },
        }}}


def test_wikimedia_commons_quarantines_source_gate_failures():
    adapter = WikimediaCommonsAdapter(FakeUnsafeCommons())

    assert adapter.search(query="guitar", limit=5) == []

    candidates = adapter.search(
        query="guitar", limit=5, include_quarantine=True)
    by_id = {c.source_id: c for c in candidates}
    assert "missing_download_url" in by_id["10"].decision.reasons
    assert "unsupported_commons_audio_format" in by_id["11"].decision.reasons
    assert "license_contradictory_rights" in by_id["12"].decision.reasons


class FakeOpenverse:
    def __init__(self):
        self.calls = []

    def get_json(self, url, *, params=None, headers=None):
        self.calls.append((url, params, headers))
        return {"results": [{
            "id": "ov1",
            "title": "C4 lead",
            "url": "https://example.test/audio.wav",
            "foreign_landing_url": "https://source.example/audio",
            "license": "cc0",
            "license_url": "https://creativecommons.org/publicdomain/zero/1.0/",
            "creator": "lead",
            "provider": "freesound",
            "tags": ["guitar"],
        }]}


def test_openverse_adapter_returns_discovery_leads_not_approved_downloads():
    http = FakeOpenverse()
    candidates = OpenverseDiscoveryAdapter(
        http, fetched_at="2026-06-12T00:00:00+00:00").search(
            query="guitar")
    assert len(candidates) == 1
    cand = candidates[0]
    assert cand.source == "openverse_discovery"
    assert cand.decision.status == "quarantine"
    assert "openverse_requires_upstream_verification" in cand.decision.reasons
    assert cand.to_dict()["schema"] == CANDIDATE_SCHEMA
    url, params, headers = http.calls[0]
    assert url == "https://api.openverse.engineering/v1/audio/"
    assert headers is None
    assert params == {
        "q": "guitar",
        "license": "cc0,pdm",
        "page_size": 50,
    }


class FakeOpenverseFreesound:
    def get_json(self, url, *, params=None, headers=None):
        return {"results": [{
            "id": "ov-fs",
            "title": "Freesound C4",
            "url": "https://cdn.freesound.org/previews/42.wav",
            "foreign_landing_url": "https://freesound.org/people/u/sounds/42/",
            "license": "cc0",
            "license_url": "https://creativecommons.org/publicdomain/zero/1.0/",
            "creator": "lead",
            "provider": "freesound",
            "tags": ["guitar"],
        }]}


class FakeFreesoundCanonical:
    def __init__(self):
        self.calls = []

    def get_json(self, url, *, params=None, headers=None):
        self.calls.append((url, params, headers))
        assert url == "https://freesound.org/apiv2/sounds/42/"
        return {
            "id": 42,
            "name": "C4.wav",
            "url": "https://freesound.org/people/u/sounds/42/",
            "download": "https://freesound.org/apiv2/sounds/42/download/",
            "license": "https://creativecommons.org/publicdomain/zero/1.0/",
            "username": "u",
            "tags": ["guitar"],
            "type": "wav",
            "duration": 1.0,
            "avg_rating": 5.0,
            "num_ratings": 4,
            "analysis": {"pitch": {"confidence": 0.9}},
        }


def test_openverse_lead_resolves_to_canonical_freesound_candidate():
    openverse = OpenverseDiscoveryAdapter(
        FakeOpenverseFreesound(),
        fetched_at="2026-06-12T00:00:00+00:00",
    )
    lead = openverse.search(query="guitar")[0]
    freesound_http = FakeFreesoundCanonical()

    resolved = openverse.resolve(
        lead,
        upstream_adapters={
            "freesound": FreesoundAdapter(
                freesound_http,
                fetched_at="2026-06-12T00:00:00+00:00",
            ),
        },
        instrument="guitar",
    )

    assert resolved.source == "freesound"
    assert resolved.source_id == "42"
    assert resolved.decision.accepted
    assert resolved.evidence.source == "freesound"
    assert resolved.evidence.evidence_hash != lead.evidence.evidence_hash
    assert resolved.descriptors["openverse_discovery"] == {
        "provider": "freesound",
        "source_id": "ov-fs",
        "source_url": "https://freesound.org/people/u/sounds/42/",
        "download_url": "https://cdn.freesound.org/previews/42.wav",
        "evidence_hash": lead.evidence.evidence_hash,
    }
    url, params, headers = freesound_http.calls[0]
    assert params == {"fields": FreesoundAdapter.fields}
    assert headers is None


class FakeOpenverseIA:
    def get_json(self, url, *, params=None, headers=None):
        return {"results": [{
            "id": "ov-ia",
            "title": "C4.wav",
            "url": "https://archive.org/download/pd-pack/C4.wav",
            "foreign_landing_url": "https://archive.org/details/pd-pack",
            "license": "cc0",
            "license_url": "https://creativecommons.org/publicdomain/zero/1.0/",
            "creator": "archive",
            "provider": "internet_archive",
            "tags": ["guitar"],
        }]}


def test_openverse_lead_resolves_to_canonical_internet_archive_candidate():
    openverse = OpenverseDiscoveryAdapter(FakeOpenverseIA())
    lead = openverse.search(query="guitar")[0]

    resolved = openverse.resolve(
        lead,
        upstream_adapters={"internet_archive": InternetArchiveAdapter(FakeIA())},
    )

    assert resolved.source == "internet_archive"
    assert resolved.source_id == "pd-pack"
    assert resolved.download_url == "https://archive.org/download/pd-pack/C4.wav"
    assert resolved.evidence.source == "internet_archive"
    assert resolved.descriptors["openverse_discovery"]["provider"] == (
        "internet_archive"
    )


class FakeOpenverseCommons:
    def get_json(self, url, *, params=None, headers=None):
        return {"results": [{
            "id": "ov-commons",
            "title": "C4.ogg",
            "url": "https://upload.wikimedia.org/C4.ogg",
            "foreign_landing_url": "https://commons.wikimedia.org/wiki/File:C4.ogg",
            "license": "cc0",
            "license_url": "https://creativecommons.org/publicdomain/zero/1.0/",
            "creator": "commons",
            "provider": "wikimedia_commons",
            "tags": ["guitar"],
        }]}


def test_openverse_lead_resolves_to_canonical_commons_candidate():
    openverse = OpenverseDiscoveryAdapter(FakeOpenverseCommons())
    lead = openverse.search(query="guitar")[0]
    commons_http = FakeCommons()

    resolved = openverse.resolve(
        lead,
        upstream_adapters={
            "wikimedia_commons": WikimediaCommonsAdapter(commons_http),
        },
    )

    assert resolved.source == "wikimedia_commons"
    assert resolved.source_id == "10"
    assert resolved.download_url == "https://upload.wikimedia.org/C4.ogg"
    assert resolved.evidence.source == "wikimedia_commons"
    assert resolved.descriptors["openverse_discovery"]["provider"] == (
        "wikimedia_commons"
    )
    url, params, headers = commons_http.calls[0]
    assert params["titles"] == "File:C4.ogg"
    assert "generator" not in params


def test_openverse_resolver_requires_supported_upstream_adapter():
    openverse = OpenverseDiscoveryAdapter(FakeOpenverseFreesound())
    lead = openverse.search(query="guitar")[0]

    with pytest.raises(ValueError, match="freesound adapter required"):
        openverse.resolve(lead, upstream_adapters={})


def test_candidate_from_dict_rejects_unknown_schema():
    data = OpenverseDiscoveryAdapter(
        FakeOpenverse(), fetched_at="2026-06-12T00:00:00+00:00").search(
            query="guitar")[0].to_dict()
    data["schema"] = "audioforge.sample-catalog.candidate/0"

    with pytest.raises(ValueError, match="unsupported sample catalog candidate schema"):
        Candidate.from_dict(data)


def test_candidate_from_dict_rejects_missing_required_fields():
    data = OpenverseDiscoveryAdapter(
        FakeOpenverse(), fetched_at="2026-06-12T00:00:00+00:00").search(
            query="guitar")[0].to_dict()
    data.pop("source_url")

    with pytest.raises(ValueError, match="candidate missing required field: source_url"):
        Candidate.from_dict(data)


def test_candidate_from_dict_rejects_malformed_evidence_object():
    data = OpenverseDiscoveryAdapter(
        FakeOpenverse(), fetched_at="2026-06-12T00:00:00+00:00").search(
            query="guitar")[0].to_dict()
    data["evidence"] = "not-an-object"

    with pytest.raises(ValueError, match="candidate evidence must be an object"):
        Candidate.from_dict(data)
