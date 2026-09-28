---
disclaimer:
  notice: >-
    No information within this document should be taken for granted. Any statement
    or premise not backed by a real logical definition or verifiable reference may
    be invalid, erroneous, or a hallucination.
  generated_by: "Claude Opus 4.8 via Claude Code; revised by Claude Opus 5.5 via Claude Code"
  date: "2026-09-28"
---

# AudioForge codebase standards

The engineering bar, tagged by how strongly each rule is actually held. The
point is honesty: a rule is only **`[Enforced]`** if a named gate fails when it
is violated. If a gate is not cited, the rule is not enforced — do not pretend
otherwise.

- **`[Enforced]`** — a gate in `make check` (which CI runs, AF-R01) fails on
  violation. The gate is cited.
- **`[Adopted]`** — upheld by review convention; no automated gate yet.
- **`[Target]`** — committed direction, not yet enforced; the roadmap item that
  would enforce it is named.

## Rules

| Rule | Status | Gate / owner |
|------|--------|--------------|
| Renders are deterministic within one numeric environment | `[Enforced]` | `tests/test_determinism.py`, `spec_hash`, the golden lock `make golden-check` (AF-R06) |
| Every engine/DSL version literal agrees with `audioforge/version.py` | `[Enforced]` | `make version-check` = `python -m audioforge.tools.bump_version --check` (AF-R09); `tests/test_version_sources.py` |
| `docs/ir.schema.json` matches `ir_json_schema()` | `[Enforced]` | `make schema-check` = `python -m audioforge.tools.gen_ir_schema --check` (AF-R05) |
| `docs/capability-manifest.json` + `DIAGNOSTIC_CODES.md` match the runtime manifest | `[Enforced]` | `make manifest-check` = `python -m audioforge.tools.gen_capability --check` (AF-R07) |
| Runtime registries match their consumers (no silent registry drift) | `[Enforced]` | `make drift-check` = `scripts/drift_inspect.py --check` (AF-R13) |
| `make check` is the exact command CI runs | `[Enforced]` | `tests/test_ci_make_check_sync.py` (AF-R01) |
| The composed gate cannot silently lose a target | `[Enforced]` | `tests/test_makefile_targets.py` (AF-R02) |
| `AGENTS.md` documents exactly the `cli.py` verbs | `[Enforced]` | `tests/test_agents_md_sync.py` (AF-R03; matches hyphenated verbs since 2026-09-28) |
| `docs/INTEROP.md` matches `interop.COVERAGE` | `[Enforced]` | `make interop-check` (ADR-0011) |
| Generated docs pages (`reference.md`, `capabilities.md`) are in sync and the nav resolves | `[Enforced]` | `make docs-gen-check` (AF-R11) |
| A C compiler is present for the native kernels every render uses | `[Enforced]` | `make native-check` (ADR-0004, ADR-0012) |
| Native kernels are registered (`_native.ENGINE_KERNELS`, `schema.NATIVE_*`) and wrapped | `[Enforced]` | `make drift-check` (`scripts/drift_inspect.py`) |
| Native kernels match scipy where they promise bit-identity; SSE2/AVX2/AVX-512 builds agree | `[Adopted]` | `tests/test_native_resample.py` covers the scipy-exact kernels; cross-ISA identity was verified once for 3.2.0, not gated |
| Documentation does not drift from CLI/schema/version | `[Enforced]` | `tests/test_docs_regression.py`, `test_cli_docs_sync.py`, `test_schema_docs_coverage.py`, `test_native_kernel_docs.py` |
| Test coverage ≥ 90.1 % | `[Adopted]` | `fail_under = 90.1` is configured, but `coverage run -m pytest -q && coverage report` is not part of `make check` |
| `uv.lock` agrees with `pyproject.toml` | `[Enforced]` | `make lock-check` = `uv lock --check` (RM-B-004; CI installs uv; skipped loudly where uv is absent) |
| No 3.11-only stdlib constructs without a guarded fallback (Python 3.10 floor) | `[Enforced]` | `make floor-check` (RM-B-004); `HARNESS-PORT-001` runs the full gate on 3.10 |
| Diagnostics carry a machine-readable `code` from the capability manifest | `[Enforced]` | `tests/test_diagnostic_codes.py`, `tests/test_mcp_contract.py` (ADR-0008) |
| TDD (Red→Green→Refactor); production-ready only (no stubs) | `[Adopted]` | review convention; `CLAUDE.md` |
| AI-authored `.md` carries the Rule-5 disclaimer frontmatter | `[Adopted]` | manual — there is **no** automated disclaimer gate in this repo |
| Lint / format / type-check floor | `[Target]` | AF-R04 (no ruff/mypy config yet) |
| IR schema enums derive from `schema.py` registries | `[Enforced]` | `tests/test_schema_sources_sync.py` (AF-R08 Phase A, ADR-0005) |
| One typed IR model (unify `schema.py` + `ir_schema.py`) | `[Target]` | AF-R08 Phase B, deferred by the operator (ADR-0005) |
| MCP agent surface reuses the in-process facade | `[Enforced]` | AF-R10 (`tests/test_mcp_contract.py::test_server_reuses_run_tool_not_a_forked_path`) |

> **CI caveat (updated 2026-09-28).** `[Enforced]` presumes the CI workflow executes.
> Runs from 2026-07-04 ended in `startup_failure` with zero jobs
> (`docs/evolution/harness.md` HARNESS-CI-001); on 2026-09-28 the GitHub API reported
> no workflow runs at all for the repository, including for the 3.2.0 push. Until the
> repository admin restores Actions, these rules are enforced by the local
> `make check` only. The sync tests keep
> CI and the local gate identical, but identical to a gate that does not run.

## Source of truth per topic

One place answers "who owns this fact":

| Topic | Owner | Derived / gated artifacts |
|-------|-------|---------------------------|
| Engine / DSL version | `audioforge/version.py` | `pyproject.toml`, `README.md`, `CHANGELOG.md` (bump tool) |
| IR contract (kinds, layers, osc, fx, targets) | `audioforge/schema.py` registries (`ir_schema.py` derives its enums; typed model is AF-R08 Phase B) | `docs/ir.schema.json` |
| Capability surface + status + diagnostic codes | `audioforge/capabilities.py` | `docs/capability-manifest.json`, `docs/DIAGNOSTIC_CODES.md` |
| Determinism contract | `audioforge/determinism.py` | `tests/golden/audio.lock.json`, render manifests |
| CLI verbs | `audioforge/cli.py` | `AGENTS.md` (gated mirror) |
| DSL grammar | `audioforge/lark_parser.py::LARK_GRAMMAR` | EBNF/GBNF (`grammar` verb) |
| Interop coverage | `audioforge/interop.py::COVERAGE` | `docs/INTEROP.md` |
| Docs-site reference pages | `docs/ir.schema.json`, `docs/capability-manifest.json` via `gen_docs` | `docs/reference.md`, `docs/capabilities.md` |
| Native kernel registry | `audioforge/_native.py::ENGINE_KERNELS`, `schema.NATIVE_OSC_SHAPES` / `NATIVE_FX_TYPES` | `audioforge/native/*.c` (checked both ways by `drift_inspect.py`) |

> `drift-risk-map.md` previously flagged that `scripts/drift_inspect.py` was built
> but never invoked by the suite (MODERATE). AF-R13 wires it into `make check`, so
> that finding is resolved: the detector now runs on every gate.
