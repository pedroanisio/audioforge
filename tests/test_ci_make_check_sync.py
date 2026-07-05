"""Regression gate binding CI to the local gate (roadmap item AF-R01).

The point of AF-R01 is that CI runs the *exact same* composed gate a developer
runs locally: `make check`. This test asserts a CI workflow literally invokes
`make check`, so CI can never silently diverge from the local gate by
hand-mirroring an out-of-date target list. Because CI calls the composed target
(not the individual gates), keeping CI in sync with `make check` is automatic —
this test only has to prove the call exists and the entrypoint is wired.

Parsing only (PyYAML); no workflow is executed.
"""
from __future__ import annotations

import re
from pathlib import Path

# Hard import (not importorskip): PyYAML is a declared dev dependency
# (pyproject `[project.optional-dependencies].dev`). If it is missing the test
# env is broken and this must fail LOUDLY at collection — a silent skip here
# would be a hole in the very gate this test exists to protect.
import yaml

REPO = Path(__file__).resolve().parent.parent
WORKFLOWS = REPO / ".github" / "workflows"
MAKEFILE = REPO / "Makefile"

_MAKE_CHECK_RE = re.compile(r"\bmake\b[^\n]*\bcheck\b")


def _load_workflows() -> list[tuple[Path, dict]]:
    assert WORKFLOWS.is_dir(), ".github/workflows/ is missing (AF-R01)"
    docs: list[tuple[Path, dict]] = []
    for path in sorted(WORKFLOWS.glob("*.yml")) + sorted(WORKFLOWS.glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            docs.append((path, data))
    return docs


def _run_steps(workflow: dict) -> list[str]:
    steps: list[str] = []
    for job in (workflow.get("jobs") or {}).values():
        if not isinstance(job, dict):
            continue
        for step in job.get("steps") or []:
            if isinstance(step, dict) and isinstance(step.get("run"), str):
                steps.append(step["run"])
    return steps


def _workflows_invoking_make_check() -> list[Path]:
    hits = []
    for path, wf in _load_workflows():
        if any(_MAKE_CHECK_RE.search(run) for run in _run_steps(wf)):
            hits.append(path)
    return hits


def test_a_workflow_invokes_make_check():
    hits = _workflows_invoking_make_check()
    assert hits, (
        "no CI workflow runs `make check` — CI must call the same composed gate "
        "developers run locally (AF-R01)"
    )


def test_ci_workflow_triggers_on_push_and_pr():
    """The gate workflow must fire on both push and pull_request, else merges
    can bypass it."""
    for path in _workflows_invoking_make_check():
        wf = yaml.safe_load(path.read_text(encoding="utf-8"))
        # PyYAML parses the bare `on:` key as the boolean True.
        triggers = wf.get("on", wf.get(True))
        assert isinstance(triggers, dict), f"{path.name}: `on:` must map triggers"
        assert "push" in triggers, f"{path.name}: gate must trigger on push"
        assert "pull_request" in triggers, f"{path.name}: gate must trigger on pull_request"


def test_ci_calls_a_real_makefile_target():
    """The target CI invokes (`check`) must actually exist in the Makefile —
    the cross-file half of the anti-drift contract."""
    assert MAKEFILE.is_file(), "Makefile missing; CI would call a nonexistent target"
    text = MAKEFILE.read_text(encoding="utf-8")
    assert re.search(r"^check\s*:", text, re.MULTILINE), (
        "Makefile has no `check` target for CI to invoke"
    )
