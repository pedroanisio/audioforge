---
disclaimer:
  notice: >-
    No information within this document should be taken for granted.
    Any statement or premise not backed by a real logical definition
    or verifiable reference may be invalid, erroneous, or a hallucination.
  generated_by: "Claude Fable 5.1 via Claude Code"
  date: "2026-09-05"
---

# HARNESS-CI-001 — GitHub Actions never executes a job (root-cause note, RM-B-002)

## Observed

| Fact | Evidence |
|---|---|
| Every run of both workflows ends in `startup_failure` with `jobs.total_count = 0` and 0 s duration | `gh run list --limit 100`: 7 runs 2026-07-04..07-05 on `main`; on 2026-09-05 the `push` and `pull_request` events for `release/engine-3.0.0` (runs 33998469102, 33998524669, and the later pushes) failed identically |
| Both workflow files parse as YAML and follow the documented schema | `python -c "import yaml; yaml.safe_load(...)"` on `ci.yml` and `backlog-governance.yml`; `tests/test_ci_make_check_sync.py` green |
| Actions are enabled for the repository with `allowed_actions: all` | `gh api repos/pedroanisio/audioforge/actions/permissions` |
| The repository is private | `gh api repos/pedroanisio/audioforge --jq .private` = true |
| The run API reports `path: "BuildFailed"`, `display_title: "(Unknown event)"`, `referenced_workflows: []` | `gh api repos/pedroanisio/audioforge/actions/runs/33998524669` |
| The token used here has scopes `gist, read:org, repo, workflow` and cannot read billing | `gh api -i /user`; `/users/pedroanisio/settings/billing/actions` → 404 (needs `user` scope) |

## Inference

A workflow-file defect would not fail a trivially simple second workflow identically,
and would normally surface an annotation. Zero jobs, zero seconds, both workflows,
private repository, over two months: this pattern matches an account-level Actions
condition — the Actions spending limit reached or set to $0, a failed payment method,
or Actions disabled for private repositories at the account level. Confidence: high
that the cause is account-level; the specific setting is unconfirmed.

## Operator action (repository admin)

1. GitHub → Settings (account) → Billing and plans → Plans and usage → Actions:
   check minutes used vs included, the spending limit, and any payment failure banner.
2. Repository → Settings → Actions → General: confirm "Allow all actions and reusable
   workflows" and that Actions are not disabled for the repository.
3. Re-run the latest failed run (`gh run rerun <id>`) or push an empty commit to the
   release branch and confirm `gh api …/actions/runs/<id>/jobs --jq .total_count` ≥ 1.
4. Record the finding and the fix in this file; `HARNESS-CI-001` flips to PASS when a
   job executes, `HARNESS-CI-002` when the matrix is green for the branch head.

## Interim

Until CI executes, the local matrix (`HARNESS-PORT-001…003`, three interpreters, same
`make check`) is the only evidence of portability, and the merge gate (M3 → M4) stays
closed by design: merging on local logs would repeat the failure mode this release exists
to end. Alternatives if the account cannot be fixed quickly: a self-hosted runner on the
reference machine (turns the reference machine into infrastructure), or another CI
provider (loses the `tests/test_ci_make_check_sync.py` pinning unless re-pointed).
