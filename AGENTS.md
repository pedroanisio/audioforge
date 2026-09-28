---
disclaimer:
  notice: >-
    No information within this document should be taken for granted. Any statement
    or premise not backed by a real logical definition or verifiable reference may
    be invalid, erroneous, or a hallucination. Every command below is derived from
    the live Makefile, pyproject.toml, and cli.py argparse surface; when in doubt,
    `make help` and `audioforge <verb> --help` are authoritative.
  generated_by: "Claude Opus 4.8 via Claude Code; revised by Claude Opus 5.5 via Claude Code"
  date: "2026-09-28"
---

# AGENTS.md — programmatic CLI & tooling reference

The single agent-facing map from intent to exact command for **AudioForge**
(`audioforge/` — deterministic `.af` → WAV + manifest). `CLAUDE.md` lists this
file at position #2 in the reading order (AF-R03). It is a hand-maintained mirror
of the live surface; `tests/test_agents_md_sync.py` gates the CLI-verb list
against `cli.py`, so a verb cannot be added or removed without this file failing.

## 1 · Runtime

- **Python 3.10+**, deps `numpy`, `scipy`, `lark`, `matplotlib` (dev extras:
  `pytest`, `coverage`, `hypothesis`, `pyyaml`, `tomli` on 3.10). Optional extras:
  `oracles` (MusicXML XSD, LilyPond, music21 on 3.11+) and `engrave` (LilyPond).
  Install: `uv sync --extra dev`, `pip install -e ".[dev]"` or `uv pip install -e ".[dev]"`.
- **A C compiler** (`cc`/`gcc`/`clang`) is required for **every render** (engine
  3.2+). The streaming DSP kernels in `audioforge/native/dsp.c` (true-peak limiter,
  biquads, Freeverb, FDN IRs, delay, saturation, wavetable voices, curves) have no
  Python fallback; the physical-model voices (bowed/blown/brass/struck/sympathetic),
  ladder/tape fx and modulated plate have their own kernels. Only `native/upfirdn.c`
  (`resample_poly`) falls back, bit-identically, to scipy. Kernels **fail loudly**
  without a compiler, are built `-O3 -march=native -ffp-contract=off` and cached per
  CPU in `$AUDIOFORGE_NATIVE_CACHE` (default `~/.cache/audioforge`); `make
  native-check` asserts a compiler is present. `validate` does not check for one.
- Optional system **libsndfile** decodes FLAC/Ogg/AIFF samples (WAV needs nothing).
- Environment: `AUDIOFORGE_JOBS` (layer threads; output identical for any value),
  `AUDIOFORGE_NATIVE_CACHE`, `AUDIOFORGE_MALLOC_TUNE=0` (leave glibc malloc alone
  during renders); importing `audioforge` first defaults `OPENBLAS_NUM_THREADS=1`.
- Console script: `audioforge = audioforge.cli:main` (run `audioforge <verb>` or
  `python -m audioforge.cli <verb>`); `audioforge --version` prints engine and DSL.

## 2 · CLI verbs

`audioforge <verb> …`. Run `audioforge <verb> --help` for exact arguments.

<!-- BEGIN cli-verbs -->
| Verb | Purpose |
|------|---------|
| `validate` | Validate an `.af` spec: resource **binding** + shape (`--no-resolve` = shape only). `OK: valid` = render-ready (given a C compiler); structured line-cited diagnostics and exit 1 otherwise. |
| `compile` | Compile `.af` → JSON IR (the hashed render contract) for inspection. |
| `render` | Render `.af` → WAV + manifest (`-o <dir>`, `--stems`, `--preset`, `--variant`, `--intensity`, `--jobs`, `--analyze`, `--plan`, `--explain`). |
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
| `score` | Proportional proof-sheet PDF: pitch, meter, dynamics, stage plot, intensity, provenance. Typeset engraving uses external LilyPond (ADR-0011); an integrated backend remains notation M5. |
| `export-midi` | Export compiled note events to a Standard MIDI File (`-o`). |
| `export-musicxml` | Export MusicXML 3.1 (`-o`; `--notated` quantizes to measures, `--bars`). |
| `import-midi` | Import a MIDI file to `.af`/IR (`--id`). |
| `import-musicxml` | Import a MusicXML file to `.af`/IR (`--id`). |
| `sample-catalog` | Public-domain sample pipeline: `search`, `resolve-openverse`, `download`, `analyze`, `build-sfz`, `audit-license`, `review`. |
| `verify` | Re-render a spec (compiled JSON IR or a single-asset `.af`) and SHA-256 compare against a manifest. Exit **0** = `REPRODUCIBLE`, **2** = `MISMATCH`, **1** = structured input error. |
<!-- END cli-verbs -->

## 3 · Make targets (the gate)

`make check` is THE composed gate — the exact command CI runs (AF-R01). Run
`make help` for the live list.

| Target | Runs |
|--------|------|
| `check` | `native-check schema-check manifest-check interop-check golden-check drift-check version-check docs-gen-check lock-check floor-check test` — the full local gate. |
| `test` | `scripts/run_tests.sh` — 16 script suites + `pytest -q`. |
| `native-check` | Assert a C compiler is present. |
| `schema-check` | IR-schema drift gate: `gen_ir_schema --check` (AF-R05). |
| `manifest-check` | Capability-manifest drift gate: `gen_capability --check` (AF-R07). |
| `interop-check` | Interop coverage-matrix drift gate: `gen_interop --check` regenerates `docs/INTEROP.md` from `audioforge.interop.COVERAGE` (ADR-0011). |
| `golden-check` | Golden-audio drift gate: `render_golden --check` (AF-R06). |
| `drift-check` | Registry drift gate: `scripts/drift_inspect.py --check` (AF-R13), incl. native kernels vs `_native.ENGINE_KERNELS`. |
| `version-check` | Version-consistency gate: `bump_version --check` (AF-R09). |
| `docs-gen-check` | Docs-site gate: `gen_docs --check` (generated pages in sync, nav resolves; AF-R11). |
| `docs-check` | Fast, not in `check`: the four doc-drift pytest files. |
| `docs` | `gen_docs --write` then `mkdocs build --strict` (needs uv). |
| `oracle-check` | MusicXML XSD validity, music21 parity and LilyPond engraving of the notation fixtures; needs `uv pip install -e '.[oracles]'`, skips loudly without it (ADR-0011; not composed into `check`). |
| `lock-check` / `floor-check` | `uv lock --check` (skips loudly without uv; CI installs it) / no 3.11-only stdlib constructs (the Python 3.10 floor, RM-B-004). |
| `clean` | Remove Python and pytest caches. |
| `help` | Default goal: list every target. |

Coverage is **not** in `make check`; run it yourself:
`coverage run -m pytest -q && coverage report` (`fail_under = 90.1`).

## 4 · Tooling & scripts

- **`audioforge/tools/`** — generators that OWN committed artifacts (never hand-edit
  their outputs) and gate runners. Run as `python -m audioforge.tools.<name>`:
  - `gen_ir_schema --write|--check` → `docs/ir.schema.json` (AF-R05).
  - `gen_capability --write|--check` → `docs/capability-manifest.json` +
    `docs/DIAGNOSTIC_CODES.md` (AF-R07).
  - `gen_interop --write|--check` → `docs/INTEROP.md` (construct × format matrix).
  - `gen_docs --write|--check` → `docs/reference.md` + `docs/capabilities.md` (AF-R11).
  - `render_golden --update|--check [--strict]` → `tests/golden/audio.lock.json` (AF-R06).
  - `bump_version --check`, or `bump_version X.Y.Z [--dsl D] [--dry-run]` (AF-R09;
    also update `docs/DSL_SPEC.md`'s header and `docs/RELEASE_NOTES.md`, which the
    docs tests pin, and the package's own version line in `uv.lock`).
  - `oracle_check` (behind `make oracle-check`), `notation_acceptance T1|T2|T3`,
    `musical_acceptance --out DIR`.
- **`scripts/`** — `run_tests.sh` (canonical runner), `drift_inspect.py` (registry
  drift, exit `0`/`1`), `check-backlog-governance.mjs` (backlog YAML validation).
  `build_*`, `gen_*`, `tune_*`, `import_sfz_library.py`, `catalog_instruments.py`
  are corpus/library builders; `harness.sh` / `harness-notation.sh` run the
  `docs/evolution/harness*.md` assertions; `examples.py` builds the composition
  catalog, pages and listening gallery; `_`-prefixed scripts are internal.

## 5 · Agent surface

Musical correctness probes: `python -m audioforge.tools.musical_acceptance --out DIR [--baseline-root CHECKOUT]` renders numerical cases and a standalone listening-review page. Generated WAVs remain outside Git. See `docs/MIGRATION_3.md` and `docs/MUSICAL_CORRECTNESS.md`.

- In-process facade: `audioforge.agent_tools.run_tool(operation, request)` over
  ops `compile, validate, plan, render, analyze, decompile, import, export,
  repair`; response envelope `schema: "audioforge.agent-tools/1"`
  (`ok`/`diagnostics`/`artifacts`/`engine_version`/`dsl_version`). In-process,
  `render` compiles and reports `renderable` per asset (no audio; use the SDK or the
  MCP `render` tool) and `import` returns an error envelope (file import is CLI-only).
  See `docs/AGENT_TOOLS.md` and `examples/agent_loop.py`.
- `audioforge capabilities` (or the committed `docs/capability-manifest.json`)
  exposes the full capability surface including a derived per-capability `status`
  (`experimental` = needs a dedicated voice/fx kernel or other environment support;
  since 3.2 every render needs the C toolchain regardless of status).
- **MCP server** (AF-R10): `python -m audioforge.mcp` runs a stdio Model Context
  Protocol server (JSON-RPC 2.0, newline-delimited) exposing the nine
  `run_tool` ops plus `capabilities` and `verify` (`{spec: <IR>, expected_sha256}`)
  as tools — pure pass-throughs, no forked logic. A `render` call renders the first
  compiled asset and emits session resources
  (`audioforge://session/{id}/{manifest.json,render.wav,waveform.png}`) so a
  vision-capable agent can read back and *see* the output. No extra dependency. Contract-gated by `tests/test_mcp_contract.py`.

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
| `docs/INTEROP.md` | `audioforge/interop.py::COVERAGE` | `gen_interop --write` |
| `docs/DIAGNOSTIC_CODES.md` | `audioforge/capabilities.py::capability_manifest` | `gen_capability --write` |
| `docs/reference.md` | `docs/ir.schema.json` | `gen_docs --write` |
| `docs/capabilities.md` | `docs/capability-manifest.json` | `gen_docs --write` |
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
0007 (musical rendering semantics and stable performance identity), 0008
(structured diagnostic codes on every Diagnostic and agent/MCP envelope), 0009
(native stereo samples and recorded interval playback), 0010 (composition examples
travel with their documentation and local renders), 0011 (notation: semantic contract
with oracle-verified interchange; engraving and musicology delegated), 0012 (native
DSP kernels on every render; bounded numeric drift per engine version).
