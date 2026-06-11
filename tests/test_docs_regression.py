import sys
import re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from audioforge.grammar import dsl_ebnf, dsl_gbnf  # noqa: E402


ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "docs" / "DSL_SPEC.md"


def test_dsl_spec_review_regressions_stay_fixed():
    text = SPEC.read_text()
    assert "same engine version" in text
    assert "Same DSL text -> same IR" not in text
    assert "eight types" not in text
    assert "where `PITCH` is a note, frequency, or chord symbol" in text
    assert ". where `PITCH`" not in text
    assert "min7b5/m7b5" not in text
    assert "§7a" not in text
    assert "§11a" not in text
    assert "## 7a." not in text
    assert "## 11a." not in text
    assert "metadata for agents" not in text
    assert "silently skipped" not in text
    assert "Known gap" not in text
    for stale in ("Tier N", "Tier S", "architecture plan"):
        assert stale not in text
    assert re.search(r"\bP3'?s?\b", text) is None
    for row in ("| `deg` |", "| `m` |"):
        assert row in text
    for directive in ("style", "perform", "ensemble", "voicing", "space"):
        assert f"| `{directive}:` |" in text


def test_exported_grammar_lists_agent_directives_and_layer_kinds():
    ebnf = dsl_ebnf()
    gbnf = dsl_gbnf()
    assert "asset_item       = smart_directive" in ebnf
    assert "smart-directive" in gbnf
    for directive in ("style", "perform", "ensemble", "voicing", "space"):
        assert directive in ebnf
        assert directive in gbnf
    for kind in ("audio", "instrument", "foley"):
        assert f'"{kind}"' in ebnf
        assert f'"{kind}"' in gbnf
