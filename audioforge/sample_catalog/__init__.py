"""Public-domain sample catalog builder primitives.

The package is intentionally build-time only: discovery, download, analysis,
review, and promotion happen outside the renderer. Runtime playback continues
to use pinned local AudioForge libraries.

Public re-exports are resolved lazily so runtime modules can import lightweight
sample-catalog constants without loading source adapters or downloader code.
"""
from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORTS = {
    "ACCEPTED_LICENSES": ".licenses",
    "AnalysisConfig": ".analyze",
    "Candidate": ".sources",
    "DownloadResult": ".download",
    "FreesoundAdapter": ".sources",
    "InternetArchiveAdapter": ".sources",
    "LicenseDecision": ".licenses",
    "LicenseEvidence": ".licenses",
    "OpenverseDiscoveryAdapter": ".sources",
    "SfzRegion": ".sfz",
    "WikimediaCommonsAdapter": ".sources",
    "analyze_sample": ".analyze",
    "audit_catalog": ".manifest",
    "build_region_sets": ".sfz",
    "build_regions": ".sfz",
    "decide_license": ".licenses",
    "download_candidate": ".download",
    "evidence_hash": ".licenses",
    "make_evidence": ".licenses",
    "promote_candidate": ".review",
    "write_library_manifest": ".manifest",
    "write_license_bundle": ".manifest",
    "write_review": ".review",
    "write_sfz": ".sfz",
}

__all__ = sorted(_EXPORTS)


def __getattr__(name: str) -> Any:
    module_name = _EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module(module_name, __name__), name)
    globals()[name] = value
    return value
