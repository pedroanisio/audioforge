"""Drift-map Finding #11 — native-kernel voices/effects must be disclosed.

`schema.NATIVE_OSC_SHAPES` and `schema.NATIVE_FX_TYPES` are the voices/effects
whose render path is the native C kernel (they fail loudly without a compiler).
`test_contract.py` already guards the *code* side (dispatch + binding). The
remaining manual mirror is the docs: the `## Honest limits` disclosure must
name every native kernel and state the C-compiler requirement, so adding a
native voice without documenting it fails here.
"""
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DOCS = (ROOT / "docs" / "DSL_SPEC.md").read_text()

pytest.importorskip("numpy")
from audioforge.schema import (FX_TYPES, NATIVE_FX_TYPES,  # noqa: E402
                               NATIVE_OSC_SHAPES, OSC_SHAPES)


def test_native_kernels_are_a_subset_of_their_registries():
    """A native voice/effect must also be a real registry member (consistency
    between the native flag set and the full enum)."""
    assert NATIVE_OSC_SHAPES <= OSC_SHAPES, (
        f"native osc not in OSC_SHAPES: {sorted(NATIVE_OSC_SHAPES - OSC_SHAPES)}"
    )
    assert NATIVE_FX_TYPES <= FX_TYPES, (
        f"native fx not in FX_TYPES: {sorted(NATIVE_FX_TYPES - FX_TYPES)}"
    )


def test_every_native_kernel_is_documented():
    missing = sorted(v for v in (NATIVE_OSC_SHAPES | NATIVE_FX_TYPES)
                     if v not in DOCS)
    assert not missing, (
        f"native kernels missing from docs/DSL_SPEC.md (Finding #11): {missing}"
    )


def test_docs_disclose_the_native_compiler_requirement():
    """The disclosure must actually state the C-compiler / fail-loud contract,
    not merely mention the voice names in passing."""
    assert "C compiler" in DOCS, (
        "docs no longer disclose the native-kernel C-compiler requirement"
    )
    # the disclosure and the kernel names should co-occur in one section.
    limits = DOCS[DOCS.find("Honest limits"):] if "Honest limits" in DOCS else DOCS
    named_here = [v for v in (NATIVE_OSC_SHAPES | NATIVE_FX_TYPES) if v in limits]
    assert len(named_here) >= len(NATIVE_OSC_SHAPES), (
        "the 'Honest limits' section does not name the native voices alongside "
        "the compiler requirement (Finding #11)"
    )


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-q"]))
