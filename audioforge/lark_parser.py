"""Lark-backed front end for the .af DSL.

This module is intentionally conservative: Lark owns the executable grammar
entry point, catches source-shape errors first, and produces the token stream
fed to the existing AST parser while the transformer migration proceeds. That
keeps current IR output stable while preventing the published grammar and
runtime syntax front end from being separate, hand-maintained concepts.
"""
from __future__ import annotations

from functools import lru_cache

from lark import Lark
from lark.exceptions import LarkError, UnexpectedInput


TOKEN_GRAMMAR = r"""
start: (COMMENT | STRING | NUMBER | IDENT | PUNCT | NL)*

COMMENT: /\#[^\n]*/
STRING: /"[^"\n]*"/
NUMBER: /[+-]?\d+(\.\d+)?(s|b|bpm|db|hz|st|c|deg|m)?\b/
IDENT: /[A-Za-z_][A-Za-z0-9_#]*/
PUNCT: /[{}():,@=.]/
NL: /\n/
%ignore /[ \t\r]+/
"""


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
def token_lexer() -> Lark:
    return Lark(TOKEN_GRAMMAR, parser="lalr", maybe_placeholders=False)


@lru_cache(maxsize=1)
def lark_parser() -> Lark:
    return Lark(LARK_GRAMMAR, parser="earley", maybe_placeholders=False)


def lark_tokenize(src: str):
    """Tokenize DSL text with Lark into the existing Tok stream shape."""
    from .dsl import DSLError, Tok

    toks = []
    last_was_nl = False
    try:
        lexed = token_lexer().lex(src)
        for token in lexed:
            kind = token.type
            text = str(token)
            line = token.line
            if kind == "COMMENT":
                continue
            if kind == "NL":
                if toks and not last_was_nl:
                    toks.append(Tok("NL", "\n", line))
                last_was_nl = True
                continue
            last_was_nl = False
            if kind == "STRING":
                toks.append(Tok("STRING", text[1:-1], line))
            elif kind == "NUMBER":
                unit = None
                for suffix in ("bpm", "deg", "db", "hz", "st", "s", "b", "c", "m"):
                    if text.endswith(suffix):
                        unit = suffix
                        break
                number = text[: -len(unit)] if unit else text
                toks.append(Tok("NUMBER", text, line, float(number), unit))
            else:
                toks.append(Tok(kind, text, line))
    except LarkError as exc:
        raise _syntax_error(exc) from None
    except ValueError as exc:
        raise DSLError(str(exc)) from None
    line = src.count("\n") + 1
    toks.append(Tok("EOF", "", line))
    return toks


def parse_assets(src: str):
    """Parse DSL text into the legacy Asset AST shape.

    Lark is the mandatory syntax front end. The legacy parser remains the AST
    adapter so compile output and diagnostics stay compatible during migration.
    """
    from .dsl import Parser

    try:
        lark_parser().parse(src)
    except LarkError as exc:
        raise _syntax_error(exc) from None
    return Parser(lark_tokenize(src)).parse()
