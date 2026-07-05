---
disclaimer:
  notice: >-
    No information within this document should be taken for granted. Any statement
    or premise not backed by a real logical definition or verifiable reference may
    be invalid, erroneous, or a hallucination.
  generated_by: "Claude Opus 4.8 via Claude Code"
  date: "2026-07-05"
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
| Every engine/DSL version literal agrees with `audioforge/version.py` | `[Enforced]` | `make version-check` = `bump_version.py --check` (AF-R09); `tests/test_version_sources.py` |
| `docs/ir.schema.json` matches `ir_json_schema()` | `[Enforced]` | `make schema-check` = `gen_ir_schema.py --check` (AF-R05) |
| `docs/capability-manifest.json` + `DIAGNOSTIC_CODES.md` match the runtime manifest | `[Enforced]` | `make manifest-check` = `gen_capability.py --check` (AF-R07) |
| Runtime registries match their consumers (no silent registry drift) | `[Enforced]` | `make drift-check` = `scripts/drift_inspect.py --check` (AF-R13) |
| `make check` is the exact command CI runs | `[Enforced]` | `tests/test_ci_make_check_sync.py` (AF-R01) |
| The composed gate cannot silently lose a target | `[Enforced]` | `tests/test_makefile_targets.py` (AF-R02) |
| `AGENTS.md` documents exactly the `cli.py` verbs | `[Enforced]` | `tests/test_agents_md_sync.py` (AF-R03) |
| Documentation does not drift from CLI/schema/version | `[Enforced]` | `tests/test_docs_regression.py`, `test_cli_docs_sync.py`, `test_schema_docs_coverage.py` |
| Test coverage ≥ 90.1 % | `[Enforced]` | `coverage report` `fail_under = 90.1` (run outside `make check`) |
| TDD (Red→Green→Refactor); production-ready only (no stubs) | `[Adopted]` | review convention; `CLAUDE.md` |
| AI-authored `.md` carries the Rule-5 disclaimer frontmatter | `[Adopted]` | manual — there is **no** automated disclaimer gate in this repo |
| Lint / format / type-check floor | `[Target]` | AF-R04 (no ruff/mypy config yet) |
| One IR source of truth (unify `schema.py` + `ir_schema.py`) | `[Target]` | AF-R08 (dual hand-synced source, drift-map HIGH) |
| MCP agent surface reuses the in-process facade | `[Adopted]` | AF-R10 (`tests/test_mcp_contract.py`) |

## Source of truth per topic

One place answers "who owns this fact":

| Topic | Owner | Derived / gated artifacts |
|-------|-------|---------------------------|
| Engine / DSL version | `audioforge/version.py` | `pyproject.toml`, `README.md`, `CHANGELOG.md` (bump tool) |
| IR contract (kinds, layers, osc, fx, targets) | `audioforge/schema.py` (+ `ir_schema.py`, dual until AF-R08) | `docs/ir.schema.json` |
| Capability surface + status + diagnostic codes | `audioforge/capabilities.py` | `docs/capability-manifest.json`, `docs/DIAGNOSTIC_CODES.md` |
| Determinism contract | `audioforge/determinism.py` | `tests/golden/audio.lock.json`, render manifests |
| CLI verbs | `audioforge/cli.py` | `AGENTS.md` (gated mirror) |
| DSL grammar | `audioforge/lark_parser.py::LARK_GRAMMAR` | EBNF/GBNF (`grammar` verb) |

> `drift-risk-map.md` previously flagged that `scripts/drift_inspect.py` was built
> but never invoked by the suite (MODERATE). AF-R13 wires it into `make check`, so
> that finding is resolved: the detector now runs on every gate.
