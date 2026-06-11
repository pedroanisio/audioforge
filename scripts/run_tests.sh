#!/bin/sh
# Canonical full-suite runner: script-style suites + pytest-collected ones.
#
# The named suites below carry __main__ assertions that pytest does not
# trigger, so they are run script-style first. The pytest pass that follows is
# NOT optional: it is the only thing that runs the drift/regression suites
# collected exclusively by pytest — docs regression (tests/test_docs_regression.py),
# CLI (tests/test_cli.py), lark grammar (tests/test_lark_parser.py), schema
# edges (tests/test_schema_edges.py), and the version-hygiene drift checks.
# Without it, contract drift ships while this "canonical" command stays green.
# Both passes must succeed for the suite to be green (set -e fails loud).
set -e
cd "$(dirname "$0")/.."
for t in determinism v2 v21 t2 t3 performance instruments mix compose \
         variation palette sampler dynamics performance_model stage contract; do
  python3 "tests/test_$t.py"
done
python3 -m pytest -q
