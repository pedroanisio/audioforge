"""Execute the notation harness with per-row logs and strict milestone exits."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

from .oracle_check import junit_passed

ROOT = Path(__file__).resolve().parents[2]
ORACLE_TESTS = "tests/test_notation_oracles.py"
CONTRACT_TESTS = "tests/test_notation_contract.py"
SELECTORS = {
    "NXML-001": "xsd_valid", "NXML-002": "meter_unit", "NXML-003": "key_changes",
    "NXML-004": "tempo_changes", "NXML-005": "pickup", "NXML-006": "dynamics",
    "NXML-007": "articulations or slurs", "NXML-008": "fermata or rehearsal",
    "NXML-009": "exact_tick", "NXML-010": "music21_parity", "NXML-011": "lossy_registry",
    "NIMP-001": "import_parts", "NIMP-002": "import_chords", "NIMP-003": "import_attributes",
    "NIMP-004": "corpus_round_trip", "NIMP-005": "self_round_trip",
    "NMIDI-002": "midi_export_parts", "NMIDI-003": "midi_tempo_map",
    "NANA-001": "chord_parity", "NANA-002": "ambiguity_set",
    "NENG-001": "lilypond_zero_warnings", "NSEM-001": "score_layer_projection",
    "NSEM-002": "tuplets or lyrics",
}
ORACLE_ROWS = {"NORA-001", "NORA-002", "NORA-003", "NXML-001", "NXML-010",
               "NIMP-004", "NMIDI-002", "NANA-001", "NENG-001"}
SURFACE_TESTS = ["tests/test_interop.py", "tests/test_score.py", "tests/test_score_layout.py",
                 "tests/test_theory_pcset.py", "tests/test_gap_closure.py",
                 "tests/test_notation_projection.py", CONTRACT_TESTS]


def source_inputs() -> dict[str, str]:
    paths = subprocess.check_output(["git", "ls-files", "--cached", "--others",
                                     "--exclude-standard", "-z"], cwd=ROOT, text=True)
    selected = {p for p in paths.split("\0") if p.startswith(("audioforge/", "tests/"))
                or p in {"Makefile", "pyproject.toml", "uv.lock", "scripts/run_tests.sh"}
                or p.startswith("docs/examples/") and p.endswith((".af", "catalog.json"))}
    return {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest()
            for p in sorted(selected) if (ROOT / p).is_file()}


def registry() -> list[dict]:
    rows = []
    for line in (ROOT / "docs/evolution/harness-notation.md").read_text().splitlines():
        if not line.startswith("| HARNESS-"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        # Some procedures contain a shell pipe. The first two and final cells
        # still identify the row, description, and checkpoint without ambiguity.
        due = [int(n) for n in re.findall(r"T(\d)", cells[-1])]
        rows.append(dict(id=cells[0], description=cells[1], due=max(due) if due else 1))
    if len(rows) != 53 or len({r["id"] for r in rows}) != 53:
        raise ValueError("notation registry must contain exactly 53 unique assertions")
    return rows


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkpoint", choices=["T1", "T2", "T3"])
    parser.add_argument("evidence_root", nargs="?", default="docs/evolution/evidence-notation")
    parser.add_argument("--skip-full", action="store_true",
                        help="record the full gate as BLOCKED for an exploratory run")
    args = parser.parse_args(argv)
    destination = Path(args.evidence_root).resolve() / args.checkpoint
    destination.mkdir(parents=True, exist_ok=True)
    work = destination / "work"
    work.mkdir(exist_ok=True)
    py = os.path.abspath(os.environ.get("PYTHON", sys.executable))
    oracle = os.environ.get("ORACLE_PY", py)
    oracle = os.path.abspath(oracle)
    environment = dict(os.environ, PYTHON=py, UV_CACHE_DIR=os.environ.get("UV_CACHE_DIR", "/tmp/uv-cache"))
    check = subprocess.run([oracle, "-c", "import music21, xmlschema, lilypond"],
                           capture_output=True, cwd=ROOT)
    oracle_available = check.returncode == 0
    context = {"checkpoint": args.checkpoint,
               "started_utc": datetime.now(timezone.utc).isoformat(),
               "commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
               "working_tree": subprocess.check_output(["git", "status", "--short"], cwd=ROOT, text=True),
               "python": py, "oracle_python": oracle, "commands": {},
               "source_inputs": source_inputs()}
    results = []
    summary = destination / "summary.tsv"
    summary.write_text("id\tresult\tdescription\tseconds\tlog\n")
    for row in registry():
        started = time.monotonic()
        ident = row["id"].removeprefix("HARNESS-")
        logfile = destination / f"{row['id']}.log"
        junit = work / f"{ident}.xml"
        env = dict(environment, AF_NOTATION_EVIDENCE=str(destination / "reports"))
        interpreter = oracle if ident in ORACLE_ROWS else py
        commands = []
        test_run = False
        status = "PASS"
        if row["due"] > int(args.checkpoint[1]):
            status = "N/A"
            logfile.write_text(f"Not due at {args.checkpoint}; required at T{row['due']}.\n")
        elif ident in ORACLE_ROWS and not oracle_available:
            status = "BLOCKED"
            logfile.write_text(f"{oracle} lacks music21, xmlschema, or lilypond.\n")
        elif ident == "NGATE-003" and args.skip_full:
            status = "BLOCKED"
            logfile.write_text("Full make check and coverage explicitly omitted with --skip-full.\n")
        else:
            if ident in SELECTORS:
                commands = [[interpreter, "-m", "pytest", "-q", ORACLE_TESTS, "-k", SELECTORS[ident], f"--junitxml={junit}"]]
                test_run = True
            elif ident == "NGATE-002":
                commands = [[py, "-m", "pytest", "-q", *SURFACE_TESTS, f"--junitxml={junit}"]]
                test_run = True
            elif ident == "NMIDI-001":
                commands = [[py, "-m", "pytest", "-q", "tests/test_interop.py", "-k", "midi", f"--junitxml={junit}"]]
                test_run = True
            elif ident == "NTUN-003":
                commands = [[py, "-m", "pytest", "-q", "tests/test_tuning.py", f"--junitxml={junit}"]]
                test_run = True
            elif ident == "NORA-001":
                install = work / f"installed-oracles-{time.time_ns()}"
                commands = [["uv", "venv", str(install), "--python", oracle],
                            ["uv", "pip", "install", "--offline", "--python", str(install / "bin/python"), "-e", ".[oracles]"],
                            [str(install / "bin/python"), "-c", "import importlib.metadata as m, lilypond, subprocess; print({n:m.version(n) for n in ('music21','xmlschema','lilypond')}); subprocess.run([lilypond.executable(), '--version'], check=True)"]]
            elif ident == "NORA-002":
                commands = [[oracle, "-c", "import xmlschema; from pathlib import Path; p=Path('tests/fixtures/musicxml/xsd'); assert (p/'LICENSE.md').exists(); xmlschema.XMLSchema(p/'musicxml.xsd', allow='local'); print('MusicXML 3.1 schema loaded with local-only access')"]]
            elif ident == "NORA-003":
                commands = [["make", "oracle-check", f"PYTHON={oracle}"],
                            [py, "-m", "pytest", "-q", CONTRACT_TESTS, "-k", "oracle_gate", f"--junitxml={junit}"]]
                test_run = True
            elif ident == "NDOC-001":
                commands = [[py, "-m", "audioforge.tools.gen_interop", "--check"]]
            elif ident == "NGATE-004":
                commands = [[py, "-m", "audioforge.tools.render_golden", "--check"]]
            elif ident == "NGATE-003":
                commands = [["make", "check", f"PYTHON={py}"],
                            [oracle if oracle_available else py, "-m", "coverage", "run", "-m", "pytest", "-q"],
                            [oracle if oracle_available else py, "-m", "coverage", "report"],
                            [oracle if oracle_available else py, "-m", "coverage", "json", "-o", str(destination / "coverage.json")]]
            elif ident == "NGATE-005":
                commands = [["git", "ls-files", "--error-unmatch", str(summary.relative_to(ROOT))]]
            elif ident == "NGATE-006":
                commands = [["node", "scripts/check-backlog-governance.mjs"]]
            else:
                commands = [[py, "-m", "pytest", "-q", CONTRACT_TESTS, "-k", "documented_contract", f"--junitxml={junit}"]]
                test_run = True
            for command in commands:
                if "pytest" in command:
                    command.append(f"--basetemp={work / (ident + '-pytest')}")
            context["commands"][ident] = commands
            with logfile.open("w") as log:
                for command in commands:
                    log.write(json.dumps(command) + "\n")
                    log.flush()
                    result = subprocess.run(command, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
                    if result.returncode:
                        status = "FAIL"
                        break
                if test_run and status == "PASS" and not junit_passed(junit):
                    status = "FAIL"
                    log.write("Selected test run was empty, skipped, or failed.\n")
        elapsed = round(time.monotonic() - started, 3)
        results.append(dict(row, result=status, seconds=elapsed, log=logfile.name))
        with summary.open("a") as handle:
            handle.write(f"{row['id']}\t{status}\t{row['description']}\t{elapsed}\t{logfile.name}\n")
        print(f"{row['id']}: {status} ({elapsed:.1f}s)", flush=True)
    context["finished_utc"] = datetime.now(timezone.utc).isoformat()
    after = source_inputs()
    context["source_inputs_changed"] = sorted(p for p in set(after) | set(context["source_inputs"])
                                              if after.get(p) != context["source_inputs"].get(p))
    context["summary_sha256"] = hashlib.sha256(summary.read_bytes()).hexdigest()
    (destination / "context.json").write_text(json.dumps(context, indent=2) + "\n")
    (destination / "results.json").write_text(json.dumps(results, indent=2) + "\n")
    return 0 if not context["source_inputs_changed"] and all(
        r["result"] in {"PASS", "N/A"} for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
