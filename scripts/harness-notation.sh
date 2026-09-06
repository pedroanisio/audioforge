#!/usr/bin/env bash
# Required notation assertions through T1, T2 or T3; later milestones stay N/A.
set -euo pipefail
cd "$(dirname "$0")/.."
exec "${PYTHON:-./.venv/bin/python}" -m audioforge.tools.notation_acceptance "$@"
