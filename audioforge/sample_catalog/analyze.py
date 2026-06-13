from __future__ import annotations

import hashlib
import math
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from audioforge.library import _decode_wav_bytes
from audioforge.sample_catalog.constants import ANALYSIS_SCHEMA
from audioforge.sample_catalog.licenses import (
    decide_license,
    validate_evidence_schema,
    validate_evidence_hash,
    validate_final_evidence_source,
)


@dataclass(frozen=True)
class AnalysisConfig:
    min_duration_s: float = 0.08
    max_duration_s: float = 12.0
    min_sample_rate: int = 22050
    min_bit_depth: int = 16
    silence_rms_dbfs: float = -60.0
    clipping_peak: float = 0.999
    min_pitch_confidence: float = 0.25
    max_transients: int = 3
    excessive_noise_floor_dbfs: float = -35.0
    min_loop_duration_s: float = 0.18


def _db(value: float) -> float:
    return 20.0 * math.log10(max(float(value), 1e-12))


def _wav_metadata(path: Path) -> tuple[int | None, int | None]:
    if path.suffix.lower() != ".wav":
        return None, None
    try:
        with wave.open(str(path)) as w:
            return w.getsampwidth() * 8, w.getnchannels()
    except Exception:
        return None, None


def _pitch_fft(x: np.ndarray, sr: int) -> tuple[float | None, float]:
    if x.size < 32:
        return None, 0.0
    n = min(x.size, sr * 2)
    y = x[:n] * np.hanning(n)
    spec = np.abs(np.fft.rfft(y))
    if spec.size < 3:
        return None, 0.0
    freqs = np.fft.rfftfreq(n, 1 / sr)
    lo = np.searchsorted(freqs, 40.0)
    hi = np.searchsorted(freqs, 5000.0)
    if hi <= lo:
        return None, 0.0
    band = spec[lo:hi]
    idx = int(np.argmax(band)) + lo
    total = float(np.sum(band))
    if total <= 1e-12:
        return None, 0.0
    return float(freqs[idx]), float(spec[idx] / total)


def _midi(freq: float | None) -> tuple[int | None, float | None]:
    if not freq or freq <= 0:
        return None, None
    midi = 69 + 12 * math.log2(freq / 440.0)
    rounded = int(round(midi))
    cents = (midi - rounded) * 100.0
    return rounded, cents


def _frames(x: np.ndarray, frame: int, hop: int) -> np.ndarray:
    if x.size == 0:
        return np.empty((0, frame), dtype=np.float64)
    if x.size < frame:
        padded = np.pad(x, (0, frame - x.size))
        return padded.reshape(1, frame)
    starts = np.arange(0, x.size - frame + 1, hop)
    return np.stack([x[start:start + frame] for start in starts])


def _lufs_approx(rms: float) -> float:
    return _db(rms) - 0.691


def _envelope_features(x: np.ndarray, sr: int) -> dict[str, Any]:
    if x.size == 0 or sr <= 0:
        return {
            "attack_time_s": None,
            "decay_time_s": None,
            "release_time_s": None,
            "sustain_rms_dbfs": None,
            "transient_count": 0,
            "noise_floor_dbfs": -240.0,
        }
    frame = max(128, int(sr * 0.023))
    hop = max(32, int(sr * 0.006))
    fr = _frames(np.abs(x), frame, hop)
    rms = np.sqrt(np.mean(fr ** 2, axis=1)) if fr.size else np.array([])
    if rms.size == 0:
        return {
            "attack_time_s": None,
            "decay_time_s": None,
            "release_time_s": None,
            "sustain_rms_dbfs": None,
            "transient_count": 0,
            "noise_floor_dbfs": -240.0,
        }
    floor = float(np.percentile(rms, 10))
    peak = float(np.max(np.abs(x)))
    if peak <= 1e-12:
        return {
            "attack_time_s": None,
            "decay_time_s": None,
            "release_time_s": None,
            "sustain_rms_dbfs": None,
            "transient_count": 0,
            "noise_floor_dbfs": _db(floor),
        }

    over = np.flatnonzero(np.abs(x) >= peak * 0.9)
    attack = float(over[0] / sr) if over.size else None

    active_threshold = max(floor * 3.0, float(np.max(rms)) * 0.2, 1e-8)
    active = rms >= active_threshold
    min_gap = max(1, int(0.04 * sr / hop))
    count = 0
    last = -min_gap
    was_active = False
    for idx, is_active in enumerate(active):
        if not is_active:
            was_active = False
            continue
        if not was_active and idx - last >= min_gap:
            count += 1
            last = idx
        was_active = True

    rms_peak = float(np.max(rms))
    peak_idx = int(np.argmax(rms))
    decay_threshold = max(floor, rms_peak * 0.7)
    decay_time = None
    after_peak = np.flatnonzero(rms[peak_idx:] <= decay_threshold)
    if after_peak.size:
        decay_time = float((peak_idx + int(after_peak[0])) * hop / sr)
    active_indices = np.flatnonzero(active)
    release_time = (
        float(active_indices[-1] * hop / sr)
        if active_indices.size else float((x.size - 1) / sr)
    )
    sustain_slice = rms[max(0, int(rms.size * 0.35)):max(1, int(rms.size * 0.8))]
    sustain = float(np.median(sustain_slice)) if sustain_slice.size else floor
    return {
        "attack_time_s": attack,
        "decay_time_s": decay_time,
        "release_time_s": release_time,
        "sustain_rms_dbfs": _db(sustain),
        "transient_count": max(1, count),
        "noise_floor_dbfs": _db(floor),
    }


def _spectral_features(x: np.ndarray, sr: int) -> tuple[float | None, float | None, float]:
    if x.size < 32 or sr <= 0:
        return None, None, 0.0
    n = min(x.size, sr * 2)
    y = x[:n] * np.hanning(n)
    mag = np.abs(np.fft.rfft(y))
    freqs = np.fft.rfftfreq(n, 1 / sr)
    mag = mag[1:]
    freqs = freqs[1:]
    total = float(np.sum(mag))
    if total <= 1e-12:
        return None, None, 0.0
    centroid = float(np.sum(freqs * mag) / total)
    bandwidth = float(np.sqrt(np.sum(((freqs - centroid) ** 2) * mag) / total))
    positive = mag[mag > 1e-12]
    if positive.size == 0:
        return centroid, bandwidth, 0.0
    flatness = float(np.exp(np.mean(np.log(positive))) / max(np.mean(positive), 1e-12))
    return centroid, bandwidth, flatness


def _loop_candidate(x: np.ndarray, sr: int, freq: float | None,
                    confidence: float, config: AnalysisConfig) -> dict[str, Any] | None:
    if x.size == 0 or sr <= 0 or not freq or confidence < config.min_pitch_confidence:
        return None
    duration = x.size / sr
    if duration < config.min_loop_duration_s:
        return None
    period = max(16, int(round(sr / freq)))
    window = min(int(sr * 0.06), max(period * 4, 64), x.size // 4)
    if window < 32:
        return None
    start = max(0, int(x.size * 0.35))
    end = min(x.size, int(x.size * 0.75))
    if end - start < window * 2:
        return None
    a = x[start:start + window]
    b = x[end - window:end]
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    corr = 0.0 if denom <= 1e-12 else float(np.dot(a, b) / denom)
    confidence_score = max(0.0, min(1.0, (corr + 1.0) / 2.0))
    return {
        "start_sample": start,
        "end_sample": end,
        "start_s": round(start / sr, 6),
        "end_s": round(end / sr, 6),
        "confidence": round(confidence_score, 6),
        "status": "review_required",
    }


def validate_analysis_record_schema(record: dict[str, Any]) -> None:
    schema = record.get("schema", ANALYSIS_SCHEMA)
    if schema != ANALYSIS_SCHEMA:
        raise ValueError(f"unsupported sample catalog analysis schema: {schema!r}")


def _candidate_evidence(candidate: dict[str, Any]) -> dict[str, Any]:
    evidence = candidate.get("evidence")
    return evidence if isinstance(evidence, dict) else {}


def _require_candidate_evidence_consistency(candidate: dict[str, Any],
                                            evidence: dict[str, Any]) -> None:
    for field in ("source", "source_id", "source_url", "download_url"):
        if field not in candidate or candidate.get(field) is None:
            continue
        candidate_value = str(candidate.get(field) or "").strip()
        evidence_value = str(evidence.get(field) or "").strip()
        if candidate_value != evidence_value:
            source = candidate.get("source", evidence.get("source", "unknown"))
            source_id = candidate.get(
                "source_id", evidence.get("source_id", "unknown"))
            raise ValueError(
                f"candidate evidence mismatch: {field} "
                f"for {source}:{source_id}")


def _require_supported_license_evidence(evidence: dict[str, Any]) -> None:
    decision = decide_license(
        license_name=evidence.get("license_name", ""),
        license_url=evidence.get("license_url", ""),
        rights_text=evidence.get("rights_text", ""),
        source_url=evidence.get("source_url", ""),
        source_id=evidence.get("source_id", ""),
    )
    if not decision.accepted:
        raise ValueError(
            "unsupported or unclear license evidence "
            f"{evidence.get('evidence_hash', '')}")


def _verify_download_record_hash(item: dict[str, Any],
                                 record: dict[str, Any],
                                 idx: int) -> None:
    expected = str(item.get("sha256") or "").strip().lower()
    if not expected:
        return
    actual = str(record.get("sha256") or "").strip().lower()
    if actual != expected:
        raise ValueError(
            "sample-catalog downloads: sha256 mismatch for "
            f"record {idx}: expected {expected}, got {actual}")


def analyze_sample(path: str | Path,
                   config: AnalysisConfig = AnalysisConfig()) -> dict[str, Any]:
    path = Path(path)
    data = path.read_bytes()
    sha = hashlib.sha256(data).hexdigest()
    ext = path.suffix.lower().lstrip(".")
    reasons: list[str] = []
    try:
        x, sr = _decode_wav_bytes(data, ext)
    except Exception as e:
        bit_depth, channels = _wav_metadata(path)
        reasons = ["decode_failed"]
        if bit_depth is not None and bit_depth < config.min_bit_depth:
            reasons.append("bit_depth_below_minimum")
        return {
            "schema": ANALYSIS_SCHEMA,
            "path": str(path),
            "sha256": sha,
            "format": ext,
            "byte_size": len(data),
            "bit_depth": bit_depth,
            "channels": channels,
            "decode_error_type": type(e).__name__,
            "status": "quarantine",
            "rejection_reasons": reasons,
        }

    duration = float(x.size / sr) if sr else 0.0
    peak = float(np.max(np.abs(x))) if x.size else 0.0
    rms = float(np.sqrt(np.mean(x ** 2))) if x.size else 0.0
    freq, confidence = _pitch_fft(x, sr)
    midi_note, cents = _midi(freq)
    envelope = _envelope_features(x, sr)
    centroid, bandwidth, flatness = _spectral_features(x, sr)
    loop = _loop_candidate(x, sr, freq, confidence, config)
    bit_depth, channels = _wav_metadata(path)

    if sr < config.min_sample_rate:
        reasons.append("sample_rate_below_minimum")
    if bit_depth is not None and bit_depth < config.min_bit_depth:
        reasons.append("bit_depth_below_minimum")
    if duration < config.min_duration_s:
        reasons.append("duration_too_short")
    if duration > config.max_duration_s:
        reasons.append("duration_too_long")
    if _db(rms) <= config.silence_rms_dbfs:
        reasons.append("silence_or_near_silence")
    if peak >= config.clipping_peak:
        reasons.append("clipping")
    if midi_note is None or confidence < config.min_pitch_confidence:
        reasons.append("pitch_confidence_below_threshold")
    if envelope["transient_count"] > config.max_transients:
        reasons.append("multiple_unrelated_events")
    if (envelope["noise_floor_dbfs"] > config.excessive_noise_floor_dbfs
            and flatness > 0.35
            and (bandwidth is not None and bandwidth > sr * 0.12)
            and confidence < config.min_pitch_confidence):
        reasons.append("excessive_noise_floor")

    return {
        "schema": ANALYSIS_SCHEMA,
        "path": str(path),
        "sha256": sha,
        "format": ext,
        "byte_size": len(data),
        "sample_rate": sr,
        "bit_depth": bit_depth,
        "channels": channels or 1,
        "duration_s": round(duration, 6),
        "peak": peak,
        "peak_dbfs": round(_db(peak), 3),
        "rms_dbfs": round(_db(rms), 3),
        "lufs_approx": round(_lufs_approx(rms), 3),
        "noise_floor_dbfs": round(envelope["noise_floor_dbfs"], 3),
        "estimated_pitch_hz": round(freq, 6) if freq else None,
        "midi_note": midi_note,
        "cents_offset": round(cents, 3) if cents is not None else None,
        "pitch_confidence": round(confidence, 6),
        "attack_time_s": round(envelope["attack_time_s"], 6)
        if envelope["attack_time_s"] is not None else None,
        "decay_time_s": round(envelope["decay_time_s"], 6)
        if envelope["decay_time_s"] is not None else None,
        "release_time_s": round(envelope["release_time_s"], 6)
        if envelope["release_time_s"] is not None else None,
        "sustain_rms_dbfs": round(envelope["sustain_rms_dbfs"], 3)
        if envelope["sustain_rms_dbfs"] is not None else None,
        "transient_count": envelope["transient_count"],
        "spectral_centroid_hz": round(centroid, 6) if centroid is not None else None,
        "spectral_bandwidth_hz": round(bandwidth, 6) if bandwidth is not None else None,
        "spectral_flatness": round(flatness, 6),
        "loop_candidate": loop,
        "quality_score": max(0.0, 1.0 - 0.15 * len(reasons)),
        "status": "accepted" if not reasons else "quarantine",
        "rejection_reasons": reasons,
    }


def analyze_downloads(downloads: list[dict[str, Any]], out_dir: str | Path) -> list[dict[str, Any]]:
    root = Path(out_dir)
    root.mkdir(parents=True, exist_ok=True)
    if not downloads:
        raise ValueError("sample-catalog downloads: no download records found")
    out = []
    for idx, item in enumerate(downloads):
        path = item.get("path")
        if not path:
            raise ValueError(
                f"sample-catalog downloads: record {idx} missing path")
        record = analyze_sample(path)
        _verify_download_record_hash(item, record, idx)
        candidate = item.get("candidate") or {}
        evidence = _candidate_evidence(candidate)
        if evidence.get("evidence_hash"):
            validate_evidence_schema(evidence)
            validate_evidence_hash(evidence)
            validate_final_evidence_source(evidence)
            _require_supported_license_evidence(evidence)
            _require_candidate_evidence_consistency(candidate, evidence)
            record.update({
                "source": candidate.get("source"),
                "source_id": candidate.get("source_id"),
                "source_url": candidate.get("source_url"),
                "source_evidence_id": evidence["evidence_hash"],
                "license_evidence": evidence,
                "license_name": evidence.get("license_name"),
                "license_url": evidence.get("license_url"),
                "source_descriptors": candidate.get("descriptors", {}),
                "source_raw_metadata": candidate.get("raw_metadata", {}),
            })
        else:
            reasons = list(record.get("rejection_reasons", []))
            if "missing_license_evidence" not in reasons:
                reasons.append("missing_license_evidence")
            record["rejection_reasons"] = reasons
            record["status"] = "quarantine"
        path = root / f"{record['sha256']}.json"
        import json
        path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
        out.append(record)
    return out
