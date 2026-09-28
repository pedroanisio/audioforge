"""Lark-backed front end for the .af DSL — the single parsing path.

`LARK_GRAMMAR` is the one executable grammar for the language: it owns lexing
and structure, and `parse_assets` walks the resulting parse tree directly into
the `Asset`/`Layer` AST the compiler consumes. There is no second tokenizer and
no hand-rolled recursive-descent parser; the grammar published as EBNF/GBNF in
`audioforge.grammar` is this same source. Closing audit finding F9 (two parsers
for one language) and tightening F8 (grammar artifacts as a faithful mirror).

The walker is deliberately top-down and stateful (mirroring the previous
recursive-descent order) so slur-group counters and pending motif `play`
expansions are assigned in source order — the AST is identical to what the
legacy parser produced, which the corpus oracle test pins.
"""
from __future__ import annotations

from functools import lru_cache

from lark import Lark, Token, Tree
from lark.exceptions import LarkError, UnexpectedInput


# The single executable grammar for the .af DSL. Block structure and the
# musically meaningful statements (note events, slurs, motif plays, automation
# breakpoints, markers, intent fields) are described here; genuinely free-form
# property bodies are captured as `value` token runs that the compiler
# interprets — the same division of labour the language always had.
LARK_GRAMMAR = r"""
start: (asset | _NL)*

asset: "asset" IDENT "{" (_item | _NL)* "}"
_item: marker | motif | intent | layer | stage | cutdowns | bus | master | prop

prop: IDENT COLON value

marker: "marker" IDENT AT NUMBER

motif: "motif" IDENT "{" (note_event | _NL)* "}"

intent: "intent" "{" (field | _NL)* "}"
field: IDENT COLON value

layer: "layer" IDENT COLON IDENT "{" (_litem | _NL)* "}"
// `note_event`/`slur_group` are not valid bare layer lines; they are admitted
// only so a file that scatters events under a `notes:` header onto later lines
// parses far enough for the walker to raise the precise legacy "same-line"
// diagnostic at the offending `notes:` (see `notes` / `_bare_note`).
_litem: notes_stmt | play_stmt | auto_stmt | note_event | slur_group | prop
notes_stmt: "notes" COLON [note_list]
auto_stmt: "auto" IDENT COLON breakpoint (COMMA _NL* breakpoint)*

bus: "bus" IDENT "{" (_block_item | _NL)* "}"
master: "master" "{" (_block_item | _NL)* "}"
_block_item: auto_stmt | prop

stage: "stage" "{" (stage_kv | _NL)* "}"
stage_kv: IDENT COLON value

cutdowns: "cutdowns" "{" (cutdown_line | _NL)* "}"
cutdown_line: NUMBER COLON value

note_list: note_entry (COMMA _NL* note_entry)*
note_entry: note_event | slur_group
slur_group: "slur" LPAR _NL* slur_body _NL* RPAR
slur_body: play_in_slur (COMMA _NL* play_in_slur)*   -> slur_plays
         | note_event (COMMA _NL* note_event)*        -> slur_notes

note_event: note_head AT NUMBER "for" NUMBER note_mod*
note_head: IDENT | NUMBER
note_mod: "vel" NUMBER     -> nm_vel
        | "voicing" IDENT  -> nm_voicing
        | "art" IDENT      -> nm_art
        | "gen" IDENT      -> nm_gen
        | "tech" IDENT [LPAR tech_args RPAR] -> nm_tech
        | "cutoff" LPAR NUMBER RPAR -> nm_cutoff
        | "level" LPAR NUMBER RPAR -> nm_level
        | "scan" LPAR NUMBER RPAR -> nm_scan
        | "string" NUMBER -> nm_string
        | "fret" (NUMBER | IDENT) -> nm_fret

tech_args: tech_arg (COMMA tech_arg)*
tech_arg: IDENT EQ (NUMBER | IDENT | STRING)

play_stmt: "play" IDENT AT NUMBER play_mod*
play_in_slur: "play" IDENT AT NUMBER play_mod*
play_mod: "legato"           -> pm_legato
        | "invert"           -> pm_invert
        | "retrograde"       -> pm_retro
        | "art" IDENT        -> pm_art
        | "stretch" NUMBER   -> pm_stretch
        | "diatonic" NUMBER  -> pm_diatonic
        | "transpose" NUMBER -> pm_transpose
        | "vel" NUMBER       -> pm_vel

breakpoint: NUMBER EQ NUMBER

value: _vitem*
_vitem: _scalar | AT | EQ | DOT | COLON | group | _vcomma
_vcomma: COMMA _NL*
group: LPAR _gitem* RPAR
_gitem: _scalar | AT | EQ | DOT | COLON | COMMA | group | _NL
_scalar: IDENT | NUMBER | STRING

IDENT: /[A-Za-z_][A-Za-z0-9_#]*/
NUMBER: /[+-]?\d+(\.\d+)?([eE][+-]?\d+)?(s|b|bpm|db|hz|st|c|deg|m)?\b/
STRING: /"(?:\\.|[^"\\\n])*"/
AT: "@"
EQ: "="
DOT: "."
COLON: ":"
COMMA: ","
LPAR: "("
RPAR: ")"
_NL: /(\r?\n)+/
%ignore /[ \t\r]+/
%ignore /\#[^\n]*/
"""

# Order matters: longer/ambiguous suffixes first so "12st" -> "st" (not "s"),
# "-12db" -> "db" (not "b"), "100bpm" -> "bpm". Mirrors the regex UNIT group the
# legacy tokenizer relied on.
_NUMBER_UNITS = ("bpm", "deg", "db", "hz", "st", "s", "b", "c", "m")


def _syntax_error(exc: LarkError):
    from .dsl import DSLError

    if isinstance(exc, UnexpectedInput):
        line = exc.line if exc.line and exc.line > 0 else 1
        return DSLError("invalid DSL syntax", line)
    return DSLError(str(exc))


@lru_cache(maxsize=2)
def _grammar_parser(algorithm: str) -> Lark:
    """The one grammar (LARK_GRAMMAR) compiled with a parsing algorithm."""
    return Lark(LARK_GRAMMAR, parser=algorithm, maybe_placeholders=False)


def lark_parser() -> Lark:
    """LALR(1) parser: the grammar compiles with no LALR conflicts, so it is
    unambiguous and every successful parse is the unique tree Earley would
    also build (checked on the whole corpus) -- at ~65x lower cost."""
    return _grammar_parser("lalr")


def _earley_parser() -> Lark:
    """Error path only: Earley accepts more malformed input, so the AST
    builder can name the offending entry instead of a bare syntax error."""
    return _grammar_parser("earley")


def _num_unit(text: str) -> str | None:
    for suffix in _NUMBER_UNITS:
        if text.endswith(suffix):
            return suffix
    return None


def _tok(token: Token):
    """Convert a Lark terminal into the `Tok` shape the compiler consumes."""
    from .dsl import Tok

    kind = token.type
    text = str(token)
    line = token.line
    if kind == "STRING":
        import json
        from .dsl import DSLError
        try:
            return Tok("STRING", json.loads(text), line)
        except ValueError as exc:
            raise DSLError("invalid quoted JSON string escape", line) from exc
    if kind == "NUMBER":
        unit = _num_unit(text)
        number = text[: -len(unit)] if unit else text
        return Tok("NUMBER", text, line, float(number), unit)
    if kind == "IDENT":
        return Tok("IDENT", text, line)
    # AT / EQ / DOT / COLON / COMMA / LPAR / RPAR
    return Tok("PUNCT", text, line)


def _flatten_value(node: Tree) -> list:
    """Flatten a `value`/`group` subtree to the ordered raw-token list the
    compiler expects (newlines already excluded by the grammar)."""
    out = []
    for child in node.children:
        if isinstance(child, Token):
            out.append(_tok(child))
        else:  # nested group subtree
            out.extend(_flatten_value(child))
    return out


def _tokens(node: Tree, kind: str) -> list[Token]:
    return [c for c in node.children if isinstance(c, Token) and c.type == kind]


def _subtrees(node: Tree) -> list[Tree]:
    return [c for c in node.children if isinstance(c, Tree)]


class _Builder:
    """Walks a parsed tree into the Asset AST, mirroring the historical
    recursive-descent order so stateful expansions are byte-identical."""

    def __init__(self):
        from .dsl import ARTICULATIONS, INTENT_FIELDS, NOTE_RE
        from . import theory

        self._slur_counter = 0
        self._pending_plays: list[dict] = []
        self._ARTICULATIONS = ARTICULATIONS
        self._INTENT_FIELDS = INTENT_FIELDS
        self._NOTE_RE = NOTE_RE
        self._theory = theory

    # entry ------------------------------------------------------------
    def build(self, tree: Tree):
        from .dsl import DSLError

        assets = [self.asset(t) for t in _subtrees(tree)]
        if not assets:
            raise DSLError("no 'asset' block found", 1)
        return assets

    def asset(self, t: Tree):
        from .dsl import Asset

        name = t.children[0]
        a = Asset(id=str(name), line=name.line)
        for item in t.children[1:]:
            self._dispatch(a, item)
        return a

    def _dispatch(self, a, item: Tree):
        getattr(self, f"_{item.data}")(a, item)

    # asset-body statements -------------------------------------------
    def _prop(self, a, t: Tree):
        key = str(t.children[0])
        a.props[key] = self._value_of(t)

    def _marker(self, a, t: Tree):
        name = str(t.children[0])
        num = _tokens(t, "NUMBER")[0]
        a.markers.append({"name": name, "time_s": self._seconds(_tok(num))})

    def _motif(self, a, t: Tree):
        name = str(t.children[0])
        a.motifs[name] = [self.note_event(ev) for ev in _subtrees(t)]

    def _intent(self, a, t: Tree):
        from .dsl import DSLError

        if a.intent:
            raise DSLError("asset may contain only one intent block", t.children[0].line)
        for field in _subtrees(t):
            key = str(field.children[0])
            vals = self._value_of(field)
            if key not in self._INTENT_FIELDS:
                line = vals[0].line if vals else field.children[0].line
                raise DSLError(f"unknown intent field '{key}'", line)
            a.intent[key] = vals

    def _stage(self, a, t: Tree):
        a.stage = self.stage(t, a.line)

    def _cutdowns(self, a, t: Tree):
        for line in _subtrees(t):
            a.cutdowns.append(self.cutdown(line))

    def _bus(self, a, t: Tree):
        name = str(t.children[0])
        b: dict = {"name": name, "line": t.children[0].line}
        for item in t.children[1:]:
            self._block_kv(b, item)
        a.buses.append(b)

    def _master(self, a, t: Tree):
        for item in t.children:
            self._block_kv(a.master, item)

    def _layer(self, a, t: Tree):
        from .dsl import Layer

        name = t.children[0]
        ltype = str(t.children[2])  # children: name, COLON, type, *items
        lay = Layer(name=str(name), type=ltype, line=name.line)
        for item in t.children[3:]:
            data = item.data
            if data == "notes_stmt":
                lay.props.setdefault("notes", []).extend(self.notes(item))
                if self._pending_plays:
                    lay.props.setdefault("plays", []).extend(self._pending_plays)
                    self._pending_plays = []
            elif data == "play_stmt":
                lay.props.setdefault("plays", []).append(self.play(item))
            elif data == "auto_stmt":
                tgt, pts = self.auto(item)
                lay.props.setdefault("auto", []).append((tgt, pts))
            elif data == "note_event":
                self._bare_note(item)
            elif data == "slur_group":
                from .dsl import DSLError
                lpar = _tokens(item, "LPAR")[0]
                raise DSLError("expected ':', got '('", lpar.line)
            else:  # prop
                key = str(item.children[0])
                if key == "curves":
                    lay.props.setdefault(key, []).append(self._value_of(item))
                else:
                    lay.props[key] = self._value_of(item)
        a.layers.append(lay)

    def _bare_note(self, item: Tree):
        """A note event written as a bare layer line — never valid. The legacy
        parser routed it through `prop_line` and failed at the missing colon."""
        from .dsl import DSLError

        head = item.children[0].children[0]
        at = _tokens(item, "AT")
        raise DSLError(f"expected ':', got {'@' if at else str(head)!r}", head.line)

    # shared helpers ---------------------------------------------------
    def _block_kv(self, target: dict, item: Tree):
        """bus/master share: generic prop or an `auto` automation target."""
        if item.data == "auto_stmt":
            tgt, pts = self.auto(item)
            target.setdefault("auto", []).append((tgt, pts))
        else:  # prop
            target[str(item.children[0])] = self._value_of(item)

    def _value_of(self, stmt: Tree) -> list:
        """The `value` subtree is the last child of prop/field/stage_kv lines."""
        for child in reversed(stmt.children):
            if isinstance(child, Tree) and child.data == "value":
                return _flatten_value(child)
        return []

    def _seconds(self, t) -> float:
        from .dsl import DSLError

        if t.kind != "NUMBER":
            raise DSLError(f"expected a time, got {t.text!r}", t.line)
        if t.unit in (None, "s"):
            return t.value
        raise DSLError(f"expected seconds, got unit '{t.unit}'", t.line)

    # note events ------------------------------------------------------
    def note_event(self, t: Tree) -> dict:
        from .dsl import DSLError

        head = _tok(t.children[0].children[0])
        ev: dict = {}
        if head.kind == "IDENT" and self._NOTE_RE.match(head.text):
            ev["note"] = head.text
        elif head.kind == "IDENT" and self._theory.parse_chord(head.text):
            root, quality = self._theory.parse_chord(head.text)
            ev["chord_root"] = root
            ev["chord"] = quality
        elif head.kind == "NUMBER" and head.unit == "hz":
            ev["freq_hz"] = head.value
        elif head.kind == "IDENT" and head.text == "play":
            raise DSLError(
                "play is a layer-body statement (one per line), not a "
                "notes: entry — write it on its own line inside the layer, "
                "or use slur( play … ) for a slurred motif group", head.line)
        else:
            raise DSLError(f"expected a note (e.g. C4), chord (e.g. C3min7) "
                           f"or NNNhz, got {head.text!r}", head.line)

        nums = [_tok(n) for n in _tokens(t, "NUMBER")]
        start = nums[0]
        if start.unit not in (None, "b"):
            raise DSLError("note start must be in beats (e.g. 2b)", start.line)
        ev["start_beat"] = start.value
        dur = nums[1]
        if dur.unit not in (None, "b"):
            raise DSLError("note duration must be in beats", dur.line)
        ev["dur_beats"] = dur.value

        for mod in _subtrees(t)[1:]:  # children[0] is note_head
            self._note_mod(ev, mod, head.line)
        return ev

    def _note_mod(self, ev: dict, mod: Tree, note_line: int):
        from .dsl import DSLError

        data = mod.data
        if data == "nm_vel":
            ev["vel"] = _tok(mod.children[0]).value
        elif data == "nm_art":
            art = str(mod.children[0])
            if art not in self._ARTICULATIONS:
                raise DSLError(f"unknown articulation '{art}' "
                               f"(available: {sorted(self._ARTICULATIONS)})",
                               note_line)
            ev["art"] = art
        elif data == "nm_gen":
            ev["generated"] = str(mod.children[0])
        elif data == "nm_voicing":
            v = str(mod.children[0])
            if v not in self._theory.VOICINGS:
                raise DSLError(f"unknown voicing '{v}' "
                               f"(available: {self._theory.VOICINGS})", note_line)
            ev["voicing"] = v
        elif data == "nm_tech":
            ev["technique"] = str(mod.children[0])
            params = {}
            for arg in _subtrees(mod):
                if arg.data != "tech_args":
                    continue
                for item in _subtrees(arg):
                    key = str(item.children[0])
                    val = _tok(item.children[-1])
                    params[key] = val.value if val.kind == "NUMBER" else val.text
            if params:
                ev["tech_params"] = params
        elif data in {"nm_cutoff", "nm_level", "nm_scan"}:
            target = {
                "nm_cutoff": "cutoff",
                "nm_level": "level",
                "nm_scan": "scan",
            }[data]
            value = _tok(_tokens(mod, "NUMBER")[0])
            if target == "cutoff" and value.unit not in (None, "hz"):
                raise DSLError("cutoff() expects hertz, e.g. cutoff(2500hz)",
                               value.line)
            if target == "level" and value.unit not in (None, "db"):
                raise DSLError("level() expects dB, e.g. level(-3db)",
                               value.line)
            if target == "scan" and value.unit is not None:
                raise DSLError("scan() expects a unitless 0..1 value",
                               value.line)
            ev.setdefault("curve_mods", []).append(
                {"name": target, "value": float(value.value)}
            )
        elif data == "nm_string":
            tok = _tok(_tokens(mod, "NUMBER")[0])
            if tok.unit is not None:
                raise DSLError("string expects a unitless index", tok.line)
            ev["string"] = int(tok.value)
        elif data == "nm_fret":
            child = mod.children[0]
            tok = _tok(child)
            if tok.kind == "NUMBER":
                if tok.unit is not None:
                    raise DSLError("fret expects a unitless index or x", tok.line)
                ev["fret"] = int(tok.value)
            elif tok.kind == "IDENT" and tok.text == "x":
                ev["fret"] = "x"
            else:
                raise DSLError("fret expects a unitless index or x", tok.line)

    # note lists & slurs ----------------------------------------------
    def notes(self, stmt: Tree) -> list[dict]:
        """`notes:` layer statement — the optional note_list, or the legacy
        same-line error when empty."""
        inner = [c for c in stmt.children if isinstance(c, Tree) and c.data == "note_list"]
        if not inner:
            self._empty_notes(stmt)
        return self.note_list(inner[0])

    def note_list(self, t: Tree) -> list[dict]:
        events: list[dict] = []
        for entry in _subtrees(t):
            events.extend(self._note_entry(entry))
        return events

    def _empty_notes(self, stmt: Tree):
        from .dsl import DSLError

        line = next((c.line for c in stmt.children if isinstance(c, Token)), 1)
        raise DSLError(
            "notes: needs its first event on the same line "
            "(continue across lines with trailing commas); play "
            "statements are layer-body lines, not notes: entries", line)

    def _note_entry(self, entry: Tree) -> list[dict]:
        inner = entry.children[0]
        if inner.data == "note_event":
            return [self.note_event(inner)]
        return self._slur(inner)

    def _slur(self, group: Tree) -> list[dict]:
        from .dsl import DSLError

        body = _subtrees(group)[0]  # children: LPAR, slur_body, RPAR
        if body.data == "slur_plays":
            self._slur_counter += 1
            gid = self._slur_counter
            for play in _subtrees(body):
                st = self.play(play)
                st["slur_group"] = gid
                self._pending_plays.append(st)
            return []
        # slur_notes
        notes = [self.note_event(ev) for ev in _subtrees(body)]
        if len(notes) < 2:
            rpar = _tokens(group, "RPAR")
            line = rpar[0].line if rpar else group.children[0].line
            raise DSLError("slur(...) needs at least two notes", line)
        self._slur_counter += 1
        for ev in notes:
            ev["slur"] = self._slur_counter
        return notes

    # motif plays ------------------------------------------------------
    def play(self, t: Tree) -> dict:
        from .dsl import DSLError

        name = str(t.children[0])
        at = _tok(_tokens(t, "NUMBER")[0])
        st = {"motif": name, "at_beat": at.value, "transpose_st": 0.0,
              "vel_scale": 1.0, "line": at.line}
        for mod in _subtrees(t):
            data = mod.data
            if data == "pm_legato":
                st["legato"] = True
            elif data == "pm_invert":
                st["invert"] = True
            elif data == "pm_retro":
                st["retrograde"] = True
            elif data == "pm_art":
                st["art"] = str(mod.children[0])
            elif data == "pm_stretch":
                st["stretch"] = _tok(mod.children[0]).value
            elif data == "pm_diatonic":
                st["diatonic"] = int(_tok(mod.children[0]).value)
            elif data == "pm_transpose":
                v = _tok(mod.children[0])
                if v.unit != "st":
                    raise DSLError("transpose needs semitones, e.g. +12st", v.line)
                st["transpose_st"] = v.value
            elif data == "pm_vel":
                st["vel_scale"] = _tok(mod.children[0]).value
        return st

    # automation -------------------------------------------------------
    def auto(self, t: Tree):
        from .dsl import DSLError

        tgt = str(t.children[0])
        pts = []
        last_line = t.children[0].line
        for bp in _subtrees(t):
            time_tok, val_tok = (_tok(n) for n in _tokens(bp, "NUMBER"))
            last_line = time_tok.line
            pts.append((self._seconds(time_tok), val_tok.value, val_tok.unit))
        if len(pts) < 2:
            raise DSLError("automation needs at least two breakpoints", last_line)
        return tgt, pts

    # stage ------------------------------------------------------------
    def stage(self, t: Tree, asset_line: int) -> dict:
        from .dsl import DSLError

        st: dict = {"mics": {"tree": 0.7, "close": 0.2, "ambient": 0.3},
                    "dims": [18.0, 26.0, 10.0]}
        for kv in _subtrees(t):
            key = str(kv.children[0])
            vals = self._value_of(kv)
            line = vals[0].line if vals else kv.children[0].line
            if key == "hall":
                if not vals or vals[0].kind != "STRING" or "@" not in vals[0].text:
                    raise DSLError('stage hall: "<ir.wav>@<sha256>" '
                                   '(content-addressed)', line)
                f, sha = vals[0].text.rsplit("@", 1)
                st["hall_file"], st["hall_sha256"] = f, sha
            elif key == "mics":
                self._stage_mics(st, vals, line)
            elif key == "size":
                self._stage_size(st, vals, line)
            else:
                raise DSLError(f"unknown stage property '{key}'", line)
        if "hall_file" not in st:
            raise DSLError("stage block needs a hall: \"ir@sha\" pin", asset_line)
        return st

    def _stage_mics(self, st: dict, vals: list, line: int):
        from .dsl import DSLError

        i = 0
        while i < len(vals):
            m = vals[i]
            if m.kind != "IDENT":
                i += 1
                continue
            if m.text not in ("tree", "close", "ambient"):
                raise DSLError(f"unknown mic '{m.text}' (tree/close/ambient)", m.line)
            # m '=' number  [',']
            st["mics"][m.text] = float(vals[i + 2].value)
            i += 3
            if i < len(vals) and vals[i].kind == "PUNCT" and vals[i].text == ",":
                i += 1

    def _stage_size(self, st: dict, vals: list, line: int):
        from .dsl import DSLError

        dims = [v for v in vals if v.kind == "NUMBER"]
        for d in dims:
            if d.unit not in (None, "m"):
                raise DSLError("stage size: W, L, H in meters", d.line)
        st["dims"] = [float(d.value) for d in dims]

    # cutdowns ---------------------------------------------------------
    def cutdown(self, t: Tree) -> dict:
        from .dsl import DSLError

        length = _tok(t.children[0])
        if length.kind != "NUMBER":
            raise DSLError("cutdown line: '15s: keep As to Bs, ...'", length.line)
        vals = self._value_of(t)
        cd = {"length_s": length.value, "segments": []}
        i = 0
        while i < len(vals):
            tk = vals[i]
            if tk.kind == "PUNCT" and tk.text == ",":
                i += 1
                continue
            if tk.kind == "IDENT" and tk.text == "keep":
                a_t, b_t = vals[i + 1], vals[i + 3]  # keep A to B
                cd["segments"].append([a_t.value, b_t.value])
                i += 4
            elif tk.kind == "IDENT" and tk.text == "fade":
                cd["fade_s"] = vals[i + 1].value
                i += 2
            else:
                raise DSLError(f"unexpected {tk.text!r} in cutdown line", tk.line)
        if not cd["segments"]:
            raise DSLError("cutdown needs at least one 'keep'", length.line)
        return cd


def parse_assets(src: str):
    """Parse .af DSL text into the Asset AST. Single grammar, single walk.

    ⚠ ARCHITECTURAL CONTRACT (PALS's LAW) — this is a deterministic transform,
    not LLM output; the corpus oracle / golden-snapshot regression tests pin its
    output so the grammar and the AST it produces cannot silently drift.
    """
    try:
        tree = lark_parser().parse(src)
    except LarkError:
        try:                                    # invalid input: re-parse for
            tree = _earley_parser().parse(src)  # the richer diagnostic
        except LarkError as exc:
            raise _syntax_error(exc) from None
    return _Builder().build(tree)
