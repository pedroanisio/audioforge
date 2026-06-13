import ast
import hashlib
import importlib
import json
import math
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np
import pytest

from audioforge import cli
from audioforge.sample_catalog.analyze import analyze_sample
from audioforge.sample_catalog.licenses import make_evidence
from audioforge.sample_catalog.manifest import (
    copy_samples,
    write_library_manifest,
    write_license_bundle,
)
from audioforge.sample_catalog.review import promote_candidate
from audioforge.sample_catalog.sfz import build_regions, write_sfz


RUNTIME_BOUNDARY_MODULES = (
    "audioforge/library.py",
    "audioforge/sampler.py",
    "audioforge/render.py",
    "audioforge/sdk.py",
)
NETWORK_SAMPLE_CATALOG_MODULES = {
    "audioforge.sample_catalog.download",
    "audioforge.sample_catalog.sources",
}


def _sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _imported_modules(path: str) -> set[str]:
    tree = ast.parse(Path(path).read_text(encoding="utf-8"), filename=path)
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            level_prefix = "." * int(node.level or 0)
            imported.add(level_prefix + node.module)
    return imported


def _wav(path, freq=261.625565, sr=44100):
    t = np.arange(int(sr * 0.25)) / sr
    x = np.sin(2 * math.pi * freq * t) * 0.3
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((x * 32767).astype("<i2").tobytes())


def _candidate_dir(tmp_path):
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
    write_library_manifest(
        candidate,
        name="strict-guitar",
        version="1.0.0",
        instrument="guitar",
        license_evidence_hash=bundle_hash,
    )
    return candidate


def test_license_bundle_and_manifest_fail_closed_without_evidence(tmp_path):
    with pytest.raises(ValueError, match="cannot be empty"):
        write_license_bundle([], tmp_path / "LICENSES.json")

    candidate = tmp_path / "candidate"
    candidate.mkdir()
    (candidate / "samples").mkdir()
    (candidate / "samples" / "C4.wav").write_bytes(b"not-a-real-wav")
    (candidate / "instrument.sfz").write_text("<region>\nsample=samples/C4.wav\n")
    with pytest.raises(ValueError, match="license_evidence_hash is required"):
        write_library_manifest(
            candidate,
            name="bad",
            version="0.0.0",
            instrument="guitar",
            license_evidence_hash=None,
        )


def test_promotion_audits_catalog_before_copying(tmp_path):
    candidate = _candidate_dir(tmp_path)
    (candidate / "LICENSES.json").write_text("{}\n")

    with pytest.raises(ValueError, match="license evidence bundle is malformed"):
        promote_candidate(
            candidate, tmp_path / "approved", reviewer="qa",
            reviewed_at="2026-06-12T15:00:00+00:00")


def test_cli_build_sfz_rejects_empty_accepted_analysis(tmp_path, capsys):
    analysis = tmp_path / "analysis"
    analysis.mkdir()
    (analysis / "bad.json").write_text(json.dumps({
        "path": str(tmp_path / "bad.wav"),
        "sha256": "0" * 64,
        "status": "quarantine",
        "rejection_reasons": ["silence_or_near_silence"],
    }))
    evidence = tmp_path / "evidence.json"
    evidence.write_text(json.dumps(make_evidence(
        source="freesound",
        source_id="1",
        source_url="https://freesound.org/s/1/",
        download_url="https://freesound.org/apiv2/sounds/1/download/",
        license_name="CC0",
        license_url="https://creativecommons.org/publicdomain/zero/1.0/",
        fetched_at="2026-06-12T00:00:00+00:00",
    ).to_dict()))

    assert cli.main([
        "sample-catalog", "build-sfz",
        "--instrument", "guitar",
        "--analysis", str(analysis),
        "--evidence", str(evidence),
        "--out", str(tmp_path / "candidate"),
    ]) == 1
    assert "no accepted analyses" in capsys.readouterr().err


def test_cli_build_sfz_audits_generated_candidate_before_success(
        monkeypatch, tmp_path, capsys):
    sample = tmp_path / "C4.wav"
    _wav(sample)
    analysis = tmp_path / "analysis"
    analysis.mkdir()
    (analysis / "good.json").write_text(json.dumps({
        "path": str(sample),
        "sha256": _sha256(sample),
        "status": "accepted",
        "midi_note": 60,
        "quality_score": 1.0,
    }))
    evidence = tmp_path / "evidence.json"
    evidence.write_text(json.dumps(make_evidence(
        source="freesound",
        source_id="1",
        source_url="https://freesound.org/s/1/",
        download_url="https://freesound.org/apiv2/sounds/1/download/",
        license_name="CC0",
        license_url="https://creativecommons.org/publicdomain/zero/1.0/",
        fetched_at="2026-06-12T00:00:00+00:00",
    ).to_dict()))
    calls = []

    def fail_audit(path, *, require_approved=False):
        calls.append((path, require_approved))
        raise ValueError("unrenderable_sfz: catalog has no renderable instruments")

    monkeypatch.setattr(
        "audioforge.sample_catalog.manifest.audit_catalog", fail_audit)

    assert cli.main([
        "sample-catalog", "build-sfz",
        "--instrument", "guitar",
        "--analysis", str(analysis),
        "--evidence", str(evidence),
        "--out", str(tmp_path / "candidate"),
    ]) == 1

    assert calls == [(tmp_path / "candidate", False)]
    assert "unrenderable_sfz" in capsys.readouterr().err


def test_runtime_modules_do_not_import_source_or_download_adapters():
    offenders = {}
    for module_path in RUNTIME_BOUNDARY_MODULES:
        imports = _imported_modules(module_path)
        forbidden = sorted(imports & NETWORK_SAMPLE_CATALOG_MODULES)
        if forbidden:
            offenders[module_path] = forbidden

    assert offenders == {}


def test_top_level_audioforge_import_does_not_load_source_or_download_adapters():
    code = """
import importlib
import sys
importlib.import_module("audioforge")
assert "audioforge.sample_catalog.sources" not in sys.modules
assert "audioforge.sample_catalog.download" not in sys.modules
"""
    subprocess.run([sys.executable, "-c", code], check=True)


def test_library_manifest_hash_does_not_load_source_or_download_adapters():
    code = """
import importlib
import sys
library = importlib.import_module("audioforge.library")
library._canonical_manifest_hash({
    "name": "plain",
    "version": "1.0.0",
    "license": "CC0",
    "files": [],
    "instruments": {},
})
assert "audioforge.sample_catalog.sources" not in sys.modules
assert "audioforge.sample_catalog.download" not in sys.modules
"""
    subprocess.run([sys.executable, "-c", code], check=True)
