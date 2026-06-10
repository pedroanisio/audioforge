"""pytest collection hygiene (2026-06-10 review, P3).

Several suites are script-style: their test functions take plain
positional arguments (a built library, a manifest pin) provided by their
__main__ blocks, not pytest fixtures. Collecting them produces 14 false
"errors" that mask real signal. They remain first-class suites — run
directly (python tests/test_X.py) or via scripts/run_tests.sh.
"""
collect_ignore = [
    "test_sampler.py",
    "test_dynamics.py",
    "test_performance_model.py",
    "test_stage.py",
]
