"""Lark-backed front end for the .af DSL.

This module is intentionally conservative: Lark owns the executable grammar
entry point and catches source-shape errors first, then the existing parser is
used as an AST compatibility adapter while the compiler migration proceeds.
That keeps current IR output stable while preventing the published grammar and
runtime parser from being separate, hand-maintained concepts.
"""
from __future__ import annotations

from functools import lru_cache

from lark import Lark
from lark.exceptions import LarkError, UnexpectedInput


LARK_GRAMMAR = r"""
start: _NL* asset (_NL* asset)* _NL*

asset: "asset" _WS IDENT _WS? "{" body "}"
body: item*
item: block
    | TEXT
    | _NL

block: IDENT block_head? "{" body "}"
block_head: /[^\{\}\n]+/
TEXT: /[^\{\}\n]+/

IDENT: /[A-Za-z_][A-Za-z0-9_#]*/
_WS: /[ \t\r]+/
_NL: /\n+/
%ignore /[ \t\r]+/
%ignore /\#[^\n]*/
"""


def _syntax_error(exc: LarkError):
    from .dsl import DSLError

    if isinstance(exc, UnexpectedInput):
        line = exc.line if exc.line and exc.line > 0 else 1
        return DSLError("invalid DSL syntax", line)
    return DSLError(str(exc))


@lru_cache(maxsize=1)
def lark_parser() -> Lark:
    return Lark(LARK_GRAMMAR, parser="earley", maybe_placeholders=False)


def parse_assets(src: str):
    """Parse DSL text into the legacy Asset AST shape.

    Lark is the mandatory syntax front end. The legacy parser remains the AST
    adapter so compile output and diagnostics stay compatible during migration.
    """
    from .dsl import Parser, tokenize

    try:
        lark_parser().parse(src)
    except LarkError as exc:
        raise _syntax_error(exc) from None
    return Parser(tokenize(src)).parse()
