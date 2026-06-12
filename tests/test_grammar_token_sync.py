"""The DSL grammar has a single source of truth.

Drift-map Finding #9 once described *three* statements of the grammar (the regex
`TOKEN_RE`, the Lark `TOKEN_GRAMMAR` lexer, and the published EBNF/GBNF) that had
to be kept in agreement. The consolidation onto Lark removed the first two: there
is now one executable grammar, `lark_parser.LARK_GRAMMAR`, and the published
artifacts are generated from it. These guards keep it that way — no second
tokenizer reappears, and the published grammar stays derived from the live one.
"""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DSL = (ROOT / "audioforge" / "dsl.py").read_text()
LARK = (ROOT / "audioforge" / "lark_parser.py").read_text()


def _lark_terminals() -> set[str]:
    block = re.search(r'LARK_GRAMMAR = r"""(.*?)"""', LARK, re.DOTALL).group(1)
    return set(re.findall(r"^([A-Z][A-Z_]*):", block, re.MULTILINE))


def test_single_grammar_source_no_second_tokenizer():
    """The regex lexer and its separate token grammar are gone — the language is
    stated once (Finding #9 closed)."""
    assert "TOKEN_RE" not in DSL, "a second regex tokenizer reappeared in dsl.py"
    assert "class Parser" not in DSL, "a second hand-rolled parser reappeared"
    assert "TOKEN_GRAMMAR" not in LARK, "a separate Lark lexer grammar reappeared"
    assert LARK.count('Lark(') == 1, "more than one Lark grammar is constructed"


def test_lark_grammar_defines_core_terminals():
    terms = _lark_terminals()
    assert {"IDENT", "NUMBER", "STRING"} <= terms, (
        f"core lexical terminals missing from LARK_GRAMMAR: {terms}")


def test_published_ebnf_is_generated_from_lark_source():
    """`dsl_ebnf()` must embed the live LARK_GRAMMAR, so the documented grammar
    cannot drift from the executable one."""
    pytest.importorskip("lark")
    from audioforge.grammar import dsl_ebnf
    from audioforge.lark_parser import LARK_GRAMMAR
    ebnf = dsl_ebnf()
    needle = LARK_GRAMMAR.strip().splitlines()[0].strip()
    assert needle and needle in ebnf, (
        "dsl_ebnf() no longer embeds LARK_GRAMMAR — the published grammar may "
        "have become a hand-maintained mirror (Finding #9)"
    )


def test_published_gbnf_is_nonempty_and_covers_core_terminals():
    pytest.importorskip("lark")
    from audioforge.grammar import dsl_gbnf
    gbnf = dsl_gbnf()
    assert gbnf.strip(), "dsl_gbnf() returned empty"
    low = gbnf.lower()
    assert "ident" in low and ("string" in low or "number" in low), (
        "dsl_gbnf() lost its core terminals — grammar-constrained sampling "
        "would break (Finding #9)"
    )


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-q"]))
