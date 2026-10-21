"""Distribution gate: an installed AudioForge must be able to render.

Every render compiles `audioforge/native/*.c` on demand (ADR-0012) and the
shipped samples/impulse responses are resolved by name. If either is missing
from the wheel, `pip install audioforge` yields an engine that cannot render at
all — a defect invisible to an in-repo test run. These tests pin the packaging
contract statically (fast, no build); `make package-check` and the CI `package`
job prove it end to end by building, installing into a clean venv and
rendering from outside the repository.
"""
from __future__ import annotations

import fnmatch
import io
import sys
import tarfile
import zipfile
from pathlib import Path

import pytest

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover - exercised on the 3.10 CI leg
    import tomli as tomllib

from audioforge import samples
from audioforge.tools import package_check, release_notes

ROOT = Path(__file__).resolve().parent.parent
PACKAGE = ROOT / "audioforge"


def _package_data_globs() -> list[str]:
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return data["tool"]["setuptools"]["package-data"]["audioforge"]


def test_every_runtime_data_file_is_declared_package_data():
    globs = _package_data_globs()
    required = package_check.required_package_data(ROOT)
    undeclared = [rel for rel in required
                  if not any(fnmatch.fnmatch(rel, g) for g in globs)]
    assert not undeclared, (
        f"files under audioforge/ that the wheel would drop: {undeclared}; "
        f"add a [tool.setuptools.package-data] glob")


def test_required_package_data_includes_every_native_kernel_source():
    required = set(package_check.required_package_data(ROOT))
    kernels = {f"native/{p.name}" for p in (PACKAGE / "native").glob("*.c")}
    assert kernels and kernels <= required


def test_required_package_data_ignores_caches_and_python(tmp_path):
    pkg = tmp_path / "audioforge"
    (pkg / "native").mkdir(parents=True)
    (pkg / "__pycache__").mkdir()
    (pkg / "native" / "k.c").write_text("int x;")
    (pkg / "mod.py").write_text("")
    (pkg / "__pycache__" / "mod.cpython-312.pyc").write_bytes(b"")
    (pkg / "native" / "k_abc.so").write_bytes(b"")
    assert package_check.required_package_data(tmp_path) == ["native/k.c"]


def test_bundled_samples_live_inside_the_package():
    bundled = samples.BUNDLED_SAMPLES
    assert bundled.is_dir()
    assert PACKAGE in bundled.parents
    names = {p.name for p in bundled.iterdir()}
    assert {"stalbans_ortf_ir.wav", "stalbans_ortf_ir.ATTRIBUTION.txt"} <= names


def test_bundled_samples_resolve_from_any_working_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    data = samples._find_bytes("stalbans_ortf_ir.wav")
    assert data[:4] == b"RIFF"


def test_working_directory_samples_override_bundled(tmp_path, monkeypatch):
    (tmp_path / "samples").mkdir()
    (tmp_path / "samples" / "stone_room_ir.wav").write_bytes(b"local")
    monkeypatch.chdir(tmp_path)
    assert samples._find_bytes("stone_room_ir.wav") == b"local"


def _zip(path: Path, names: list[str]) -> Path:
    with zipfile.ZipFile(path, "w") as z:
        for n in names:
            z.writestr(n, b"")
    return path


def _tar(path: Path, names: list[str]) -> Path:
    with tarfile.open(path, "w:gz") as t:
        for n in names:
            info = tarfile.TarInfo(n)
            t.addfile(info, io.BytesIO(b""))
    return path


def test_wheel_missing_reports_absent_entries(tmp_path):
    whl = _zip(tmp_path / "a.whl", ["audioforge/__init__.py", "audioforge/native/dsp.c"])
    assert package_check.missing_from_dist(whl, ["native/dsp.c", "native/upfirdn.c"]) == [
        "native/upfirdn.c"]


def test_sdist_missing_strips_the_top_level_directory(tmp_path):
    sdist = _tar(tmp_path / "audioforge-9.9.9.tar.gz",
                 ["audioforge-9.9.9/audioforge/native/dsp.c"])
    assert package_check.missing_from_dist(sdist, ["native/dsp.c"]) == []
    assert package_check.missing_from_dist(sdist, ["data/samples/x.wav"]) == [
        "data/samples/x.wav"]


def test_missing_from_dist_rejects_unknown_formats(tmp_path):
    bogus = tmp_path / "a.egg"
    bogus.write_bytes(b"")
    with pytest.raises(ValueError):
        package_check.missing_from_dist(bogus, [])


def test_find_dists_requires_exactly_one_wheel_and_sdist(tmp_path):
    with pytest.raises(FileNotFoundError):
        package_check.find_dists(tmp_path)
    _zip(tmp_path / "audioforge-1.0.0-py3-none-any.whl", [])
    _tar(tmp_path / "audioforge-1.0.0.tar.gz", [])
    wheel, sdist = package_check.find_dists(tmp_path)
    assert wheel.suffix == ".whl" and sdist.name.endswith(".tar.gz")


def test_smoke_spec_pins_the_bundled_sample_bytes():
    import hashlib
    name, sha = package_check.SMOKE_SAMPLE
    assert hashlib.sha256((samples.BUNDLED_SAMPLES / name).read_bytes()).hexdigest() == sha
    assert name in package_check.smoke_source() and sha in package_check.smoke_source()


def test_smoke_spec_renders_in_process(tmp_path, monkeypatch):
    from audioforge import AudioForge
    monkeypatch.chdir(tmp_path)
    result = AudioForge().compile(package_check.smoke_source())
    assert result.ok, result.diagnostics
    result.assets[0].export(tmp_path / "out")
    assert list((tmp_path / "out").rglob("*.wav"))


CHANGELOG = """# Changelog

## [Unreleased]

## [9.1.0] - 2026-10-21

_Engine 9.1.0 · DSL 2.0._

### Added
- thing

## [9.0.0]

- older
"""


def test_release_notes_extracts_one_section():
    body = release_notes.section(CHANGELOG, "9.1.0")
    assert body.startswith("_Engine 9.1.0")
    assert "- thing" in body and "older" not in body


def test_release_notes_rejects_missing_or_empty_sections():
    with pytest.raises(LookupError):
        release_notes.section(CHANGELOG, "8.0.0")
    with pytest.raises(LookupError):
        release_notes.section(CHANGELOG, "Unreleased")


def test_tag_version_parses_engine_tags_only():
    assert release_notes.tag_version("engine-3.3.0") == "3.3.0"
    assert release_notes.tag_version("refs/tags/engine-3.3.0") == "3.3.0"
    for bad in ("v3.3.0", "engine-3.3", "dsl-2.0"):
        with pytest.raises(ValueError):
            release_notes.tag_version(bad)


def test_release_notes_cli_refuses_a_tag_that_disagrees_with_version_py(capsys):
    assert release_notes.main(["--tag", "engine-0.0.1"]) == 1
    assert "ENGINE_VERSION" in capsys.readouterr().err


def test_release_notes_cli_prints_the_current_version_section(capsys):
    from audioforge.version import ENGINE_VERSION
    assert release_notes.main(["--tag", f"engine-{ENGINE_VERSION}"]) == 0
    assert f"Engine {ENGINE_VERSION}" in capsys.readouterr().out
