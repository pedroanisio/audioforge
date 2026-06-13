import json
import math
import hashlib
import wave

import numpy as np
import pytest

from audioforge import cli
from audioforge.sample_catalog.constants import ANALYSIS_SCHEMA, CANDIDATE_SCHEMA
from audioforge.sample_catalog.licenses import decide_license, make_evidence
from audioforge.sample_catalog.sources import Candidate


def _sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class FakeHttp:
    def __init__(self):
        self.wav = None

    def get_json(self, url, *, params=None, headers=None):
        return {
            "next": None,
            "results": [{
                "id": 1,
                "name": "C4.wav",
                "url": "https://freesound.org/s/1/",
                "download": "https://freesound.org/apiv2/sounds/1/download/",
                "license": "CC0",
                "username": "alice",
                "tags": ["guitar"],
                "type": "wav",
            }],
        }

    def get_bytes(self, url, *, headers=None):
        return self.wav or b"bytes"


def _wav_bytes(freq=261.625565, sr=44100):
    t = np.arange(int(sr * 0.25)) / sr
    x = np.sin(2 * math.pi * freq * t) * 0.3
    data = (x * 32767).astype("<i2").tobytes()
    import io
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(data)
    return buf.getvalue()


def test_sample_catalog_cli_search_download_analyze_build_review(monkeypatch, capsys, tmp_path):
    fake = FakeHttp()
    fake.wav = _wav_bytes()
    monkeypatch.setattr(cli, "_UrllibHttp", lambda: fake)

    search = tmp_path / "search.json"
    assert cli.main([
        "sample-catalog", "search",
        "--source", "freesound",
        "--instrument", "guitar",
        "--out", str(search),
    ]) == 0
    assert "sample-catalog search ->" in capsys.readouterr().out
    candidates = json.loads(search.read_text())
    assert candidates[0]["schema"] == CANDIDATE_SCHEMA
    assert candidates[0]["evidence"]["evidence_hash"]

    cache = tmp_path / "cache"
    assert cli.main([
        "sample-catalog", "download",
        "--candidates", str(search),
        "--out", str(cache),
        "--token", "tok",
    ]) == 0
    assert (cache / "downloads.json").exists()

    analysis = tmp_path / "analysis"
    assert cli.main([
        "sample-catalog", "analyze",
        "--downloads", str(cache / "downloads"),
        "--out", str(analysis),
    ]) == 0
    analysis_records = [
        json.loads(path.read_text()) for path in analysis.glob("*.json")
    ]
    assert analysis_records[0]["schema"] == ANALYSIS_SCHEMA
    expected_evidence_hash = candidates[0]["evidence"]["evidence_hash"]
    assert analysis_records[0]["source_evidence_id"] == expected_evidence_hash
    assert analysis_records[0]["license_evidence"]["evidence_hash"] == (
        expected_evidence_hash
    )
    assert analysis_records[0]["source_raw_metadata"]

    candidate = tmp_path / "candidate"
    assert cli.main([
        "sample-catalog", "build-sfz",
        "--instrument", "guitar",
        "--analysis", str(analysis),
        "--out", str(candidate),
    ]) == 0
    assert (candidate / "instrument.sfz").exists()
    assert (candidate / "library.manifest.json").exists()
    manifest = json.loads((candidate / "library.manifest.json").read_text())
    assert manifest["regions"][0]["source_evidence_id"] == expected_evidence_hash
    assert manifest["regions"][0]["quality"] == {
        "analysis_schema": analysis_records[0]["schema"],
        "quality_score": analysis_records[0]["quality_score"],
        "pitch_confidence": analysis_records[0]["pitch_confidence"],
        "status": analysis_records[0]["status"],
    }
    assert manifest["regions"][0]["diagnostics"] == {
        "rejection_reasons": analysis_records[0]["rejection_reasons"],
        "warnings": [],
    }
    assert manifest["analysis_summary"]["accepted_samples"] == 1
    assert manifest["analysis_summary"]["quality_score_mean"] == (
        analysis_records[0]["quality_score"]
    )

    assert cli.main(["sample-catalog", "audit-license", str(candidate)]) == 0
    assert '"ok": true' in capsys.readouterr().out

    assert cli.main([
        "sample-catalog", "review",
        str(candidate),
        "--reviewer", "qa",
        "--notes", "auditioned",
    ]) == 0
    assert (candidate / "review.md").exists()
    review_text = (candidate / "review.md").read_text()
    assert "## Source And License Evidence" in review_text
    assert "## Pitch Map" in review_text
    assert "## Audition" in review_text


class FakeSecondarySearchHttp:
    def __init__(self):
        self.calls = []

    def get_json(self, url, *, params=None, headers=None):
        self.calls.append((url, params, headers))
        if url.endswith("advancedsearch.php"):
            return {"response": {"docs": [{
                "identifier": "pd-pack",
                "title": "PD Pack",
                "creator": "archive",
                "licenseurl": (
                    "https://creativecommons.org/publicdomain/zero/1.0/"
                ),
            }]}}
        if url.endswith("/metadata/pd-pack"):
            return {
                "metadata": {
                    "title": "PD Pack",
                    "creator": "archive",
                    "licenseurl": (
                        "https://creativecommons.org/publicdomain/zero/1.0/"
                    ),
                    "subject": ["isolated notes", "guitar"],
                },
                "files": [{"name": "C4.wav", "format": "WAVE", "size": "123"}],
            }
        if url == "https://commons.wikimedia.org/w/api.php":
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
                        "LicenseUrl": {
                            "value": (
                                "https://creativecommons.org/publicdomain/zero/1.0/"
                            ),
                        },
                        "UsageTerms": {"value": "Public domain"},
                        "Artist": {"value": "commons"},
                    },
                }],
            }}}}
        if url == "https://api.openverse.engineering/v1/audio/":
            return {"results": [{
                "id": "ov1",
                "title": "C4 lead",
                "url": "https://example.test/audio.wav",
                "foreign_landing_url": "https://source.example/audio",
                "license": "cc0",
                "license_url": (
                    "https://creativecommons.org/publicdomain/zero/1.0/"
                ),
                "creator": "lead",
                "provider": "freesound",
                "tags": ["guitar"],
            }]}
        raise AssertionError(f"unexpected URL {url}")

    def get_bytes(self, url, *, headers=None):
        raise AssertionError("search should not download bytes")


class FakeOpenverseResolveHttp:
    def __init__(self):
        self.calls = []
        self.wav = _wav_bytes()

    def get_json(self, url, *, params=None, headers=None):
        self.calls.append((url, params, headers))
        if url == "https://api.openverse.engineering/v1/audio/":
            return {"results": [{
                "id": "ov-fs",
                "title": "Freesound C4",
                "url": "https://cdn.freesound.org/previews/42.wav",
                "foreign_landing_url": (
                    "https://freesound.org/people/u/sounds/42/"
                ),
                "license": "cc0",
                "license_url": (
                    "https://creativecommons.org/publicdomain/zero/1.0/"
                ),
                "creator": "lead",
                "provider": "freesound",
                "tags": ["guitar"],
            }]}
        if url == "https://freesound.org/apiv2/sounds/42/":
            return {
                "id": 42,
                "name": "C4.wav",
                "url": "https://freesound.org/people/u/sounds/42/",
                "download": "https://freesound.org/apiv2/sounds/42/download/",
                "license": (
                    "https://creativecommons.org/publicdomain/zero/1.0/"
                ),
                "username": "u",
                "tags": ["guitar"],
                "type": "wav",
                "duration": 1.0,
                "avg_rating": 5.0,
                "num_ratings": 4,
                "analysis": {"pitch": {"confidence": 0.9}},
            }
        raise AssertionError(f"unexpected URL {url}")

    def get_bytes(self, url, *, headers=None):
        self.calls.append((url, None, headers))
        assert url == "https://freesound.org/apiv2/sounds/42/download/"
        assert headers == {"Authorization": "Bearer tok"}
        return self.wav


@pytest.mark.parametrize("source, expected_source, expected_status", [
    ("internet-archive", "internet_archive", "accepted"),
    ("wikimedia-commons", "wikimedia_commons", "accepted"),
    ("openverse", "openverse_discovery", "quarantine"),
])
def test_sample_catalog_cli_search_routes_secondary_source_adapters(
        monkeypatch, capsys, tmp_path, source, expected_source, expected_status):
    fake = FakeSecondarySearchHttp()
    monkeypatch.setattr(cli, "_UrllibHttp", lambda: fake)

    search = tmp_path / f"{source}.json"
    assert cli.main([
        "sample-catalog", "search",
        "--source", source,
        "--instrument", "guitar",
        "--out", str(search),
    ]) == 0

    assert "sample-catalog search ->" in capsys.readouterr().out
    candidates = json.loads(search.read_text())
    assert len(candidates) == 1
    assert candidates[0]["schema"] == CANDIDATE_SCHEMA
    assert candidates[0]["source"] == expected_source
    assert candidates[0]["decision"]["status"] == expected_status
    assert candidates[0]["evidence"]["evidence_hash"]


def test_sample_catalog_cli_resolve_openverse_writes_downloadable_upstream_candidate(
        monkeypatch, capsys, tmp_path):
    fake = FakeOpenverseResolveHttp()
    monkeypatch.setattr(cli, "_UrllibHttp", lambda: fake)

    leads = tmp_path / "openverse.json"
    assert cli.main([
        "sample-catalog", "search",
        "--source", "openverse",
        "--instrument", "guitar",
        "--out", str(leads),
    ]) == 0
    lead_rows = json.loads(leads.read_text())
    assert lead_rows[0]["source"] == "openverse_discovery"
    assert lead_rows[0]["decision"]["status"] == "quarantine"

    resolved = tmp_path / "resolved.json"
    assert cli.main([
        "sample-catalog", "resolve-openverse",
        "--candidates", str(leads),
        "--instrument", "guitar",
        "--out", str(resolved),
    ]) == 0
    assert "sample-catalog resolve-openverse ->" in capsys.readouterr().out
    rows = json.loads(resolved.read_text())
    assert rows[0]["source"] == "freesound"
    assert rows[0]["decision"]["status"] == "accepted"
    assert rows[0]["evidence"]["source"] == "freesound"
    assert rows[0]["evidence"]["evidence_hash"] != (
        lead_rows[0]["evidence"]["evidence_hash"]
    )
    assert rows[0]["descriptors"]["openverse_discovery"] == {
        "download_url": "https://cdn.freesound.org/previews/42.wav",
        "evidence_hash": lead_rows[0]["evidence"]["evidence_hash"],
        "provider": "freesound",
        "source_id": "ov-fs",
        "source_url": "https://freesound.org/people/u/sounds/42/",
    }

    cache = tmp_path / "cache"
    assert cli.main([
        "sample-catalog", "download",
        "--candidates", str(resolved),
        "--out", str(cache),
        "--token", "tok",
    ]) == 0
    assert (cache / "downloads.json").exists()
    assert "sample-catalog download ->" in capsys.readouterr().out


def test_sample_catalog_analysis_summary_counts_ia_source_context_review():
    summary = cli._analysis_summary([
        {
            "quality_score": 0.95,
            "source": "internet_archive",
            "source_descriptors": {
                "source_context": {
                    "status": "manual_review_required",
                    "reason": "internet_archive_context_not_sample_pack_isolated_note_or_institutional",
                },
            },
        },
        {
            "quality_score": 0.9,
            "source": "internet_archive",
            "source_descriptors": {
                "source_context": {
                    "status": "preferred",
                    "matched": ["sample_pack_or_isolated_note"],
                },
            },
        },
    ])

    assert summary["accepted_samples"] == 2
    assert summary["internet_archive_source_context_review_required"] == 1


def test_sample_catalog_cli_download_reports_missing_freesound_oauth(capsys, tmp_path):
    evidence = make_evidence(
        source="freesound",
        source_id="1",
        source_url="https://freesound.org/s/1/",
        download_url="https://freesound.org/apiv2/sounds/1/download/",
        license_name="CC0",
        license_url="https://creativecommons.org/publicdomain/zero/1.0/",
        fetched_at="2026-06-12T00:00:00+00:00",
    )
    candidate = Candidate(
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
    candidates = tmp_path / "candidates.json"
    candidates.write_text(json.dumps([candidate.to_dict()]))

    assert cli.main([
        "sample-catalog", "download",
        "--candidates", str(candidates),
        "--out", str(tmp_path / "cache"),
    ]) == 1
    assert "Freesound downloads require OAuth2" in capsys.readouterr().err


def test_sample_catalog_cli_reports_missing_json_input_without_traceback(
        capsys, tmp_path):
    assert cli.main([
        "sample-catalog", "download",
        "--candidates", str(tmp_path / "missing.json"),
        "--out", str(tmp_path / "cache"),
    ]) == 1

    err = capsys.readouterr().err
    assert "Error: sample-catalog input: cannot read" in err
    assert "file not found" in err
    assert "Traceback" not in err
    assert "FileNotFoundError" not in err


def test_sample_catalog_cli_analyze_reports_missing_downloads_without_traceback(
        capsys, tmp_path):
    assert cli.main([
        "sample-catalog", "analyze",
        "--downloads", str(tmp_path / "missing-downloads"),
        "--out", str(tmp_path / "analysis"),
    ]) == 1

    err = capsys.readouterr().err
    assert "Error: sample-catalog downloads: cannot read" in err
    assert "file not found" in err
    assert "Traceback" not in err
    assert "FileNotFoundError" not in err


def test_sample_catalog_cli_analyze_reports_empty_downloads_without_traceback(
        capsys, tmp_path):
    downloads = tmp_path / "downloads"
    downloads.mkdir()

    assert cli.main([
        "sample-catalog", "analyze",
        "--downloads", str(downloads),
        "--out", str(tmp_path / "analysis"),
    ]) == 1

    err = capsys.readouterr().err
    assert "Error: sample-catalog downloads: no files found" in err
    assert "Traceback" not in err


def test_sample_catalog_cli_analyze_reports_empty_download_manifest_without_traceback(
        capsys, tmp_path):
    downloads = tmp_path / "downloads.json"
    downloads.write_text("[]\n")

    assert cli.main([
        "sample-catalog", "analyze",
        "--downloads", str(downloads),
        "--out", str(tmp_path / "analysis"),
    ]) == 1

    err = capsys.readouterr().err
    assert "Error: sample-catalog downloads: no download records found" in err
    assert "Traceback" not in err


@pytest.mark.parametrize("payload, message", [
    ({"not_items": []}, "expected JSON list or object with 'items' list"),
    ({"items": {"source": "freesound"}}, "expected 'items' list"),
    ([{"source": "freesound"}, "not-an-object"], "expected item objects"),
])
def test_sample_catalog_cli_download_rejects_malformed_candidate_envelopes(
        payload, message, capsys, tmp_path):
    candidates = tmp_path / "candidates.json"
    candidates.write_text(json.dumps(payload))

    assert cli.main([
        "sample-catalog", "download",
        "--candidates", str(candidates),
        "--out", str(tmp_path / "cache"),
    ]) == 1

    err = capsys.readouterr().err
    assert message in err
    assert "Traceback" not in err


def test_sample_catalog_cli_download_rejects_malformed_candidate_record(
        capsys, tmp_path):
    candidates = tmp_path / "candidates.json"
    candidates.write_text(json.dumps([{
        "source": "freesound",
        "source_id": "1",
        "download_url": "https://freesound.org/apiv2/sounds/1/download/",
        "filename": "C4.wav",
        "decision": {
            "status": "accepted",
            "license_id": "CC0-1.0",
            "reasons": [],
        },
    }]))

    assert cli.main([
        "sample-catalog", "download",
        "--candidates", str(candidates),
        "--out", str(tmp_path / "cache"),
        "--token", "tok",
    ]) == 1

    err = capsys.readouterr().err
    assert "Error: candidate missing required field: source_url" in err
    assert "Traceback" not in err
    assert "KeyError" not in err


def test_sample_catalog_cli_download_passes_retry_budget(monkeypatch, tmp_path):
    evidence = make_evidence(
        source="freesound",
        source_id="1",
        source_url="https://freesound.org/s/1/",
        download_url="https://freesound.org/apiv2/sounds/1/download/",
        license_name="CC0",
        license_url="https://creativecommons.org/publicdomain/zero/1.0/",
        fetched_at="2026-06-12T00:00:00+00:00",
    )
    candidate = Candidate(
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
    candidates = tmp_path / "candidates.json"
    candidates.write_text(json.dumps([candidate.to_dict()]))

    calls = []

    class FlakyHttp:
        def get_bytes(self, url, *, headers=None):
            calls.append((url, headers))
            if len(calls) == 1:
                raise TimeoutError("temporary transport failure")
            return _wav_bytes()

    monkeypatch.setattr(cli, "_UrllibHttp", FlakyHttp)

    assert cli.main([
        "sample-catalog", "download",
        "--candidates", str(candidates),
        "--out", str(tmp_path / "cache"),
        "--token", "tok",
        "--retries", "2",
    ]) == 0

    assert len(calls) == 2


def test_sample_catalog_cli_download_resumes_from_existing_manifest(
        monkeypatch, tmp_path):
    evidence = make_evidence(
        source="freesound",
        source_id="1",
        source_url="https://freesound.org/s/1/",
        download_url="https://freesound.org/apiv2/sounds/1/download/",
        license_name="CC0",
        license_url="https://creativecommons.org/publicdomain/zero/1.0/",
        fetched_at="2026-06-12T00:00:00+00:00",
    )
    candidate = Candidate(
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
    candidates = tmp_path / "candidates.json"
    candidates.write_text(json.dumps([candidate.to_dict()]))

    calls = []

    class ResumeHttp:
        def get_bytes(self, url, *, headers=None):
            calls.append((url, headers))
            return _wav_bytes()

    monkeypatch.setattr(cli, "_UrllibHttp", ResumeHttp)

    cache = tmp_path / "cache"
    args = [
        "sample-catalog", "download",
        "--candidates", str(candidates),
        "--out", str(cache),
        "--token", "tok",
    ]

    assert cli.main(args) == 0
    assert len(calls) == 1
    first_manifest = json.loads((cache / "downloads.json").read_text())
    assert first_manifest[0]["reused"] is False

    assert cli.main(args) == 0
    assert len(calls) == 1
    second_manifest = json.loads((cache / "downloads.json").read_text())
    assert second_manifest[0]["sha256"] == first_manifest[0]["sha256"]
    assert second_manifest[0]["reused"] is True


def test_sample_catalog_cli_approve_requires_reviewed_at(capsys, tmp_path):
    candidate = _build_reviewable_candidate(tmp_path)

    assert cli.main([
        "sample-catalog", "review",
        str(candidate),
        "--reviewer", "qa",
        "--approve-to", str(tmp_path / "approved"),
    ]) == 1

    assert "reviewed_at is required" in capsys.readouterr().err


def test_sample_catalog_cli_approve_records_explicit_reviewed_at(tmp_path):
    candidate = _build_reviewable_candidate(tmp_path)
    reviewed_at = "2026-06-12T15:00:00+00:00"
    approved_root = tmp_path / "approved"

    assert cli.main([
        "sample-catalog", "review",
        str(candidate),
        "--reviewer", "qa",
        "--reviewed-at", reviewed_at,
        "--approve-to", str(approved_root),
    ]) == 0

    manifests = list(approved_root.rglob("library.manifest.json"))
    assert len(manifests) == 1
    manifest = json.loads(manifests[0].read_text())
    assert manifest["review"]["reviewed_at"] == reviewed_at


def _build_reviewable_candidate(tmp_path):
    from audioforge.sample_catalog.manifest import (
        copy_samples, write_library_manifest, write_license_bundle)
    from audioforge.sample_catalog.sfz import build_regions, write_sfz

    sample = tmp_path / "src" / "C4.wav"
    sample.parent.mkdir()
    sample.write_bytes(_wav_bytes())
    candidate = tmp_path / "candidate"
    copied = copy_samples([sample], candidate / "samples")
    analysis = {
        "path": str(copied[0]),
        "sha256": "0" * 64,
        "status": "accepted",
        "midi_note": 60,
    }
    write_sfz(build_regions([analysis]), candidate / "instrument.sfz")
    ev = make_evidence(
        source="freesound",
        source_id="1",
        source_url="https://freesound.org/s/1/",
        download_url="https://freesound.org/apiv2/sounds/1/download/",
        license_name="CC0",
        license_url="https://creativecommons.org/publicdomain/zero/1.0/",
        fetched_at="2026-06-12T00:00:00+00:00",
    ).to_dict()
    bundle = write_license_bundle([ev], candidate / "LICENSES.json")
    bundle_hash = json.loads(bundle.read_text())["license_evidence_hash"]
    write_library_manifest(
        candidate,
        name="reviewable-guitar",
        version="1.0.0",
        instrument="guitar",
        license_evidence_hash=bundle_hash,
        license_evidence=[ev],
    )
    return candidate


def test_existing_ingest_and_libgen_cli_still_work(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr("audioforge.samples.ingest", lambda directory: [])
    monkeypatch.setattr(
        "audioforge.library.generate_manifest",
        lambda directory, name, version, license_str: {
            "name": name,
            "version": version,
            "license": license_str,
            "files": [],
            "instruments": {},
            "manifest_sha256": "c" * 64,
        },
    )
    assert cli.main(["ingest", str(tmp_path)]) == 0
    assert cli.main([
        "libgen", str(tmp_path), "--name", "kit",
        "--version", "1.2.3", "--license", "CC0",
    ]) == 0
    assert "pin: kit@" in capsys.readouterr().out


def test_sample_catalog_cli_build_sfz_writes_explicit_articulations(tmp_path):
    sample_a = tmp_path / "C4_stac_rr1.wav"
    sample_b = tmp_path / "C4_stac_rr2.wav"
    sample_a.write_bytes(b"a")
    sample_b.write_bytes(b"b")
    analysis = tmp_path / "analysis"
    analysis.mkdir()
    (analysis / "a.json").write_text(json.dumps({
        "path": str(sample_a),
        "sha256": _sha256(sample_a),
        "status": "accepted",
        "midi_note": 60,
        "articulation": "staccato",
        "velocity_layer": "soft",
        "round_robin_group": "c4_stac",
    }))
    (analysis / "b.json").write_text(json.dumps({
        "path": str(sample_b),
        "sha256": _sha256(sample_b),
        "status": "accepted",
        "midi_note": 60,
        "articulation": "staccato",
        "velocity_layer": "soft",
        "round_robin_group": "c4_stac",
    }))
    evidence = tmp_path / "evidence.json"
    evidence.write_text(json.dumps(make_evidence(
        source="freesound",
        source_id="1",
        source_url="https://freesound.org/s/1/",
        download_url="https://freesound.org/apiv2/sounds/1/download/",
        license_name="CC0",
        license_url="https://creativecommons.org/publicdomain/zero/1.0/",
        fetched_at="2026-06-12T00:00:00+00:00",
    ).to_dict()))

    out = tmp_path / "candidate"
    assert cli.main([
        "sample-catalog", "build-sfz",
        "--instrument", "guitar",
        "--analysis", str(analysis),
        "--evidence", str(evidence),
        "--out", str(out),
    ]) == 0

    assert (out / "instrument_staccato.sfz").exists()
    manifest = json.loads((out / "library.manifest.json").read_text())
    assert manifest["instruments"]["guitar"]["articulations"] == {
        "staccato": "instrument_staccato.sfz"
    }
    text = (out / "instrument_staccato.sfz").read_text()
    assert "lovel=1" in text
    assert "hivel=63" in text
    assert "seq_length=2" in text


def test_sample_catalog_cli_build_sfz_rejects_unknown_analysis_schema(capsys, tmp_path):
    sample = tmp_path / "C4.wav"
    sample.write_bytes(b"a")
    analysis = tmp_path / "analysis"
    analysis.mkdir()
    (analysis / "a.json").write_text(json.dumps({
        "schema": "audioforge.sample-catalog.analysis/0",
        "path": str(sample),
        "sha256": "a" * 64,
        "status": "accepted",
        "midi_note": 60,
    }))
    evidence = tmp_path / "evidence.json"
    evidence.write_text(json.dumps(make_evidence(
        source="freesound",
        source_id="1",
        source_url="https://freesound.org/s/1/",
        download_url="https://freesound.org/apiv2/sounds/1/download/",
        license_name="CC0",
        license_url="https://creativecommons.org/publicdomain/zero/1.0/",
        fetched_at="2026-06-12T00:00:00+00:00",
    ).to_dict()))

    assert cli.main([
        "sample-catalog", "build-sfz",
        "--instrument", "guitar",
        "--analysis", str(analysis),
        "--evidence", str(evidence),
        "--out", str(tmp_path / "candidate"),
    ]) == 1

    assert "unsupported sample catalog analysis schema" in capsys.readouterr().err


def test_sample_catalog_cli_build_sfz_accepts_list_evidence_file(tmp_path):
    sample = tmp_path / "C4.wav"
    sample.write_bytes(b"a")
    analysis = tmp_path / "analysis"
    analysis.mkdir()
    (analysis / "a.json").write_text(json.dumps({
        "path": str(sample),
        "sha256": _sha256(sample),
        "status": "accepted",
        "midi_note": 60,
    }))
    evidence = tmp_path / "evidence.json"
    evidence.write_text(json.dumps([make_evidence(
        source="freesound",
        source_id="1",
        source_url="https://freesound.org/s/1/",
        download_url="https://freesound.org/apiv2/sounds/1/download/",
        license_name="CC0",
        license_url="https://creativecommons.org/publicdomain/zero/1.0/",
        fetched_at="2026-06-12T00:00:00+00:00",
    ).to_dict()]))

    candidate = tmp_path / "candidate"
    assert cli.main([
        "sample-catalog", "build-sfz",
        "--instrument", "guitar",
        "--analysis", str(analysis),
        "--evidence", str(evidence),
        "--out", str(candidate),
    ]) == 0

    bundle = json.loads((candidate / "LICENSES.json").read_text())
    assert len(bundle["evidence"]) == 1


def test_sample_catalog_cli_build_sfz_rejects_unknown_license_bundle_schema(
        capsys, tmp_path):
    sample = tmp_path / "C4.wav"
    sample.write_bytes(b"a")
    analysis = tmp_path / "analysis"
    analysis.mkdir()
    (analysis / "a.json").write_text(json.dumps({
        "path": str(sample),
        "sha256": _sha256(sample),
        "status": "accepted",
        "midi_note": 60,
    }))
    evidence_item = make_evidence(
        source="freesound",
        source_id="1",
        source_url="https://freesound.org/s/1/",
        download_url="https://freesound.org/apiv2/sounds/1/download/",
        license_name="CC0",
        license_url="https://creativecommons.org/publicdomain/zero/1.0/",
        fetched_at="2026-06-12T00:00:00+00:00",
    ).to_dict()
    evidence = tmp_path / "LICENSES.json"
    evidence.write_text(json.dumps({
        "schema": "audioforge.sample-catalog.licenses/0",
        "evidence": [evidence_item],
    }))
    candidate = tmp_path / "candidate"

    assert cli.main([
        "sample-catalog", "build-sfz",
        "--instrument", "guitar",
        "--analysis", str(analysis),
        "--evidence", str(evidence),
        "--out", str(candidate),
    ]) == 1

    err = capsys.readouterr().err
    assert "unsupported sample catalog license bundle schema" in err
    assert "Traceback" not in err
    assert not candidate.exists()


def test_sample_catalog_cli_build_sfz_rejects_analysis_sample_hash_mismatch(
        capsys, tmp_path):
    sample = tmp_path / "C4.wav"
    sample.write_bytes(b"real sample bytes")
    analysis = tmp_path / "analysis"
    analysis.mkdir()
    (analysis / "a.json").write_text(json.dumps({
        "path": str(sample),
        "sha256": "0" * 64,
        "status": "accepted",
        "midi_note": 60,
    }))
    evidence = tmp_path / "evidence.json"
    evidence.write_text(json.dumps(make_evidence(
        source="freesound",
        source_id="1",
        source_url="https://freesound.org/s/1/",
        download_url="https://freesound.org/apiv2/sounds/1/download/",
        license_name="CC0",
        license_url="https://creativecommons.org/publicdomain/zero/1.0/",
        fetched_at="2026-06-12T00:00:00+00:00",
    ).to_dict()))

    assert cli.main([
        "sample-catalog", "build-sfz",
        "--instrument", "guitar",
        "--analysis", str(analysis),
        "--evidence", str(evidence),
        "--out", str(tmp_path / "candidate"),
    ]) == 1

    err = capsys.readouterr().err
    assert "sample-catalog analysis: sha256 mismatch" in err
    assert "Traceback" not in err
    assert not (tmp_path / "candidate").exists()


def test_sample_catalog_cli_build_sfz_rejects_duplicate_sample_filenames(
        capsys, tmp_path):
    sample_a = tmp_path / "one" / "C4.wav"
    sample_b = tmp_path / "two" / "C4.wav"
    sample_a.parent.mkdir()
    sample_b.parent.mkdir()
    sample_a.write_bytes(b"first sample bytes")
    sample_b.write_bytes(b"second sample bytes")
    analysis = tmp_path / "analysis"
    analysis.mkdir()
    (analysis / "a.json").write_text(json.dumps({
        "path": str(sample_a),
        "sha256": _sha256(sample_a),
        "status": "accepted",
        "midi_note": 60,
    }))
    (analysis / "b.json").write_text(json.dumps({
        "path": str(sample_b),
        "sha256": _sha256(sample_b),
        "status": "accepted",
        "midi_note": 62,
    }))
    evidence = tmp_path / "evidence.json"
    evidence.write_text(json.dumps(make_evidence(
        source="freesound",
        source_id="1",
        source_url="https://freesound.org/s/1/",
        download_url="https://freesound.org/apiv2/sounds/1/download/",
        license_name="CC0",
        license_url="https://creativecommons.org/publicdomain/zero/1.0/",
        fetched_at="2026-06-12T00:00:00+00:00",
    ).to_dict()))

    candidate = tmp_path / "candidate"
    assert cli.main([
        "sample-catalog", "build-sfz",
        "--instrument", "guitar",
        "--analysis", str(analysis),
        "--evidence", str(evidence),
        "--out", str(candidate),
    ]) == 1

    err = capsys.readouterr().err
    assert "sample-catalog analysis: duplicate sample filename C4.wav" in err
    assert "Traceback" not in err
    assert not candidate.exists()


def test_sample_catalog_cli_build_sfz_reports_missing_explicit_evidence_path(
        capsys, tmp_path):
    sample = tmp_path / "C4.wav"
    sample.write_bytes(b"a")
    ev = make_evidence(
        source="freesound",
        source_id="1",
        source_url="https://freesound.org/s/1/",
        download_url="https://freesound.org/apiv2/sounds/1/download/",
        license_name="CC0",
        license_url="https://creativecommons.org/publicdomain/zero/1.0/",
        fetched_at="2026-06-12T00:00:00+00:00",
    ).to_dict()
    analysis = tmp_path / "analysis"
    analysis.mkdir()
    (analysis / "a.json").write_text(json.dumps({
        "path": str(sample),
        "sha256": _sha256(sample),
        "status": "accepted",
        "midi_note": 60,
        "source_evidence_id": ev["evidence_hash"],
        "license_evidence": ev,
    }))

    assert cli.main([
        "sample-catalog", "build-sfz",
        "--instrument", "guitar",
        "--analysis", str(analysis),
        "--evidence", str(tmp_path / "missing-evidence.json"),
        "--out", str(tmp_path / "candidate"),
    ]) == 1

    err = capsys.readouterr().err
    assert "Error: sample-catalog evidence: cannot read" in err
    assert "file not found" in err
    assert "Traceback" not in err
    assert "FileNotFoundError" not in err


def test_sample_catalog_cli_build_sfz_reports_empty_explicit_evidence_dir(
        capsys, tmp_path):
    sample = tmp_path / "C4.wav"
    sample.write_bytes(b"a")
    ev = make_evidence(
        source="freesound",
        source_id="1",
        source_url="https://freesound.org/s/1/",
        download_url="https://freesound.org/apiv2/sounds/1/download/",
        license_name="CC0",
        license_url="https://creativecommons.org/publicdomain/zero/1.0/",
        fetched_at="2026-06-12T00:00:00+00:00",
    ).to_dict()
    analysis = tmp_path / "analysis"
    analysis.mkdir()
    (analysis / "a.json").write_text(json.dumps({
        "path": str(sample),
        "sha256": _sha256(sample),
        "status": "accepted",
        "midi_note": 60,
        "source_evidence_id": ev["evidence_hash"],
        "license_evidence": ev,
    }))
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()

    assert cli.main([
        "sample-catalog", "build-sfz",
        "--instrument", "guitar",
        "--analysis", str(analysis),
        "--evidence", str(evidence_dir),
        "--out", str(tmp_path / "candidate"),
    ]) == 1

    err = capsys.readouterr().err
    assert "Error: sample-catalog evidence: no evidence files found" in err
    assert "Traceback" not in err


def test_sample_catalog_cli_reports_invalid_analysis_json_without_traceback(
        capsys, tmp_path):
    analysis = tmp_path / "analysis"
    analysis.mkdir()
    (analysis / "bad.json").write_text("{not json")
    evidence = tmp_path / "evidence.json"
    evidence.write_text(json.dumps(make_evidence(
        source="freesound",
        source_id="1",
        source_url="https://freesound.org/s/1/",
        download_url="https://freesound.org/apiv2/sounds/1/download/",
        license_name="CC0",
        license_url="https://creativecommons.org/publicdomain/zero/1.0/",
        fetched_at="2026-06-12T00:00:00+00:00",
    ).to_dict()))

    assert cli.main([
        "sample-catalog", "build-sfz",
        "--instrument", "guitar",
        "--analysis", str(analysis),
        "--evidence", str(evidence),
        "--out", str(tmp_path / "candidate"),
    ]) == 1

    err = capsys.readouterr().err
    assert "Error: sample-catalog analysis: invalid JSON" in err
    assert "line 1 column 2" in err
    assert "Traceback" not in err
    assert "JSONDecodeError" not in err


def test_sample_catalog_cli_reports_malformed_analysis_record_without_traceback(
        capsys, tmp_path):
    analysis = tmp_path / "analysis"
    analysis.mkdir()
    (analysis / "bad.json").write_text(json.dumps([{
        "path": str(tmp_path / "C4.wav"),
        "status": "accepted",
    }]))
    evidence = tmp_path / "evidence.json"
    evidence.write_text(json.dumps(make_evidence(
        source="freesound",
        source_id="1",
        source_url="https://freesound.org/s/1/",
        download_url="https://freesound.org/apiv2/sounds/1/download/",
        license_name="CC0",
        license_url="https://creativecommons.org/publicdomain/zero/1.0/",
        fetched_at="2026-06-12T00:00:00+00:00",
    ).to_dict()))

    assert cli.main([
        "sample-catalog", "build-sfz",
        "--instrument", "guitar",
        "--analysis", str(analysis),
        "--evidence", str(evidence),
        "--out", str(tmp_path / "candidate"),
    ]) == 1

    err = capsys.readouterr().err
    assert "sample-catalog analysis: expected analysis object" in err
    assert "Traceback" not in err
    assert "AttributeError" not in err


def test_sample_catalog_cli_build_sfz_reports_missing_analysis_path(
        capsys, tmp_path):
    evidence = tmp_path / "evidence.json"
    evidence.write_text(json.dumps(make_evidence(
        source="freesound",
        source_id="1",
        source_url="https://freesound.org/s/1/",
        download_url="https://freesound.org/apiv2/sounds/1/download/",
        license_name="CC0",
        license_url="https://creativecommons.org/publicdomain/zero/1.0/",
        fetched_at="2026-06-12T00:00:00+00:00",
    ).to_dict()))

    assert cli.main([
        "sample-catalog", "build-sfz",
        "--instrument", "guitar",
        "--analysis", str(tmp_path / "missing-analysis"),
        "--evidence", str(evidence),
        "--out", str(tmp_path / "candidate"),
    ]) == 1

    err = capsys.readouterr().err
    assert "Error: sample-catalog analysis: cannot read" in err
    assert "file not found" in err
    assert "Traceback" not in err
    assert "FileNotFoundError" not in err


def test_sample_catalog_cli_build_sfz_reports_empty_analysis_dir(
        capsys, tmp_path):
    analysis = tmp_path / "analysis"
    analysis.mkdir()
    evidence = tmp_path / "evidence.json"
    evidence.write_text(json.dumps(make_evidence(
        source="freesound",
        source_id="1",
        source_url="https://freesound.org/s/1/",
        download_url="https://freesound.org/apiv2/sounds/1/download/",
        license_name="CC0",
        license_url="https://creativecommons.org/publicdomain/zero/1.0/",
        fetched_at="2026-06-12T00:00:00+00:00",
    ).to_dict()))

    assert cli.main([
        "sample-catalog", "build-sfz",
        "--instrument", "guitar",
        "--analysis", str(analysis),
        "--evidence", str(evidence),
        "--out", str(tmp_path / "candidate"),
    ]) == 1

    err = capsys.readouterr().err
    assert "Error: sample-catalog analysis: no analysis files found" in err
    assert "Traceback" not in err


def test_sample_catalog_cli_build_sfz_preserves_guitar_mechanics(tmp_path):
    sample_a = tmp_path / "C4.wav"
    sample_b = tmp_path / "D4.wav"
    sample_a.write_bytes(b"a")
    sample_b.write_bytes(b"b")
    analysis = tmp_path / "analysis"
    analysis.mkdir()
    ev = make_evidence(
        source="freesound",
        source_id="1",
        source_url="https://freesound.org/s/1/",
        download_url="https://freesound.org/apiv2/sounds/1/download/",
        license_name="CC0",
        license_url="https://creativecommons.org/publicdomain/zero/1.0/",
        fetched_at="2026-06-12T00:00:00+00:00",
    ).to_dict()
    (analysis / "a.json").write_text(json.dumps({
        "path": str(sample_a),
        "sha256": _sha256(sample_a),
        "status": "accepted",
        "midi_note": 60,
        "source_evidence_id": ev["evidence_hash"],
        "string": "A2",
        "fret": 3,
        "tuning": ["E2", "A2", "D3", "G3", "B3", "E4"],
        "session": "take-7",
    }))
    (analysis / "b.json").write_text(json.dumps({
        "path": str(sample_b),
        "sha256": _sha256(sample_b),
        "status": "accepted",
        "midi_note": 62,
        "source_evidence_id": ev["evidence_hash"],
    }))
    evidence = tmp_path / "evidence.json"
    evidence.write_text(json.dumps(ev))

    out = tmp_path / "candidate"
    assert cli.main([
        "sample-catalog", "build-sfz",
        "--instrument", "guitar",
        "--analysis", str(analysis),
        "--evidence", str(evidence),
        "--out", str(out),
    ]) == 0

    manifest = json.loads((out / "library.manifest.json").read_text())
    by_sample = {r["sample"]: r["mechanics"] for r in manifest["regions"]}
    assert by_sample["samples/C4.wav"] == {
        "status": "source_proven",
        "string": "A2",
        "fret": 3,
        "tuning": ["E2", "A2", "D3", "G3", "B3", "E4"],
        "session": "take-7",
    }
    assert by_sample["samples/D4.wav"] == {
        "status": "unavailable",
        "reason": "source_metadata_absent",
    }
