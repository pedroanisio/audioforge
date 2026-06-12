"""Drift-map Finding #10 — schema enums must be documented in the DSL spec.

The schema registries (kinds, oscillators, fx, articulations, …) are restated
as tables/prose in `docs/DSL_SPEC.md`. Only partial checks existed; a value
added to the engine could go undocumented silently. This asserts every member
of each registry appears in the spec, as a whole word, so a new enum value
forces a docs update.

(This is the docs-facing twin of `test_manifest_registry_coverage.py`, which
guards the same registries against the agent-facing capability manifest.)
"""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DOCS = (ROOT / "docs" / "DSL_SPEC.md").read_text()

pytest.importorskip("numpy")
from audioforge.schema import (FX_TYPES, KINDS, LAYER_TYPES, NOISE_COLORS,  # noqa: E402
                               OSC_SHAPES)
from audioforge.dsl import (ARTICULATIONS, DYNAMIC_MARKS, EMOTIONS,  # noqa: E402
                            GROOVE_TEMPLATES)


def _documented(value) -> bool:
    # whole-word / whole-token match, tolerant of the `#`-suffixed chord-ish
    # tokens never occurring here; values are short identifiers or ints.
    return re.search(rf"(?<![\w-]){re.escape(str(value))}(?![\w-])", DOCS) is not None


@pytest.mark.parametrize("registry_name, registry", [
    ("KINDS", KINDS),
    ("OSC_SHAPES", OSC_SHAPES),
    ("FX_TYPES", FX_TYPES),
    ("NOISE_COLORS", NOISE_COLORS),
    ("LAYER_TYPES", LAYER_TYPES),
    ("ARTICULATIONS", ARTICULATIONS),
    ("EMOTIONS", EMOTIONS),
    ("GROOVE_TEMPLATES", GROOVE_TEMPLATES),
    ("DYNAMIC_MARKS", tuple(DYNAMIC_MARKS)),
])
def test_every_enum_value_is_documented(registry_name, registry):
    missing = sorted(v for v in registry if not _documented(v))
    assert not missing, (
        f"{registry_name} values absent from docs/DSL_SPEC.md (Finding #10): "
        f"{missing} — document them in the spec tables"
    )


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-q"]))
