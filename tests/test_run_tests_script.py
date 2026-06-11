"""Smoke checks locking the canonical full-suite runner contract.

Drift-risk-map Finding #2: `scripts/run_tests.sh` is advertised (README) as the
canonical full-suite runner, but historically it only invoked the script-style
`python3 tests/test_*.py` suites and never `pytest`. That let the pytest-only
drift/regression suites (docs regression, CLI, lark grammar, schema edges,
version hygiene) silently not run under the documented command — contract drift
could ship while the canonical command stayed green.

These tests fail loudly if the canonical runner ever again stops invoking
pytest, or if the docs-regression suite (the representative pytest-only drift
guard) becomes uncollectable by pytest.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts" / "run_tests.sh"
CONFTEST = ROOT / "tests" / "conftest.py"
DOCS_REGRESSION = ROOT / "tests" / "test_docs_regression.py"


def test_canonical_runner_exists():
    assert RUNNER.is_file(), f"missing canonical runner: {RUNNER}"


def test_canonical_runner_invokes_pytest():
    """The runner must execute pytest, not only the script-style suites."""
    text = RUNNER.read_text()
    assert re.search(r"\bpytest\b", text), (
        "scripts/run_tests.sh must invoke pytest so the pytest-only drift "
        "suites run under the canonical command (Finding #2)"
    )
    # the script-style suites must still be run too — the pytest pass is
    # additive, not a replacement that would drop the __main__ assertions.
    assert "tests/test_$t.py" in text or "tests/test_" in text, (
        "scripts/run_tests.sh should still run the script-style suites"
    )


def test_docs_regression_is_collectable_by_pytest():
    """The runner's pytest pass only enforces drift if the docs-regression
    suite is actually collected — i.e. not silenced via collect_ignore."""
    assert DOCS_REGRESSION.is_file(), f"missing {DOCS_REGRESSION}"
    ignored = CONFTEST.read_text()
    # crude but sufficient: the suite's basename must not appear in any
    # collect_ignore entry.
    m = re.search(r"collect_ignore\s*=\s*\[(.*?)\]", ignored, re.DOTALL)
    body = m.group(1) if m else ""
    assert "test_docs_regression" not in body, (
        "test_docs_regression.py is in conftest collect_ignore — the canonical "
        "runner's pytest pass would not execute it, defeating Finding #2's fix"
    )


if __name__ == "__main__":
    test_canonical_runner_exists()
    test_canonical_runner_invokes_pytest()
    test_docs_regression_is_collectable_by_pytest()
    print("PASS  canonical runner invokes pytest and collects the drift suites")
