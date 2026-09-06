"""Tuning directive honesty (ADR-0011 §5; HARNESS-NTUN-003).

Until the n-EDO resolver lands (RN-T-002), a non-12 `tuning:` directive is metadata the
renderer never reads. Compiling one must say so with a registered diagnostic code rather
than rendering 12-TET silently.
"""
import re
from pathlib import Path

from audioforge import AudioForge
from audioforge.capabilities import capability_manifest
from audioforge.schema import TUNING_NOT_RENDERED_CODE

FIXTURES = Path(__file__).parent / "fixtures" / "notation"
SRC_19 = (FIXTURES / "microtonal_19edo.af").read_text()


def _tuning_diags(result):
    return [d for d in result.diagnostics if d.code == TUNING_NOT_RENDERED_CODE]


def test_non_12_edo_tuning_compiles_with_a_loud_registered_diagnostic():
    result = AudioForge().compile(SRC_19)
    assert result.ok, result.diagnostics
    hits = _tuning_diags(result)
    assert len(hits) == 1, result.diagnostics
    assert "divisions=19" in hits[0].message and "12-TET" in hits[0].message
    assert result.assets[0].spec["notation"]["tuning"]["divisions"] == 19
    assert TUNING_NOT_RENDERED_CODE in capability_manifest()["diagnostic_codes"]


def test_12_edo_and_absent_tuning_stay_silent():
    twelve = re.sub(r"divisions=19", "divisions=12", SRC_19)
    absent = "\n".join(l for l in SRC_19.splitlines() if not l.strip().startswith("tuning:"))
    for src in (twelve, absent):
        result = AudioForge().compile(src)
        assert result.ok, result.diagnostics
        assert not _tuning_diags(result), result.diagnostics
