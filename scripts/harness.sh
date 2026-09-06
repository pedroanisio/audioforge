#!/usr/bin/env bash
# scripts/harness.sh — run the automated assertions of docs/evolution/harness.md
# usage: scripts/harness.sh <checkpoint e.g. T1> [evidence-root]
# env:   PYTHON (default ./.venv/bin/python)  PY310 PY311 PY312 (matrix interpreters)
#        RELEASE_SHA (default HEAD)  HARNESS_QUICK=1 (skip long checks)  HARNESS_ONLY="ID ID" (run a subset)
set -u
CP=${1:?checkpoint label}; EVROOT=${2:-docs/evolution/evidence}; mkdir -p "$EVROOT"; EV="$(cd "$EVROOT" && pwd)/$CP"; W="$EV/work"; mkdir -p "$W"   # absolute: rows cd elsewhere; work/ holds WAVs, exports: gitignored
SITE="$(mktemp -d)"   # mkdocs refuses a site_dir inside docs_dir
CLEAN='git status --porcelain --untracked-files=all -- . ":(exclude)docs/evolution/evidence"'   # the evidence bundle being written is not dirt
PY=${PYTHON:-./.venv/bin/python}; PY="$(cd "$(dirname "$PY")" && pwd)/$(basename "$PY")"   # absolute, not symlink-resolved: rows cd into exports
SHA=${RELEASE_SHA:-$(git rev-parse HEAD)}
SUM="$EV/summary.tsv"; printf 'id\tresult\tdescription\tseconds\tlog\n' > "$SUM"
{ echo "checkpoint=$CP"; echo "sha=$SHA"; echo "date=$(date -u +%FT%TZ)"; git status --porcelain | wc -l | sed 's/^/dirty_paths=/'; } > "$EV/context.txt"

sel() { [ -z "${HARNESS_ONLY:-}" ] && return 0; case " $HARNESS_ONLY " in *" $1 "*) return 0;; *) return 1;; esac; }   # HARNESS_ONLY="ID ID" runs a subset
run() { local id=$1 desc=$2; shift 2; local log="$EV/$id.log" t0=$SECONDS r
  sel "$id" || { printf '%s\tSKIPPED\t%s (filtered)\t0\t-\n' "$id" "$desc" | tee -a "$SUM"; return; }
  if "$@" >"$log" 2>&1; then r=PASS; else r=FAIL; fi
  printf '%s\t%s\t%s\t%s\t%s\n' "$id" "$r" "$desc" "$((SECONDS-t0))" "$log" | tee -a "$SUM"; }
heavy() { sel "$1" || { printf '%s\tSKIPPED\t%s (filtered)\t0\t-\n' "$1" "$2" | tee -a "$SUM"; return; }; if [ "${HARNESS_QUICK:-0}" = 1 ]; then printf '%s\tSKIPPED\t%s\t0\t-\n' "$1" "$2" | tee -a "$SUM"; else run "$@"; fi; }
manual() { sel "$1" || return 0; printf '%s\tMANUAL\t%s\t0\t-\n' "$1" "$2" | tee -a "$SUM"; }
py() { "$PY" - "$@"; }   # read a python program from stdin

# --- AUD / MUS ------------------------------------------------------------
run HARNESS-AUD-001 "A1 gain once"            "$PY" -m pytest -q -p no:cacheprovider tests/test_audio_correctness.py -k gain_is_applied_once
run HARNESS-AUD-002 "A2 release at note-off"  "$PY" -m pytest -q -p no:cacheprovider tests/test_audio_correctness.py -k "release_starts_at_note_off or during_attack or sustain_loop_exits"
run HARNESS-AUD-003 "A3 anti-alias"           "$PY" -m pytest -q -p no:cacheprovider tests/test_audio_correctness.py -k "out_of_band or in_band_tone or aliases_during_glide"
run HARNESS-AUD-004 "A4 mastering"            "$PY" -m pytest -q -p no:cacheprovider tests/test_audio_correctness.py -k "preserves_absolute_level or explicit_request or normalization_dsl_roundtrip or intersample or does_not_skip_peak_safety"
run HARNESS-MUS-001 "M1 harmony"              "$PY" -m pytest -q -p no:cacheprovider tests/test_musical_correctness.py -k "chord_extensions or explicit_chord_quality or ambiguous_harmony or unknown_cluster or modulation or voice_leading_preserves or emotion_reports"
run HARNESS-MUS-002 "M2 phrase evidence"      "$PY" -m pytest -q -p no:cacheprovider tests/test_musical_correctness.py tests/test_ai_agent_dsl.py -k "fabricate or polyphonic_gates or coordinated or cadence_candidates or share_timing_motion or phrase or voicing_directive"
run HARNESS-MUS-003 "M3 technique fidelity"   "$PY" -m pytest -q -p no:cacheprovider tests/test_musical_correctness.py tests/test_render_plan.py tests/test_expressive_techniques_lowering.py tests/test_performance_model.py -k "technique_approximation or legato_requires or plan_authority_matches_performance_rng_stream or lower_technique or legato or section or phrasing or slur"
run HARNESS-MUS-004 "M4 arrangement + loops"  "$PY" -m pytest -q -p no:cacheprovider tests/test_arrangement_correctness.py tests/test_audio_correctness.py -k "repeat or clip or meter or curve or event_ids or loop_safe or loop_check or render_ready_validation"
run HARNESS-MUS-005 "M5 performance identity" "$PY" -m pytest -q -p no:cacheprovider tests/test_audio_correctness.py tests/test_musical_correctness.py tests/test_arrangement_correctness.py -k "mix_edits_preserve or explicit_performance_seed or inserting_an_earlier_note or uint64_seed or event_ids_unique"
run HARNESS-MUS-006 "M6 analysis context"     "$PY" -m pytest -q -p no:cacheprovider tests/test_musical_correctness.py tests/test_ai_agent_dsl.py -k "analysis_observations or authored_rests or analysis_returns_actionable"

# --- ACC ------------------------------------------------------------------
heavy HARNESS-ACC-001 "acceptance cases pass"  "$PY" -m audioforge.tools.musical_acceptance --out "$W/acceptance"
[ -f "$W/acceptance/manifest.json" ] && cp "$W/acceptance/manifest.json" "$EV/acceptance-manifest.json"
acc002() { local b="$W/baseline-2.16.0"; mkdir -p "$b" && git archive engine-2.16.0 | tar -x -C "$b" \
  && "$PY" -m audioforge.tools.musical_acceptance --out "$W/acceptance_ab" --baseline-root "$b" >/dev/null \
  && py "$W/acceptance_ab/manifest.json" <<'PYEOF'
import json,sys; m=json.load(open(sys.argv[1])); c=m["cases"]
ok=all(not x["revisions"]["baseline"]["passed"] and x["revisions"]["current"]["passed"] for x in c)
print({x["id"]:(x["revisions"]["baseline"]["passed"],x["revisions"]["current"]["passed"]) for x in c}); sys.exit(0 if ok and len(c)==7 else 1)
PYEOF
}
heavy HARNESS-ACC-002 "baseline fails, current passes" acc002
manual HARNESS-ACC-003 "listening review recorded (see harness.md 3.3)"
acc004() { "$PY" -m audioforge.tools.musical_acceptance --out "$W/acceptance_b" >/dev/null && py "$W/acceptance/manifest.json" "$W/acceptance_b/manifest.json" <<'PYEOF'
import json,sys; a,b=[json.load(open(p)) for p in sys.argv[1:3]]
h=lambda m:{c["id"]:c["revisions"]["current"]["output_sha256"] for c in m["cases"]}; sys.exit(0 if h(a)==h(b) else 1)
PYEOF
}
heavy HARNESS-ACC-004 "acceptance bundle reproducible" acc004

# --- GATE -----------------------------------------------------------------
heavy HARNESS-GATE-001 "make check"            timeout 300 make check PYTHON="$PY"
heavy HARNESS-GATE-002 "coverage >= 90.1"      bash -c "$PY -m coverage run -m pytest -q -p no:cacheprovider && $PY -m coverage report"
run   HARNESS-GATE-003 "golden strict same-env" "$PY" -m audioforge.tools.render_golden --check
heavy HARNESS-GATE-004 "mkdocs strict"          uv run --with mkdocs-material mkdocs build --strict --site-dir "$SITE"
run   HARNESS-GATE-005 "backlog governance"     node scripts/check-backlog-governance.mjs
run   HARNESS-GATE-006 "git diff --check"       git diff --check

# --- PORT -----------------------------------------------------------------
for v in 310 311 312; do var=PY$v; sel HARNESS-PORT-00$(( v==310?1:(v==311?2:3) )) || continue; if [ -n "${!var:-}" ]; then heavy HARNESS-PORT-00$(( v==310?1:(v==311?2:3) )) "make check py3.${v#3}" make check PYTHON="${!var}"; else printf 'HARNESS-PORT-00%s\tBLOCKED\tno %s interpreter\t0\t-\n' "$(( v==310?1:(v==311?2:3) ))" "$var" | tee -a "$SUM"; fi; done
if ls "$EV"/HARNESS-PORT-00*.log >/dev/null 2>&1; then run HARNESS-PORT-004 "cross-env golden advisory" bash -c "grep -h 'golden-check' $EV/HARNESS-PORT-00*.log | grep -q 'reproduce byte-for-byte'"; else printf 'HARNESS-PORT-004\tSKIPPED\tcross-env golden advisory (no PORT logs)\t0\t-\n' | tee -a "$SUM"; fi

# --- CI -------------------------------------------------------------------
ci001() { local id; id=$(gh run list -L 1 --json databaseId --jq '.[0].databaseId') && [ "$(gh api "repos/{owner}/{repo}/actions/runs/$id/jobs" --jq .total_count)" -ge 1 ]; }
run HARNESS-CI-001 "a CI job executed" ci001
run HARNESS-CI-002 "ci green on branch head" bash -c "gh run list --workflow ci --branch \"\$(git branch --show-current)\" -L 1 --json conclusion,headSha --jq '.[0] | select(.conclusion==\"success\" and .headSha==\"$SHA\")' | grep -q success"
run HARNESS-CI-003 "ci green on main"        bash -c "gh run list --workflow ci --branch main -L 1 --json conclusion --jq '.[0].conclusion' | grep -qx success"
run HARNESS-CI-004 "backlog-governance green" bash -c "gh run list --workflow backlog-governance -L 1 --json conclusion --jq '.[0].conclusion' | grep -qx success"

# --- VCS / REL ------------------------------------------------------------
run HARNESS-VCS-001 "tree clean"             bash -c "test -z \"\$($CLEAN)\""
run HARNESS-VCS-002 "branch pushed == local" bash -c "test -z \"\$($CLEAN)\" && git fetch -q origin && test \"\$(git rev-parse HEAD)\" = \"\$(git rev-parse origin/\$(git branch --show-current))\""
run HARNESS-VCS-003 "PR approved"            bash -c 'gh pr view --json reviews --jq ".reviews[].state" | grep -q APPROVED'
run HARNESS-VCS-004 "merged into origin/main" bash -c "test -z \"\$($CLEAN)\" && git merge-base --is-ancestor $SHA origin/main"
run HARNESS-REL-001 "version literals"       "$PY" -m audioforge.tools.bump_version --check
run HARNESS-REL-002 "changelog consolidated" bash -c "! awk '/^## \[Unreleased\]/,/^## \[3.0.0\]/' CHANGELOG.md | grep -q 'Track E' && grep -Eq '^## \[3.0.0\] - 20[0-9]{2}-' CHANGELOG.md"
run HARNESS-REL-003 "release tags on origin" bash -c "test \"\$(git ls-remote --tags origin | grep -cE 'refs/tags/(engine-3\.0\.0|dsl-2\.0)$')\" = 2 && git merge-base --is-ancestor engine-3.0.0 origin/main"
run HARNESS-REL-004 "uv lock in sync"        uv lock --check

# --- GOV ------------------------------------------------------------------
run HARNESS-GOV-001 "backlog knows the repair" bash -c "grep -q 'ADR-0007' docs/backlog.yml && node scripts/check-backlog-governance.mjs >/dev/null"
run HARNESS-GOV-002 "Track E statuses done"    py <<'PYEOF'
import re,sys; y=open("docs/backlog.yml").read(); bad=[]
for i in ("BL-004","BL-010","BL-011","BL-012","BL-013","BL-014"):
    m=re.search(rf"id: {i}\n(.*?)(?=\n  - id: |\Z)", y, re.S); st=re.search(r'status: "(\w[\w-]*)"', m.group(1)).group(1) if m else "missing"
    if st!="done": bad.append((i,st))
print(bad); sys.exit(1 if bad else 0)
PYEOF
run HARNESS-GOV-003 "ledger vocabulary + harness ids" bash -c "! grep -q '| Verified |' docs/MUSICAL_CORRECTNESS.md && test \"\$(grep -c 'HARNESS-' docs/MUSICAL_CORRECTNESS.md)\" -ge 12"
run HARNESS-GOV-004 "ADR-0001 points to ADR-0007"  grep -q 'ADR-0007' docs/adr/0001-determinism-oracle.md
run HARNESS-GOV-005 "index.md claim corrected"     bash -c "! grep -q 'every render, forever' docs/index.md"
run HARNESS-GOV-006 "ADR-0007 status honest"       bash -c "(test -z \"\$($CLEAN)\" && git merge-base --is-ancestor $SHA origin/main 2>/dev/null) || ! grep -Eiq 'Status:\*\* .*implemented' docs/adr/0007-musical-render-semantics.md"
run HARNESS-GOV-007 "agent-task pointer valid"     bash -c '[ ! -f .agent-tasks/.current_task ] || jq -e --arg t "$(cat .agent-tasks/.current_task)" "any(.task_id==\$t)" .agent-tasks/registry.json >/dev/null'
manual HARNESS-GOV-008 "ledger citations accurate (see harness.md 3.9)"

# --- CON ------------------------------------------------------------------
run HARNESS-CON-001 "emitted codes registered" py <<'PYEOF'
import sys; from audioforge.capabilities import capability_manifest
codes=set(capability_manifest()["diagnostic_codes"]); need={"ambiguous_harmony","unrecognized_harmony","loop_boundary_tail","render_plan_approximation","dead_air","mono_image","low_foundation_weak","very_bright"}
print("missing:", sorted(need-codes)); sys.exit(0 if need<=codes else 1)
PYEOF
run HARNESS-CON-002 "Diagnostic has code field" py <<'PYEOF'
import dataclasses,sys; from audioforge.sdk import Diagnostic; f={x.name for x in dataclasses.fields(Diagnostic)}; print(f); sys.exit(0 if "code" in f else 1)
PYEOF
run HARNESS-CON-003 "verify .af gives structured error" bash -c "! ($PY -m audioforge.cli verify tests/golden/audio/synth_voice.af /dev/null 2>&1 | grep -q 'Expecting value')"
run HARNESS-CON-004 "validate does not mutate caller" py <<'PYEOF'
import copy,sys; from audioforge.schema import validate_spec; from audioforge.agent_tools import run_tool
raw={"id":"r","kind":"cue","duration_s":2.0,"sample_rate":48000,"bpm":120,"score":{"sections":[{"name":"verse","start_beat":0,"dur_beats":4}],"repeats":[{"section":"verse","count":2}]},"layers":[{"name":"m","type":"notes","osc":"sine","notes":[{"note":"C4","start_beat":0,"dur_beats":0.5}]}],"master":{"target_peak_dbfs":-1}}
a=copy.deepcopy(raw); validate_spec(a); b=copy.deepcopy(raw); run_tool("validate",{"spec":b})
print("validate_spec mutated:", a!=raw, "run_tool mutated:", b!=raw); sys.exit(0 if a==raw and b==raw else 1)
PYEOF

# --- PERF / MIG / RB / OBS / SEC -------------------------------------------
if grep -q $'^HARNESS-GATE-001\tSKIPPED' "$SUM"; then printf 'HARNESS-PERF-001\tSKIPPED\tmake check <= 300 s\t0\t-\n' | tee -a "$SUM"; else run HARNESS-PERF-001 "make check <= 300 s" bash -c "awk -F'\t' '\$1==\"HARNESS-GATE-001\"{exit !(\$2==\"PASS\" && \$4<=300)}' $SUM"; fi
run HARNESS-PERF-002 "resampler cost bounded + documented" bash -c "$PY - <<'PYEOF' && grep -Eiq 'resampl.*(cost|slower|time)' docs/MIGRATION_3.md
import time,sys,numpy as np; from audioforge.sampler import Region,render_region
SR=48000; src=np.sin(2*np.pi*440*np.arange(SR*2)/SR); out={}
for s,lim in ((12,.130),(24,.250)):
    r=Region(pitch_keycenter=60,ampeg_attack=.001,ampeg_release=.1); best=min((lambda t0:(render_region(r,src,SR,60+s,SR,SR),time.perf_counter()-t0)[1])(time.perf_counter()) for _ in range(3)); out[s]=(best,lim)
print(out); sys.exit(0 if all(b<=l for b,l in out.values()) else 1)
PYEOF"
mig001() { local b="$W/baseline-2.16.0"; [ -d "$b" ] || { mkdir -p "$b" && git archive engine-2.16.0 | tar -x -C "$b"; }
  local spec="$PWD/tests/golden/audio/synth_voice.af"   # the 2.16.0 tag predates the golden corpus: take the spec from this tree (DSL 1.9-compatible)
  mkdir -p "$W/mig"
  (cd "$b" && PYTHONPATH="$b" "$PY" -m audioforge.cli render "$spec" -o "$W/mig" && PYTHONPATH="$b" "$PY" -m audioforge.cli compile "$spec" > "$W/mig/legacy.ir.json") || { echo "mig001: baseline render/compile failed"; return 1; }
  "$PY" -m audioforge.cli verify "$W/mig/legacy.ir.json" "$W/mig/synth_voice.manifest.json"; [ $? -eq 2 ]; }
heavy HARNESS-MIG-001 "legacy manifest -> MISMATCH exit 2" mig001
run   HARNESS-MIG-002 "repo .af specs compile+render" py <<'PYEOF'
import sys; from pathlib import Path; from audioforge import AudioForge
bad=[p.name for p in list(Path("static/samples").glob("*.af"))+list(Path("tests/golden/audio").glob("*.af")) if not AudioForge().compile(p.read_text()).ok]
print("failed:", bad); sys.exit(1 if bad else 0)
PYEOF
run   HARNESS-MIG-003 "migration flags audio review" py <<'PYEOF'
import sys; from audioforge.ir_schema import migrate_ir_spec; m=migrate_ir_spec({"id":"x"},"1.2")["_meta"]["migration"]; print(m); sys.exit(0 if m.get("audio_review_required") is True and m.get("to")=="2.0" else 1)
PYEOF
run   HARNESS-RB-001 "rollback anchor resolves"  git rev-parse --verify engine-2.16.0
rb002() { local d="$W/rollback-2.16.0" p shim="$W/shim" out; p="$(cd "$(dirname "$PY")" && pwd)/$(basename "$PY")"; mkdir -p "$d" "$shim"   # absolute but NOT symlink-resolved: readlink -f escapes the venv
  printf '#!/bin/sh\nexec %s "$@"\n' "$p" > "$shim/python3"; cp "$shim/python3" "$shim/python"; chmod +x "$shim/python3" "$shim/python"  # wrapper, not symlink: a venv python reached via an outside symlink loses its site-packages
  git archive engine-2.16.0 | tar -x -C "$d" && ln -sfn "$PWD/libraries" "$d/libraries" || return 1
  out="$d/.gate.out"
  (cd "$d" && export PATH="$shim:$PATH" PYTHONPATH="$d" PYTHON="$p"; if [ -f Makefile ]; then make check PYTHON="$p"; else sh scripts/run_tests.sh; fi) > "$out" 2>&1; local rc=$?
  cat "$out"
  [ $rc -eq 0 ] && return 0
  # 2.16.0 predates the Makefile, its runner hardcodes python3, and its current.txt snapshot test is
  # locale-dependent (docs/MIGRATION_3.md "Rolling back"). That single documented fixture failure is tolerated.
  [ "$(grep -c '^FAILED' "$out")" = 1 ] && grep -q '^FAILED tests/test_catalog_freshness.py::test_current_txt_matches_fresh_tree_snapshot' "$out" \
    && { echo "rb002: only the documented locale-dependent snapshot test failed; engine tests green"; return 0; }
  return $rc; }
heavy HARNESS-RB-002 "previous release gate green in export" rb002
run   HARNESS-OBS-001 "manifest carries identities" bash -c "$PY -m audioforge.cli render tests/golden/audio/synth_voice.af -o $W/obs >/dev/null && $PY -c \"import json,sys; m=json.load(open('$W/obs/synth_voice.manifest.json')); need={'spec_hash','performance_hash','performance_seed','engine_version','output_sha256','plan_hash'}; print(sorted(need-set(m))); sys.exit(0 if need<=set(m) else 1)\""
run   HARNESS-OBS-002 "evidence bundle tracked"     bash -c "test -s $SUM && git ls-files --error-unmatch docs/evolution/evidence >/dev/null 2>&1"
if command -v unshare >/dev/null && unshare -rn true 2>/dev/null; then heavy HARNESS-SEC-001 "suite offline" unshare -rn make test PYTHON="$PY"; else printf 'HARNESS-SEC-001\tBLOCKED\tno unprivileged network namespace\t0\t-\n' | tee -a "$SUM"; fi
run   HARNESS-SEC-002 "no secrets tracked"          bash -c "test \"\$(git grep -nE 'ghp_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|-----BEGIN (RSA|OPENSSH|EC) PRIVATE KEY|xox[baprs]-' -- . ':!uv.lock' | wc -l)\" = 0"

echo; awk -F'\t' 'NR>1{n[$2]++} END{for(k in n) printf "%s=%d ", k, n[k]; print ""}' "$SUM"
