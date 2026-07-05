"""Tests for wiring drift_inspect into the gate + the standards ratchet (AF-R13)."""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DRIFT = REPO / "scripts" / "drift_inspect.py"
STANDARDS = REPO / "docs" / "codebase-standards.md"
MAKEFILE = REPO / "Makefile"


def test_drift_inspect_check_runs_clean():
    proc = subprocess.run([sys.executable, str(DRIFT), "--check"], cwd=REPO,
                          capture_output=True, text=True)
    assert proc.returncode == 0, f"registry drift detected:\n{proc.stdout}\n{proc.stderr}"


def test_drift_inspect_rejects_unknown_flag():
    proc = subprocess.run([sys.executable, str(DRIFT), "--bogus"], cwd=REPO,
                          capture_output=True, text=True)
    assert proc.returncode != 0  # argparse rejects unknown args


def test_standards_doc_exists():
    assert STANDARDS.is_file(), "docs/codebase-standards.md must exist (AF-R13)"
    assert STANDARDS.read_text(encoding="utf-8").startswith("---"), "needs disclaimer frontmatter"


def test_every_enforced_rule_cites_a_gate():
    """A rule may claim `[Enforced]` only if its row names a gate (make/test/
    coverage) — the ratchet's honesty invariant."""
    text = STANDARDS.read_text(encoding="utf-8")
    enforced_rows = [ln for ln in text.splitlines()
                     if ln.startswith("|") and "`[Enforced]`" in ln]
    assert enforced_rows, "standards doc has no enforced rules"
    for row in enforced_rows:
        gate_cell = row.split("|")[-2]  # last content column = gate/owner
        assert re.search(r"make |test_|coverage|\.py", gate_cell), (
            f"[Enforced] rule cites no gate: {row.strip()}"
        )


def test_make_check_includes_drift_check():
    text = MAKEFILE.read_text(encoding="utf-8")
    check_line = next(ln for ln in text.splitlines()
                      if re.match(r"^check\s*:", ln))
    assert "drift-check" in check_line, "`make check` must compose `drift-check` (AF-R13)"
