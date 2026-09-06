---
disclaimer:
  notice: >-
    No information within this document should be taken for granted.
    Any statement or premise not backed by a real logical definition
    or verifiable reference may be invalid, erroneous, or a hallucination.
  generated_by: "Claude Fable 5.1 via Claude Code"
  date: "2026-09-05"
---

# T1 — Foundation checkpoint (commit 4157c74, release/engine-3.0.0)

## Disclaimer

This work is subject to the methodological caveats and commitments described in [@DISCLAIMER.md](../../../../DISCLAIMER.md).
> No statement or premise not backed by a real logical definition or verifiable reference should be taken for granted.

Back to the [root README](../../../../README.md) · harness: [docs/evolution/harness.md](../../harness.md)

Filtered run: `HARNESS_ONLY` = the T1 gate rows (VCS-001, VCS-002, REL-004, PORT-001,
OBS-002, GATE-006, SEC-002) plus CI-001. Result: 7 PASS, 1 FAIL (CI-001). The gate is open.
CI-001 is diagnosed in `ci-root-cause.md`; the fix needs the repository admin (RM-B-002).
The Python 3.10 gate (PORT-001) took 201 s and passed after commit 5a3244f.
