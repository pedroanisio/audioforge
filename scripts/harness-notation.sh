#!/usr/bin/env bash
# Required notation assertions through T1, T2 or T3; later milestones stay N/A.
set -euo pipefail
cd "$(dirname "$0")/.."
notation_python="${PYTHON:-./.venv/bin/python}"
oracle_python="${ORACLE_PY:-$notation_python}"
# musicxml2ly invokes `lilypond --version` through PATH, even when the main
# engraving command uses the wheel's absolute executable path.
if notation_lilypond_dir=$("$oracle_python" -c \
  'from pathlib import Path; import lilypond; print(Path(lilypond.executable()).parent)' 2>/dev/null); then
  export PATH="$notation_lilypond_dir:$PATH"
fi
exec "$notation_python" -m audioforge.tools.notation_acceptance "$@"
