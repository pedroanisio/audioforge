"""Drift-map Finding #8 — export-preset docs must match `sdk.EXPORT_PRESETS`.

`EXPORT_PRESETS` defines sample rate / bit depth / target LUFS for each
delivery preset. The README and DSL spec restate those numbers in prose, but
only `social_video` was ever asserted. A change to `broadcast`,
`cinematic_master`, or `web_preview` could leave the docs stale silently.

This derives the expected tokens from `EXPORT_PRESETS` and asserts the docs
clause for each preset carries the right kHz / bit / LUFS values.
"""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "docs" / "DSL_SPEC.md"
README = ROOT / "README.md"

pytest.importorskip("numpy")
from audioforge.sdk import EXPORT_PRESETS  # noqa: E402


def _preset_table_line(text: str) -> str:
    """Return the single line/paragraph that enumerates all four presets (the
    delivery-spec table prose), ignoring incidental code-example mentions."""
    for line in text.splitlines():
        if all(n in line for n in EXPORT_PRESETS):
            return line
    raise AssertionError("no line lists all export presets together")


def _preset_clause(line: str, name: str) -> str:
    """Within the table line, the prose run describing one preset: from its
    name up to the next preset name or a separator."""
    i = line.find(name)
    assert i != -1, f"preset '{name}' is not in the table line"
    tail = line[i + len(name): i + len(name) + 60]
    return re.split(r"social_video|broadcast|cinematic_master|web_preview", tail)[0]


def test_docs_spec_preset_values_match_constants():
    line = _preset_table_line(SPEC.read_text())
    for name, p in EXPORT_PRESETS.items():
        clause = _preset_clause(line, name)
        khz = str(p["sample_rate"] // 1000)          # 48000->48, 96000->96, 22050->22
        bit = str(p["bit_depth"])
        lufs = str(int(abs(p["target_lufs"])))       # -23.0 -> 23
        assert khz in clause, f"{name}: sample rate {khz}k missing in docs clause {clause!r}"
        assert bit in clause, f"{name}: bit depth {bit} missing in docs clause {clause!r}"
        assert lufs in clause, f"{name}: LUFS {lufs} missing in docs clause {clause!r}"


def test_readme_lists_every_preset_with_rate_and_depth():
    line = _preset_table_line(README.read_text())
    for name, p in EXPORT_PRESETS.items():
        clause = _preset_clause(line, name)
        khz = str(p["sample_rate"] // 1000)
        bit = str(p["bit_depth"])
        assert khz in clause and bit in clause, (
            f"README export-preset prose stale for '{name}': "
            f"expected {khz}k/{bit} in {clause!r} (Finding #8)"
        )


def test_all_presets_documented_in_both():
    for surface in (SPEC, README):
        text = surface.read_text()
        missing = [n for n in EXPORT_PRESETS if n not in text]
        assert not missing, f"{surface.name} omits presets: {missing}"


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-q"]))
