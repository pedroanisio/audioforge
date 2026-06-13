from __future__ import annotations

import re
import time
from dataclasses import dataclass, field, replace
from typing import Any, Protocol
from urllib.parse import unquote, urljoin, urlparse

from .constants import CANDIDATE_SCHEMA, LICENSE_EVIDENCE_SCHEMA
from .licenses import LicenseDecision, LicenseEvidence, decide_license, make_evidence


_DOWNLOAD_AUDIO_EXTS = ("wav", "aiff", "aif", "flac", "ogg", "oga", "mp3")
FREESOUND_MIN_PITCH_CONFIDENCE = 0.25
PITCHED_INSTRUMENT_REJECT_TAGS = (
    "loop",
    "loops",
    "beat",
    "beats",
    "song",
    "songs",
    "speech",
    "voice",
    "spoken",
    "field-recording",
    "field_recording",
    "fieldrecording",
    "mix",
    "mixed",
    "backing-track",
    "backing_track",
)
_PERCUSSION_INSTRUMENT_TERMS = {
    "beat",
    "beats",
    "drum",
    "drums",
    "kick",
    "percussion",
    "snare",
}
_FREESOUND_PITCH_CONFIDENCE_TOKENS = {
    "key",
    "note",
    "pitch",
    "tonal",
}
SECONDARY_SOURCE_REVIEW_REQUIREMENTS = {
    "internet_archive": "manual_public_domain_provenance_review",
    "wikimedia_commons": "manual_commons_license_metadata_review",
}
INTERNET_ARCHIVE_AMBIGUOUS_RIGHTS_MARKERS = (
    "all rights reserved",
    "rights reserved",
    "not public domain",
    "copyright ",
    "©",
    "(c)",
)
INTERNET_ARCHIVE_PREFERRED_CONTEXT_TERMS = {
    "sample": "sample_pack_or_isolated_note",
    "samples": "sample_pack_or_isolated_note",
    "sample-pack": "sample_pack_or_isolated_note",
    "isolated": "sample_pack_or_isolated_note",
    "single-note": "sample_pack_or_isolated_note",
    "note": "sample_pack_or_isolated_note",
    "notes": "sample_pack_or_isolated_note",
    "instrument": "sample_pack_or_isolated_note",
    "instrumental": "sample_pack_or_isolated_note",
    "institution": "institutional_collection",
    "institutional": "institutional_collection",
    "museum": "institutional_collection",
    "library": "institutional_collection",
    "collection": "institutional_collection",
}
SOURCE_ADAPTER_CLI_TO_ID = {
    "freesound": "freesound",
    "internet-archive": "internet_archive",
    "wikimedia-commons": "wikimedia_commons",
    "openverse": "openverse_discovery",
}
SOURCE_ADAPTERS = tuple(SOURCE_ADAPTER_CLI_TO_ID.values())
SOURCE_ADAPTER_CLI_NAMES = tuple(SOURCE_ADAPTER_CLI_TO_ID.keys())


def _required_text_field(data: dict[str, Any], key: str, *,
                         context: str = "candidate") -> str:
    value = data.get(key)
    if key not in data or value is None:
        raise ValueError(f"{context} missing required field: {key}")
    return str(value)


def _object_field(data: dict[str, Any], key: str, *,
                  context: str = "candidate") -> dict[str, Any]:
    value = data.get(key) or {}
    if not isinstance(value, dict):
        raise ValueError(f"{context} {key} must be an object")
    return value


def _string_tuple_field(data: dict[str, Any], key: str) -> tuple[str, ...]:
    value = data.get(key, ())
    if value is None:
        return ()
    if not isinstance(value, (list, tuple)):
        raise ValueError(f"candidate {key} must be a list")
    return tuple(str(item) for item in value)


class JsonHttpClient(Protocol):
    def get_json(self, url: str, *, params: dict[str, Any] | None = None,
                 headers: dict[str, str] | None = None) -> dict[str, Any]:
        ...


@dataclass(frozen=True)
class Candidate:
    source: str
    source_id: str
    source_url: str
    download_url: str
    filename: str
    license_name: str
    license_url: str
    rights_text: str = ""
    creator: str = ""
    tags: tuple[str, ...] = ()
    descriptors: dict[str, Any] = field(default_factory=dict)
    raw_metadata: dict[str, Any] = field(default_factory=dict)
    decision: LicenseDecision | None = None
    evidence: LicenseEvidence | None = None
    schema: str = CANDIDATE_SCHEMA

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "source": self.source,
            "source_id": self.source_id,
            "source_url": self.source_url,
            "download_url": self.download_url,
            "filename": self.filename,
            "license_name": self.license_name,
            "license_url": self.license_url,
            "rights_text": self.rights_text,
            "creator": self.creator,
            "tags": list(self.tags),
            "descriptors": self.descriptors,
            "raw_metadata": self.raw_metadata,
            "decision": self.decision.to_dict() if self.decision else None,
            "evidence": self.evidence.to_dict() if self.evidence else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Candidate":
        if not isinstance(data, dict):
            raise ValueError("candidate must be an object")
        schema = data.get("schema", CANDIDATE_SCHEMA)
        if schema != CANDIDATE_SCHEMA:
            raise ValueError(f"unsupported sample catalog candidate schema: {schema!r}")
        decision = _object_field(data, "decision")
        ev = _object_field(data, "evidence")
        descriptors = _object_field(data, "descriptors")
        raw_metadata = _object_field(data, "raw_metadata")
        return cls(
            source=_required_text_field(data, "source"),
            source_id=_required_text_field(data, "source_id"),
            source_url=_required_text_field(data, "source_url"),
            download_url=_required_text_field(data, "download_url"),
            filename=_required_text_field(data, "filename"),
            license_name=data.get("license_name", ""),
            license_url=data.get("license_url", ""),
            rights_text=data.get("rights_text", ""),
            creator=data.get("creator", ""),
            tags=_string_tuple_field(data, "tags"),
            descriptors=descriptors,
            raw_metadata=raw_metadata,
            decision=(LicenseDecision(
                decision.get("status", "quarantine"),
                decision.get("license_id"),
                tuple(decision.get("reasons", ())),
            ) if decision else None),
            evidence=(LicenseEvidence(
                source=_required_text_field(ev, "source",
                                            context="candidate evidence"),
                source_id=_required_text_field(ev, "source_id",
                                               context="candidate evidence"),
                source_url=_required_text_field(ev, "source_url",
                                                context="candidate evidence"),
                download_url=_required_text_field(
                    ev, "download_url", context="candidate evidence"),
                license_name=_required_text_field(
                    ev, "license_name", context="candidate evidence"),
                license_url=_required_text_field(
                    ev, "license_url", context="candidate evidence"),
                rights_text=ev.get("rights_text", ""),
                creator=ev.get("creator", ""),
                fetched_at=_required_text_field(ev, "fetched_at",
                                                context="candidate evidence"),
                schema=ev.get("schema", LICENSE_EVIDENCE_SCHEMA),
                evidence_hash=_required_text_field(
                    ev, "evidence_hash", context="candidate evidence"),
            ) if ev else None),
            schema=schema,
        )


class FreesoundAdapter:
    """Freesound API adapter with injectable transport for no-network tests."""

    base_url = "https://freesound.org/apiv2/"
    fields = (
        "id,name,url,download,license,username,tags,type,duration,filesize,"
        "avg_rating,num_ratings,pack,analysis"
    )
    preferred_types = ("wav", "aiff", "flac")

    def __init__(self, http: JsonHttpClient, *, token: str | None = None,
                 fetched_at: str | None = None,
                 min_duration_s: float = 0.08,
                 max_duration_s: float = 12.0,
                 min_rating: float = 3.0,
                 min_interval_s: float = 0.0,
                 sleep=time.sleep,
                 now=time.monotonic):
        self.http = http
        self.token = token
        self.fetched_at = fetched_at
        self.min_duration_s = min_duration_s
        self.max_duration_s = max_duration_s
        self.min_rating = min_rating
        self.min_interval_s = min_interval_s
        self.sleep = sleep
        self.now = now

    def search(self, *, instrument: str, limit: int = 50,
               include_quarantine: bool = False) -> list[Candidate]:
        type_filter = "(" + " OR ".join(
            f"type:{t}" for t in self.preferred_types) + ")"
        exclude_filter = ""
        if _is_pitched_instrument_query(instrument):
            exclude_filter = " " + " ".join(
                f"-tag:{tag}" for tag in PITCHED_INSTRUMENT_REJECT_TAGS)
        params = {
            "query": instrument,
            "fields": self.fields,
            "page_size": min(max(int(limit), 1), 150),
            "filter": (
                'license:"Creative Commons 0" '
                f'tag:{instrument} '
                f"{type_filter} "
                f"duration:[{self.min_duration_s:g} TO {self.max_duration_s:g}] "
                f"avg_rating:[{self.min_rating:g} TO *]"
                f"{exclude_filter}"
            ),
        }
        headers = self._headers()
        url = urljoin(self.base_url, "search/text/")
        out: list[Candidate] = []
        last_request_at = None
        while url and len(out) < limit:
            if self.min_interval_s > 0 and last_request_at is not None:
                delay = self.min_interval_s - (self.now() - last_request_at)
                if delay > 0:
                    self.sleep(delay)
            payload = self.http.get_json(url, params=params, headers=headers)
            last_request_at = self.now()
            params = None
            for row in payload.get("results", []):
                cand = self._candidate(row, instrument=instrument)
                if cand.decision and (cand.decision.accepted or include_quarantine):
                    out.append(cand)
                if len(out) >= limit:
                    break
            url = payload.get("next")
        return out

    def candidate_by_id(self, sound_id: str, *, instrument: str = "",
                        include_quarantine: bool = False) -> Candidate:
        payload = self.http.get_json(
            urljoin(self.base_url, f"sounds/{sound_id}/"),
            params={"fields": self.fields},
            headers=self._headers(),
        )
        cand = self._candidate(payload, instrument=instrument)
        if cand.decision and (cand.decision.accepted or include_quarantine):
            return cand
        raise ValueError(
            f"freesound:{sound_id} did not pass canonical upstream gates")

    def _headers(self) -> dict[str, str] | None:
        if not self.token:
            return None
        return {"Authorization": f"Bearer {self.token}"}

    def _candidate(self, row: dict[str, Any], *, instrument: str = "") -> Candidate:
        license_name = row.get("license", "")
        license_url = row.get("license", "")
        sound_type = str(row.get("type") or "").strip().lower()
        download_url = row.get("download") or ""
        decision = decide_license(
            license_name=license_name,
            license_url=license_url,
            source_url=row.get("url", ""),
            source_id=str(row.get("id", "")),
        )
        decision = _with_source_gate_reasons(
            decision,
            download_url=download_url,
            reasons=(
                () if sound_type in self.preferred_types
                else ("unsupported_freesound_file_type",)
            )
            + _unsuitable_pitched_content_reasons(row, instrument)
            + _freesound_pitch_confidence_reasons(row, instrument),
        )
        evidence = make_evidence(
            source="freesound",
            source_id=str(row.get("id", "")),
            source_url=row.get("url", ""),
            download_url=download_url,
            license_name=license_name,
            license_url=license_url,
            creator=row.get("username", ""),
            fetched_at=self.fetched_at,
        )
        return Candidate(
            source="freesound",
            source_id=str(row.get("id", "")),
            source_url=row.get("url", ""),
            download_url=evidence.download_url,
            filename=row.get("name") or f"freesound-{row.get('id')}.wav",
            license_name=license_name,
            license_url=license_url,
            creator=row.get("username", ""),
            tags=tuple(row.get("tags", ())),
            descriptors={
                "duration": row.get("duration"),
                "type": sound_type,
                "filesize": row.get("filesize"),
                "avg_rating": row.get("avg_rating"),
                "num_ratings": row.get("num_ratings"),
                "pack": row.get("pack"),
                "analysis": row.get("analysis", {}),
            },
            raw_metadata=row,
            decision=decision,
            evidence=evidence,
        )


class InternetArchiveAdapter:
    base_url = "https://archive.org/"
    audio_exts = (".wav", ".aiff", ".aif", ".flac", ".ogg", ".oga", ".mp3")

    def __init__(self, http: JsonHttpClient, *, fetched_at: str | None = None):
        self.http = http
        self.fetched_at = fetched_at

    def search(self, *, query: str, limit: int = 50,
               include_quarantine: bool = False) -> list[Candidate]:
        payload = self.http.get_json(
            urljoin(self.base_url, "advancedsearch.php"),
            params={
                "q": f"mediatype:audio AND ({query})",
                "fl[]": ["identifier", "title", "creator", "licenseurl", "rights"],
                "rows": min(max(int(limit), 1), 100),
                "page": 1,
                "output": "json",
            },
            headers=None,
        )
        docs = payload.get("response", {}).get("docs", [])
        out: list[Candidate] = []
        for doc in docs:
            out.extend(self._item_candidates(doc, include_quarantine=include_quarantine))
            if len(out) >= limit:
                break
        return out[:limit]

    def candidates_for_identifier(self, identifier: str, *,
                                  include_quarantine: bool = False) -> list[Candidate]:
        return self._item_candidates(
            {"identifier": identifier},
            include_quarantine=include_quarantine,
        )

    def _item_candidates(self, doc: dict[str, Any], *,
                         include_quarantine: bool) -> list[Candidate]:
        identifier = str(doc.get("identifier", ""))
        meta = self.http.get_json(urljoin(self.base_url, f"metadata/{identifier}"))
        item_meta = meta.get("metadata", {})
        license_url = (item_meta.get("licenseurl") or doc.get("licenseurl")
                       or item_meta.get("license") or "")
        rights = item_meta.get("rights") or doc.get("rights") or ""
        creator = item_meta.get("creator") or doc.get("creator") or ""
        title = item_meta.get("title") or doc.get("title") or identifier
        source_context = _internet_archive_source_context(doc, item_meta)
        candidates = []
        for f in meta.get("files", []):
            name = f.get("name", "")
            if not name.lower().endswith(self.audio_exts):
                continue
            source_url = f"https://archive.org/details/{identifier}"
            download_url = f"https://archive.org/download/{identifier}/{name}"
            decision = decide_license(
                license_name=license_url,
                license_url=license_url,
                rights_text=rights,
                source_url=source_url,
                source_id=identifier,
            )
            decision = _with_source_gate_reasons(
                decision,
                download_url=download_url,
                reasons=_internet_archive_ambiguous_rights_reasons(rights),
            )
            evidence = make_evidence(
                source="internet_archive",
                source_id=identifier,
                source_url=source_url,
                download_url=download_url,
                license_name=license_url or rights,
                license_url=license_url,
                rights_text=rights,
                creator=str(creator),
                fetched_at=self.fetched_at,
            )
            cand = Candidate(
                source="internet_archive",
                source_id=identifier,
                source_url=source_url,
                download_url=download_url,
                filename=name,
                license_name=license_url or rights,
                license_url=license_url,
                rights_text=str(rights),
                creator=str(creator),
                tags=(str(title),),
                descriptors={
                    "format": f.get("format"),
                    "size": f.get("size"),
                    "source_context": source_context,
                    "review_requirement": (
                        SECONDARY_SOURCE_REVIEW_REQUIREMENTS["internet_archive"]
                    ),
                },
                raw_metadata={"doc": doc, "file": f, "metadata": item_meta},
                decision=decision,
                evidence=evidence,
            )
            if decision.accepted or include_quarantine:
                candidates.append(cand)
        return candidates


class WikimediaCommonsAdapter:
    api_url = "https://commons.wikimedia.org/w/api.php"

    def __init__(self, http: JsonHttpClient, *, fetched_at: str | None = None):
        self.http = http
        self.fetched_at = fetched_at

    def search(self, *, query: str, limit: int = 50,
               include_quarantine: bool = False) -> list[Candidate]:
        payload = self.http.get_json(self.api_url, params={
            "action": "query",
            "generator": "search",
            "gsrsearch": f"file:{query}",
            "gsrnamespace": 6,
            "gsrlimit": min(max(int(limit), 1), 50),
            "prop": "imageinfo",
            "iiprop": "url|sha1|mime|mediatype|extmetadata",
            "format": "json",
        }, headers=None)
        return self._candidates_from_pages(
            payload.get("query", {}).get("pages", {}),
            limit=limit,
            include_quarantine=include_quarantine,
        )

    def candidates_for_title(self, title: str, *,
                             include_quarantine: bool = False) -> list[Candidate]:
        payload = self.http.get_json(self.api_url, params={
            "action": "query",
            "titles": title,
            "prop": "imageinfo",
            "iiprop": "url|sha1|mime|mediatype|extmetadata",
            "format": "json",
        }, headers=None)
        return self._candidates_from_pages(
            payload.get("query", {}).get("pages", {}),
            limit=1,
            include_quarantine=include_quarantine,
        )

    def _candidates_from_pages(self, pages: dict[str, Any], *, limit: int,
                               include_quarantine: bool) -> list[Candidate]:
        out = []
        for page in pages.values():
            info = (page.get("imageinfo") or [{}])[0]
            if info.get("mediatype") != "AUDIO":
                continue
            download_url = info.get("url", "")
            ext = info.get("extmetadata", {})
            license_name = _meta_value(ext, "LicenseShortName")
            license_url = _meta_value(ext, "LicenseUrl")
            rights = _meta_value(ext, "UsageTerms")
            creator = _meta_value(ext, "Artist")
            source_url = page.get("fullurl") or (
                "https://commons.wikimedia.org/wiki/" + page.get("title", "").replace(" ", "_"))
            decision = decide_license(
                license_name=license_name,
                license_url=license_url,
                rights_text=rights,
                source_url=source_url,
                source_id=str(page.get("pageid", "")),
            )
            mime = str(info.get("mime") or "")
            filename = page.get("title", "commons-audio").split(":", 1)[-1]
            suffix = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
            decision = _with_source_gate_reasons(
                decision,
                download_url=download_url,
                reasons=(
                    () if mime.startswith("audio/") and suffix in _DOWNLOAD_AUDIO_EXTS
                    else ("unsupported_commons_audio_format",)
                ),
            )
            evidence = make_evidence(
                source="wikimedia_commons",
                source_id=str(page.get("pageid", "")),
                source_url=source_url,
                download_url=download_url,
                license_name=license_name,
                license_url=license_url,
                rights_text=rights,
                creator=creator,
                fetched_at=self.fetched_at,
            )
            cand = Candidate(
                source="wikimedia_commons",
                source_id=str(page.get("pageid", "")),
                source_url=source_url,
                download_url=download_url,
                filename=filename,
                license_name=license_name,
                license_url=license_url,
                rights_text=rights,
                creator=creator,
                tags=(page.get("title", ""),),
                descriptors={
                    "sha1": info.get("sha1"),
                    "mime": info.get("mime"),
                    "mediatype": info.get("mediatype"),
                    "review_requirement": (
                        SECONDARY_SOURCE_REVIEW_REQUIREMENTS["wikimedia_commons"]
                    ),
                },
                raw_metadata=page,
                decision=decision,
                evidence=evidence,
            )
            if decision.accepted or include_quarantine:
                out.append(cand)
        return out[:limit]


class OpenverseDiscoveryAdapter:
    api_url = "https://api.openverse.engineering/v1/audio/"

    def __init__(self, http: JsonHttpClient, *, fetched_at: str | None = None):
        self.http = http
        self.fetched_at = fetched_at

    def search(self, *, query: str, limit: int = 50) -> list[Candidate]:
        payload = self.http.get_json(self.api_url, params={
            "q": query,
            "license": "cc0,pdm",
            "page_size": min(max(int(limit), 1), 100),
        }, headers=None)
        out = []
        for row in payload.get("results", [])[:limit]:
            source_url = row.get("foreign_landing_url") or row.get("url") or ""
            download_url = row.get("url") or ""
            evidence = make_evidence(
                source="openverse_discovery",
                source_id=str(row.get("id", "")),
                source_url=source_url,
                download_url=download_url,
                license_name=row.get("license", ""),
                license_url=row.get("license_url", ""),
                rights_text="Openverse discovery lead; verify upstream before download",
                creator=row.get("creator", ""),
                fetched_at=self.fetched_at,
            )
            out.append(Candidate(
                source="openverse_discovery",
                source_id=str(row.get("id", "")),
                source_url=source_url,
                download_url=download_url,
                filename=(row.get("title") or row.get("id") or "openverse-audio"),
                license_name=row.get("license", ""),
                license_url=row.get("license_url", ""),
                rights_text="Openverse discovery lead; verify upstream before download",
                creator=row.get("creator", ""),
                tags=tuple(row.get("tags") or ()),
                descriptors={"provider": row.get("provider"),
                             "mature": row.get("mature")},
                raw_metadata=row,
                decision=LicenseDecision(
                    "quarantine", None,
                    ("openverse_requires_upstream_verification",),
                ),
                evidence=evidence,
            ))
        return out

    def resolve(self, lead: Candidate | dict[str, Any], *,
                upstream_adapters: dict[str, Any], instrument: str = "",
                include_quarantine: bool = False) -> Candidate:
        """Resolve an Openverse discovery lead through canonical source evidence."""
        cand = lead if isinstance(lead, Candidate) else Candidate.from_dict(lead)
        if cand.source != "openverse_discovery":
            raise ValueError("only openverse_discovery candidates can be resolved")

        provider = _openverse_provider(cand)
        urls = _openverse_urls(cand)
        if provider is None:
            provider = _provider_from_urls(urls)
        if provider is None:
            raise ValueError("openverse lead has no supported upstream provider")

        adapter = upstream_adapters.get(provider)
        if adapter is None:
            raise ValueError(f"{provider} adapter required for Openverse resolution")

        if provider == "freesound":
            sound_id = _extract_freesound_id(urls)
            if sound_id is None:
                raise ValueError("openverse lead missing Freesound sound id")
            resolved = adapter.candidate_by_id(
                sound_id,
                instrument=instrument,
                include_quarantine=include_quarantine,
            )
        elif provider == "internet_archive":
            identifier = _extract_internet_archive_identifier(urls)
            if identifier is None:
                raise ValueError("openverse lead missing Internet Archive identifier")
            resolved = _select_resolved_candidate(
                cand,
                adapter.candidates_for_identifier(
                    identifier,
                    include_quarantine=include_quarantine,
                ),
            )
        elif provider == "wikimedia_commons":
            title = _extract_commons_title(urls)
            if title is None:
                raise ValueError("openverse lead missing Wikimedia Commons title")
            resolved = _select_resolved_candidate(
                cand,
                adapter.candidates_for_title(
                    title,
                    include_quarantine=include_quarantine,
                ),
            )
        else:
            raise ValueError(f"unsupported Openverse upstream provider: {provider}")

        return _with_openverse_discovery_context(resolved, cand, provider)


def _meta_value(extmetadata: dict[str, Any], key: str) -> str:
    value = extmetadata.get(key, "")
    if isinstance(value, dict):
        return str(value.get("value", "")).strip()
    return str(value or "").strip()


def _with_source_gate_reasons(decision: LicenseDecision, *, download_url: str,
                              reasons: tuple[str, ...] = ()) -> LicenseDecision:
    gate_reasons = list(reasons)
    if not str(download_url or "").strip():
        gate_reasons.append("missing_download_url")
    if not gate_reasons:
        return decision
    return LicenseDecision(
        "quarantine",
        decision.license_id,
        tuple(dict.fromkeys((*decision.reasons, *gate_reasons))),
    )


def _openverse_provider(candidate: Candidate) -> str | None:
    values = [
        candidate.descriptors.get("provider"),
        candidate.raw_metadata.get("provider"),
        candidate.raw_metadata.get("source"),
    ]
    for value in values:
        normalized = _normalize_openverse_provider(value)
        if normalized is not None:
            return normalized
    return None


def _normalize_openverse_provider(value: Any) -> str | None:
    text = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    if text in {"freesound", "freesound_org"}:
        return "freesound"
    if text in {"internet_archive", "archive_org", "the_internet_archive"}:
        return "internet_archive"
    if text in {"wikimedia_commons", "wikimedia", "commons"}:
        return "wikimedia_commons"
    return None


def _openverse_urls(candidate: Candidate) -> tuple[str, ...]:
    values = [
        candidate.source_url,
        candidate.download_url,
        candidate.raw_metadata.get("foreign_landing_url"),
        candidate.raw_metadata.get("url"),
    ]
    return tuple(str(value) for value in values if value)


def _provider_from_urls(urls: tuple[str, ...]) -> str | None:
    for url in urls:
        host = urlparse(url).netloc.lower()
        if "freesound.org" in host:
            return "freesound"
        if "archive.org" in host:
            return "internet_archive"
        if "wikimedia.org" in host or "wikimedia.commons" in host:
            return "wikimedia_commons"
    return None


def _extract_freesound_id(urls: tuple[str, ...]) -> str | None:
    for url in urls:
        match = re.search(r"/sounds/(\d+)/?", url)
        if match:
            return match.group(1)
    return None


def _extract_internet_archive_identifier(urls: tuple[str, ...]) -> str | None:
    for url in urls:
        parsed = urlparse(url)
        if "archive.org" not in parsed.netloc.lower():
            continue
        parts = [unquote(part) for part in parsed.path.split("/") if part]
        if len(parts) >= 2 and parts[0] in {"details", "download"}:
            return parts[1]
    return None


def _extract_commons_title(urls: tuple[str, ...]) -> str | None:
    for url in urls:
        parsed = urlparse(url)
        if "wikimedia.org" not in parsed.netloc.lower():
            continue
        parts = [unquote(part) for part in parsed.path.split("/") if part]
        if len(parts) >= 2 and parts[0] == "wiki":
            return parts[1].replace("_", " ")
    return None


def _select_resolved_candidate(lead: Candidate,
                               candidates: list[Candidate]) -> Candidate:
    if not candidates:
        raise ValueError("Openverse upstream resolution produced no candidates")
    lead_urls = {lead.source_url, lead.download_url}
    for candidate in candidates:
        if candidate.source_url in lead_urls or candidate.download_url in lead_urls:
            return candidate
    lead_name = str(lead.filename or "").lower()
    for candidate in candidates:
        if lead_name and candidate.filename.lower() == lead_name:
            return candidate
    if len(candidates) == 1:
        return candidates[0]
    raise ValueError("Openverse upstream resolution matched multiple candidates")


def _with_openverse_discovery_context(
        resolved: Candidate, lead: Candidate, provider: str) -> Candidate:
    descriptors = dict(resolved.descriptors)
    descriptors["openverse_discovery"] = {
        "provider": provider,
        "source_id": lead.source_id,
        "source_url": lead.source_url,
        "download_url": lead.download_url,
        "evidence_hash": lead.evidence.evidence_hash if lead.evidence else None,
    }
    raw_metadata = dict(resolved.raw_metadata)
    raw_metadata["openverse_discovery"] = lead.raw_metadata
    return replace(resolved, descriptors=descriptors, raw_metadata=raw_metadata)


def _internet_archive_ambiguous_rights_reasons(rights: Any) -> tuple[str, ...]:
    text = str(rights or "").strip().lower()
    if not text:
        return ()
    if any(marker in text for marker in INTERNET_ARCHIVE_AMBIGUOUS_RIGHTS_MARKERS):
        return ("internet_archive_ambiguous_rights",)
    return ()


def _internet_archive_source_context(
        doc: dict[str, Any], item_meta: dict[str, Any]) -> dict[str, Any]:
    values = [
        item_meta.get("title"),
        doc.get("title"),
        item_meta.get("description"),
        doc.get("description"),
        item_meta.get("subject"),
        doc.get("subject"),
        item_meta.get("collection"),
        doc.get("collection"),
        item_meta.get("creator"),
        doc.get("creator"),
    ]
    tokens = _content_tokens(_flatten_strings(values))
    matched = {
        INTERNET_ARCHIVE_PREFERRED_CONTEXT_TERMS[token]
        for token in tokens
        if token in INTERNET_ARCHIVE_PREFERRED_CONTEXT_TERMS
    }
    if matched:
        return {
            "status": "preferred",
            "matched": sorted(matched),
        }
    return {
        "status": "manual_review_required",
        "reason": "internet_archive_context_not_sample_pack_isolated_note_or_institutional",
    }


def _is_pitched_instrument_query(instrument: str) -> bool:
    terms = {
        token for token in _content_tokens([instrument])
    }
    return not bool(terms & _PERCUSSION_INSTRUMENT_TERMS)


def _unsuitable_pitched_content_reasons(
        row: dict[str, Any], instrument: str) -> tuple[str, ...]:
    if not _is_pitched_instrument_query(instrument):
        return ()
    values = [str(row.get("name") or "")]
    values.extend(str(tag) for tag in row.get("tags", ()))
    tags = _content_tokens(values)
    if tags & set(PITCHED_INSTRUMENT_REJECT_TAGS):
        return ("unsuitable_pitched_instrument_content",)
    return ()


def _freesound_pitch_confidence_reasons(
        row: dict[str, Any], instrument: str) -> tuple[str, ...]:
    if not _is_pitched_instrument_query(instrument):
        return ()
    confidences = list(_pitch_confidence_values(row.get("analysis", {})))
    for key in ("pitch_confidence", "note_confidence"):
        value = row.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            confidences.append(float(value))
    if confidences and max(confidences) < FREESOUND_MIN_PITCH_CONFIDENCE:
        return ("pitch_confidence_below_threshold",)
    return ()


def _pitch_confidence_values(
        value: Any, path: tuple[str, ...] = ()) -> tuple[float, ...]:
    if isinstance(value, dict):
        out: list[float] = []
        for key, item in value.items():
            out.extend(_pitch_confidence_values(
                item, (*path, str(key).lower())))
        return tuple(out)
    if isinstance(value, (list, tuple)):
        out = []
        for item in value:
            out.extend(_pitch_confidence_values(item, path))
        return tuple(out)
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return ()
    path_tokens = _confidence_path_tokens(path)
    if (
        any("confidence" in part for part in path)
        and bool(path_tokens & _FREESOUND_PITCH_CONFIDENCE_TOKENS)
    ):
        return (float(value),)
    return ()


def _confidence_path_tokens(path: tuple[str, ...]) -> set[str]:
    tokens: set[str] = set()
    for part in path:
        tokens.update(
            token for token in part.replace("-", "_").split("_") if token)
    return tokens


def _flatten_strings(values: list[Any]) -> list[str]:
    out: list[str] = []
    for value in values:
        if value is None:
            continue
        if isinstance(value, (list, tuple, set)):
            out.extend(str(item) for item in value if item is not None)
        else:
            out.append(str(value))
    return out


def _content_tokens(values: list[str]) -> set[str]:
    tokens: set[str] = set()
    for value in values:
        normalized = value.lower().replace("_", "-")
        for part in normalized.replace(".", " ").replace("/", " ").split():
            stripped = part.strip(" ,;:()[]{}")
            if stripped:
                tokens.add(stripped)
                tokens.add(stripped.replace("-", "_"))
                tokens.add(stripped.replace("-", ""))
    return tokens
