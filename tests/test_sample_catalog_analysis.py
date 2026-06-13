import json
import math
import wave

import numpy as np

from audioforge.sample_catalog.analyze import (
    AnalysisConfig,
    analyze_downloads,
    analyze_sample,
    validate_analysis_record_schema,
)
from audioforge.sample_catalog.constants import ANALYSIS_SCHEMA
from audioforge.sample_catalog.licenses import evidence_hash, make_evidence


def _write_wav(path, x, *, sr=44100):
    pcm = np.clip(x, -1, 1)
    data = (pcm * 32767).astype("<i2").tobytes()
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(data)


def _write_wav_8bit(path, x, *, sr=44100):
    pcm = np.clip((x + 1.0) * 127.5, 0, 255).astype("u1")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(1)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())


def _wav(path, *, freq=440.0, amp=0.3, sr=44100, dur=0.25):
    t = np.arange(int(sr * dur)) / sr
    x = np.sin(2 * math.pi * freq * t) * amp
    _write_wav(path, x, sr=sr)


def test_analyze_sample_accepts_clean_pitched_wav(tmp_path):
    wav = tmp_path / "A4.wav"
    _wav(wav)
    result = analyze_sample(wav)
    assert result["schema"] == ANALYSIS_SCHEMA
    assert result["status"] == "accepted"
    assert result["sample_rate"] == 44100
    assert result["bit_depth"] == 16
    assert result["lufs_approx"] < result["rms_dbfs"]
    assert result["midi_note"] == 69
    assert result["pitch_confidence"] >= 0.25
    assert result["attack_time_s"] is not None
    assert result["release_time_s"] is not None
    assert result["sustain_rms_dbfs"] is not None
    assert result["spectral_centroid_hz"] is not None
    assert result["spectral_bandwidth_hz"] is not None
    assert result["transient_count"] == 1
    assert result["loop_candidate"]["status"] == "review_required"


def test_analyze_sample_quarantines_silence_and_clipping(tmp_path):
    silent = tmp_path / "silent.wav"
    _wav(silent, amp=0.0)
    result = analyze_sample(silent)
    assert result["status"] == "quarantine"
    assert "silence_or_near_silence" in result["rejection_reasons"]

    clipped = tmp_path / "clip.wav"
    _wav(clipped, amp=1.0)
    result = analyze_sample(
        clipped, AnalysisConfig(clipping_peak=0.99, min_pitch_confidence=0.0))
    assert "clipping" in result["rejection_reasons"]


def test_analyze_sample_quarantines_multiple_note_events(tmp_path):
    sr = 44100
    x = np.zeros(int(sr * 0.8))
    tone = np.sin(2 * math.pi * 440.0 * np.arange(int(sr * 0.06)) / sr) * 0.35
    for start_s in (0.05, 0.18, 0.31, 0.44, 0.57):
        start = int(sr * start_s)
        x[start:start + tone.size] += tone
    wav = tmp_path / "bursts.wav"
    _write_wav(wav, x, sr=sr)

    result = analyze_sample(wav, AnalysisConfig(min_pitch_confidence=0.0))

    assert result["status"] == "quarantine"
    assert result["transient_count"] > 3
    assert "multiple_unrelated_events" in result["rejection_reasons"]


def test_analyze_sample_quarantines_broadband_noise_floor(tmp_path):
    rng = np.random.default_rng(1234)
    x = rng.normal(0.0, 0.15, int(44100 * 0.35))
    wav = tmp_path / "noise.wav"
    _write_wav(wav, x)

    result = analyze_sample(wav)

    assert result["status"] == "quarantine"
    assert result["noise_floor_dbfs"] > -35.0
    assert result["spectral_flatness"] > 0.35
    assert "excessive_noise_floor" in result["rejection_reasons"]


def test_analyze_sample_quarantines_bit_depth_below_minimum(tmp_path):
    sr = 44100
    t = np.arange(int(sr * 0.25)) / sr
    x = np.sin(2 * math.pi * 440.0 * t) * 0.3
    wav = tmp_path / "A4_8bit.wav"
    _write_wav_8bit(wav, x, sr=sr)

    result = analyze_sample(
        wav, AnalysisConfig(min_bit_depth=16, min_pitch_confidence=0.0))

    assert result["schema"] == ANALYSIS_SCHEMA
    assert result["status"] == "quarantine"
    assert result["bit_depth"] == 8
    assert "bit_depth_below_minimum" in result["rejection_reasons"]


def test_analyze_sample_quarantines_sample_rate_below_minimum(tmp_path):
    wav = tmp_path / "A4_low_sample_rate.wav"
    _wav(wav, sr=16000)

    result = analyze_sample(
        wav, AnalysisConfig(min_sample_rate=44100, min_pitch_confidence=0.0))

    assert result["schema"] == ANALYSIS_SCHEMA
    assert result["status"] == "quarantine"
    assert result["sample_rate"] == 16000
    assert "sample_rate_below_minimum" in result["rejection_reasons"]


def test_analyze_sample_quarantines_duration_outside_bounds(tmp_path):
    short = tmp_path / "A4_too_short.wav"
    _wav(short, dur=0.04)

    result = analyze_sample(
        short, AnalysisConfig(min_duration_s=0.08, min_pitch_confidence=0.0))

    assert result["schema"] == ANALYSIS_SCHEMA
    assert result["status"] == "quarantine"
    assert result["duration_s"] == 0.04
    assert "duration_too_short" in result["rejection_reasons"]

    long = tmp_path / "A4_too_long.wav"
    _wav(long, dur=0.25)

    result = analyze_sample(
        long, AnalysisConfig(max_duration_s=0.08, min_pitch_confidence=0.0))

    assert result["schema"] == ANALYSIS_SCHEMA
    assert result["status"] == "quarantine"
    assert result["duration_s"] == 0.25
    assert "duration_too_long" in result["rejection_reasons"]


def test_analyze_sample_uses_stable_decode_failure_reason(tmp_path):
    bad = tmp_path / "bad.wav"
    bad.write_bytes(b"not a wav")

    result = analyze_sample(bad)

    assert result["status"] == "quarantine"
    assert result["rejection_reasons"] == ["decode_failed"]
    assert result["decode_error_type"]


def test_validate_analysis_record_schema_rejects_unknown_schema():
    try:
        validate_analysis_record_schema({
            "schema": "audioforge.sample-catalog.analysis/0"
        })
    except ValueError as e:
        assert "unsupported sample catalog analysis schema" in str(e)
    else:
        raise AssertionError("unknown sample-catalog analysis schema was accepted")


def test_analyze_downloads_preserves_license_evidence_and_source_metadata(tmp_path):
    wav = tmp_path / "A4.wav"
    _wav(wav)
    evidence = make_evidence(
        source="freesound",
        source_id="1",
        source_url="https://freesound.org/s/1/",
        download_url="https://freesound.org/apiv2/sounds/1/download/",
        license_name="CC0",
        license_url="https://creativecommons.org/publicdomain/zero/1.0/",
        fetched_at="2026-06-12T00:00:00+00:00",
    ).to_dict()
    downloads = [{
        "path": str(wav),
        "candidate": {
            "source": "freesound",
            "source_id": "1",
            "source_url": "https://freesound.org/s/1/",
            "descriptors": {
                "source_context": {
                    "status": "manual_review_required",
                    "reason": "internet_archive_context_not_sample_pack_isolated_note_or_institutional",
                },
            },
            "raw_metadata": {"pack": "clean-guitar"},
            "evidence": evidence,
        },
    }]

    records = analyze_downloads(downloads, tmp_path / "analysis")

    record = records[0]
    assert record["license_evidence"]["evidence_hash"] == evidence["evidence_hash"]
    assert record["source_evidence_id"] == evidence["evidence_hash"]
    assert record["source_descriptors"]["source_context"]["status"] == (
        "manual_review_required"
    )
    assert record["source_raw_metadata"] == {"pack": "clean-guitar"}
    written = json.loads(next((tmp_path / "analysis").glob("*.json")).read_text())
    assert written["license_evidence"] == record["license_evidence"]
    assert written["source_descriptors"] == record["source_descriptors"]
    assert written["source_raw_metadata"] == {"pack": "clean-guitar"}


def test_analyze_downloads_quarantines_accepted_audio_without_license_evidence(tmp_path):
    wav = tmp_path / "A4.wav"
    _wav(wav)

    records = analyze_downloads([{
        "path": str(wav),
        "candidate": {
            "source": "freesound",
            "source_id": "1",
            "source_url": "https://freesound.org/s/1/",
        },
    }], tmp_path / "analysis")

    record = records[0]
    assert record["midi_note"] == 69
    assert record["status"] == "quarantine"
    assert "missing_license_evidence" in record["rejection_reasons"]
    assert "source_evidence_id" not in record


def test_analyze_downloads_rejects_forged_license_evidence_before_write(tmp_path):
    wav = tmp_path / "A4.wav"
    _wav(wav)
    evidence = make_evidence(
        source="freesound",
        source_id="1",
        source_url="https://freesound.org/s/1/",
        download_url="https://freesound.org/apiv2/sounds/1/download/",
        license_name="CC0",
        license_url="https://creativecommons.org/publicdomain/zero/1.0/",
        fetched_at="2026-06-12T00:00:00+00:00",
    ).to_dict()
    evidence["creator"] = "tampered creator"

    try:
        analyze_downloads([{
            "path": str(wav),
            "candidate": {
                "source": "freesound",
                "source_id": "1",
                "source_url": "https://freesound.org/s/1/",
                "evidence": evidence,
            },
        }], tmp_path / "analysis")
    except ValueError as e:
        assert "license evidence hash mismatch" in str(e)
    else:
        raise AssertionError("forged license evidence was accepted")

    assert not list((tmp_path / "analysis").glob("*.json"))


def test_analyze_downloads_rejects_unknown_evidence_schema_before_write(tmp_path):
    wav = tmp_path / "A4.wav"
    _wav(wav)
    evidence = make_evidence(
        source="freesound",
        source_id="1",
        source_url="https://freesound.org/s/1/",
        download_url="https://freesound.org/apiv2/sounds/1/download/",
        license_name="CC0",
        license_url="https://creativecommons.org/publicdomain/zero/1.0/",
        fetched_at="2026-06-12T00:00:00+00:00",
    ).to_dict()
    evidence["schema"] = "audioforge.sample-catalog.evidence/0"
    evidence["evidence_hash"] = evidence_hash(evidence)

    try:
        analyze_downloads([{
            "path": str(wav),
            "candidate": {
                "source": "freesound",
                "source_id": "1",
                "source_url": "https://freesound.org/s/1/",
                "evidence": evidence,
            },
        }], tmp_path / "analysis")
    except ValueError as e:
        assert "unsupported license evidence schema" in str(e)
    else:
        raise AssertionError("unknown license evidence schema was accepted")

    assert not list((tmp_path / "analysis").glob("*.json"))


def test_analyze_downloads_rejects_openverse_discovery_evidence_before_write(tmp_path):
    wav = tmp_path / "A4.wav"
    _wav(wav)
    evidence = make_evidence(
        source="openverse_discovery",
        source_id="lead-1",
        source_url="https://openverse.engineering/audio/lead-1",
        download_url="https://example.test/audio.wav",
        license_name="CC0",
        license_url="https://creativecommons.org/publicdomain/zero/1.0/",
        rights_text="Openverse discovery lead; verify upstream before download",
        fetched_at="2026-06-12T00:00:00+00:00",
    ).to_dict()

    try:
        analyze_downloads([{
            "path": str(wav),
            "candidate": {
                "source": "openverse_discovery",
                "source_id": "lead-1",
                "source_url": "https://openverse.engineering/audio/lead-1",
                "evidence": evidence,
            },
        }], tmp_path / "analysis")
    except ValueError as e:
        assert "openverse discovery evidence requires upstream verification" in str(e)
    else:
        raise AssertionError("openverse discovery evidence was accepted")

    assert not list((tmp_path / "analysis").glob("*.json"))


def test_analyze_downloads_rejects_unsupported_license_evidence_before_write(
        tmp_path):
    wav = tmp_path / "A4.wav"
    _wav(wav)
    evidence = make_evidence(
        source="freesound",
        source_id="2",
        source_url="https://freesound.org/s/2/",
        download_url="https://freesound.org/apiv2/sounds/2/download/",
        license_name="CC-BY",
        license_url="https://creativecommons.org/licenses/by/4.0/",
        fetched_at="2026-06-12T00:00:00+00:00",
    ).to_dict()

    try:
        analyze_downloads([{
            "path": str(wav),
            "candidate": {
                "source": "freesound",
                "source_id": "2",
                "source_url": "https://freesound.org/s/2/",
                "evidence": evidence,
            },
        }], tmp_path / "analysis")
    except ValueError as e:
        assert "unsupported or unclear license evidence" in str(e)
    else:
        raise AssertionError("unsupported license evidence was accepted")

    assert not list((tmp_path / "analysis").glob("*.json"))


def test_analyze_downloads_rejects_download_sha256_mismatch_before_write(
        tmp_path):
    wav = tmp_path / "A4.wav"
    _wav(wav)
    evidence = make_evidence(
        source="freesound",
        source_id="1",
        source_url="https://freesound.org/s/1/",
        download_url="https://freesound.org/apiv2/sounds/1/download/",
        license_name="CC0",
        license_url="https://creativecommons.org/publicdomain/zero/1.0/",
        fetched_at="2026-06-12T00:00:00+00:00",
    ).to_dict()

    try:
        analyze_downloads([{
            "path": str(wav),
            "sha256": "0" * 64,
            "candidate": {
                "source": "freesound",
                "source_id": "1",
                "source_url": "https://freesound.org/s/1/",
                "evidence": evidence,
            },
        }], tmp_path / "analysis")
    except ValueError as e:
        assert "sample-catalog downloads: sha256 mismatch" in str(e)
    else:
        raise AssertionError("stale download sha256 was accepted")

    assert not list((tmp_path / "analysis").glob("*.json"))


def test_analyze_downloads_rejects_candidate_evidence_source_mismatch(tmp_path):
    wav = tmp_path / "A4.wav"
    _wav(wav)
    evidence = make_evidence(
        source="freesound",
        source_id="1",
        source_url="https://freesound.org/s/1/",
        download_url="https://freesound.org/apiv2/sounds/1/download/",
        license_name="CC0",
        license_url="https://creativecommons.org/publicdomain/zero/1.0/",
        fetched_at="2026-06-12T00:00:00+00:00",
    ).to_dict()

    try:
        analyze_downloads([{
            "path": str(wav),
            "candidate": {
                "source": "freesound",
                "source_id": "1",
                "source_url": "https://freesound.org/s/tampered/",
                "evidence": evidence,
            },
        }], tmp_path / "analysis")
    except ValueError as e:
        assert "candidate evidence mismatch: source_url" in str(e)
    else:
        raise AssertionError("candidate/evidence source mismatch was accepted")

    assert not list((tmp_path / "analysis").glob("*.json"))


def test_analyze_downloads_rejects_malformed_download_record(tmp_path):
    try:
        analyze_downloads([{"sha256": "a" * 64}], tmp_path / "analysis")
    except ValueError as e:
        assert "sample-catalog downloads: record 0 missing path" in str(e)
    else:
        raise AssertionError("malformed download record was accepted")
