"""Constrained-generation grammar artifacts for the .af DSL."""
from __future__ import annotations


_EBNF = r"""
file             = { asset } ;
asset            = "asset" IDENT "{" { asset_item } "}" ;
asset_item       = property | marker | motif | stage | cutdowns | bus | layer | master ;
property         = IDENT ":" value_list newline ;
smart_directive  = ("style" | "perform" | "ensemble" | "voicing" | "space") ":" value_list newline ;
marker           = "marker" IDENT "@" NUMBER "s" newline ;
motif            = "motif" IDENT "{" { note_event } "}" ;
layer            = "layer" IDENT ":" IDENT "{" { layer_item } "}" ;
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
transform        = "legato" | "invert" | "retrograde" | "stretch" NUMBER | "diatonic" SIGNED_NUMBER | "transpose" SIGNED_NUMBER "st" | "vel" NUMBER ;
value_list       = VALUE { VALUE | "," | "(" | ")" | "=" | "@" } ;
newline          = "\n" ;
"""


_GBNF = r"""
root ::= (asset ws*)+
asset ::= "asset" ws ident ws "{" ws asset-item* "}" ws
asset-item ::= smart-directive | property | marker | motif | bus | layer | master | stage | cutdowns
smart-directive ::= ("style" | "perform" | "ensemble" | "voicing" | "space") ":" value-list nl
property ::= ident ":" value-list nl
marker ::= "marker" ws ident ws "@" ws number "s" nl
motif ::= "motif" ws ident ws "{" ws note-event* "}" ws
layer ::= "layer" ws ident ws ":" ws ident ws "{" ws layer-item* "}" ws
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
    return _EBNF.strip() + "\n"


def dsl_gbnf() -> str:
    return _GBNF.strip() + "\n"

