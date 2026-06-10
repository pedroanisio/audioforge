#!/bin/sh
# Canonical full-suite runner: script-style suites + pytest-collected ones.
set -e
cd "$(dirname "$0")/.."
for t in determinism v2 v21 t2 t3 performance instruments mix compose \
         variation palette sampler dynamics performance_model stage contract; do
  python3 "tests/test_$t.py"
done
