---
disclaimer:
  notice: >-
    No information within this document should be taken for granted.
    Any statement or premise not backed by a real logical definition
    or verifiable reference may be invalid, erroneous, or a hallucination.
  generated_by: "Claude Fable 5.1 via Claude Code"
  date: "2026-09-05"
---

# T2 — Core capabilities on a commit (commit 4157c74, release/engine-3.0.0)

## Disclaimer

This work is subject to the methodological caveats and commitments described in [@DISCLAIMER.md](../../../../DISCLAIMER.md).
> No statement or premise not backed by a real logical definition or verifiable reference should be taken for granted.

Back to the [root README](../../../../README.md) · harness: [docs/evolution/harness.md](../../harness.md)

Full run: 49 PASS, 8 FAIL, 2 MANUAL. Seven failures are operator-gated rows that cannot
pass yet (CI-001…004: Actions fail at startup; VCS-003: no approving review; VCS-004: not
merged; REL-003: not tagged). The eighth, MIG-001, failed because the runner used a
relative interpreter path after changing into the baseline export and rendered a spec the
`engine-2.16.0` tag does not contain (the golden corpus postdates it); the runner was fixed
and the row re-measured in `../T2-supplement/` (PASS: 2.16.0 manifest verified by 3.0.0
yields MISMATCH, exit 2). Every T2 gate row passes; the gate is open. `T2-attempt1/` is the
earlier run on cacee01 that exposed the runner defects.

Heavy rows: GATE-001 213 s, GATE-002 197 s, PORT-001 218 s, PORT-002 253 s (Python 3.11),
PORT-003 194 s (3.12), RB-002 120 s, SEC-001 250 s (`unshare -rn make test`).
