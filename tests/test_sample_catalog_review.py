import json
import math
import shutil
import wave

import numpy as np
import pytest

from audioforge.sample_catalog.analyze import analyze_sample
from audioforge.sample_catalog.licenses import make_evidence
from audioforge.sample_catalog.manifest import (
    audit_catalog,
    copy_samples,
    write_library_manifest,
    write_license_bundle,
)
from audioforge.sample_catalog.review import promote_candidate, write_review
from audioforge.sample_catalog.sfz import build_regions, write_sfz


def _wav(path, freq=261.625565, sr=44100):
    t = np.arange(int(sr * 0.25)) / sr
    x = np.sin(2 * math.pi * freq * t) * 0.3
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((x * 32767).astype("<i2").tobytes())


def _candidate(tmp_path, *, analysis_summary=None, evidence_source="freesound"):
    src = tmp_path / "src" / "C4.wav"
    src.parent.mkdir(parents=True)
    _wav(src)
    analysis = analyze_sample(src)
    candidate = tmp_path / "candidate"
    copied = copy_samples([src], candidate / "samples")
    analysis["path"] = str(copied[0])
    write_sfz(build_regions([analysis]), candidate / "instrument.sfz")
    source_url = {
        "freesound": "https://freesound.org/s/1/",
        "internet_archive": "https://archive.org/details/pd-pack",
        "wikimedia_commons": "https://commons.wikimedia.org/wiki/File:C4.ogg",
    }.get(evidence_source, "https://freesound.org/s/1/")
    download_url = {
        "freesound": "https://freesound.org/apiv2/sounds/1/download/",
        "internet_archive": "https://archive.org/download/pd-pack/C4.wav",
        "wikimedia_commons": "https://upload.wikimedia.org/C4.ogg",
    }.get(evidence_source, "https://freesound.org/apiv2/sounds/1/download/")
    evidence = make_evidence(
        source=evidence_source,
        source_id="1",
        source_url=source_url,
        download_url=download_url,
        license_name="CC0-1.0",
        license_url="https://creativecommons.org/publicdomain/zero/1.0/",
        creator="alice",
        fetched_at="2026-06-12T00:00:00+00:00",
    ).to_dict()
    bundle = write_license_bundle([evidence], candidate / "LICENSES.json")
    bundle_hash = json.loads(bundle.read_text())["license_evidence_hash"]
    write_library_manifest(
        candidate,
        name="review-guitar",
        version="1.0.0",
        instrument="guitar",
        license_evidence_hash=bundle_hash,
        license_evidence=[evidence],
        analysis_summary=analysis_summary or {"accepted_samples": 1},
    )
    return candidate


def test_review_report_contains_license_pitch_warning_and_audition_sections(tmp_path):
    candidate = _candidate(tmp_path)
    review = write_review(candidate, reviewer="qa", notes="auditioned cleanly")
    text = review.read_text()

    assert "## Source And License Evidence" in text
    assert "https://freesound.org/s/1/" in text
    assert "CC0-1.0" in text
    assert "## Pitch Map" in text
    assert "| guitar | sustain | 60 | 60-60 | 1-127 | `samples/C4.wav`" in text
    assert "## Catalog Diagnostics" in text
    assert "- Instruments: 1" in text
    assert "- Renderable: 1" in text
    assert "- Blocked: 0" in text
    assert "- Render blockers: none" in text
    assert "| instrument | `instrument.sfz` | yes | none | wav | C4-C4 | 1-127 | 1 |" in text
    assert "## Quality Warnings" in text
    assert "Catalog is still a candidate" in text
    assert "## Audition" in text
    assert "audioforge sample-catalog audit-license" in text
    assert "Catalog.build('.').to_dict()" in text
    assert 'library: "review-guitar@' in text
    assert 'instrument: "guitar"' in text
    assert "notes: C4 @ 0b for 1b" in text
    assert "auditioned cleanly" in text


def test_review_report_is_path_portable_for_same_catalog(tmp_path):
    first = _candidate(tmp_path / "one")
    second = _candidate(tmp_path / "two")

    first_text = write_review(
        first, reviewer="qa", notes="auditioned cleanly").read_text()
    second_text = write_review(
        second, reviewer="qa", notes="auditioned cleanly").read_text()

    assert first_text == second_text
    assert str(first) not in first_text
    assert str(second) not in second_text
    assert "audioforge sample-catalog audit-license ." in first_text
    assert "Catalog.build('.').to_dict()" in first_text
    assert "## Catalog Diagnostics" in first_text


def test_review_report_surfaces_quality_score_warnings(tmp_path):
    candidate = _candidate(tmp_path, analysis_summary={
        "accepted_samples": 2,
        "quality_score_min": 0.7,
        "quality_score_mean": 0.82,
        "quality_score_max": 1.0,
    })

    text = write_review(candidate, reviewer="qa").read_text()

    assert "Quality score minimum is low (0.700)" in text
    assert "Quality score mean is below target (0.820)" in text


def test_review_report_surfaces_internet_archive_source_context_warning(tmp_path):
    candidate = _candidate(tmp_path, analysis_summary={
        "accepted_samples": 2,
        "internet_archive_source_context_review_required": 2,
    }, evidence_source="internet_archive")

    text = write_review(candidate, reviewer="qa").read_text()

    assert (
        "Internet Archive source context is not clearly a sample pack, "
        "isolated note, or institutional collection for 2 accepted sample(s)."
    ) in text


@pytest.mark.parametrize("source, warning", [
    ("internet_archive", "manual public-domain provenance review"),
    ("wikimedia_commons", "manual Commons license metadata review"),
])
def test_review_report_surfaces_secondary_source_review_requirements(
        tmp_path, source, warning):
    candidate = _candidate(tmp_path, evidence_source=source)

    text = write_review(candidate, reviewer="qa").read_text()

    assert warning in text


def test_review_report_requires_catalog_audit_before_write(tmp_path):
    candidate = _candidate(tmp_path)
    (candidate / "samples" / "C4.wav").unlink()

    with pytest.raises(ValueError, match="catalog_diagnostics does not match"):
        write_review(candidate, reviewer="qa")

    assert not (candidate / "review.md").exists()


def test_promotion_uses_explicit_reviewed_at_for_reproducible_manifest(tmp_path):
    reviewed_at = "2026-06-12T15:00:00+00:00"
    first = promote_candidate(
        _candidate(tmp_path / "one"),
        tmp_path / "approved-one",
        reviewer="qa",
        reviewed_at=reviewed_at,
    )
    second = promote_candidate(
        _candidate(tmp_path / "two"),
        tmp_path / "approved-two",
        reviewer="qa",
        reviewed_at=reviewed_at,
    )

    first_manifest = json.loads((first / "library.manifest.json").read_text())
    second_manifest = json.loads((second / "library.manifest.json").read_text())

    assert first_manifest["review"] == {
        "status": "approved",
        "reviewer": "qa",
        "reviewed_at": reviewed_at,
    }
    assert first_manifest["manifest_sha256"] == second_manifest["manifest_sha256"]


def test_promotion_refuses_to_overwrite_existing_approved_version(tmp_path):
    approved_root = tmp_path / "approved"
    promote_candidate(
        _candidate(tmp_path / "one"),
        approved_root,
        reviewer="qa",
        reviewed_at="2026-06-12T15:00:00+00:00",
    )

    with pytest.raises(FileExistsError):
        promote_candidate(
            _candidate(tmp_path / "two"),
            approved_root,
            reviewer="qa",
            reviewed_at="2026-06-12T15:00:00+00:00",
        )


def test_candidate_cannot_bypass_review_by_manual_approved_root_copy(tmp_path):
    candidate = _candidate(tmp_path / "source")
    approved_root = tmp_path / "approved"
    manually_copied = approved_root / "review-guitar" / "1.0.0"
    shutil.copytree(candidate, manually_copied)

    with pytest.raises(ValueError, match="catalog is not approved"):
        audit_catalog(manually_copied, require_approved=True)

    manifest = json.loads((manually_copied / "library.manifest.json").read_text())
    assert manifest["catalog_state"] == "candidate"
    assert manifest["review"] == {"status": "pending"}


def test_promotion_with_explicit_version_updates_manifest_and_hash(tmp_path):
    approved = promote_candidate(
        _candidate(tmp_path),
        tmp_path / "approved",
        reviewer="qa",
        reviewed_at="2026-06-12T15:00:00+00:00",
        version="1.0.1",
    )

    manifest = json.loads((approved / "library.manifest.json").read_text())

    assert approved.name == "1.0.1"
    assert manifest["version"] == "1.0.1"
    assert manifest["manifest_sha256"] != "0" * 64


def test_promotion_requires_explicit_reviewed_at(tmp_path):
    try:
        promote_candidate(
            _candidate(tmp_path),
            tmp_path / "approved",
            reviewer="qa",
        )
    except TypeError:
        return
    raise AssertionError("promote_candidate must require reviewed_at")


def test_promotion_rejects_timezone_less_reviewed_at(tmp_path):
    with pytest.raises(ValueError, match="reviewed_at must include timezone"):
        promote_candidate(
            _candidate(tmp_path),
            tmp_path / "approved",
            reviewer="qa",
            reviewed_at="2026-06-12T15:00:00",
        )
