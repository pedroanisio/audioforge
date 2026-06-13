import json
import math
import wave

import numpy as np
import pytest

from audioforge.catalog import Catalog
from audioforge.library import (
    _canonical_manifest_hash,
    add_approved_catalog_path,
    add_library_path,
    load_library,
)
from audioforge.sample_catalog.analyze import analyze_sample
from audioforge.sample_catalog.licenses import evidence_hash, make_evidence
from audioforge.sample_catalog.manifest import (
    _catalog_diagnostics,
    attach_region_library_pins,
    audit_catalog,
    copy_samples,
    write_library_manifest,
    write_license_bundle,
)
from audioforge.sample_catalog.review import promote_candidate
from audioforge.sample_catalog.sfz import build_regions, write_sfz


def _wav(path, freq=261.625565, sr=44100):
    t = np.arange(int(sr * 0.25)) / sr
    x = np.sin(2 * math.pi * freq * t) * 0.3
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((x * 32767).astype("<i2").tobytes())


def _candidate_library(tmp_path):
    src = tmp_path / "src" / "C4.wav"
    src.parent.mkdir()
    _wav(src)
    analysis = analyze_sample(src)
    candidate = tmp_path / "candidate"
    copied = copy_samples([src], candidate / "samples")
    analysis["path"] = str(copied[0])
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
    manifest = write_library_manifest(
        candidate,
        name="public-guitar",
        version="1.0.0",
        instrument="guitar",
        catalog_state="candidate",
        license_evidence_hash=bundle_hash,
        license_evidence=[ev],
        analysis_summary={"accepted_samples": 1},
    )
    return candidate, manifest


def test_manifest_loads_through_existing_loader_and_catalog_reports_renderable(tmp_path):
    candidate, manifest = _candidate_library(tmp_path)
    add_library_path(tmp_path)
    lib = load_library({
        "name": manifest["name"],
        "manifest_sha256": manifest["manifest_sha256"],
    })
    assert lib.regions("guitar")[0].sample == "samples/C4.wav"

    cat = Catalog.build(candidate)
    assert len(cat.renderable()) == 1
    audit = audit_catalog(candidate)
    assert audit["ok"] is True


def test_license_bundle_rejects_wrong_evidence_schema(tmp_path):
    ev = make_evidence(
        source="freesound",
        source_id="1",
        source_url="https://freesound.org/s/1/",
        download_url="https://freesound.org/apiv2/sounds/1/download/",
        license_name="CC0",
        license_url="https://creativecommons.org/publicdomain/zero/1.0/",
        fetched_at="2026-06-12T00:00:00+00:00",
    ).to_dict()
    ev["schema"] = "audioforge.sample-catalog.evidence/0"
    ev["evidence_hash"] = "0" * 64

    with pytest.raises(ValueError, match="unsupported license evidence schema"):
        write_license_bundle([ev], tmp_path / "LICENSES.json")


def test_license_bundle_rejects_mismatched_evidence_hash(tmp_path):
    ev = make_evidence(
        source="freesound",
        source_id="1",
        source_url="https://freesound.org/s/1/",
        download_url="https://freesound.org/apiv2/sounds/1/download/",
        license_name="CC0",
        license_url="https://creativecommons.org/publicdomain/zero/1.0/",
        fetched_at="2026-06-12T00:00:00+00:00",
    ).to_dict()
    ev["evidence_hash"] = "0" * 64

    with pytest.raises(ValueError, match="license evidence hash mismatch"):
        write_license_bundle([ev], tmp_path / "LICENSES.json")


def test_license_bundle_rejects_openverse_discovery_evidence(tmp_path):
    ev = make_evidence(
        source="openverse_discovery",
        source_id="ov-1",
        source_url="https://example.test/source",
        download_url="https://example.test/C4.wav",
        license_name="CC0",
        license_url="https://creativecommons.org/publicdomain/zero/1.0/",
        rights_text="Openverse discovery lead; verify upstream before download",
        fetched_at="2026-06-12T00:00:00+00:00",
    ).to_dict()

    with pytest.raises(ValueError, match="upstream verification"):
        write_license_bundle([ev], tmp_path / "LICENSES.json")


def test_license_bundle_rejects_unsupported_license_evidence(tmp_path):
    ev = make_evidence(
        source="freesound",
        source_id="2",
        source_url="https://freesound.org/s/2/",
        download_url="https://freesound.org/apiv2/sounds/2/download/",
        license_name="CC-BY",
        license_url="https://creativecommons.org/licenses/by/4.0/",
        fetched_at="2026-06-12T00:00:00+00:00",
    ).to_dict()

    with pytest.raises(ValueError, match="unsupported or unclear license"):
        write_license_bundle([ev], tmp_path / "LICENSES.json")


def test_require_approved_rejects_candidate_and_missing_evidence(tmp_path):
    candidate, manifest = _candidate_library(tmp_path)
    add_library_path(tmp_path)
    with pytest.raises(ValueError, match="approved catalog required"):
        load_library({
            "name": manifest["name"],
            "manifest_sha256": manifest["manifest_sha256"],
        }, require_approved=True)

    data = json.loads((candidate / "library.manifest.json").read_text())
    data["catalog_state"] = "approved"
    data["license_evidence_hash"] = None
    (candidate / "library.manifest.json").write_text(json.dumps(data, indent=1))
    with pytest.raises(ValueError, match="manifest self-hash invalid"):
        load_library({
            "name": manifest["name"],
            "manifest_sha256": manifest["manifest_sha256"],
        }, require_approved=True)


def test_sample_catalog_acceptance_metadata_is_manifest_hashed(tmp_path):
    candidate, manifest = _candidate_library(tmp_path)
    add_library_path(tmp_path)

    data = json.loads((candidate / "library.manifest.json").read_text())
    data["catalog_state"] = "approved"
    (candidate / "library.manifest.json").write_text(json.dumps(data, indent=1))
    with pytest.raises(ValueError, match="manifest self-hash invalid"):
        load_library({
            "name": manifest["name"],
            "manifest_sha256": manifest["manifest_sha256"],
        })


def test_sample_catalog_region_summary_is_manifest_hashed(tmp_path):
    candidate, manifest = _candidate_library(tmp_path)
    add_library_path(tmp_path)

    data = json.loads((candidate / "library.manifest.json").read_text())
    data["regions"][0]["hikey"] = 61
    (candidate / "library.manifest.json").write_text(json.dumps(data, indent=1))
    with pytest.raises(ValueError, match="manifest self-hash invalid"):
        load_library({
            "name": manifest["name"],
            "manifest_sha256": manifest["manifest_sha256"],
        })


def test_manifest_records_region_library_pin_handoff_fields(tmp_path):
    candidate, manifest = _candidate_library(tmp_path)

    expected = {
        "name": manifest["name"],
        "version": manifest["version"],
        "manifest_sha256": manifest["manifest_sha256"],
        "builder_version": manifest["builder_version"],
    }
    assert manifest["regions"][0]["library_pin"] == expected


def test_manifest_records_region_sample_identity_handoff_fields(tmp_path):
    candidate, manifest = _candidate_library(tmp_path)
    sample = candidate / "samples" / "C4.wav"
    region = manifest["regions"][0]

    assert region["sample_identity"] == {
        "sample": "samples/C4.wav",
        "byte_size": sample.stat().st_size,
        "sample_sha256": region["sample_sha256"],
        "source_evidence_id": region["source_evidence_id"],
        "license_evidence_hash": manifest["license_evidence_hash"],
    }


def test_manifest_records_region_coverage_handoff_fields(tmp_path):
    candidate, manifest = _candidate_library(tmp_path)
    region = manifest["regions"][0]

    assert region["coverage"] == {
        "instrument": "guitar",
        "articulation": "sustain",
        "keycenter_midi": 60,
        "key_range": [60, 60],
        "velocity_range": [1, 127],
        "round_robin": {
            "group": None,
            "index": None,
            "size": 1,
        },
        "loop": {
            "mode": "no_loop",
            "start": 0,
            "end": 0,
            "candidate_withheld": False,
        },
    }


def test_manifest_records_catalog_diagnostics_handoff_fields(tmp_path):
    candidate, manifest = _candidate_library(tmp_path)

    assert manifest["catalog_diagnostics"] == {
        "instrument_count": 1,
        "renderable_count": 1,
        "blocked_count": 0,
        "renderable_instruments": [
            {"id": "instrument", "sfz": "instrument.sfz"},
        ],
        "blocked_instruments": [],
        "render_blockers": [],
        "ignored_opcodes": [],
        "instruments": [
            {
                "id": "instrument",
                "sfz": "instrument.sfz",
                "category": "samples",
                "articulation": "default",
                "renderable": True,
                "render_blockers": [],
                "ignored_opcodes": [],
                "missing_samples": [],
                "sample_formats": ["wav"],
                "sample_counts": {
                    "unique": 1,
                    "present": 1,
                    "missing": 0,
                },
                "key_range": {
                    "low_midi": 60,
                    "high_midi": 60,
                    "low_note": "C4",
                    "high_note": "C4",
                },
                "pitch_keycenters": [60],
                "velocity_layers": [[1, 127]],
                "round_robin_max": 1,
                "uses_include": False,
                "regions": 1,
            },
        ],
    }
    assert manifest["catalog_diagnostics"] == _catalog_diagnostics(candidate)


def test_catalog_diagnostics_records_blocked_instruments(tmp_path):
    candidate = tmp_path / "blocked"
    samples = candidate / "samples"
    samples.mkdir(parents=True)
    (samples / "C4.xyz").write_bytes(b"not-a-runtime-audio-format")
    (candidate / "instrument.sfz").write_text(
        "<region>\nsample=samples/C4.xyz\npitch_keycenter=60\n",
        encoding="utf-8",
    )

    diagnostics = _catalog_diagnostics(candidate)

    assert diagnostics["renderable_count"] == 0
    assert diagnostics["blocked_count"] == 1
    assert diagnostics["render_blockers"] == ["unsupported_format"]
    assert diagnostics["blocked_instruments"] == [
        {
            "id": "instrument",
            "sfz": "instrument.sfz",
            "render_blockers": ["unsupported_format"],
            "missing_samples": [],
            "ignored_opcodes": [],
            "sample_formats": ["xyz"],
        },
    ]


def test_manifest_records_per_sample_source_evidence(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    c4 = src / "C4.wav"
    d4 = src / "D4.wav"
    _wav(c4, freq=261.625565)
    _wav(d4, freq=293.664768)
    analyses = [analyze_sample(c4), analyze_sample(d4)]
    candidate = tmp_path / "multi"
    copied = copy_samples([c4, d4], candidate / "samples")
    for row, copied_path in zip(analyses, copied):
        row["path"] = str(copied_path)
    write_sfz(build_regions(analyses), candidate / "instrument.sfz")

    ev_c4 = make_evidence(
        source="freesound",
        source_id="1",
        source_url="https://freesound.org/s/1/",
        download_url="https://freesound.org/apiv2/sounds/1/download/",
        license_name="CC0",
        license_url="https://creativecommons.org/publicdomain/zero/1.0/",
        fetched_at="2026-06-12T00:00:00+00:00",
    ).to_dict()
    ev_d4 = make_evidence(
        source="internet_archive",
        source_id="pd-pack",
        source_url="https://archive.org/details/pd-pack",
        download_url="https://archive.org/download/pd-pack/D4.wav",
        license_name="CC0",
        license_url="https://creativecommons.org/publicdomain/zero/1.0/",
        fetched_at="2026-06-12T00:00:00+00:00",
    ).to_dict()
    bundle = write_license_bundle([ev_c4, ev_d4], candidate / "LICENSES.json")
    bundle_hash = json.loads(bundle.read_text())["license_evidence_hash"]

    manifest = write_library_manifest(
        candidate,
        name="multi-evidence",
        version="1.0.0",
        instrument="guitar",
        license_evidence_hash=bundle_hash,
        license_evidence=[ev_c4, ev_d4],
        sample_evidence_ids={
            "samples/C4.wav": ev_c4["evidence_hash"],
            "samples/D4.wav": ev_d4["evidence_hash"],
        },
    )

    by_sample = {r["sample"]: r["source_evidence_id"] for r in manifest["regions"]}
    assert by_sample == {
        "samples/C4.wav": ev_c4["evidence_hash"],
        "samples/D4.wav": ev_d4["evidence_hash"],
    }


def test_manifest_records_round_robin_handoff_fields(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    c4_a = src / "C4_a.wav"
    c4_b = src / "C4_b.wav"
    _wav(c4_a, freq=261.625565)
    _wav(c4_b, freq=261.625565)
    analyses = [analyze_sample(c4_a), analyze_sample(c4_b)]
    candidate = tmp_path / "round-robin"
    copied = copy_samples([c4_a, c4_b], candidate / "samples")
    for row, copied_path in zip(analyses, copied):
        row["path"] = str(copied_path)
        row["round_robin_group"] = "take-a"
    write_sfz(build_regions(analyses), candidate / "instrument.sfz")

    ev = make_evidence(
        source="freesound",
        source_id="rr-pack",
        source_url="https://freesound.org/s/rr-pack/",
        download_url="https://freesound.org/apiv2/sounds/rr-pack/download/",
        license_name="CC0",
        license_url="https://creativecommons.org/publicdomain/zero/1.0/",
        fetched_at="2026-06-12T00:00:00+00:00",
    ).to_dict()
    bundle = write_license_bundle([ev], candidate / "LICENSES.json")
    bundle_hash = json.loads(bundle.read_text())["license_evidence_hash"]

    manifest = write_library_manifest(
        candidate,
        name="round-robin-guitar",
        version="1.0.0",
        instrument="guitar",
        license_evidence_hash=bundle_hash,
        license_evidence=[ev],
    )

    by_sample = {r["sample"]: r for r in manifest["regions"]}
    assert by_sample["samples/C4_a.wav"]["round_robin"] == {
        "group": "guitar::sustain::pitch60::keys60-60::vel1-127",
        "index": 1,
        "size": 2,
    }
    assert by_sample["samples/C4_b.wav"]["round_robin"] == {
        "group": "guitar::sustain::pitch60::keys60-60::vel1-127",
        "index": 2,
        "size": 2,
    }


def test_manifest_records_per_region_quality_and_diagnostics(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    c4 = src / "C4.wav"
    _wav(c4, freq=261.625565)
    analysis = analyze_sample(c4)
    candidate = tmp_path / "quality"
    copied = copy_samples([c4], candidate / "samples")
    analysis["path"] = str(copied[0])
    analysis["warnings"] = ["manual_review_recommended"]
    write_sfz(build_regions([analysis]), candidate / "instrument.sfz")

    ev = make_evidence(
        source="freesound",
        source_id="quality-pack",
        source_url="https://freesound.org/s/quality-pack/",
        download_url="https://freesound.org/apiv2/sounds/quality-pack/download/",
        license_name="CC0",
        license_url="https://creativecommons.org/publicdomain/zero/1.0/",
        fetched_at="2026-06-12T00:00:00+00:00",
    ).to_dict()
    bundle = write_license_bundle([ev], candidate / "LICENSES.json")
    bundle_hash = json.loads(bundle.read_text())["license_evidence_hash"]

    manifest = write_library_manifest(
        candidate,
        name="quality-guitar",
        version="1.0.0",
        instrument="guitar",
        license_evidence_hash=bundle_hash,
        license_evidence=[ev],
        sample_analysis_records=[analysis],
    )

    region = manifest["regions"][0]
    assert region["quality"] == {
        "analysis_schema": analysis["schema"],
        "quality_score": analysis["quality_score"],
        "pitch_confidence": analysis["pitch_confidence"],
        "status": analysis["status"],
    }
    assert region["diagnostics"] == {
        "rejection_reasons": analysis["rejection_reasons"],
        "warnings": ["manual_review_recommended"],
    }


def test_manifest_writer_rejects_license_evidence_hash_mismatch(tmp_path):
    candidate, _ = _candidate_library(tmp_path)
    ev = make_evidence(
        source="freesound",
        source_id="1",
        source_url="https://freesound.org/s/1/",
        download_url="https://freesound.org/apiv2/sounds/1/download/",
        license_name="CC0",
        license_url="https://creativecommons.org/publicdomain/zero/1.0/",
        fetched_at="2026-06-12T00:00:00+00:00",
    ).to_dict()

    manifest_path = candidate / "library.manifest.json"
    manifest_path.unlink()
    with pytest.raises(ValueError, match="license evidence hash mismatch"):
        write_library_manifest(
            candidate,
            name="stale-license-hash",
            version="1.0.0",
            instrument="guitar",
            license_evidence_hash="0" * 64,
            license_evidence=[ev],
        )

    assert not manifest_path.exists()


def test_manifest_writer_rejects_missing_license_evidence_before_write(tmp_path):
    candidate, _ = _candidate_library(tmp_path)
    manifest_path = candidate / "library.manifest.json"
    license_path = candidate / "LICENSES.json"
    manifest_path.unlink()
    license_path.unlink()

    with pytest.raises(ValueError, match="license evidence is required"):
        write_library_manifest(
            candidate,
            name="missing-license-evidence",
            version="1.0.0",
            instrument="guitar",
            license_evidence_hash="0" * 64,
        )

    assert not manifest_path.exists()


def test_manifest_writer_rejects_unsupported_license_before_write(tmp_path):
    candidate, _ = _candidate_library(tmp_path)
    bad_evidence = make_evidence(
        source="freesound",
        source_id="2",
        source_url="https://freesound.org/s/2/",
        download_url="https://freesound.org/apiv2/sounds/2/download/",
        license_name="CC-BY",
        license_url="https://creativecommons.org/licenses/by/4.0/",
        fetched_at="2026-06-12T00:00:00+00:00",
    ).to_dict()
    bad_bundle = {
        "schema": "audioforge.sample-catalog.licenses/1",
        "evidence": [bad_evidence],
    }
    bad_bundle["license_evidence_hash"] = evidence_hash({
        "schema": bad_bundle["schema"],
        "evidence": bad_bundle["evidence"],
    })
    (candidate / "LICENSES.json").write_text(
        json.dumps(bad_bundle, indent=2, sort_keys=True) + "\n")
    manifest_path = candidate / "library.manifest.json"
    manifest_path.unlink()

    with pytest.raises(ValueError, match="unsupported or unclear license"):
        write_library_manifest(
            candidate,
            name="bad-license",
            version="1.0.0",
            instrument="guitar",
            license_evidence_hash=bad_bundle["license_evidence_hash"],
        )

    assert not manifest_path.exists()


def test_manifest_records_guitar_source_mechanics_or_explicit_absence(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    c4 = src / "C4.wav"
    d4 = src / "D4.wav"
    _wav(c4, freq=261.625565)
    _wav(d4, freq=293.664768)
    analyses = [analyze_sample(c4), analyze_sample(d4)]
    candidate = tmp_path / "mechanics"
    copied = copy_samples([c4, d4], candidate / "samples")
    for row, copied_path in zip(analyses, copied):
        row["path"] = str(copied_path)
    write_sfz(build_regions(analyses), candidate / "instrument.sfz")

    ev = make_evidence(
        source="freesound",
        source_id="mechanics-pack",
        source_url="https://freesound.org/s/mechanics-pack/",
        download_url="https://freesound.org/apiv2/sounds/mechanics-pack/download/",
        license_name="CC0",
        license_url="https://creativecommons.org/publicdomain/zero/1.0/",
        fetched_at="2026-06-12T00:00:00+00:00",
    ).to_dict()
    bundle = write_license_bundle([ev], candidate / "LICENSES.json")
    bundle_hash = json.loads(bundle.read_text())["license_evidence_hash"]

    manifest = write_library_manifest(
        candidate,
        name="mechanics-guitar",
        version="1.0.0",
        instrument="guitar",
        license_evidence_hash=bundle_hash,
        license_evidence=[ev],
        sample_mechanics={
            "samples/C4.wav": {
                "string": "A2",
                "fret": 3,
                "tuning": ["E2", "A2", "D3", "G3", "B3", "E4"],
                "session": "pack-a",
            },
        },
    )

    by_sample = {r["sample"]: r["mechanics"] for r in manifest["regions"]}
    assert by_sample["samples/C4.wav"] == {
        "status": "source_proven",
        "string": "A2",
        "fret": 3,
        "tuning": ["E2", "A2", "D3", "G3", "B3", "E4"],
        "session": "pack-a",
    }
    assert by_sample["samples/D4.wav"] == {
        "status": "unavailable",
        "reason": "source_metadata_absent",
    }


def test_manifest_records_unreviewed_loop_candidate_without_emitting_loop(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    c4 = src / "C4.wav"
    _wav(c4, freq=261.625565)
    analysis = analyze_sample(c4)
    assert analysis["loop_candidate"]["status"] == "review_required"

    candidate = tmp_path / "loop-review"
    copied = copy_samples([c4], candidate / "samples")
    analysis["path"] = str(copied[0])
    write_sfz(build_regions([analysis]), candidate / "instrument.sfz")

    ev = make_evidence(
        source="freesound",
        source_id="loop-pack",
        source_url="https://freesound.org/s/loop-pack/",
        download_url="https://freesound.org/apiv2/sounds/loop-pack/download/",
        license_name="CC0",
        license_url="https://creativecommons.org/publicdomain/zero/1.0/",
        fetched_at="2026-06-12T00:00:00+00:00",
    ).to_dict()
    bundle = write_license_bundle([ev], candidate / "LICENSES.json")
    bundle_hash = json.loads(bundle.read_text())["license_evidence_hash"]

    manifest = write_library_manifest(
        candidate,
        name="loop-review-guitar",
        version="1.0.0",
        instrument="guitar",
        license_evidence_hash=bundle_hash,
        license_evidence=[ev],
        sample_loop_candidates={
            "samples/C4.wav": analysis["loop_candidate"],
        },
    )

    region = manifest["regions"][0]
    assert region["loop_mode"] == "no_loop"
    assert region["loop_start"] == 0
    assert region["loop_end"] == 0
    assert region["loop_candidate"] == {
        "status": "review_required",
        "reason": "loop_candidate_not_emitted_without_review",
        "start_sample": analysis["loop_candidate"]["start_sample"],
        "end_sample": analysis["loop_candidate"]["end_sample"],
        "start_s": analysis["loop_candidate"]["start_s"],
        "end_s": analysis["loop_candidate"]["end_s"],
        "confidence": analysis["loop_candidate"]["confidence"],
    }


def test_manifest_rejects_ambiguous_multi_evidence_regions(tmp_path):
    candidate, _ = _candidate_library(tmp_path)
    ev_a = make_evidence(
        source="freesound",
        source_id="1",
        source_url="https://freesound.org/s/1/",
        download_url="https://freesound.org/apiv2/sounds/1/download/",
        license_name="CC0",
        license_url="https://creativecommons.org/publicdomain/zero/1.0/",
        fetched_at="2026-06-12T00:00:00+00:00",
    ).to_dict()
    ev_b = make_evidence(
        source="internet_archive",
        source_id="pd-pack",
        source_url="https://archive.org/details/pd-pack",
        download_url="https://archive.org/download/pd-pack/C4.wav",
        license_name="CC0",
        license_url="https://creativecommons.org/publicdomain/zero/1.0/",
        fetched_at="2026-06-12T00:00:00+00:00",
    ).to_dict()
    bundle = write_license_bundle([ev_a, ev_b], candidate / "LICENSES.json")
    bundle_hash = json.loads(bundle.read_text())["license_evidence_hash"]

    with pytest.raises(ValueError, match="missing source evidence id"):
        write_library_manifest(
            candidate,
            name="ambiguous",
            version="1.0.0",
            instrument="guitar",
            license_evidence_hash=bundle_hash,
            license_evidence=[ev_a, ev_b],
        )


def test_audit_rejects_region_unknown_source_evidence(tmp_path):
    candidate, _ = _candidate_library(tmp_path)
    manifest_path = candidate / "library.manifest.json"
    data = json.loads(manifest_path.read_text())
    data["regions"][0]["source_evidence_id"] = "missing-evidence"
    data["manifest_sha256"] = _canonical_manifest_hash(data)
    manifest_path.write_text(json.dumps(data, indent=1, sort_keys=True) + "\n")

    with pytest.raises(ValueError, match="unknown source evidence"):
        audit_catalog(candidate)


def test_audit_rejects_region_sample_hash_not_matching_manifest_files(tmp_path):
    candidate, _ = _candidate_library(tmp_path)
    manifest_path = candidate / "library.manifest.json"
    data = json.loads(manifest_path.read_text())
    data["regions"][0]["sample_sha256"] = "0" * 64
    data["manifest_sha256"] = _canonical_manifest_hash(data)
    manifest_path.write_text(json.dumps(data, indent=1, sort_keys=True) + "\n")

    with pytest.raises(ValueError, match="sample_sha256 does not match"):
        audit_catalog(candidate)


def test_audit_rejects_region_library_pin_mismatch(tmp_path):
    candidate, _ = _candidate_library(tmp_path)
    manifest_path = candidate / "library.manifest.json"
    data = json.loads(manifest_path.read_text())
    data["regions"][0]["library_pin"]["manifest_sha256"] = "0" * 64
    data["manifest_sha256"] = _canonical_manifest_hash(data)
    manifest_path.write_text(json.dumps(data, indent=1, sort_keys=True) + "\n")

    with pytest.raises(ValueError, match="library_pin does not match manifest"):
        audit_catalog(candidate)


def test_audit_rejects_region_sample_identity_mismatch(tmp_path):
    candidate, _ = _candidate_library(tmp_path)
    manifest_path = candidate / "library.manifest.json"
    data = json.loads(manifest_path.read_text())
    data["regions"][0]["sample_identity"]["byte_size"] = 0
    data["manifest_sha256"] = _canonical_manifest_hash(data)
    attach_region_library_pins(data)
    manifest_path.write_text(json.dumps(data, indent=1, sort_keys=True) + "\n")

    with pytest.raises(ValueError, match="sample_identity does not match"):
        audit_catalog(candidate)


def test_audit_rejects_region_coverage_mismatch(tmp_path):
    candidate, _ = _candidate_library(tmp_path)
    manifest_path = candidate / "library.manifest.json"
    data = json.loads(manifest_path.read_text())
    data["regions"][0]["coverage"]["key_range"] = [0, 127]
    data["manifest_sha256"] = _canonical_manifest_hash(data)
    attach_region_library_pins(data)
    manifest_path.write_text(json.dumps(data, indent=1, sort_keys=True) + "\n")

    with pytest.raises(ValueError, match="coverage does not match manifest"):
        audit_catalog(candidate)


def test_audit_rejects_catalog_diagnostics_mismatch(tmp_path):
    candidate, _ = _candidate_library(tmp_path)
    manifest_path = candidate / "library.manifest.json"
    data = json.loads(manifest_path.read_text())
    data["catalog_diagnostics"]["renderable_count"] = 0
    data["manifest_sha256"] = _canonical_manifest_hash(data)
    attach_region_library_pins(data)
    manifest_path.write_text(json.dumps(data, indent=1, sort_keys=True) + "\n")

    with pytest.raises(ValueError, match="catalog_diagnostics does not match"):
        audit_catalog(candidate)


def test_audit_rejects_guitar_region_missing_mechanics_metadata(tmp_path):
    candidate, _ = _candidate_library(tmp_path)
    manifest_path = candidate / "library.manifest.json"
    data = json.loads(manifest_path.read_text())
    data["regions"][0].pop("mechanics", None)
    data["manifest_sha256"] = _canonical_manifest_hash(data)
    manifest_path.write_text(json.dumps(data, indent=1, sort_keys=True) + "\n")

    with pytest.raises(ValueError, match="missing guitar mechanics metadata"):
        audit_catalog(candidate)


def test_review_promotion_makes_approved_catalog_loadable_in_strict_mode(tmp_path):
    candidate, _ = _candidate_library(tmp_path)
    approved = promote_candidate(
        candidate, tmp_path / "approved", reviewer="qa",
        reviewed_at="2026-06-12T15:00:00+00:00")
    manifest = json.loads((approved / "library.manifest.json").read_text())
    add_library_path(approved.parent)
    lib = load_library({
        "name": manifest["name"],
        "manifest_sha256": manifest["manifest_sha256"],
    }, require_approved=True)
    assert lib.regions("guitar")


def test_approved_catalog_path_helper_resolves_instrument_version_layout(tmp_path):
    candidate, _ = _candidate_library(tmp_path)
    approved_root = tmp_path / "_catalog" / "approved"
    approved = promote_candidate(
        candidate, approved_root, reviewer="qa",
        reviewed_at="2026-06-12T15:00:00+00:00")
    manifest = json.loads((approved / "library.manifest.json").read_text())

    cat = Catalog.build(approved_root)
    assert cat.renderable()

    registered = add_approved_catalog_path(approved_root)
    assert registered == approved_root
    lib = load_library({
        "name": manifest["name"],
        "manifest_sha256": manifest["manifest_sha256"],
    }, require_approved=True)

    assert lib.root == approved
    assert lib.regions("guitar")


def test_strict_loader_rejects_approved_catalog_without_license_bundle(tmp_path):
    candidate, _ = _candidate_library(tmp_path)
    approved = promote_candidate(
        candidate, tmp_path / "approved", reviewer="qa",
        reviewed_at="2026-06-12T15:00:00+00:00")
    manifest = json.loads((approved / "library.manifest.json").read_text())
    (approved / "LICENSES.json").unlink()
    add_library_path(approved.parent)

    with pytest.raises(ValueError, match="missing LICENSES.json"):
        load_library({
            "name": manifest["name"],
            "manifest_sha256": manifest["manifest_sha256"],
        }, require_approved=True)


def test_strict_loader_and_audit_reject_approved_sample_hash_mismatch(tmp_path):
    candidate, _ = _candidate_library(tmp_path)
    approved = promote_candidate(
        candidate, tmp_path / "approved", reviewer="qa",
        reviewed_at="2026-06-12T15:00:00+00:00")
    manifest = json.loads((approved / "library.manifest.json").read_text())
    (approved / "samples" / "C4.wav").write_bytes(b"tampered")
    add_library_path(approved.parent)

    with pytest.raises(ValueError, match="hash mismatch"):
        load_library({
            "name": manifest["name"],
            "manifest_sha256": manifest["manifest_sha256"],
        }, require_approved=True)
    with pytest.raises(ValueError, match="hash mismatch"):
        audit_catalog(approved, require_approved=True)


def test_strict_loader_rejects_approved_region_sample_sha_mismatch(tmp_path):
    candidate, _ = _candidate_library(tmp_path)
    approved = promote_candidate(
        candidate, tmp_path / "approved", reviewer="qa",
        reviewed_at="2026-06-12T15:00:00+00:00")
    manifest_path = approved / "library.manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["regions"][0]["sample_sha256"] = "0" * 64
    manifest["manifest_sha256"] = _canonical_manifest_hash(manifest)
    manifest_path.write_text(json.dumps(manifest, indent=1, sort_keys=True) + "\n")
    add_library_path(approved.parent)

    with pytest.raises(ValueError, match="sample_sha256 does not match"):
        load_library({
            "name": manifest["name"],
            "manifest_sha256": manifest["manifest_sha256"],
        }, require_approved=True)
    with pytest.raises(ValueError, match="sample_sha256 does not match"):
        audit_catalog(approved, require_approved=True)


def test_strict_loader_rejects_approved_region_sample_not_pinned(tmp_path):
    candidate, _ = _candidate_library(tmp_path)
    approved = promote_candidate(
        candidate, tmp_path / "approved", reviewer="qa",
        reviewed_at="2026-06-12T15:00:00+00:00")
    manifest_path = approved / "library.manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["regions"][0]["sample"] = "samples/unpinned.wav"
    manifest["manifest_sha256"] = _canonical_manifest_hash(manifest)
    manifest_path.write_text(json.dumps(manifest, indent=1, sort_keys=True) + "\n")
    add_library_path(approved.parent)

    with pytest.raises(ValueError, match="is not pinned in manifest files"):
        load_library({
            "name": manifest["name"],
            "manifest_sha256": manifest["manifest_sha256"],
        }, require_approved=True)
    with pytest.raises(ValueError, match="is not pinned in manifest files"):
        audit_catalog(approved, require_approved=True)


def test_strict_loader_rejects_approved_catalog_with_unknown_builder_version(tmp_path):
    candidate, _ = _candidate_library(tmp_path)
    approved = promote_candidate(
        candidate, tmp_path / "approved", reviewer="qa",
        reviewed_at="2026-06-12T15:00:00+00:00")
    manifest_path = approved / "library.manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["builder_version"] = "audioforge.sample-catalog/0"
    manifest["manifest_sha256"] = _canonical_manifest_hash(manifest)
    manifest_path.write_text(json.dumps(manifest, indent=1, sort_keys=True) + "\n")
    add_library_path(approved.parent)

    with pytest.raises(ValueError, match="unsupported sample catalog builder version"):
        load_library({
            "name": manifest["name"],
            "manifest_sha256": manifest["manifest_sha256"],
        }, require_approved=True)
    with pytest.raises(ValueError, match="unsupported sample catalog builder version"):
        audit_catalog(approved, require_approved=True)


@pytest.mark.parametrize("review, message", [
    ({}, "review status is not approved"),
    ({"status": "pending", "reviewer": "qa",
      "reviewed_at": "2026-06-12T15:00:00+00:00"},
     "review status is not approved"),
    ({"status": "approved", "reviewer": "",
      "reviewed_at": "2026-06-12T15:00:00+00:00"},
     "review reviewer is required"),
    ({"status": "approved", "reviewer": "qa", "reviewed_at": ""},
     "reviewed_at is required"),
    ({"status": "approved", "reviewer": "qa", "reviewed_at": "not-a-date"},
     "reviewed_at must be ISO-8601"),
    ({"status": "approved", "reviewer": "qa",
      "reviewed_at": "2026-06-12T15:00:00"},
     "reviewed_at must include timezone"),
])
def test_strict_loader_rejects_approved_catalog_without_review_gate_metadata(
        tmp_path, review, message):
    candidate, _ = _candidate_library(tmp_path)
    approved = promote_candidate(
        candidate, tmp_path / "approved", reviewer="qa",
        reviewed_at="2026-06-12T15:00:00+00:00")
    manifest_path = approved / "library.manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["review"] = review
    manifest["manifest_sha256"] = _canonical_manifest_hash(manifest)
    manifest_path.write_text(json.dumps(manifest, indent=1, sort_keys=True) + "\n")
    add_library_path(approved.parent)

    with pytest.raises(ValueError, match=message):
        load_library({
            "name": manifest["name"],
            "manifest_sha256": manifest["manifest_sha256"],
        }, require_approved=True)
    with pytest.raises(ValueError, match=message):
        audit_catalog(approved, require_approved=True)


def test_strict_loader_rejects_approved_guitar_without_mechanics_metadata(tmp_path):
    candidate, _ = _candidate_library(tmp_path)
    approved = promote_candidate(
        candidate, tmp_path / "approved", reviewer="qa",
        reviewed_at="2026-06-12T15:00:00+00:00")
    manifest_path = approved / "library.manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["regions"][0].pop("mechanics", None)
    manifest["manifest_sha256"] = _canonical_manifest_hash(manifest)
    manifest_path.write_text(json.dumps(manifest, indent=1, sort_keys=True) + "\n")
    add_library_path(approved.parent)

    with pytest.raises(ValueError, match="missing guitar mechanics metadata"):
        load_library({
            "name": manifest["name"],
            "manifest_sha256": manifest["manifest_sha256"],
        }, require_approved=True)


def test_strict_loader_rejects_approved_catalog_diagnostics_mismatch(tmp_path):
    candidate, _ = _candidate_library(tmp_path)
    approved = promote_candidate(
        candidate, tmp_path / "approved", reviewer="qa",
        reviewed_at="2026-06-12T15:00:00+00:00")
    manifest_path = approved / "library.manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["catalog_diagnostics"]["blocked_count"] = 1
    manifest["manifest_sha256"] = _canonical_manifest_hash(manifest)
    attach_region_library_pins(manifest)
    manifest_path.write_text(json.dumps(manifest, indent=1, sort_keys=True) + "\n")
    add_library_path(approved.parent)

    with pytest.raises(ValueError, match="catalog_diagnostics does not match"):
        load_library({
            "name": manifest["name"],
            "manifest_sha256": manifest["manifest_sha256"],
        }, require_approved=True)


def test_strict_loader_rejects_approved_catalog_with_bad_evidence_schema(tmp_path):
    candidate, _ = _candidate_library(tmp_path)
    approved = promote_candidate(
        candidate, tmp_path / "approved", reviewer="qa",
        reviewed_at="2026-06-12T15:00:00+00:00")
    bundle_path = approved / "LICENSES.json"
    bundle = json.loads(bundle_path.read_text())
    bad_evidence = dict(bundle["evidence"][0])
    bad_evidence["schema"] = "audioforge.sample-catalog.evidence/0"
    bad_evidence["evidence_hash"] = evidence_hash(bad_evidence)
    bad_bundle = {"schema": bundle["schema"], "evidence": [bad_evidence]}
    bad_bundle["license_evidence_hash"] = evidence_hash(bad_bundle)
    bundle_path.write_text(json.dumps(bad_bundle, indent=2, sort_keys=True) + "\n")

    manifest_path = approved / "library.manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["license_evidence_hash"] = bad_bundle["license_evidence_hash"]
    for region in manifest["regions"]:
        region["source_evidence_id"] = bad_evidence["evidence_hash"]
    manifest["manifest_sha256"] = _canonical_manifest_hash(manifest)
    manifest_path.write_text(json.dumps(manifest, indent=1, sort_keys=True) + "\n")
    add_library_path(approved.parent)

    with pytest.raises(ValueError, match="unsupported license evidence schema"):
        load_library({
            "name": manifest["name"],
            "manifest_sha256": manifest["manifest_sha256"],
        }, require_approved=True)
    with pytest.raises(ValueError, match="unsupported license evidence schema"):
        audit_catalog(approved, require_approved=True)


def test_strict_loader_rejects_approved_catalog_with_mismatched_evidence_hash(tmp_path):
    candidate, _ = _candidate_library(tmp_path)
    approved = promote_candidate(
        candidate, tmp_path / "approved", reviewer="qa",
        reviewed_at="2026-06-12T15:00:00+00:00")
    bundle_path = approved / "LICENSES.json"
    bundle = json.loads(bundle_path.read_text())
    bad_evidence = dict(bundle["evidence"][0])
    original_evidence_hash = bad_evidence["evidence_hash"]
    bad_evidence["creator"] = "tampered creator"
    bad_bundle = {"schema": bundle["schema"], "evidence": [bad_evidence]}
    bad_bundle["license_evidence_hash"] = evidence_hash(bad_bundle)
    bundle_path.write_text(json.dumps(bad_bundle, indent=2, sort_keys=True) + "\n")

    manifest_path = approved / "library.manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["license_evidence_hash"] = bad_bundle["license_evidence_hash"]
    for region in manifest["regions"]:
        region["source_evidence_id"] = original_evidence_hash
    manifest["manifest_sha256"] = _canonical_manifest_hash(manifest)
    manifest_path.write_text(json.dumps(manifest, indent=1, sort_keys=True) + "\n")
    add_library_path(approved.parent)

    with pytest.raises(ValueError, match="license evidence hash mismatch"):
        load_library({
            "name": manifest["name"],
            "manifest_sha256": manifest["manifest_sha256"],
        }, require_approved=True)
    with pytest.raises(ValueError, match="license evidence hash mismatch"):
        audit_catalog(approved, require_approved=True)


def test_strict_loader_rejects_approved_catalog_with_unsupported_license(tmp_path):
    candidate, _ = _candidate_library(tmp_path)
    approved = promote_candidate(
        candidate, tmp_path / "approved", reviewer="qa",
        reviewed_at="2026-06-12T15:00:00+00:00")
    bad_evidence = make_evidence(
        source="freesound",
        source_id="2",
        source_url="https://freesound.org/s/2/",
        download_url="https://freesound.org/apiv2/sounds/2/download/",
        license_name="CC-BY",
        license_url="https://creativecommons.org/licenses/by/4.0/",
        fetched_at="2026-06-12T00:00:00+00:00",
    ).to_dict()
    bad_bundle = {
        "schema": "audioforge.sample-catalog.licenses/1",
        "evidence": [bad_evidence],
    }
    bad_bundle["license_evidence_hash"] = evidence_hash({
        "schema": bad_bundle["schema"],
        "evidence": bad_bundle["evidence"],
    })
    (approved / "LICENSES.json").write_text(
        json.dumps(bad_bundle, indent=2, sort_keys=True) + "\n")
    manifest_path = approved / "library.manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["license_evidence_hash"] = bad_bundle["license_evidence_hash"]
    for region in manifest["regions"]:
        region["source_evidence_id"] = bad_evidence["evidence_hash"]
    manifest["manifest_sha256"] = _canonical_manifest_hash(manifest)
    manifest_path.write_text(json.dumps(manifest, indent=1, sort_keys=True) + "\n")
    add_library_path(approved.parent)

    with pytest.raises(ValueError, match="unsupported or unclear license"):
        load_library({
            "name": manifest["name"],
            "manifest_sha256": manifest["manifest_sha256"],
        }, require_approved=True)


def test_strict_loader_rejects_approved_catalog_with_openverse_evidence(tmp_path):
    candidate, _ = _candidate_library(tmp_path)
    approved = promote_candidate(
        candidate, tmp_path / "approved", reviewer="qa",
        reviewed_at="2026-06-12T15:00:00+00:00")
    bad_evidence = make_evidence(
        source="openverse_discovery",
        source_id="ov-1",
        source_url="https://example.test/source",
        download_url="https://example.test/C4.wav",
        license_name="CC0",
        license_url="https://creativecommons.org/publicdomain/zero/1.0/",
        rights_text="Openverse discovery lead; verify upstream before download",
        fetched_at="2026-06-12T00:00:00+00:00",
    ).to_dict()
    bundle = {
        "schema": "audioforge.sample-catalog.licenses/1",
        "evidence": [bad_evidence],
    }
    bundle["license_evidence_hash"] = evidence_hash({
        "schema": bundle["schema"],
        "evidence": bundle["evidence"],
    })
    (approved / "LICENSES.json").write_text(
        json.dumps(bundle, indent=2, sort_keys=True) + "\n")
    manifest_path = approved / "library.manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["license_evidence_hash"] = bundle["license_evidence_hash"]
    for region in manifest["regions"]:
        region["source_evidence_id"] = bad_evidence["evidence_hash"]
    manifest["manifest_sha256"] = _canonical_manifest_hash(manifest)
    manifest_path.write_text(json.dumps(manifest, indent=1, sort_keys=True) + "\n")
    add_library_path(approved.parent)

    with pytest.raises(ValueError, match="upstream verification"):
        load_library({
            "name": manifest["name"],
            "manifest_sha256": manifest["manifest_sha256"],
        }, require_approved=True)
    with pytest.raises(ValueError, match="upstream verification"):
        audit_catalog(approved, require_approved=True)
