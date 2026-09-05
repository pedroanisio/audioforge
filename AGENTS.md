---
disclaimer:
  notice: >-
    No information within this document should be taken for granted. Any statement
    or premise not backed by a real logical definition or verifiable reference may
    be invalid, erroneous, or a hallucination. Every command below is derived from
    the live Makefile, pyproject.toml, and cli.py argparse surface; when in doubt,
    `make help` and `audioforge <verb> --help` are authoritative.
  generated_by: "Claude Opus 4.8 via Claude Code"
  date: "2026-07-04"
---

# AGENTS.md — programmatic CLI & tooling reference

The single agent-facing map from intent to exact command for **AudioForge**
(`audioforge/` — deterministic `.af` → WAV + manifest). `CLAUDE.md` lists this
file at position #2 in the reading order (AF-R03). It is a hand-maintained mirror
of the live surface; `tests/test_agents_md_sync.py` gates the CLI-verb list
against `cli.py`, so a verb cannot be added or removed without this file failing.

## 1 · Runtime

- **Python 3.10+**, deps `numpy`, `scipy`, `lark`, `matplotlib` (dev extras:
  `pytest`, `coverage`, `hypothesis`, `pyyaml`). Install: `pip install -e ".[dev]"`
  or `uv pip install -e ".[dev]"`.
- **A C compiler** (`cc`/`gcc`/`clang`) is required for the native kernels
  (bowed/blown/brass/struck/sympathetic oscillators, ladder/tape fx). They **fail
  loudly** if absent — `make native-check` asserts a compiler is present.
- Console script: `audioforge = audioforge.cli:main` (run `audioforge <verb>` or
  `python -m audioforge.cli <verb>`).

## 2 · CLI verbs

`audioforge <verb> …`. Run `audioforge <verb> --help` for exact arguments.

<!-- BEGIN cli-verbs -->
| Verb | Purpose |
|------|---------|
| `validate` | Validate an `.af` spec: resource **binding** + shape. `OK: valid` = render-ready; structured line-cited diagnostics otherwise. |
| `compile` | Compile `.af` → JSON IR (the hashed render contract) for inspection. |
| `render` | Render `.af` → WAV + manifest (`-o <dir>`, `--stems`). |
| `plan` | Emit the derived `audioforge.render-plan/1` (routes, fallbacks, evidence) before render. |
| `batch` | Render a directory of specs. |
| `pack` | One spec → a seeded variant pack (`--variants N`), hash-tracked in a pack manifest. |
| `campaign` | Spliced cutdowns (`cutdowns { … }`) from one premaster with per-cut loudness. |
| `libgen` | Build a content-addressed instrument library (pins sample bytes + mapping into one hash). |
| `ingest` | Ingest a sample-pack directory → hashed catalog + paste-ready snippets. |
| `decompile` | IR → `.af` source. |
| `repair` | Apply structured repairs to a spec. |
| `capabilities` | Emit the machine-readable capability manifest (see §6). |
| `grammar` | Emit the DSL grammar (EBNF/GBNF), derived from the single Lark grammar. |
| `score` | Score-layout output. |
| `verify` | Re-render a spec (compiled JSON IR or a single-asset `.af`) and SHA-256 compare against a manifest. Exit **0** = `REPRODUCIBLE`, **2** = `MISMATCH`, **1** = structured input error. |
<!-- END cli-verbs -->

## 3 · Make targets (the gate)

`make check` is THE composed gate — the exact command CI runs (AF-R01). Run
`make help` for the live list.

| Target | Runs |
|--------|------|
| `check` | `native-check schema-check manifest-check golden-check test` — the full local gate. |
| `test` | `scripts/run_tests.sh` — 16 script suites + `pytest -q`. |
| `native-check` | Assert a C compiler is present. |
| `schema-check` | IR-schema drift gate: `gen_ir_schema --check` (AF-R05). |
| `manifest-check` | Capability-manifest drift gate: `gen_capability --check` (AF-R07). |
| `golden-check` | Golden-audio drift gate: `render_golden --check` (AF-R06). |
| `docs-check` / `version-check` | Fast doc / version-hygiene subsets. |
| `clean` | Remove Python caches. |

Coverage is **not** in `make check`; run it yourself:
`coverage run -m pytest -q && coverage report` (`fail_under = 90.1`).

## 4 · Tooling & scripts

- **`audioforge/tools/`** — generators that OWN committed artifacts. Each has a
  `--write` (regenerate) and `--check` (fail-on-drift) twin; never hand-edit their
  outputs.
  - `python -m audioforge.tools.gen_ir_schema` → `docs/ir.schema.json` (AF-R05).
  - `python -m audioforge.tools.gen_capability` → `docs/capability-manifest.json`
    + `docs/DIAGNOSTIC_CODES.md` (AF-R07).
  - `python -m audioforge.tools.render_golden` → `tests/golden/audio.lock.json`
    (`--update` re-pins, `--check` gates, `--strict` for cross-env; AF-R06).
- **`scripts/`** — `run_tests.sh` (canonical runner), `drift_inspect.py` (registry
  drift, exit `0`/`1`), `check-backlog-governance.mjs` (backlog YAML validation).
  `build_*`, `gen_*`, `tune_*`, `import_sfz_library.py`, `catalog_instruments.py`
  are corpus/library builders; `_`-prefixed scripts are internal.

## 5 · Agent surface

Musical correctness probes: `python -m audioforge.tools.musical_acceptance --out DIR [--baseline-root CHECKOUT]` renders numerical cases and a standalone listening-review page. Generated WAVs remain outside Git. See `docs/MIGRATION_3.md` and `docs/MUSICAL_CORRECTNESS.md`.

- In-process facade: `audioforge.agent_tools.run_tool(operation, request)` over
  ops `compile, validate, plan, render, analyze, decompile, import, export,
  repair`; response envelope `schema: "audioforge.agent-tools/1"`
  (`ok`/`diagnostics`/`artifacts`/`engine_version`/`dsl_version`). See
  `docs/AGENT_TOOLS.md` and `examples/agent_loop.py`.
- `audioforge capabilities` (or the committed `docs/capability-manifest.json`)
  exposes the full capability surface including a derived per-capability `status`
  (`stable` = pure-Python; `experimental` = native-kernel/env-dependent).
- **MCP server** (AF-R10): `python -m audioforge.mcp` runs a stdio Model Context
  Protocol server (JSON-RPC 2.0, newline-delimited) exposing the nine
  `run_tool` ops plus `capabilities` and `verify` as tools — pure pass-throughs,
  no forked logic. A `render` call also emits session resources
  (`audioforge://session/{id}/{manifest.json,render.wav,waveform.png}`) so a
  vision-capable agent can read back and *see* the output. Pure-Python (no extra
  dependency). Contract-gated by `tests/test_mcp_contract.py`.

- **Coordination state** lives in `.agent-tasks/` (gitignored): `registry.json`
  holds active tasks, `locks/` one file per locked path, `archive/` closed tasks.
  `.current_task`, when present, must name a task that is in `registry.json`;
  a pointer to an archived task is stale and should be removed
  (`docs/evolution/harness.md` HARNESS-GOV-007).

## 6 · Generated-artifact policy

These files are **generated** — never hand-edit them; edit the source and rerun
the paired `--write`, then let the `--check` gate confirm:

| Artifact | Source | Regenerate |
|----------|--------|------------|
| `docs/ir.schema.json` | `audioforge/ir_schema.py::ir_json_schema` | `gen_ir_schema --write` |
| `docs/capability-manifest.json` | `audioforge/capabilities.py::capability_manifest` | `gen_capability --write` |
| `docs/DIAGNOSTIC_CODES.md` | same | `gen_capability --write` |
| `tests/golden/audio.lock.json` | `tests/golden/audio/*.af` renders | `render_golden --update` |

Rendered WAVs are **never** committed — the golden lock re-renders them. The DSL
grammar (`grammar` verb) is derived from `audioforge.lark_parser.LARK_GRAMMAR`.

## 7 · Architecture decisions (ADRs)

Load-bearing decisions live in `docs/adr/` (template: `docs/adr/adr-template.md`).
**Adoption rule (AF-R12):** any change that alters the **IR contract**, the
**determinism model**, or a **public surface** (CLI verbs, agent-tools/MCP tools,
generated artifacts) ships with an ADR — a new `docs/adr/NNNN-*.md` recording
Context / Decision / Consequences. Current records: ADR-0001 (determinism oracle),
0002 (non-vocal scope), 0003 (IR-is-truth), 0004 (native kernels fail loud), 0005
(one IR source of truth; Phase B deferred), 0006 (generator-owns-artifact),
0007 (musical rendering semantics and stable performance identity).
