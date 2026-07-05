# AudioForge — composed local gate (roadmap item AF-R02).
#
# `make check` is THE gate: the single command a developer runs locally and the
# exact command CI runs (AF-R01). Every target is real — no stub gates. As
# generator-backed gates land (AF-R05 schema --check has; AF-R04 lint pending),
# add them as prerequisites of `check`; `tests/test_makefile_targets.py` pins the
# contract and `tests/test_ci_make_check_sync.py` keeps CI calling this same target.
#
# Self-documenting: `make` (or `make help`) lists every target and its purpose.

# Interpreter selection mirrors scripts/run_tests.sh: prefer the project venv
# when present, else python3 (CI installs deps into python3 directly). An
# explicit PYTHON=... on the command line or environment overrides this.
PYTHON ?= $(shell [ -x ./.venv/bin/python ] && printf '%s' ./.venv/bin/python || printf '%s' python3)
export PYTHON

.DEFAULT_GOAL := help
.PHONY: help check test native-check schema-check docs-check version-check clean

help:  ## List available targets
	@grep -hE '^[a-zA-Z0-9_.-]+:.*?## ' $(MAKEFILE_LIST) \
	  | sort \
	  | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

check: native-check schema-check test  ## Run the full local gate (what CI runs)

test:  ## Run the canonical suite (script suites + pytest) via run_tests.sh
	@sh scripts/run_tests.sh

native-check:  ## Verify a C compiler is present (deterministic kernels need it)
	@$(PYTHON) -c "import audioforge._native as n; \
	assert n.native_available(), \
	'no C compiler (cc/gcc/clang) found; deterministic native kernels cannot build'; \
	print('native-check: C compiler present')"

schema-check:  ## IR-schema drift gate: docs/ir.schema.json == ir_json_schema() (AF-R05)
	@$(PYTHON) -m audioforge.tools.gen_ir_schema --check

# --- Discrete fast gates (real subsets of the suite, for local iteration) ------
# Not prerequisites of `check` (the `test` target already runs them all); these
# exist so an agent or developer can run one drift class quickly.

docs-check:  ## Fast: documentation drift guards only
	@$(PYTHON) -m pytest -q tests/test_docs_regression.py tests/test_cli_docs_sync.py \
	  tests/test_export_presets_docs.py tests/test_native_kernel_docs.py

version-check:  ## Fast: version-source hygiene guards only
	@$(PYTHON) -m pytest -q tests/test_version_sources.py

clean:  ## Remove Python caches and compiled artifacts
	@find . -type d -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name '*.pyc' -delete 2>/dev/null || true
	@rm -rf .pytest_cache
