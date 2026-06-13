from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from audioforge.catalog import Catalog
from audioforge.library import (add_library_path, generate_manifest,
                                load_library, _canonical_manifest_hash)

from .constants import (
    ANALYSIS_SCHEMA,
    LICENSE_BUNDLE_SCHEMA,
    LICENSE_EVIDENCE_SCHEMA,
    SAMPLE_CATALOG_BUILDER_VERSION,
)
from .licenses import (
    canonical_json,
    decide_license,
    evidence_hash,
    validate_evidence_hash,
    validate_final_evidence_source,
)


def _require_evidence_hash(value: str | None) -> str:
    if not value:
        raise ValueError("license_evidence_hash is required")
    return value


def _license_bundle_hash(bundle: dict[str, Any]) -> str:
    return evidence_hash({
        "schema": bundle["schema"],
        "evidence": bundle["evidence"],
    })


def _verify_license_evidence_hash(
        expected_hash: str, evidence: list[dict[str, Any]]) -> None:
    actual_hash = _license_bundle_hash({
        "schema": LICENSE_BUNDLE_SCHEMA,
        "evidence": sorted(evidence, key=lambda e: e["evidence_hash"]),
    })
    if actual_hash != expected_hash:
        raise ValueError(
            "license evidence hash mismatch: "
            f"expected {expected_hash}, got {actual_hash}")


def _validate_evidence_schema(evidence: list[dict[str, Any]]) -> None:
    for item in evidence:
        if item.get("schema") != LICENSE_EVIDENCE_SCHEMA:
            raise ValueError(
                "unsupported license evidence schema: "
                f"{item.get('schema')!r}")
        validate_evidence_hash(item)
        validate_final_evidence_source(item)
        decision = decide_license(
            license_name=item.get("license_name", ""),
            license_url=item.get("license_url", ""),
            rights_text=item.get("rights_text", ""),
            source_url=item.get("source_url", ""),
            source_id=item.get("source_id", ""),
        )
        if not decision.accepted:
            raise ValueError(
                "unsupported or unclear license evidence "
                f"{item.get('evidence_hash', '')}")


def _sample_hashes(manifest: dict[str, Any]) -> dict[str, str]:
    return {f["path"]: f["sha256"] for f in manifest.get("files", [])}


def _audit_region_evidence(manifest: dict[str, Any],
                           evidence: list[dict[str, Any]]) -> None:
    evidence_ids = {e.get("evidence_hash") for e in evidence}
    sample_hashes = _sample_hashes(manifest)
    regions = manifest.get("regions")
    if not isinstance(regions, list) or not regions:
        raise ValueError("catalog manifest missing region evidence summaries")
    _validate_evidence_schema(evidence)
    for idx, region in enumerate(regions):
        sample = region.get("sample")
        if not sample:
            raise ValueError(f"catalog region {idx} missing sample path")
        if sample not in sample_hashes:
            raise ValueError(
                f"catalog region {sample} is not pinned in manifest files")
        if region.get("sample_sha256") != sample_hashes[sample]:
            raise ValueError(
                f"catalog region {sample} sample_sha256 does not match "
                "manifest files")
        evidence_id = region.get("source_evidence_id")
        if not evidence_id:
            raise ValueError(
                f"catalog region {sample} missing source_evidence_id")
        if evidence_id not in evidence_ids:
            raise ValueError(
                f"catalog region {sample} references unknown source evidence")


def _is_guitar_instrument(instrument: str | None) -> bool:
    return "guitar" in (instrument or "").lower()


def _normalize_mechanics(value: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    out: dict[str, Any] = {}
    for key in ("string", "fret", "tuning", "position", "session"):
        if value.get(key) is not None:
            out[key] = value[key]
    if "session" not in out and value.get("session_id") is not None:
        out["session"] = value["session_id"]
    if not out:
        return None
    return {"status": "source_proven", **out}


def _unavailable_mechanics() -> dict[str, str]:
    return {
        "status": "unavailable",
        "reason": "source_metadata_absent",
    }


def _mechanics_for_region(sample: str, instrument: str,
                          sample_mechanics: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    mechanics = _normalize_mechanics(sample_mechanics.get(sample))
    if mechanics is not None:
        return mechanics
    if _is_guitar_instrument(instrument):
        return _unavailable_mechanics()
    return None


def _loop_candidate_for_region(
        sample: str,
        sample_loop_candidates: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    candidate = sample_loop_candidates.get(sample)
    if not isinstance(candidate, dict):
        return None
    return {
        "status": "review_required",
        "reason": "loop_candidate_not_emitted_without_review",
        "start_sample": candidate.get("start_sample"),
        "end_sample": candidate.get("end_sample"),
        "start_s": candidate.get("start_s"),
        "end_s": candidate.get("end_s"),
        "confidence": candidate.get("confidence"),
    }


def _loop_not_emitted(loop_mode: Any) -> bool:
    return loop_mode in (None, "no_loop")


def _round_robin_for_region(instrument: str, articulation: str,
                            region: Any) -> dict[str, Any] | None:
    if int(getattr(region, "seq_length", 1) or 1) <= 1:
        return None
    return {
        "group": (
            f"{instrument}::{articulation}::"
            f"pitch{region.pitch_keycenter}::"
            f"keys{region.lokey}-{region.hikey}::"
            f"vel{region.lovel}-{region.hivel}"
        ),
        "index": int(region.seq_position),
        "size": int(region.seq_length),
    }


def _sample_analysis_index(
        records: list[dict[str, Any]] | None) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for record in records or []:
        schema = record.get("schema", ANALYSIS_SCHEMA)
        if schema != ANALYSIS_SCHEMA:
            raise ValueError(
                f"unsupported sample catalog analysis schema: {schema!r}")
        path = record.get("path")
        if not path:
            continue
        sample = f"samples/{Path(path).name}"
        out[sample] = record
    return out


def _quality_for_region(
        sample: str,
        sample_analysis_records: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    record = sample_analysis_records.get(sample)
    if not record:
        return None
    return {
        "analysis_schema": record.get("schema", ANALYSIS_SCHEMA),
        "quality_score": record.get("quality_score"),
        "pitch_confidence": record.get("pitch_confidence"),
        "status": record.get("status"),
    }


def _diagnostics_for_region(
        sample: str,
        sample_analysis_records: dict[str, dict[str, Any]]) -> dict[str, list[Any]] | None:
    record = sample_analysis_records.get(sample)
    if not record:
        return None
    return {
        "rejection_reasons": list(record.get("rejection_reasons", [])),
        "warnings": list(record.get("warnings", [])),
    }


def _sample_identity(
        directory: Path,
        sample: str,
        sample_sha256: str | None,
        source_evidence_id: str | None,
        license_evidence_hash: str | None) -> dict[str, Any]:
    path = directory / sample
    return {
        "sample": sample,
        "byte_size": path.stat().st_size if path.is_file() else None,
        "sample_sha256": sample_sha256,
        "source_evidence_id": source_evidence_id,
        "license_evidence_hash": license_evidence_hash,
    }


def _coverage_for_region(region: dict[str, Any]) -> dict[str, Any]:
    return {
        "instrument": region.get("instrument"),
        "articulation": region.get("articulation"),
        "keycenter_midi": region.get("pitch_keycenter"),
        "key_range": [region.get("lokey"), region.get("hikey")],
        "velocity_range": [region.get("lovel"), region.get("hivel")],
        "round_robin": region.get("round_robin") or {
            "group": None,
            "index": None,
            "size": 1,
        },
        "loop": {
            "mode": region.get("loop_mode") or "no_loop",
            "start": region.get("loop_start"),
            "end": region.get("loop_end"),
            "candidate_withheld": "loop_candidate" in region,
        },
    }


def validate_region_coverages(manifest: dict[str, Any]) -> None:
    for idx, region in enumerate(manifest.get("regions", [])):
        sample = region.get("sample") or idx
        coverage = region.get("coverage")
        if not isinstance(coverage, dict):
            raise ValueError(
                f"catalog region {sample} missing coverage")
        expected = _coverage_for_region(region)
        if coverage != expected:
            raise ValueError(
                f"catalog region {sample} coverage does not match manifest")


def _catalog_instrument_diagnostics(instrument: Any) -> dict[str, Any]:
    samples = instrument.samples or {}
    out: dict[str, Any] = {
        "id": instrument.id,
        "sfz": instrument.sfz,
        "category": instrument.category,
        "articulation": instrument.articulation,
        "renderable": bool(instrument.renderable),
        "render_blockers": list(instrument.render_blockers),
        "ignored_opcodes": list(instrument.ignored_opcodes),
        "missing_samples": list(instrument.missing_samples),
        "sample_formats": list(samples.get("formats", [])),
        "sample_counts": {
            "unique": samples.get("unique", 0),
            "present": samples.get("present", 0),
            "missing": samples.get("missing", 0),
        },
        "key_range": dict(instrument.key_range),
        "pitch_keycenters": list(instrument.pitch_keycenters),
        "velocity_layers": list(instrument.velocity_layers),
        "round_robin_max": int(instrument.round_robin_max),
        "uses_include": bool(instrument.uses_include),
        "regions": int(instrument.regions),
    }
    if instrument.parse_error:
        out["parse_error"] = instrument.parse_error
    return out


def _catalog_diagnostics(directory: str | Path) -> dict[str, Any]:
    catalog = Catalog.build(directory)
    instruments = sorted(
        (_catalog_instrument_diagnostics(i) for i in catalog.instruments),
        key=lambda i: (i["sfz"], i["id"], i["articulation"]),
    )
    blockers = sorted({
        blocker
        for instrument in instruments
        for blocker in instrument["render_blockers"]
    })
    ignored_opcodes = sorted({
        opcode
        for instrument in instruments
        for opcode in instrument["ignored_opcodes"]
    })
    return {
        "instrument_count": len(instruments),
        "renderable_count": sum(1 for i in instruments if i["renderable"]),
        "blocked_count": sum(1 for i in instruments if not i["renderable"]),
        "renderable_instruments": [
            {"id": i["id"], "sfz": i["sfz"]}
            for i in instruments
            if i["renderable"]
        ],
        "blocked_instruments": [
            {
                "id": i["id"],
                "sfz": i["sfz"],
                "render_blockers": i["render_blockers"],
                "missing_samples": i["missing_samples"],
                "ignored_opcodes": i["ignored_opcodes"],
                "sample_formats": i["sample_formats"],
                **({"parse_error": i["parse_error"]}
                   if "parse_error" in i else {}),
            }
            for i in instruments
            if not i["renderable"]
        ],
        "render_blockers": blockers,
        "ignored_opcodes": ignored_opcodes,
        "instruments": instruments,
    }


def validate_catalog_diagnostics(manifest: dict[str, Any],
                                 directory: str | Path) -> None:
    diagnostics = manifest.get("catalog_diagnostics")
    if not isinstance(diagnostics, dict):
        raise ValueError("catalog manifest missing catalog_diagnostics")
    expected = _catalog_diagnostics(directory)
    if diagnostics != expected:
        raise ValueError("catalog_diagnostics does not match catalog files")


def validate_region_sample_identities(manifest: dict[str, Any],
                                      root: str | Path | None = None) -> None:
    sample_hashes = _sample_hashes(manifest)
    root_path = Path(root) if root is not None else None
    for idx, region in enumerate(manifest.get("regions", [])):
        sample = region.get("sample")
        identity = region.get("sample_identity")
        label = sample or idx
        if not isinstance(identity, dict):
            raise ValueError(
                f"catalog region {label} missing sample_identity")
        expected = {
            "sample": sample,
            "byte_size": identity.get("byte_size"),
            "sample_sha256": sample_hashes.get(sample),
            "source_evidence_id": region.get("source_evidence_id"),
            "license_evidence_hash": manifest.get("license_evidence_hash"),
        }
        if root_path is not None and sample:
            path = root_path / sample
            if path.is_file():
                expected["byte_size"] = path.stat().st_size
        if identity != expected:
            raise ValueError(
                f"catalog region {label} sample_identity does not match manifest")


def _library_pin(manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": manifest.get("name"),
        "version": manifest.get("version", ""),
        "manifest_sha256": manifest.get("manifest_sha256"),
        "builder_version": manifest.get("builder_version"),
    }


def attach_region_library_pins(manifest: dict[str, Any]) -> None:
    pin = _library_pin(manifest)
    for region in manifest.get("regions", []):
        region["library_pin"] = dict(pin)


def validate_region_library_pins(manifest: dict[str, Any]) -> None:
    expected = _library_pin(manifest)
    for idx, region in enumerate(manifest.get("regions", [])):
        pin = region.get("library_pin")
        sample = region.get("sample") or idx
        if pin != expected:
            raise ValueError(
                f"catalog region {sample} library_pin does not match manifest")


def audit_region_mechanics(manifest: dict[str, Any]) -> None:
    for idx, region in enumerate(manifest.get("regions", [])):
        if not _is_guitar_instrument(region.get("instrument")):
            continue
        sample = region.get("sample") or idx
        mechanics = region.get("mechanics")
        if not isinstance(mechanics, dict):
            raise ValueError(
                f"catalog region {sample} missing guitar mechanics metadata")
        status = mechanics.get("status")
        if status == "source_proven":
            if not any(mechanics.get(k) is not None
                       for k in ("string", "fret", "tuning", "position",
                                 "session")):
                raise ValueError(
                    f"catalog region {sample} has empty guitar mechanics metadata")
        elif status == "unavailable":
            if mechanics.get("reason") != "source_metadata_absent":
                raise ValueError(
                    f"catalog region {sample} has invalid mechanics absence reason")
        else:
            raise ValueError(
                f"catalog region {sample} has invalid mechanics status")


def validate_approved_review_metadata(manifest: dict[str, Any]) -> None:
    review = manifest.get("review")
    if not isinstance(review, dict):
        raise ValueError("approved catalog missing review metadata")
    if review.get("status") != "approved":
        raise ValueError("approved catalog review status is not approved")
    if not str(review.get("reviewer") or "").strip():
        raise ValueError("approved catalog review reviewer is required")
    reviewed_at = str(review.get("reviewed_at") or "").strip()
    if not reviewed_at:
        raise ValueError("approved catalog reviewed_at is required")
    try:
        parsed = datetime.fromisoformat(reviewed_at.replace("Z", "+00:00"))
    except ValueError as e:
        raise ValueError("approved catalog reviewed_at must be ISO-8601") from e
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("approved catalog reviewed_at must include timezone")


def validate_builder_version(manifest: dict[str, Any]) -> None:
    builder_version = manifest.get("builder_version")
    if builder_version != SAMPLE_CATALOG_BUILDER_VERSION:
        raise ValueError(
            "unsupported sample catalog builder version: "
            f"{builder_version!r}")


def _region_summary(directory: Path, manifest: dict[str, Any],
                    evidence: list[dict[str, Any]],
                    sample_evidence_ids: dict[str, str] | None = None,
                    sample_mechanics: dict[str, dict[str, Any]] | None = None,
                    sample_loop_candidates: dict[str, dict[str, Any]] | None = None,
                    sample_analysis_records: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    from audioforge.sampler import parse_sfz

    evidence_ids = sorted(e["evidence_hash"] for e in evidence)
    evidence_id = evidence_ids[0] if len(evidence_ids) == 1 else None
    sample_evidence_ids = sample_evidence_ids or {}
    sample_mechanics = sample_mechanics or {}
    sample_loop_candidates = sample_loop_candidates or {}
    sample_analysis = _sample_analysis_index(sample_analysis_records)
    hashes = _sample_hashes(manifest)
    rows = []
    for instrument, spec in sorted(manifest["instruments"].items()):
        arts = spec.get("articulations", {}) or {"sustain": spec["sfz"]}
        for articulation, sfz_rel in sorted(arts.items()):
            text = (directory / sfz_rel).read_text(encoding="utf-8")
            regions, ignored = parse_sfz(text)
            if ignored:
                raise ValueError(
                    f"generated SFZ has ignored opcodes: {sorted(ignored)}")
            prefix = Path(sfz_rel).parent.as_posix()
            prefix = "" if prefix == "." else prefix + "/"
            for r in regions:
                sample = (prefix + r.sample).replace("//", "/")
                source_evidence_id = sample_evidence_ids.get(sample) or evidence_id
                if evidence and not source_evidence_id:
                    raise ValueError(
                        f"sample {sample} is missing source evidence id")
                row = {
                    "instrument": instrument,
                    "articulation": articulation,
                    "sample": sample,
                    "sample_sha256": hashes.get(sample),
                    "pitch_keycenter": r.pitch_keycenter,
                    "lokey": r.lokey,
                    "hikey": r.hikey,
                    "lovel": r.lovel,
                    "hivel": r.hivel,
                    "loop_mode": r.loop_mode,
                    "loop_start": r.loop_start,
                    "loop_end": r.loop_end,
                    "source_evidence_id": source_evidence_id,
                }
                round_robin = _round_robin_for_region(
                    instrument, articulation, r)
                if round_robin is not None:
                    row["round_robin"] = round_robin
                quality = _quality_for_region(sample, sample_analysis)
                if quality is not None:
                    row["quality"] = quality
                diagnostics = _diagnostics_for_region(sample, sample_analysis)
                if diagnostics is not None:
                    row["diagnostics"] = diagnostics
                mechanics = _mechanics_for_region(
                    sample, instrument, sample_mechanics)
                if mechanics is not None:
                    row["mechanics"] = mechanics
                loop_candidate = _loop_candidate_for_region(
                    sample, sample_loop_candidates)
                if loop_candidate is not None and _loop_not_emitted(r.loop_mode):
                    row["loop_candidate"] = loop_candidate
                row["sample_identity"] = _sample_identity(
                    directory, sample, row["sample_sha256"],
                    source_evidence_id, manifest.get("license_evidence_hash"))
                row["coverage"] = _coverage_for_region(row)
                rows.append(row)
    return sorted(rows, key=lambda r: (
        r["instrument"], r["articulation"], r["pitch_keycenter"],
        r["lovel"], r["sample"]))


def write_license_bundle(evidence: list[dict[str, Any]], path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not evidence:
        raise ValueError("license evidence bundle cannot be empty")
    _validate_evidence_schema(evidence)
    bundle = {
        "schema": LICENSE_BUNDLE_SCHEMA,
        "evidence": sorted(evidence, key=lambda e: e["evidence_hash"]),
    }
    bundle["license_evidence_hash"] = _license_bundle_hash(bundle)
    path.write_text(json.dumps(bundle, indent=2, sort_keys=True) + "\n")
    return path


def write_library_manifest(directory: str | Path, *, name: str, version: str,
                           instrument: str, license_str: str = "CC0",
                           catalog_state: str = "candidate",
                           license_evidence_hash: str | None = None,
                           license_evidence: list[dict[str, Any]] | None = None,
                           sample_evidence_ids: dict[str, str] | None = None,
                           sample_mechanics: dict[str, dict[str, Any]] | None = None,
                           sample_loop_candidates: dict[str, dict[str, Any]] | None = None,
                           sample_analysis_records: list[dict[str, Any]] | None = None,
                           articulations: dict[str, str] | None = None,
                           analysis_summary: dict[str, Any] | None = None,
                           review: dict[str, Any] | None = None) -> dict[str, Any]:
    if catalog_state not in {"candidate", "approved"}:
        raise ValueError("catalog_state must be candidate or approved")
    expected_evidence_hash = _require_evidence_hash(license_evidence_hash)
    if license_evidence is None:
        bundle_path = Path(directory) / "LICENSES.json"
        if bundle_path.is_file():
            license_evidence = json.loads(bundle_path.read_text()).get("evidence", [])
    if not license_evidence:
        raise ValueError("license evidence is required")
    _validate_evidence_schema(license_evidence)
    _verify_license_evidence_hash(expected_evidence_hash, license_evidence)
    articulations = articulations or {"sustain": "instrument.sfz"}
    for art, sfz_rel in articulations.items():
        sfz = Path(directory) / sfz_rel
        if not sfz.is_file():
            raise ValueError(f"missing generated SFZ for {art}: {sfz}")
    samples = Path(directory) / "samples"
    if not samples.is_dir() or not any(samples.iterdir()):
        raise ValueError(f"missing generated samples: {samples}")
    default_sfz = articulations.get("sustain") or next(iter(articulations.values()))
    instruments = {
        instrument: {
            "sfz": default_sfz,
            "articulations": articulations,
        }
    }
    manifest = generate_manifest(
        directory,
        name=name,
        version=version,
        license_str=license_str,
        instruments=instruments,
    )
    manifest.update({
        "builder_version": SAMPLE_CATALOG_BUILDER_VERSION,
        "catalog_state": catalog_state,
        "license_evidence_hash": license_evidence_hash,
        "analysis_summary": analysis_summary or {},
        "review": review or {"status": "pending"},
    })
    manifest["regions"] = _region_summary(
        Path(directory), manifest, license_evidence or [], sample_evidence_ids,
        sample_mechanics, sample_loop_candidates, sample_analysis_records)
    manifest["catalog_diagnostics"] = _catalog_diagnostics(directory)
    audit_region_mechanics(manifest)
    manifest["manifest_sha256"] = _canonical_manifest_hash(manifest)
    attach_region_library_pins(manifest)
    path = Path(directory) / "library.manifest.json"
    path.write_text(json.dumps(manifest, indent=1, sort_keys=True) + "\n")
    return manifest


def audit_catalog(directory: str | Path, *, require_approved: bool = False) -> dict[str, Any]:
    directory = Path(directory)
    mp = directory / "library.manifest.json"
    if not mp.is_file():
        raise ValueError(f"missing manifest: {mp}")
    manifest = json.loads(mp.read_text())
    if not manifest.get("license_evidence_hash"):
        raise ValueError("catalog manifest missing license_evidence_hash")
    validate_builder_version(manifest)
    licenses = directory / "LICENSES.json"
    if not licenses.is_file():
        raise ValueError("catalog missing LICENSES.json")
    bundle = json.loads(licenses.read_text())
    if (bundle.get("schema") != LICENSE_BUNDLE_SCHEMA
            or not isinstance(bundle.get("evidence"), list)):
        raise ValueError("catalog license evidence bundle is malformed")
    actual_bundle_hash = _license_bundle_hash(bundle)
    if actual_bundle_hash != manifest["license_evidence_hash"]:
        raise ValueError("catalog license evidence hash mismatch")
    _audit_region_evidence(manifest, bundle["evidence"])
    audit_region_mechanics(manifest)
    validate_region_coverages(manifest)
    validate_catalog_diagnostics(manifest, directory)
    if require_approved:
        if manifest.get("catalog_state") != "approved":
            raise ValueError("catalog is not approved")
        validate_approved_review_metadata(manifest)
    validate_region_library_pins(manifest)
    if not require_approved:
        validate_region_sample_identities(manifest, directory)

    add_library_path(directory.parent)
    load_library({
        "name": manifest["name"],
        "manifest_sha256": manifest["manifest_sha256"],
    }, require_approved=require_approved)
    if require_approved:
        validate_region_sample_identities(manifest, directory)
    cat = Catalog.build(directory)
    renderable = [i.to_dict() for i in cat.renderable()]
    if not renderable:
        raise ValueError("catalog has no renderable instruments")
    return {
        "ok": True,
        "manifest_sha256": manifest["manifest_sha256"],
        "catalog_state": manifest.get("catalog_state"),
        "renderable_instruments": renderable,
    }


def copy_samples(sample_paths: list[str | Path], samples_dir: str | Path) -> list[Path]:
    samples_dir = Path(samples_dir)
    samples_dir.mkdir(parents=True, exist_ok=True)
    out = []
    for src in sample_paths:
        src = Path(src)
        dst = samples_dir / src.name
        if src.resolve() != dst.resolve():
            shutil.copyfile(src, dst)
        out.append(dst)
    return out
