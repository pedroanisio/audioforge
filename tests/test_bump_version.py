"""Tests for the version-bump tool + consistency gate (roadmap item AF-R09)."""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from audioforge.tools import bump_version as bv

ROOT = Path(__file__).resolve().parents[1]


def test_check_passes_on_committed_tree():
    ok, report = bv.check()
    assert ok, "version sites disagree on a clean tree:\n" + "\n".join(report)


def test_truth_matches_runtime_version():
    from audioforge import version as v

    assert bv.truth() == (v.ENGINE_VERSION, v.DSL_VERSION)


def test_check_detects_pyproject_drift(tmp_path, monkeypatch):
    pj = tmp_path / "pyproject.toml"
    pj.write_text('[project]\nversion = "9.9.9"\n', encoding="utf-8")
    monkeypatch.setattr(bv, "PYPROJECT", pj)
    ok, report = bv.check()
    assert not ok and any("pyproject" in r for r in report)


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    """Copy every managed site into a tmp tree and retarget the tool at it."""
    files = {}
    for name, src in {
        "version.py": ROOT / "audioforge" / "version.py",
        "pyproject.toml": ROOT / "pyproject.toml",
        "README.md": ROOT / "README.md",
        "CHANGELOG.md": ROOT / "CHANGELOG.md",
    }.items():
        dst = tmp_path / name
        shutil.copy(src, dst)
        files[name] = dst
    monkeypatch.setattr(bv, "VERSION_PY", files["version.py"])
    monkeypatch.setattr(bv, "PYPROJECT", files["pyproject.toml"])
    monkeypatch.setattr(bv, "README", files["README.md"])
    monkeypatch.setattr(bv, "CHANGELOG", files["CHANGELOG.md"])
    return files


def test_bump_rewrites_every_site_and_stays_consistent(sandbox):
    bv.bump("2.17.0", "2.0")
    assert bv.truth() == ("2.17.0", "2.0")
    ok, report = bv.check()
    assert ok, report
    assert 'version = "2.17.0"' in sandbox["pyproject.toml"].read_text()
    assert "Engine 2.17.0" in sandbox["README.md"].read_text()
    assert "DSL 2.0" in sandbox["README.md"].read_text()


def test_bump_inserts_changelog_section(sandbox):
    bv.bump("2.17.0")
    cl = sandbox["CHANGELOG.md"].read_text()
    assert "## [2.17.0]" in cl and "## [Unreleased]" in cl
    # the new section sits directly under Unreleased
    assert cl.index("## [Unreleased]") < cl.index("## [2.17.0]") < cl.index("## [2.16.0]")


def test_dry_run_writes_nothing(sandbox):
    before = {k: p.read_text() for k, p in sandbox.items()}
    plan = bv.bump("2.17.0", dry_run=True)
    assert any("dry run" in line for line in plan)
    for k, p in sandbox.items():
        assert p.read_text() == before[k], f"{k} changed under --dry-run"


def test_bump_rejects_non_semver():
    with pytest.raises(ValueError):
        bv.bump("2.17")  # not MAJOR.MINOR.PATCH


def test_main_check_zero_on_committed_tree():
    assert bv.main(["--check"]) == 0


def test_main_check_nonzero_on_drift(tmp_path, monkeypatch, capsys):
    pj = tmp_path / "pyproject.toml"
    pj.write_text('version = "9.9.9"\n', encoding="utf-8")
    monkeypatch.setattr(bv, "PYPROJECT", pj)
    assert bv.main(["--check"]) == 1
    assert "!=" in capsys.readouterr().err


def test_main_dry_run(sandbox, capsys):
    assert bv.main(["2.18.0", "--dry-run"]) == 0
    assert "2.18.0" in capsys.readouterr().out
    assert bv.truth() == ("2.16.0", "1.9")  # unchanged
