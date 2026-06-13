from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from .licenses import (
    canonical_json,
    decide_license,
    validate_evidence_schema,
    validate_evidence_hash,
    validate_final_evidence_source,
)
from .sources import Candidate

SUPPORTED_DOWNLOAD_AUDIO_EXTS = frozenset({
    "wav", "aiff", "aif", "flac", "ogg", "oga", "mp3",
})


class BytesHttpClient(Protocol):
    def get_bytes(self, url: str, *, headers: dict[str, str] | None = None) -> bytes:
        ...


@dataclass(frozen=True)
class DownloadResult:
    sha256: str
    path: str
    evidence_path: str
    size: int
    candidate: dict[str, Any]
    reused: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "sha256": self.sha256,
            "path": self.path,
            "evidence_path": self.evidence_path,
            "size": self.size,
            "candidate": self.candidate,
            "reused": self.reused,
        }


def _ext(filename: str, url: str) -> str:
    name = (filename or url).split("?", 1)[0].rsplit("/", 1)[-1]
    if "." not in name:
        return "bin"
    return name.rsplit(".", 1)[-1].lower()


def _require_supported_audio_ext(candidate: Candidate, ext: str) -> None:
    if ext not in SUPPORTED_DOWNLOAD_AUDIO_EXTS:
        raise ValueError(
            f"candidate {candidate.source}:{candidate.source_id} has "
            f"unsupported audio extension {ext!r}")


def _has_bearer_token(headers: dict[str, str] | None) -> bool:
    if not headers:
        return False
    value = headers.get("Authorization") or headers.get("authorization") or ""
    return value.strip().lower().startswith("bearer ") and bool(value.split(None, 1)[-1].strip())


def _require_candidate_evidence_consistency(candidate: Candidate,
                                            evidence_data: dict[str, Any]) -> None:
    pairs = {
        "source": (candidate.source, evidence_data.get("source")),
        "source_id": (candidate.source_id, evidence_data.get("source_id")),
        "source_url": (candidate.source_url, evidence_data.get("source_url")),
        "download_url": (candidate.download_url, evidence_data.get("download_url")),
    }
    for field, (candidate_value, evidence_value) in pairs.items():
        if str(candidate_value or "").strip() != str(evidence_value or "").strip():
            raise ValueError(
                f"candidate evidence mismatch: {field} "
                f"for {candidate.source}:{candidate.source_id}")


def _require_supported_license_evidence(evidence_data: dict[str, Any]) -> None:
    decision = decide_license(
        license_name=evidence_data.get("license_name", ""),
        license_url=evidence_data.get("license_url", ""),
        rights_text=evidence_data.get("rights_text", ""),
        source_url=evidence_data.get("source_url", ""),
        source_id=evidence_data.get("source_id", ""),
    )
    if not decision.accepted:
        raise ValueError(
            "unsupported or unclear license evidence "
            f"{evidence_data.get('evidence_hash', '')}")


def download_candidate(candidate: Candidate | dict[str, Any], out_dir: str | Path,
                       http: BytesHttpClient, *,
                       headers: dict[str, str] | None = None,
                       expected_sha256: str | None = None,
                       min_interval_s: float = 0.0,
                       last_request_at: float | None = None,
                       max_attempts: int = 1,
                       retry_sleep_s: float = 0.0,
                       sleep=time.sleep,
                       now=time.monotonic) -> DownloadResult:
    cand = candidate if isinstance(candidate, Candidate) else Candidate.from_dict(candidate)
    if not cand.decision or not cand.decision.accepted:
        raise ValueError(
            f"candidate {cand.source}:{cand.source_id} is not license-approved")
    if not cand.evidence:
        raise ValueError(f"candidate {cand.source}:{cand.source_id} has no evidence")
    if not cand.download_url.strip():
        raise ValueError(
            f"candidate {cand.source}:{cand.source_id} has no download URL")

    root = Path(out_dir)
    ext = _ext(cand.filename, cand.download_url)
    _require_supported_audio_ext(cand, ext)
    evidence_data = cand.evidence.to_dict()
    validate_evidence_schema(evidence_data)
    validate_evidence_hash(evidence_data)
    validate_final_evidence_source(evidence_data)
    _require_supported_license_evidence(evidence_data)
    _require_candidate_evidence_consistency(cand, evidence_data)

    ev_dir = root / "evidence"
    ev_dir.mkdir(parents=True, exist_ok=True)
    ev_path = ev_dir / f"{cand.evidence.evidence_hash}.json"
    if not ev_path.exists():
        ev_path.write_text(canonical_json(evidence_data) + "\n")

    if expected_sha256:
        sha = expected_sha256.lower()
        dst = root / "downloads" / sha[:2] / f"{sha}.{ext}"
        if dst.exists():
            data = dst.read_bytes()
            actual = hashlib.sha256(data).hexdigest()
            if actual != sha:
                raise ValueError(
                    f"cached download hash mismatch for {cand.source}:{cand.source_id}: "
                    f"expected {sha}, got {actual}")
            return DownloadResult(
                sha256=sha,
                path=str(dst),
                evidence_path=str(ev_path),
                size=len(data),
                candidate=cand.to_dict(),
                reused=True,
            )

    if min_interval_s > 0 and last_request_at is not None:
        delay = min_interval_s - (now() - last_request_at)
        if delay > 0:
            sleep(delay)

    if cand.source == "freesound" and not _has_bearer_token(headers):
        raise ValueError(
            f"candidate {cand.source}:{cand.source_id}: "
            "Freesound downloads require OAuth2 bearer token")

    attempts = max(1, int(max_attempts))
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            data = http.get_bytes(cand.download_url, headers=headers)
            break
        except Exception as e:  # transport boundary: normalize for CLI/users
            last_error = e
            if attempt >= attempts:
                raise ValueError(
                    f"download failed after {attempts} attempts for "
                    f"{cand.source}:{cand.source_id}: {type(e).__name__}"
                ) from e
            if retry_sleep_s > 0:
                sleep(retry_sleep_s)
    else:  # pragma: no cover - loop always breaks or raises
        raise ValueError(
            f"download failed after {attempts} attempts for "
            f"{cand.source}:{cand.source_id}: {type(last_error).__name__}")

    sha = hashlib.sha256(data).hexdigest()
    if expected_sha256 and sha != expected_sha256.lower():
        raise ValueError(
            f"download hash mismatch for {cand.source}:{cand.source_id}: "
            f"expected {expected_sha256}, got {sha}")

    dl_dir = root / "downloads" / sha[:2]
    dl_dir.mkdir(parents=True, exist_ok=True)
    dst = dl_dir / f"{sha}.{ext}"
    if not dst.exists():
        tmp = dst.with_suffix(dst.suffix + ".tmp")
        tmp.write_bytes(data)
        tmp.replace(dst)

    return DownloadResult(
        sha256=sha,
        path=str(dst),
        evidence_path=str(ev_path),
        size=len(data),
        candidate=cand.to_dict(),
        reused=False,
    )


def save_download_results(results: list[DownloadResult], path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([r.to_dict() for r in results],
                               indent=2, sort_keys=True) + "\n")
    return path
