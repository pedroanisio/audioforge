#!/usr/bin/env bash
# scripts/harness-notation.sh — assertions of docs/evolution/harness-notation.md
# usage: scripts/harness-notation.sh <checkpoint> [evidence-root]
# env:   PYTHON (default ./.venv/bin/python)  ORACLE_PY (interpreter with music21+lilypond+xmlschema)
#        HARNESS_ONLY="ID ID" (subset)  RELEASE_SHA (default HEAD)
set -u
CP=${1:?checkpoint label}; EVROOT=${2:-docs/evolution/evidence-notation}; mkdir -p "$EVROOT"; EV="$(cd "$EVROOT" && pwd)/$CP"; W="$EV/work"; mkdir -p "$W"
PY=${PYTHON:-./.venv/bin/python}; PY="$(cd "$(dirname "$PY")" && pwd)/$(basename "$PY")"; OPY=${ORACLE_PY:-}
SHA=${RELEASE_SHA:-$(git rev-parse HEAD)}; SUM="$EV/summary.tsv"; printf 'id\tresult\tdescription\tseconds\tlog\n' > "$SUM"
{ echo "checkpoint=$CP"; echo "sha=$SHA"; echo "date=$(date -u +%FT%TZ)"; echo "oracle_py=${OPY:-none}"; } > "$EV/context.txt"
sel() { [ -z "${HARNESS_ONLY:-}" ] && return 0; case " $HARNESS_ONLY " in *" $1 "*) return 0;; *) return 1;; esac; }
run() { local id=$1 desc=$2; shift 2; local log="$EV/$id.log" t0=$SECONDS r
  sel "$id" || { printf '%s\tSKIPPED\t%s (filtered)\t0\t-\n' "$id" "$desc" | tee -a "$SUM"; return; }
  if "$@" >"$log" 2>&1; then r=PASS; else r=FAIL; fi
  printf '%s\t%s\t%s\t%s\t%s\n' "$id" "$r" "$desc" "$((SECONDS-t0))" "$log" | tee -a "$SUM"; }
oracle() { local id=$1 desc=$2; shift 2; sel "$id" || { printf '%s\tSKIPPED\t%s (filtered)\t0\t-\n' "$id" "$desc" | tee -a "$SUM"; return; }
  if [ -z "$OPY" ] || ! "$OPY" -c "import music21, xmlschema, lilypond" >/dev/null 2>&1; then printf '%s\tBLOCKED\t%s (ORACLE_PY lacks music21/xmlschema/lilypond)\t0\t-\n' "$id" "$desc" | tee -a "$SUM"; return; fi
  run "$id" "$desc" "$@"; }
T="tests/test_notation_oracles.py"     # created by RN-O-003; selectors below fail until then (intended at T0)
PT() { "$PY" -m pytest -q -p no:cacheprovider "$@"; }
# --- NORA
run    HARNESS-NORA-001 "oracles extra installs"        bash -c "grep -q '^oracles' pyproject.toml && d=\$(mktemp -d) && uv venv \$d --python 3.12 -q && uv pip install -q --python \$d/bin/python -e '.[oracles]' && \$d/bin/python -c 'import music21, xmlschema, lilypond, subprocess; print(subprocess.run([lilypond.executable(), \"--version\"], capture_output=True, text=True).stdout.splitlines()[0])'"
run    HARNESS-NORA-002 "XSD vendored"                  bash -c "ls tests/fixtures/musicxml/xsd/musicxml.xsd tests/fixtures/musicxml/xsd/xml.xsd tests/fixtures/musicxml/xsd/xlink.xsd tests/fixtures/musicxml/xsd/LICENSE* >/dev/null"
run    HARNESS-NORA-003 "make oracle-check exists"      bash -c "grep -q '^oracle-check:' Makefile && make -n oracle-check >/dev/null"
run    HARNESS-NORA-004 "CI oracle job green"           bash -c "gh run list --workflow ci -L 1 --json conclusion --jq '.[0].conclusion' | grep -qx success && gh run view \"\$(gh run list --workflow ci -L 1 --json databaseId --jq '.[0].databaseId')\" --json jobs --jq '.jobs[].name' | grep -qi oracle"
# --- NXML (oracle rows use the oracle test module; structural rows use the projection tests)
oracle HARNESS-NXML-001 "notated export XSD-valid"       PT $T -k "xsd_valid"
run    HARNESS-NXML-002 "meter beats+unit from spec"     PT $T -k "meter_unit"
run    HARNESS-NXML-003 "key changes exported"           PT $T -k "key_changes"
run    HARNESS-NXML-004 "tempo changes exported"         PT $T -k "tempo_changes"
run    HARNESS-NXML-005 "pickup exported"                PT $T -k "pickup"
run    HARNESS-NXML-006 "dynamics exported"              PT $T -k "dynamics"
run    HARNESS-NXML-007 "articulations/slurs exported"   PT $T -k "articulations or slurs"
run    HARNESS-NXML-008 "fermata/rehearsal exported"     PT $T -k "fermata or rehearsal"
run    HARNESS-NXML-009 "exact-tick export parts+chords" PT $T -k "exact_tick"
oracle HARNESS-NXML-010 "music21 structural parity"      PT $T -k "music21_parity"
run    HARNESS-NXML-011 "lossy codes + generated matrix" bash -c "$PY -m audioforge.tools.gen_interop --check && $PY -m pytest -q -p no:cacheprovider $T -k lossy_registry"
# --- NIMP / NMIDI
run    HARNESS-NIMP-001 "import: one layer per part"     PT $T -k "import_parts"
run    HARNESS-NIMP-002 "import: chords/backup/voices"   PT $T -k "import_chords"
run    HARNESS-NIMP-003 "import: attribute changes+ties" PT $T -k "import_attributes"
oracle HARNESS-NIMP-004 "corpus round trip"              PT $T -k "corpus_round_trip"
run    HARNESS-NIMP-005 "self round trip"                PT $T -k "self_round_trip"
run    HARNESS-NMIDI-001 "multi-track MIDI import"       PT tests/test_interop.py -k "midi" 
oracle HARNESS-NMIDI-002 "MIDI export parts+notes"       PT $T -k "midi_export_parts"
run    HARNESS-NMIDI-003 "MIDI export tempo map"         PT $T -k "midi_tempo_map"
# --- NTUN
run    HARNESS-NTUN-001 "tuning drives render (FFT)"     PT tests/test_tuning.py -k "edo_fft"
run    HARNESS-NTUN-002 "12-TET default byte-identical"  "$PY" -m audioforge.tools.render_golden --check
run    HARNESS-NTUN-003 "tuning_not_rendered diagnostic" "$PY" - <<'PYEOF'
import sys; from audioforge import AudioForge
r = AudioForge().compile("asset t { kind: cue\n duration: 1s\n tempo: 120bpm\n tuning: edo divisions=19 base=A4 hz=440\n layer m : notes { osc: sine\n notes: A4 @ 0b for 1b }\n}")
msgs = " ".join(d.message for d in r.diagnostics); print(msgs); sys.exit(0 if "tuning_not_rendered" in msgs or "renders 19" in msgs else 1)
PYEOF
run    HARNESS-NTUN-004 "microtonal interop"             PT tests/test_tuning.py -k "interop"
# --- NANA
oracle HARNESS-NANA-001 "chord roots agree with music21" PT $T -k "chord_parity"
run    HARNESS-NANA-002 "ambiguity set documented"       bash -c "grep -q 'dim7' docs/MIGRATION_3.md && grep -q 'sus2' docs/MIGRATION_3.md && $PY -m pytest -q -p no:cacheprovider $T -k ambiguity_set"
run    HARNESS-NANA-003 "analysis scope stated"          "$PY" -c "import numpy as np, sys; from audioforge.analysis import analyze_audio; r = analyze_audio(np.zeros((8000,2)), 8000); sys.exit(0 if r.get('assessment_scope') else 1)"
run    HARNESS-NANA-004 "pc-set via analyze"             "$PY" -c "import sys; from audioforge.agent_tools import run_tool; r = run_tool('analyze', {'pitch_classes': [0,4,7]}); sys.exit(0 if r['ok'] and any('prime_form' in str(a) for a in r['artifacts']) else 1)"
run    HARNESS-NANA-005 "music21 bridge decision"        bash -c "grep -qiE 'music21' docs/adr/0009-*.md"
# --- NENG
oracle HARNESS-NENG-001 "LilyPond engraves, 0 warnings"  PT $T -k "lilypond_zero_warnings"
run    HARNESS-NENG-002 "score --engrave backend"        bash -c "$PY -m audioforge.cli score --help | grep -q -- '--engrave'"
run    HARNESS-NENG-003 "proof sheet labelled"           bash -c "! grep -qi 'engrav' audioforge/score.py"
run    HARNESS-NENG-004 "no missing-glyph warnings"      PT -W error::UserWarning tests/test_score.py tests/test_score_layout.py
# --- NDOC
run    HARNESS-NDOC-001 "INTEROP matrix generated"       "$PY" -m audioforge.tools.gen_interop --check
run    HARNESS-NDOC-002 "manifest notation coverage"     "$PY" -c "import json, sys; m = json.load(open('docs/capability-manifest.json')); s = json.dumps(m); sys.exit(0 if 'tuplet' in s and 'lyric' in s and 'coverage' in json.dumps(m.get('interop', {})) else 1)"
run    HARNESS-NDOC-003 "README notation section"        bash -c "grep -qiE '^## .*(notation|score)' README.md"
run    HARNESS-NDOC-004 "DSL_GAP_SPEC limits stated"     bash -c "grep -q 'HARNESS-NTUN' docs/DSL_GAP_SPEC.md && grep -q 'HARNESS-NIMP' docs/DSL_GAP_SPEC.md"
run    HARNESS-NDOC-005 "ADR-0009 present"               bash -c "ls docs/adr/0009-*.md >/dev/null && grep -q '## Decision' docs/adr/0009-*.md"
# --- NGATE
run    HARNESS-NGATE-001 "fixture corpus"                bash -c "test \"\$(ls tests/fixtures/notation/*.af 2>/dev/null | wc -l)\" -ge 8"
run    HARNESS-NGATE-002 "surface tests pass"            PT tests/test_interop.py tests/test_score.py tests/test_score_layout.py tests/test_theory_pcset.py tests/test_gap_closure.py
run    HARNESS-NGATE-003 "make check + coverage"         bash -c "make check PYTHON=$PY && $PY -m coverage run -m pytest -q -p no:cacheprovider && $PY -m coverage report"
run    HARNESS-NGATE-004 "goldens unchanged"             "$PY" -m audioforge.tools.render_golden --check
run    HARNESS-NGATE-005 "evidence tracked"              bash -c "test -s $SUM && git ls-files --error-unmatch docs/evolution/evidence-notation >/dev/null 2>&1"
run    HARNESS-NGATE-006 "backlog registered"            bash -c "grep -q 'harness-notation' docs/backlog.yml && node scripts/check-backlog-governance.mjs >/dev/null"
# --- NPERF / NSEM
run    HARNESS-NPERF-001 "export budgets"                PT tests/test_notation_perf.py -k "export"
oracle HARNESS-NPERF-002 "lilypond budget"               PT tests/test_notation_perf.py -k "lilypond"
run    HARNESS-NPERF-003 "proof sheet budget"            PT tests/test_notation_perf.py -k "proof_sheet"
run    HARNESS-NPERF-004 "import budget"                 PT tests/test_notation_perf.py -k "import"
run    HARNESS-NSEM-001 "score_layer projections"        PT $T -k "score_layer_projection"
run    HARNESS-NSEM-002 "tuplets/lyrics projected"       PT $T -k "tuplets or lyrics"
echo; awk -F'\t' 'NR>1{n[$2]++} END{for(k in n) printf "%s=%d ", k, n[k]; print ""}' "$SUM"
