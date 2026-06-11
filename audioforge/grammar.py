"""Constrained-generation grammar artifacts for the .af DSL.

Generated from audioforge/lark_parser.py as the executable grammar source.
The EBNF/GBNF below are publishing forms kept aligned with that parser.
"""
from __future__ import annotations

from .lark_parser import LARK_GRAMMAR


_EBNF = r"""
(* Generated from audioforge/lark_parser.py. Executable Lark source:
__LARK_SOURCE__
*)

file             = { asset } ;
asset            = "asset" IDENT "{" { asset_item } "}" ;
asset_item       = smart_directive | intent_block | score_property | timing_property | property | marker | motif | stage | cutdowns | bus | layer | master ;
score_property   = meter | pickup | form | repeat | polymeter ;
property         = IDENT ":" value_list newline ;
timing_property  = ("fermata" | "hold") ":" hold_event { "," hold_event } newline ;
smart_directive  = ("style" | "perform" | "ensemble" | "voicing" | "space") ":" value_list newline ;
intent_block     = "intent" "{" { intent_field } "}" ;
intent_field     = ("density" | "contour" | "texture" | "affect" | "avoid" | "repair" | "style_text") ":" value_list newline ;
meter            = "meter" ":" NUMBER NUMBER newline ;
pickup           = "pickup" ":" NUMBER "b" newline ;
form             = "form" ":" IDENT NUMBER "b" "for" NUMBER "b" { "," IDENT NUMBER "b" "for" NUMBER "b" } newline ;
repeat           = "repeat" ":" IDENT "x" NUMBER newline ;
polymeter        = "polymeter" ":" IDENT NUMBER NUMBER newline ;
marker           = "marker" IDENT "@" NUMBER "s" newline ;
motif            = "motif" IDENT "{" { note_event } "}" ;
layer            = "layer" IDENT ":" ("tone" | "notes" | "sweep" | "noise" | "drums" | "grain" | "sample" | "audio" | "foley" | "instrument") "{" { layer_item } "}" ;
layer_item       = property | notes | play | automation ;
notes            = "notes" ":" note_entry { "," note_entry } newline ;
play             = "play" IDENT "@" NUMBER "b" { transform } newline ;
automation       = "auto" IDENT ":" breakpoint { "," breakpoint } newline ;
master           = "master" "{" { property | automation } "}" ;
bus              = "bus" IDENT "{" { property | automation } "}" ;
stage            = "stage" "{" { property } "}" ;
cutdowns         = "cutdowns" "{" { property } "}" ;
note_entry       = note_event | "slur" "(" note_event { "," note_event } ")" ;
note_event       = PITCH "@" NUMBER "b" "for" NUMBER "b" [ "vel" NUMBER ] [ "art" IDENT ] [ "voicing" IDENT ] ;
breakpoint       = NUMBER "s" "=" NUMBER [ UNIT ] ;
hold_event       = NUMBER "b" "=" NUMBER "s" ;
transform        = "legato" | "invert" | "retrograde" | "stretch" NUMBER | "diatonic" SIGNED_NUMBER | "transpose" SIGNED_NUMBER "st" | "vel" NUMBER ;
value_list       = VALUE { VALUE | "," | "(" | ")" | "=" | "@" } ;
newline          = "\n" ;
"""


_GBNF = r"""
# Generated from audioforge/lark_parser.py. Executable grammar source is
# exposed as audioforge.lark_parser.LARK_GRAMMAR.

root ::= (asset ws*)+
asset ::= "asset" ws ident ws "{" ws asset-item* "}" ws
asset-item ::= smart-directive | intent-block | score-property | timing-property | property | marker | motif | bus | layer | master | stage | cutdowns
score-property ::= meter | pickup | form | repeat | polymeter
meter ::= "meter:" ws number ws number nl
pickup ::= "pickup:" ws number "b" nl
form ::= "form:" ws ident ws number "b" ws "for" ws number "b" ("," ws ident ws number "b" ws "for" ws number "b")* nl
repeat ::= "repeat:" ws ident ws "x" number nl
polymeter ::= "polymeter:" ws ident ws number ws number nl
smart-directive ::= ("style" | "perform" | "ensemble" | "voicing" | "space") ":" value-list nl
intent-block ::= "intent" ws "{" ws intent-field* "}" ws
intent-field ::= ("density" | "contour" | "texture" | "affect" | "avoid" | "repair" | "style_text") ":" ws value-list nl
property ::= ident ":" value-list nl
timing-property ::= ("fermata" | "hold") ":" ws hold-event ("," ws hold-event)* nl
marker ::= "marker" ws ident ws "@" ws number "s" nl
motif ::= "motif" ws ident ws "{" ws note-event* "}" ws
layer ::= "layer" ws ident ws ":" ws layer-kind ws "{" ws layer-item* "}" ws
layer-kind ::= "tone" | "notes" | "sweep" | "noise" | "drums" | "grain" | "sample" | "audio" | "foley" | "instrument"
layer-item ::= property | notes | play | automation
notes ::= "notes:" ws note-entry ("," ws note-entry)* nl
play ::= "play" ws ident ws "@" ws number "b" (ws transform)* nl
automation ::= "auto" ws ident ":" ws breakpoint ("," ws breakpoint)* nl
master ::= "master" ws "{" ws (property | automation)* "}" ws
bus ::= "bus" ws ident ws "{" ws (property | automation)* "}" ws
stage ::= "stage" ws "{" ws property* "}" ws
cutdowns ::= "cutdowns" ws "{" ws property* "}" ws
note-entry ::= note-event | "slur(" ws note-event ("," ws note-event)+ ws ")"
note-event ::= pitch ws "@" ws number "b" ws "for" ws number "b" (ws "vel" ws number)? (ws "art" ws ident)? (ws "voicing" ws ident)?
breakpoint ::= number "s" ws "=" ws number unit?
hold-event ::= number "b" ws "=" ws number "s"
transform ::= "legato" | "invert" | "retrograde" | ("stretch" ws number) | ("diatonic" ws signed-number) | ("transpose" ws signed-number "st") | ("vel" ws number)
value-list ::= ([^\n{}]+)
pitch ::= [A-Ga-g] ("#" | "b")? "-"? [0-9]+ [A-Za-z0-9#b]*
ident ::= [A-Za-z_][A-Za-z0-9_#]*
number ::= "-"? [0-9]+ ("." [0-9]+)?
signed-number ::= ("+" | "-")? [0-9]+ ("." [0-9]+)?
unit ::= "s" | "b" | "bpm" | "db" | "hz" | "st" | "c" | "deg" | "m"
ws ::= ([ \t\r\n])*
nl ::= "\n"+
"""


def dsl_ebnf() -> str:
    return _EBNF.replace("__LARK_SOURCE__", LARK_GRAMMAR.strip()).strip() + "\n"


def dsl_gbnf() -> str:
    return _GBNF.strip() + "\n"
