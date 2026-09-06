# T1 — Foundation checkpoint (commit 4157c74, release/engine-3.0.0)

Filtered run: `HARNESS_ONLY` = the T1 gate rows (VCS-001, VCS-002, REL-004, PORT-001,
OBS-002, GATE-006, SEC-002) plus CI-001. Result: 7 PASS, 1 FAIL (CI-001). The gate is open.
CI-001 is diagnosed in `ci-root-cause.md`; the fix needs the repository admin (RM-B-002).
The Python 3.10 gate (PORT-001) took 201 s and passed after commit 5a3244f.
