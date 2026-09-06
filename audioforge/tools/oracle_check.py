"""Run optional notation oracles, rejecting empty or skipped test runs."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

DEPENDENCIES = ("music21", "xmlschema", "lilypond")
SKIP_MESSAGE = "oracle-check: SKIPPED — install '.[oracles]'"


def missing_dependencies() -> list[str]:
    return [name for name in DEPENDENCIES if importlib.util.find_spec(name) is None]


def junit_passed(path: Path) -> bool:
    if not path.exists():
        return False
    cases = ET.parse(path).findall(".//testcase")
    return bool(cases) and all(not any(c.find(t) is not None for t in
                                        ("failure", "error", "skipped")) for c in cases)


def main(argv=None) -> int:
    if missing_dependencies():
        print(SKIP_MESSAGE)
        return 0
    with tempfile.TemporaryDirectory(prefix="audioforge-oracles-") as directory:
        report = Path(directory) / "junit.xml"
        result = subprocess.run([sys.executable, "-m", "pytest", "-q",
                                 "tests/test_notation_oracles.py",
                                 f"--junitxml={report}"])
        return result.returncode or (0 if junit_passed(report) else 1)


if __name__ == "__main__":
    raise SystemExit(main())
