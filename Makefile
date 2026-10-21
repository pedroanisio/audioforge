# AudioForge — composed local gate (roadmap item AF-R02).
#
# `make check` is THE gate: the single command a developer runs locally and the
# exact command CI runs (AF-R01). Every target is real — no stub gates. As
# generator-backed gates land (schema/manifest/golden/drift/version have;
# AF-R04 lint pending), add them as prerequisites of `check`;
# `tests/test_makefile_targets.py` pins the contract and
# `tests/test_ci_make_check_sync.py` keeps CI calling this same target.
#
# Self-documenting: `make` (or `make help`) lists every target and its purpose.

# Interpreter selection mirrors scripts/run_tests.sh: prefer the project venv
# when present, else python3 (CI installs deps into python3 directly). An
# explicit PYTHON=... on the command line or environment overrides this.
PYTHON ?= $(shell [ -x ./.venv/bin/python ] && printf '%s' ./.venv/bin/python || printf '%s' python3)
export PYTHON

.DEFAULT_GOAL := help
.PHONY: help check test native-check schema-check manifest-check interop-check golden-check drift-check version-check docs-gen-check lock-check floor-check oracle-check package-check docs docs-check clean

help:  ## List available targets
	@grep -hE '^[a-zA-Z0-9_.-]+:.*?## ' $(MAKEFILE_LIST) \
	  | sort \
	  | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

check: native-check schema-check manifest-check interop-check golden-check drift-check version-check docs-gen-check lock-check floor-check test  ## Run the full local gate (what CI runs)

test:  ## Run the canonical suite (script suites + pytest) via run_tests.sh
	@sh scripts/run_tests.sh

native-check:  ## Verify a C compiler is present (deterministic kernels need it)
	@$(PYTHON) -c "import audioforge._native as n; \
	assert n.native_available(), \
	'no C compiler (cc/gcc/clang) found; deterministic native kernels cannot build'; \
	print('native-check: C compiler present')"

schema-check:  ## IR-schema drift gate: docs/ir.schema.json == ir_json_schema() (AF-R05)
	@$(PYTHON) -m audioforge.tools.gen_ir_schema --check

manifest-check:  ## Capability-manifest drift gate: docs/capability-manifest.json + DIAGNOSTIC_CODES.md (AF-R07)
	@$(PYTHON) -m audioforge.tools.gen_capability --check

golden-check:  ## Golden-audio drift gate: re-render the corpus vs the hash lock (AF-R06)
	@$(PYTHON) -m audioforge.tools.render_golden --check

drift-check:  ## Registry drift gate: runtime registries vs their consumers (AF-R13)
	@$(PYTHON) scripts/drift_inspect.py --check

interop-check:  ## Interop coverage-matrix drift gate: docs/INTEROP.md is generated from audioforge.interop.COVERAGE (ADR-0011)
	@$(PYTHON) -m audioforge.tools.gen_interop --check

docs-gen-check:  ## Docs-site drift gate: generated reference/capabilities pages + nav resolve (AF-R11)
	@$(PYTHON) -m audioforge.tools.gen_docs --check

docs:  ## Build the docs site: regenerate pages then `mkdocs build --strict` (AF-R11; needs uv)
	@$(PYTHON) -m audioforge.tools.gen_docs --write
	@uv run --with mkdocs-material mkdocs build --strict

version-check:  ## Version-consistency gate: every version literal == version.py (AF-R09)
	@$(PYTHON) -m audioforge.tools.bump_version --check

lock-check:  ## Lockfile gate: uv.lock agrees with pyproject.toml (RM-B-004; CI installs uv; skips loudly without it)
	@if command -v uv >/dev/null 2>&1; then uv lock --check && echo "lock-check: uv.lock in sync with pyproject.toml"; \
	else echo "lock-check: SKIPPED — uv is not installed (install uv to enforce; CI does)"; fi

oracle-check:  ## Oracle gate: MusicXML XSD validity, music21 parity, LilyPond engraving (needs the `oracles` extra; skips loudly without it; ADR-0011)
	@$(PYTHON) -m audioforge.tools.oracle_check

package-check:  ## Distribution gate: build sdist+wheel, assert they carry every data file, install into a clean venv and render outside the repo (needs network; not in `check`)
	@$(PYTHON) -m audioforge.tools.package_check


floor-check:  ## Python-floor gate: no 3.11-only stdlib constructs without a guarded fallback (requires-python >= 3.10; RM-B-004)
	@if grep -rnE 'from datetime import[^#]*\bUTC\b|datetime\.UTC\b|^import tomllib\b|from typing import[^#]*\b(Self|LiteralString|Never)\b|\bStrEnum\b|except\*' --include='*.py' audioforge tests scripts; then \
	  echo "floor-check: 3.11-only construct found above; guard it or use a 3.10-compatible form"; exit 1; fi
	@echo "floor-check: no 3.11-only stdlib constructs in audioforge/ tests/ scripts/"

# --- Discrete fast gates (real subsets of the suite, for local iteration) ------
# Not prerequisites of `check` (the `test` target already runs them all); these
# exist so an agent or developer can run one drift class quickly.

docs-check:  ## Fast: documentation drift guards only
	@$(PYTHON) -m pytest -q tests/test_docs_regression.py tests/test_cli_docs_sync.py \
	  tests/test_export_presets_docs.py tests/test_native_kernel_docs.py

clean:  ## Remove Python caches and compiled artifacts
	@find . -type d -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name '*.pyc' -delete 2>/dev/null || true
	@rm -rf .pytest_cache
