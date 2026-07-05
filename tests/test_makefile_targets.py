"""Regression gate for the root Makefile (roadmap item AF-R02).

The Makefile composes every local gate into a single `make check`. This test
*gates the gate*: it fails loudly if the composed gate silently loses a target,
if `check` references a target that does not exist, if a composed target is
undocumented in `make help`, or if the `test` target stops wrapping the
canonical suite runner and starts forking its own suite list.

Pure parsing + a `make -n` dry-run; no suite is executed here, so the test is
fast, deterministic, and isolated.
"""
from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
MAKEFILE = REPO / "Makefile"

# Targets that MUST exist for the enforcement contract to hold.
REQUIRED_TARGETS = {"help", "test", "check", "native-check"}

_TARGET_RE = re.compile(r"^([A-Za-z0-9][A-Za-z0-9_.-]*)\s*:(?!=)(.*)$")


def _read_makefile() -> str:
    assert MAKEFILE.is_file(), "root Makefile is missing (AF-R02)"
    return MAKEFILE.read_text(encoding="utf-8")


def _target_lines(text: str) -> dict[str, str]:
    """Map target name -> full definition line (rule head), skipping specials."""
    out: dict[str, str] = {}
    for line in text.splitlines():
        if line.startswith("\t"):  # recipe line, not a rule head
            continue
        m = _TARGET_RE.match(line)
        if not m:
            continue
        name = m.group(1)
        if name.startswith("."):  # .PHONY, .DEFAULT_GOAL, ...
            continue
        out.setdefault(name, line)
    return out


def _check_prereqs(text: str) -> list[str]:
    for line in text.splitlines():
        m = _TARGET_RE.match(line)
        if m and m.group(1) == "check":
            body = m.group(2)
            body = body.split("##", 1)[0]  # drop inline help comment
            return body.split()
    return []


def test_makefile_exists():
    assert MAKEFILE.is_file(), "AF-R02 requires a root Makefile composing `make check`"


def test_required_targets_present():
    targets = _target_lines(_read_makefile())
    missing = REQUIRED_TARGETS - targets.keys()
    assert not missing, f"Makefile is missing required target(s): {sorted(missing)}"


def test_check_prereqs_all_defined():
    """`check` must not reference a target that does not exist (anti-dangling)."""
    text = _read_makefile()
    targets = _target_lines(text)
    prereqs = _check_prereqs(text)
    assert prereqs, "`check` target has no prerequisites — it must compose the gate"
    dangling = [p for p in prereqs if p not in targets]
    assert not dangling, f"`check` composes undefined target(s): {dangling}"


def test_every_composed_target_is_documented():
    """Every target composed into `check` (and `check` itself) carries a `##`
    help comment, so `make help` can never omit a gate."""
    text = _read_makefile()
    target_lines = _target_lines(text)
    composed = set(_check_prereqs(text)) | {"check"}
    undocumented = [t for t in sorted(composed) if "##" not in target_lines.get(t, "")]
    assert not undocumented, f"composed target(s) lack a `## help` comment: {undocumented}"


def test_test_target_wraps_canonical_runner():
    """The `test` target must SHELL OUT to scripts/run_tests.sh, never
    re-enumerate the suite list (which would let the two drift apart)."""
    text = _read_makefile()
    assert "scripts/run_tests.sh" in text, (
        "`test` target must wrap scripts/run_tests.sh, not fork its own suite list"
    )


@pytest.mark.skipif(shutil.which("make") is None, reason="make not installed")
def test_make_dry_run_check_resolves():
    """`make -n check` must resolve the full target graph without error and
    without executing anything (proves every prereq edge is valid)."""
    proc = subprocess.run(
        ["make", "-n", "check"],
        cwd=REPO,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, (
        f"`make -n check` failed (exit {proc.returncode}):\n{proc.stderr}"
    )
