from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from .constants import LICENSE_EVIDENCE_SCHEMA

ACCEPTED_LICENSES = {"CC0-1.0", "PDM", "PUBLIC-DOMAIN"}
DISCOVERY_ONLY_SOURCES = frozenset({"openverse_discovery"})
_CC0_URL = "https://creativecommons.org/publicdomain/zero/1.0/"
_PDM_URL = "https://creativecommons.org/public-domain/pdm/"
_CONTRADICTORY_RIGHTS = (
    "all rights reserved",
    "copyright",
    "©",
    "(c)",
    "not public domain",
    "rights reserved",
)


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _canon_url(url: str) -> str:
    url = _clean(url)
    return url[:-1] + "/" if url and not url.endswith("/") else url


def normalize_license(name: str = "", url: str = "",
                      rights_text: str = "") -> str | None:
    text = " ".join([_clean(name), _clean(url), _clean(rights_text)]).lower()
    url = _canon_url(url).lower()
    if "creativecommons.org/publicdomain/zero/1.0" in url:
        return "CC0-1.0"
    if "cc0" in text or "creative commons 0" in text:
        return "CC0-1.0"
    if "creativecommons.org/public-domain/pdm" in url:
        return "PDM"
    if "public domain mark" in text or "no known copyright" in text:
        return "PDM"
    if "public domain" in text and not any(
        blocked in text for blocked in ("cc-by", "attribution",
                                        "noncommercial", "sharealike")
    ):
        return "PUBLIC-DOMAIN"
    return None


def _has_contradictory_rights(*values: str) -> bool:
    text = " ".join(_clean(value) for value in values).lower()
    return any(marker in text for marker in _CONTRADICTORY_RIGHTS)


@dataclass(frozen=True)
class LicenseDecision:
    status: str
    license_id: str | None
    reasons: tuple[str, ...] = ()

    @property
    def accepted(self) -> bool:
        return self.status == "accepted"

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "license_id": self.license_id,
            "reasons": list(self.reasons),
        }


@dataclass(frozen=True)
class LicenseEvidence:
    source: str
    source_id: str
    source_url: str
    download_url: str
    license_name: str
    license_url: str
    rights_text: str
    creator: str
    fetched_at: str
    schema: str = LICENSE_EVIDENCE_SCHEMA
    evidence_hash: str = ""

    def normalized(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "source": self.source,
            "source_id": self.source_id,
            "source_url": self.source_url,
            "download_url": self.download_url,
            "license_name": self.license_name,
            "license_url": self.license_url,
            "rights_text": self.rights_text,
            "creator": self.creator,
            "fetched_at": self.fetched_at,
        }

    def to_dict(self) -> dict[str, Any]:
        data = self.normalized()
        data["evidence_hash"] = self.evidence_hash or evidence_hash(data)
        return data


def canonical_json(data: Any) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True)


def evidence_hash(data: dict[str, Any]) -> str:
    core = dict(data)
    core.pop("evidence_hash", None)
    return hashlib.sha256(canonical_json(core).encode("utf-8")).hexdigest()


def validate_evidence_hash(data: dict[str, Any]) -> None:
    actual = data.get("evidence_hash")
    if not actual:
        raise ValueError("license evidence entry missing evidence_hash")
    expected = evidence_hash(data)
    if actual != expected:
        raise ValueError(
            "license evidence hash mismatch: "
            f"expected {expected}, got {actual}")


def validate_evidence_schema(data: dict[str, Any]) -> None:
    schema = data.get("schema")
    if schema != LICENSE_EVIDENCE_SCHEMA:
        raise ValueError(f"unsupported license evidence schema: {schema!r}")


def validate_final_evidence_source(data: dict[str, Any]) -> None:
    source = _clean(data.get("source"))
    if source in DISCOVERY_ONLY_SOURCES:
        raise ValueError(
            "openverse discovery evidence requires upstream verification")


def make_evidence(*, source: str, source_id: str, source_url: str,
                  download_url: str, license_name: str, license_url: str,
                  rights_text: str = "", creator: str = "",
                  fetched_at: str | None = None) -> LicenseEvidence:
    fetched_at = fetched_at or datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    ev = LicenseEvidence(
        source=_clean(source),
        source_id=_clean(source_id),
        source_url=_clean(source_url),
        download_url=_clean(download_url),
        license_name=_clean(license_name),
        license_url=_canon_url(license_url),
        rights_text=_clean(rights_text),
        creator=_clean(creator),
        fetched_at=fetched_at,
        schema=LICENSE_EVIDENCE_SCHEMA,
    )
    return LicenseEvidence(**ev.normalized(), evidence_hash=evidence_hash(ev.normalized()))


def decide_license(*, license_name: str = "", license_url: str = "",
                   rights_text: str = "", source_url: str = "",
                   source_id: str = "") -> LicenseDecision:
    lic = normalize_license(license_name, license_url, rights_text)
    if not lic:
        return LicenseDecision(
            "quarantine", None,
            ("license_not_allowed_or_unclear",),
        )
    if _has_contradictory_rights(
        license_name, rights_text
    ):
        reason = (
            "public_domain_contradictory_rights"
            if lic in {"PDM", "PUBLIC-DOMAIN"}
            else "license_contradictory_rights"
        )
        return LicenseDecision(
            "quarantine", lic,
            (reason,),
        )
    if lic in {"PDM", "PUBLIC-DOMAIN"} and (not source_url or not source_id):
        return LicenseDecision(
            "quarantine", lic,
            ("public_domain_requires_stable_source_evidence",),
        )
    if lic not in ACCEPTED_LICENSES:
        return LicenseDecision("quarantine", lic, ("license_not_allowed",))
    return LicenseDecision("accepted", lic, ())
