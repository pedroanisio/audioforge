from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from audioforge.catalog import note_name
from audioforge.library import _canonical_manifest_hash

from .manifest import attach_region_library_pins, audit_catalog

SECONDARY_SOURCE_REVIEW_WARNINGS = {
    "internet_archive": (
        "Internet Archive evidence requires manual public-domain provenance "
        "review before approval."
    ),
    "wikimedia_commons": (
        "Wikimedia Commons evidence requires manual Commons license metadata "
        "review before approval."
    ),
}


def _load_license_bundle(candidate_dir: Path) -> dict[str, Any]:
    path = candidate_dir / "LICENSES.json"
    if not path.is_file():
        return {"evidence": []}
    return json.loads(path.read_text())


def _warning_lines(manifest: dict[str, Any], evidence: list[dict[str, Any]]) -> list[str]:
    warnings = []
    summary = manifest.get("analysis_summary", {})
    accepted = summary.get("accepted_samples")
    if accepted == 0:
        warnings.append("No accepted samples are recorded.")
    quality_min = summary.get("quality_score_min")
    if quality_min is not None and float(quality_min) < 0.85:
        warnings.append(
            f"Quality score minimum is low ({float(quality_min):.3f}); "
            "audition and inspect analysis records before approval.")
    quality_mean = summary.get("quality_score_mean")
    if quality_mean is not None and float(quality_mean) < 0.9:
        warnings.append(
            f"Quality score mean is below target ({float(quality_mean):.3f}); "
            "review source consistency before approval.")
    ia_context_review = summary.get(
        "internet_archive_source_context_review_required")
    if ia_context_review:
        warnings.append(
            "Internet Archive source context is not clearly a sample pack, "
            f"isolated note, or institutional collection for {int(ia_context_review)} "
            "accepted sample(s).")
    if manifest.get("catalog_state") != "approved":
        warnings.append("Catalog is still a candidate and must not be used as approved.")
    if not evidence:
        warnings.append("No license evidence entries are present.")
    for source in sorted({str(e.get("source") or "") for e in evidence}):
        warning = SECONDARY_SOURCE_REVIEW_WARNINGS.get(source)
        if warning:
            warnings.append(warning)
    if not manifest.get("regions"):
        warnings.append("No manifest region summaries are present.")
    return warnings


def _pitch_map_lines(regions: list[dict[str, Any]]) -> list[str]:
    if not regions:
        return ["No regions recorded."]
    lines = [
        "| Instrument | Articulation | Keycenter | Range | Velocity | Sample | Evidence |",
        "| --- | --- | ---: | --- | --- | --- | --- |",
    ]
    for r in regions:
        lines.append(
            "| {instrument} | {articulation} | {pitch_keycenter} | "
            "{lokey}-{hikey} | {lovel}-{hivel} | `{sample}` | `{evidence}` |".format(
                instrument=r.get("instrument", ""),
                articulation=r.get("articulation", ""),
                pitch_keycenter=r.get("pitch_keycenter", ""),
                lokey=r.get("lokey", ""),
                hikey=r.get("hikey", ""),
                lovel=r.get("lovel", ""),
                hivel=r.get("hivel", ""),
                sample=r.get("sample", ""),
                evidence=r.get("source_evidence_id") or "",
            )
        )
    return lines


def _license_lines(evidence: list[dict[str, Any]]) -> list[str]:
    if not evidence:
        return ["No license evidence found."]
    lines = [
        "| Source | ID | License | Creator | Source URL | Evidence |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for e in sorted(evidence, key=lambda item: item["evidence_hash"]):
        lines.append(
            "| {source} | `{source_id}` | {license_name} | {creator} | {url} | `{hash}` |".format(
                source=e.get("source", ""),
                source_id=e.get("source_id", ""),
                license_name=e.get("license_name", ""),
                creator=e.get("creator", ""),
                url=e.get("source_url", ""),
                hash=e.get("evidence_hash", ""),
            )
        )
    return lines


def _catalog_diagnostics_lines(manifest: dict[str, Any]) -> list[str]:
    diagnostics = manifest.get("catalog_diagnostics")
    if not isinstance(diagnostics, dict):
        return ["Catalog diagnostics are not present in the manifest."]
    blockers = diagnostics.get("render_blockers") or []
    ignored = diagnostics.get("ignored_opcodes") or []
    lines = [
        f"- Instruments: {diagnostics.get('instrument_count', 0)}",
        f"- Renderable: {diagnostics.get('renderable_count', 0)}",
        f"- Blocked: {diagnostics.get('blocked_count', 0)}",
        f"- Render blockers: {', '.join(blockers) if blockers else 'none'}",
        f"- Ignored opcodes: {', '.join(ignored) if ignored else 'none'}",
        "",
        "| Instrument | SFZ | Renderable | Blockers | Formats | Key range | Velocity layers | Round robin |",
        "| --- | --- | --- | --- | --- | --- | --- | ---: |",
    ]
    instruments = sorted(
        diagnostics.get("instruments", []),
        key=lambda item: (str(item.get("sfz") or ""),
                          str(item.get("id") or "")),
    )
    if not instruments:
        lines.append("| none | none | no | none | none | none | none | 1 |")
        return lines
    for instrument in instruments:
        key_range = instrument.get("key_range") or {}
        key = (
            f"{key_range.get('low_note', '')}-"
            f"{key_range.get('high_note', '')}"
        ).strip("-") or "none"
        velocity = ", ".join(
            f"{layer[0]}-{layer[1]}"
            for layer in instrument.get("velocity_layers", [])
            if isinstance(layer, list) and len(layer) == 2
        ) or "none"
        lines.append(
            "| {id} | `{sfz}` | {renderable} | {blockers} | {formats} | "
            "{key} | {velocity} | {round_robin} |".format(
                id=instrument.get("id", ""),
                sfz=instrument.get("sfz", ""),
                renderable="yes" if instrument.get("renderable") else "no",
                blockers=", ".join(instrument.get("render_blockers") or [])
                or "none",
                formats=", ".join(instrument.get("sample_formats") or [])
                or "none",
                key=key,
                velocity=velocity,
                round_robin=instrument.get("round_robin_max", 1),
            )
        )
    return lines


def _audition_lines(manifest: dict[str, Any]) -> list[str]:
    regions = sorted(manifest.get("regions", []), key=lambda r: (
        r.get("instrument", ""),
        r.get("articulation", ""),
        r.get("pitch_keycenter", 60),
        r.get("sample", ""),
    ))
    if not regions:
        return [
            "```bash",
            "audioforge sample-catalog audit-license .",
            "```",
        ]
    region = regions[0]
    instrument = str(region.get("instrument") or next(iter(manifest["instruments"])))
    articulation = str(region.get("articulation") or "sustain")
    midi = int(region.get("pitch_keycenter") or 60)
    pitch = note_name(midi)
    library_ref = f"{manifest['name']}@{manifest['manifest_sha256']}"
    return [
        "```bash",
        "audioforge sample-catalog audit-license .",
        "python -c \"from audioforge.catalog import Catalog; import json; "
        "print(json.dumps(Catalog.build('.').to_dict(), indent=2))\"",
        "```",
        "",
        "```af",
        "asset sample_catalog_audition {",
        "  bpm: 90",
        f"  library: \"{library_ref}\"",
        "  layer audition : instrument {",
        f"    instrument: \"{instrument}\"",
        f"    articulation: {articulation}",
        f"    notes: {pitch} @ 0b for 1b",
        "  }",
        "}",
        "```",
    ]


def _normalize_reviewed_at(value: str) -> str:
    value = str(value or "").strip()
    if not value:
        raise ValueError("reviewed_at is required for promotion")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("reviewed_at must include timezone")
    return parsed.replace(microsecond=0).isoformat()


def write_review(candidate_dir: str | Path, *, reviewer: str | None = None,
                 status: str = "pending", reviewed_at: str | None = None,
                 notes: str = "") -> Path:
    candidate_dir = Path(candidate_dir)
    audit_catalog(candidate_dir)
    manifest = json.loads((candidate_dir / "library.manifest.json").read_text())
    bundle = _load_license_bundle(candidate_dir)
    evidence = bundle.get("evidence", [])
    warnings = _warning_lines(manifest, evidence)
    lines = [
        f"# Review: {manifest['name']}",
        "",
        f"- Status: {status}",
        f"- Reviewer: {reviewer or ''}",
        f"- Reviewed at: {reviewed_at or ''}",
        f"- Manifest: {manifest['manifest_sha256']}",
        f"- Catalog state: {manifest.get('catalog_state', 'candidate')}",
        f"- License evidence: {manifest.get('license_evidence_hash')}",
        f"- Accepted samples: {manifest.get('analysis_summary', {}).get('accepted_samples', 'unknown')}",
        "",
        "## Source And License Evidence",
        "",
        *_license_lines(evidence),
        "",
        "## Pitch Map",
        "",
        *_pitch_map_lines(manifest.get("regions", [])),
        "",
        "## Catalog Diagnostics",
        "",
        *_catalog_diagnostics_lines(manifest),
        "",
        "## Quality Warnings",
        "",
        *(f"- {w}" for w in warnings),
        *(["- None"] if not warnings else []),
        "",
        "## Audition",
        "",
        *_audition_lines(manifest),
        "",
        "## Notes",
        "",
        notes.strip(),
        "",
    ]
    path = candidate_dir / "review.md"
    path.write_text("\n".join(lines))
    return path


def promote_candidate(candidate_dir: str | Path, approved_root: str | Path, *,
                      reviewer: str, reviewed_at: str,
                      version: str | None = None) -> Path:
    candidate_dir = Path(candidate_dir)
    manifest_path = candidate_dir / "library.manifest.json"
    manifest = json.loads(manifest_path.read_text())
    if not manifest.get("license_evidence_hash"):
        raise ValueError("cannot promote catalog without license evidence")
    if not reviewer:
        raise ValueError("reviewer is required for promotion")
    reviewed_at = _normalize_reviewed_at(reviewed_at)
    audit_catalog(candidate_dir)

    target_version = version or manifest.get("version", "0.0.0")
    dest = Path(approved_root) / manifest["name"] / target_version
    if dest.exists():
        raise FileExistsError(dest)
    shutil.copytree(candidate_dir, dest)

    manifest["version"] = target_version
    manifest["catalog_state"] = "approved"
    manifest["review"] = {
        "status": "approved",
        "reviewer": reviewer,
        "reviewed_at": reviewed_at,
    }
    manifest["manifest_sha256"] = _canonical_manifest_hash(manifest)
    attach_region_library_pins(manifest)
    (dest / "library.manifest.json").write_text(
        json.dumps(manifest, indent=1, sort_keys=True) + "\n")
    write_review(dest, reviewer=reviewer, status="approved",
                 reviewed_at=reviewed_at)
    return dest
