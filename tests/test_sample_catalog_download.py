import hashlib

import pytest

from audioforge.sample_catalog.download import download_candidate
from audioforge.sample_catalog.sources import Candidate
from audioforge.sample_catalog.licenses import (
    LicenseDecision,
    decide_license,
    evidence_hash,
    make_evidence,
)


class FakeBytes:
    def __init__(self, data=b"abc"):
        self.data = data
        self.calls = []

    def get_bytes(self, url, *, headers=None):
        self.calls.append((url, headers))
        return self.data


class FlakyBytes:
    def __init__(self, failures: int, data=b"abc"):
        self.failures = failures
        self.data = data
        self.calls = []

    def get_bytes(self, url, *, headers=None):
        self.calls.append((url, headers))
        if len(self.calls) <= self.failures:
            raise TimeoutError("temporary transport failure")
        return self.data


def _candidate():
    evidence = make_evidence(
        source="freesound",
        source_id="1",
        source_url="https://freesound.org/s/1/",
        download_url="https://freesound.org/apiv2/sounds/1/download/",
        license_name="CC0",
        license_url="https://creativecommons.org/publicdomain/zero/1.0/",
        fetched_at="2026-06-12T00:00:00+00:00",
    )
    return Candidate(
        source="freesound",
        source_id="1",
        source_url=evidence.source_url,
        download_url=evidence.download_url,
        filename="C4.wav",
        license_name="CC0",
        license_url=evidence.license_url,
        decision=decide_license(
            license_name="CC0",
            license_url=evidence.license_url,
            source_url=evidence.source_url,
            source_id=evidence.source_id,
        ),
        evidence=evidence,
    )


def test_download_candidate_writes_content_addressed_file_and_evidence(tmp_path):
    http = FakeBytes(b"sample-bytes")
    result = download_candidate(_candidate(), tmp_path, http,
                                headers={"Authorization": "Bearer tok"})

    sha = hashlib.sha256(b"sample-bytes").hexdigest()
    assert result.sha256 == sha
    assert result.size == len(b"sample-bytes")
    assert (tmp_path / "downloads" / sha[:2] / f"{sha}.wav").read_bytes() == b"sample-bytes"
    assert result.evidence_path.endswith(".json")
    assert http.calls == [("https://freesound.org/apiv2/sounds/1/download/",
                           {"Authorization": "Bearer tok"})]


def test_download_candidate_reuses_cached_expected_hash_without_transport(tmp_path):
    cand = _candidate()
    data = b"sample-bytes"
    sha = hashlib.sha256(data).hexdigest()
    dst = tmp_path / "downloads" / sha[:2] / f"{sha}.wav"
    dst.parent.mkdir(parents=True)
    dst.write_bytes(data)

    http = FakeBytes(b"new-bytes")
    result = download_candidate(cand, tmp_path, http, expected_sha256=sha)

    assert result.reused is True
    assert result.path == str(dst)
    assert http.calls == []


def test_download_candidate_applies_injected_rate_limit(tmp_path):
    sleeps = []
    times = iter([10.0])
    result = download_candidate(
        _candidate(),
        tmp_path,
        FakeBytes(b"rate"),
        headers={"Authorization": "Bearer tok"},
        min_interval_s=1.5,
        last_request_at=9.0,
        sleep=sleeps.append,
        now=lambda: next(times),
    )

    assert result.reused is False
    assert sleeps == [0.5]


def test_download_candidate_rejects_hash_mismatch(tmp_path):
    with pytest.raises(ValueError, match="download hash mismatch"):
        download_candidate(_candidate(), tmp_path, FakeBytes(b"wrong"),
                           headers={"Authorization": "Bearer tok"},
                           expected_sha256="0" * 64)


def test_download_candidate_retries_transient_transport_failure(tmp_path):
    http = FlakyBytes(failures=1, data=b"retry-ok")
    sleeps = []

    result = download_candidate(
        _candidate(),
        tmp_path,
        http,
        headers={"Authorization": "Bearer tok"},
        max_attempts=2,
        retry_sleep_s=0.25,
        sleep=sleeps.append,
    )

    assert result.sha256 == hashlib.sha256(b"retry-ok").hexdigest()
    assert len(http.calls) == 2
    assert sleeps == [0.25]


def test_download_candidate_reports_retry_exhaustion_without_file(tmp_path):
    http = FlakyBytes(failures=2, data=b"unreachable")

    with pytest.raises(ValueError, match="download failed after 2 attempts"):
        download_candidate(
            _candidate(),
            tmp_path,
            http,
            headers={"Authorization": "Bearer tok"},
            max_attempts=2,
            retry_sleep_s=0.1,
            sleep=lambda _: None,
        )

    assert len(http.calls) == 2
    assert not (tmp_path / "downloads").exists()


def test_download_candidate_requires_oauth_for_fresh_freesound_download(tmp_path):
    http = FakeBytes(b"sample")

    with pytest.raises(ValueError, match="Freesound downloads require OAuth2"):
        download_candidate(_candidate(), tmp_path, http)

    assert http.calls == []


def test_download_candidate_rejects_quarantined_candidate(tmp_path):
    cand = _candidate()
    data = cand.to_dict()
    data["decision"] = {
        "status": "quarantine",
        "license_id": None,
        "reasons": ["license_not_allowed_or_unclear"],
    }
    with pytest.raises(ValueError, match="not license-approved"):
        download_candidate(data, tmp_path, FakeBytes())


def test_download_candidate_rejects_missing_download_url(tmp_path):
    cand = _candidate().to_dict()
    cand["download_url"] = ""
    cand["evidence"]["download_url"] = ""
    http = FakeBytes()

    with pytest.raises(ValueError, match="no download URL"):
        download_candidate(cand, tmp_path, http)

    assert http.calls == []


def test_download_candidate_rejects_unsupported_audio_extension_before_transport(tmp_path):
    cand = _candidate().to_dict()
    cand["filename"] = "score.pdf"
    cand["download_url"] = "https://example.test/score.pdf"
    cand["evidence"]["download_url"] = cand["download_url"]
    http = FakeBytes()

    with pytest.raises(ValueError, match="unsupported audio extension"):
        download_candidate(cand, tmp_path, http,
                           headers={"Authorization": "Bearer tok"})

    assert http.calls == []


def test_download_candidate_rejects_mismatched_evidence_hash_before_write(tmp_path):
    cand = _candidate().to_dict()
    cand["evidence"]["creator"] = "tampered creator"
    http = FakeBytes()

    with pytest.raises(ValueError, match="license evidence hash mismatch"):
        download_candidate(cand, tmp_path, http,
                           headers={"Authorization": "Bearer tok"})

    assert http.calls == []
    assert not (tmp_path / "evidence").exists()


def test_download_candidate_rejects_unknown_evidence_schema_before_write(tmp_path):
    cand = _candidate().to_dict()
    cand["evidence"]["schema"] = "audioforge.sample-catalog.evidence/0"
    cand["evidence"]["evidence_hash"] = evidence_hash(cand["evidence"])
    http = FakeBytes()

    with pytest.raises(ValueError, match="unsupported license evidence schema"):
        download_candidate(cand, tmp_path, http,
                           headers={"Authorization": "Bearer tok"})

    assert http.calls == []
    assert not (tmp_path / "evidence").exists()


def test_download_candidate_rejects_candidate_evidence_mismatch_before_write(tmp_path):
    cand = _candidate().to_dict()
    cand["download_url"] = "https://example.test/tampered.wav"
    http = FakeBytes()

    with pytest.raises(ValueError, match="candidate evidence mismatch: download_url"):
        download_candidate(cand, tmp_path, http,
                           headers={"Authorization": "Bearer tok"})

    assert http.calls == []
    assert not (tmp_path / "evidence").exists()


def test_download_candidate_rejects_accepted_openverse_discovery_lead(tmp_path):
    evidence = make_evidence(
        source="openverse_discovery",
        source_id="ov-1",
        source_url="https://example.test/source",
        download_url="https://example.test/C4.wav",
        license_name="CC0",
        license_url="https://creativecommons.org/publicdomain/zero/1.0/",
        rights_text="Openverse discovery lead; verify upstream before download",
        fetched_at="2026-06-12T00:00:00+00:00",
    )
    cand = Candidate(
        source="openverse_discovery",
        source_id="ov-1",
        source_url=evidence.source_url,
        download_url=evidence.download_url,
        filename="C4.wav",
        license_name="CC0",
        license_url=evidence.license_url,
        decision=LicenseDecision("accepted", "CC0-1.0", ()),
        evidence=evidence,
    )
    http = FakeBytes()

    with pytest.raises(ValueError, match="upstream verification"):
        download_candidate(cand, tmp_path, http)

    assert http.calls == []
    assert not (tmp_path / "evidence").exists()


def test_download_candidate_rejects_accepted_unsupported_license_evidence(
        tmp_path):
    evidence = make_evidence(
        source="freesound",
        source_id="2",
        source_url="https://freesound.org/s/2/",
        download_url="https://freesound.org/apiv2/sounds/2/download/",
        license_name="CC-BY",
        license_url="https://creativecommons.org/licenses/by/4.0/",
        fetched_at="2026-06-12T00:00:00+00:00",
    )
    cand = Candidate(
        source="freesound",
        source_id="2",
        source_url=evidence.source_url,
        download_url=evidence.download_url,
        filename="C4.wav",
        license_name="CC-BY",
        license_url=evidence.license_url,
        decision=LicenseDecision("accepted", "CC-BY", ()),
        evidence=evidence,
    )
    http = FakeBytes()

    with pytest.raises(ValueError, match="unsupported or unclear license"):
        download_candidate(cand, tmp_path, http,
                           headers={"Authorization": "Bearer tok"})

    assert http.calls == []
    assert not (tmp_path / "evidence").exists()
