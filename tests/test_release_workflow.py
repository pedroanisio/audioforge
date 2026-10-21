"""CI/CD contract for distributions (parsing only; no workflow is executed).

The `ci` workflow must prove on every push/PR that the built wheel installs and
renders (`make package-check`), and the `release` workflow must only publish
from an `engine-X.Y.Z` tag that agrees with `audioforge/version.py`, after the
same package gate, with the CHANGELOG section as the release body.
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
WORKFLOWS = REPO / ".github" / "workflows"


def _load(name: str) -> dict:
    return yaml.safe_load((WORKFLOWS / name).read_text(encoding="utf-8"))


def _triggers(wf: dict) -> dict:
    return wf.get("on", wf.get(True))  # PyYAML parses bare `on:` as True


def _runs(job: dict) -> list[str]:
    return [s["run"] for s in job.get("steps", []) if isinstance(s.get("run"), str)]


def test_ci_has_a_package_job_running_the_package_gate():
    jobs = _load("ci.yml")["jobs"]
    assert "package" in jobs
    assert any(re.search(r"\bmake\b.*\bpackage-check\b", r) for r in _runs(jobs["package"]))


def test_workflows_can_be_dispatched_manually():
    for name in ("ci.yml", "release.yml"):
        assert "workflow_dispatch" in _triggers(_load(name)), name


def test_release_triggers_on_engine_tags_only():
    tags = _triggers(_load("release.yml"))["push"]["tags"]
    assert tags == ["engine-*"]


def test_release_gates_tag_builds_checks_and_publishes_in_order():
    wf = _load("release.yml")
    assert wf.get("permissions", {}).get("contents") == "write"
    runs = "\n".join(r for job in wf["jobs"].values() for r in _runs(job))
    order = [
        r"audioforge\.tools\.release_notes --tag",
        r"audioforge\.tools\.bump_version --check",
        r"(uv build|python -m build)",
        r"audioforge\.tools\.package_check --dist",
        r"gh release (create|upload)",
    ]
    positions = []
    for pattern in order:
        m = re.search(pattern, runs)
        assert m, f"release workflow never runs /{pattern}/"
        positions.append(m.start())
    assert positions == sorted(positions), "release steps are out of order"


def test_release_runs_the_ci_gate_before_publishing():
    """The release reuses ci.yml (not a hand-mirrored copy of it, AF-R01) and
    publishes only after that gate — `make check` plus the package job — passes."""
    assert "workflow_call" in _triggers(_load("ci.yml"))
    jobs = _load("release.yml")["jobs"]
    gates = [n for n, j in jobs.items() if j.get("uses") == "./.github/workflows/ci.yml"]
    assert gates, "release.yml must call ./.github/workflows/ci.yml"
    publishing = [j for j in jobs.values() if any("gh release" in r for r in _runs(j))]
    assert publishing
    for job in publishing:
        needs = job.get("needs", [])
        needs = [needs] if isinstance(needs, str) else needs
        assert set(gates) <= set(needs), "publishing job must `needs:` the CI gate"


def test_makefile_exposes_package_check():
    text = (REPO / "Makefile").read_text(encoding="utf-8")
    assert re.search(r"^package-check\s*:", text, re.M)
    assert "audioforge.tools.package_check" in text
