"""Drift-map Finding #9 — the DSL grammar surfaces must stay in sync.

There are three statements of the lexical grammar:
  * `audioforge/dsl.py` `TOKEN_RE` — the legacy regex tokenizer's named groups;
  * `audioforge/lark_parser.py` `TOKEN_GRAMMAR` — the Lark lexer's terminals;
  * `audioforge/grammar.py` `dsl_ebnf()` / `dsl_gbnf()` — the published grammar
    (exposed via `audioforge grammar`), which is *generated* from
    `LARK_GRAMMAR`.

`test_lark_parser.py` already proves the two tokenizers produce identical token
streams on sample input. This adds the structural guard: the meaningful token
KINDS must match, and the published EBNF must remain generated from the Lark
source (not hand-maintained), so the documented grammar cannot silently drift.
"""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DSL = (ROOT / "audioforge" / "dsl.py").read_text()
LARK = (ROOT / "audioforge" / "lark_parser.py").read_text()

# `UNIT` is a sub-group *inside* the NUMBER token; `WS` is whitespace that Lark
# drops via `%ignore` rather than emitting as a terminal. Both are legitimately
# absent from the Lark terminal set, so they are not part of the comparison.
_DSL_ONLY_NONTERMINALS = {"UNIT", "WS"}


def _dsl_token_kinds() -> set[str]:
    return set(re.findall(r"\(\?P<([A-Z]+)>", DSL)) - _DSL_ONLY_NONTERMINALS


def _lark_token_terminals() -> set[str]:
    block = re.search(r'TOKEN_GRAMMAR = r"""(.*?)"""', LARK, re.DOTALL).group(1)
    return set(re.findall(r"^([A-Z]+):", block, re.MULTILINE))


def test_tokenizer_kind_sets_match():
    dsl_kinds = _dsl_token_kinds()
    lark_terms = _lark_token_terminals()
    assert dsl_kinds == lark_terms, (
        "token KINDS drifted between dsl.py TOKEN_RE and lark_parser.py "
        f"TOKEN_GRAMMAR (Finding #9): only-in-dsl={sorted(dsl_kinds - lark_terms)} "
        f"only-in-lark={sorted(lark_terms - dsl_kinds)}"
    )
    # sanity: the comparison is non-trivial
    assert {"IDENT", "NUMBER", "STRING", "PUNCT", "NL"} <= dsl_kinds


def test_published_ebnf_is_generated_from_lark_source():
    """`dsl_ebnf()` must embed the live LARK_GRAMMAR, so the documented grammar
    cannot drift from the executable one."""
    pytest.importorskip("lark")
    from audioforge.grammar import dsl_ebnf
    from audioforge.lark_parser import LARK_GRAMMAR
    ebnf = dsl_ebnf()
    # a distinctive chunk of the Lark source must appear verbatim in the EBNF
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
    # the GBNF must still describe the core lexical atoms agents rely on
    low = gbnf.lower()
    assert "ident" in low and ("string" in low or "number" in low), (
        "dsl_gbnf() lost its core terminals — grammar-constrained sampling "
        "would break (Finding #9)"
    )


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-q"]))
