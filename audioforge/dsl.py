"""AudioForge DSL (.af) — lexer, parser, compiler.

The DSL is the agent/human authoring surface. It compiles to the JSON spec
(the deterministic intermediate representation rendered by the engine).
Everything "semantic sugar" — emotion tags, intensity curves, motifs, key —
is expanded at compile time into explicit JSON parameters, so the IR remains
the single inspectable ground truth for what will be rendered.

Compilation returns (spec, diagnostics). Errors raise DSLError with line
numbers; diagnostics are non-fatal warnings agents can act on (out-of-scale
notes, hot gains, loop-safety issues).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from . import theory
from .lark_parser import parse_assets
from .synth import NOTE_OFFSETS
from .styles import STYLE_PACKS

DSL_VERSION = "1.0"


class DSLError(ValueError):
    def __init__(self, msg: str, line: int | None = None):
        super().__init__(f"line {line}: {msg}" if line else msg)
        self.line = line


# --------------------------------------------------------------------- lexer
TOKEN_RE = re.compile(r"""
    (?P<COMMENT>\#[^\n]*)
  | (?P<STRING>"[^"\n]*")
  | (?P<NUMBER>[+-]?\d+(\.\d+)?(?P<UNIT>s|b|bpm|db|hz|st|c|deg|m)?\b)
  | (?P<IDENT>[A-Za-z_][A-Za-z0-9_#]*)
  | (?P<PUNCT>[{}():,@=.])
  | (?P<NL>\n)
  | (?P<WS>[ \t\r]+)
""", re.VERBOSE)

NOTE_RE = re.compile(r"^[A-Ga-g][#b]?-?\d$")


@dataclass
class Tok:
    kind: str       # NUMBER | IDENT | PUNCT | NL | EOF
    text: str
    line: int
    value: float | None = None
    unit: str | None = None


def tokenize(src: str) -> list[Tok]:
    toks: list[Tok] = []
    line = 1
    pos = 0
    while pos < len(src):
        m = TOKEN_RE.match(src, pos)
        if not m:
            raise DSLError(f"unexpected character {src[pos]!r}", line)
        pos = m.end()
        kind = m.lastgroup if m.lastgroup != "UNIT" else "NUMBER"
        for k in ("COMMENT", "STRING", "NUMBER", "IDENT", "PUNCT", "NL",
                  "WS"):
            if m.group(k) is not None:
                kind = k
                break
        text = m.group(kind)
        if kind == "WS" or kind == "COMMENT":
            continue
        if kind == "NL":
            line += 1
            if toks and toks[-1].kind != "NL":
                toks.append(Tok("NL", "\n", line - 1))
            continue
        if kind == "STRING":
            toks.append(Tok("STRING", text[1:-1], line))
            continue
        if kind == "NUMBER":
            unit = m.group("UNIT")
            num = float(text[:-len(unit)]) if unit else float(text)
            toks.append(Tok("NUMBER", text, line, num, unit))
        else:
            toks.append(Tok(kind, text, line))
    toks.append(Tok("EOF", "", line))
    return toks


# -------------------------------------------------------------------- parser
@dataclass
class Layer:
    name: str
    type: str
    props: dict = field(default_factory=dict)
    line: int = 0


@dataclass
class Asset:
    id: str
    props: dict = field(default_factory=dict)
    markers: list = field(default_factory=list)
    motifs: dict = field(default_factory=dict)
    layers: list = field(default_factory=list)
    buses: list = field(default_factory=list)
    cutdowns: list = field(default_factory=list)
    stage: dict | None = None
    master: dict = field(default_factory=dict)
    line: int = 0


class Parser:
    _slur_counter = 0   # shadowed per instance in __init__

    def __init__(self, toks: list[Tok]):
        self._slur_counter = 0
        self._pending_plays: list[dict] = []
        self.toks = toks
        self.i = 0

    def peek(self) -> Tok:
        return self.toks[self.i]

    def next(self) -> Tok:
        t = self.toks[self.i]
        self.i += 1
        return t

    def skip_nl(self):
        while self.peek().kind == "NL":
            self.next()

    def expect(self, kind: str, text: str | None = None) -> Tok:
        t = self.next()
        if t.kind != kind or (text is not None and t.text != text):
            want = text or kind
            raise DSLError(f"expected {want!r}, got {t.text!r}", t.line)
        return t

    # value helpers ----------------------------------------------------
    def _seconds(self, t: Tok) -> float:
        if t.kind != "NUMBER":
            raise DSLError(f"expected a time, got {t.text!r}", t.line)
        if t.unit in (None, "s"):
            return t.value
        raise DSLError(f"expected seconds, got unit '{t.unit}'", t.line)

    def _scalar(self, t: Tok):
        """NUMBER (unit-normalized) or IDENT as string."""
        if t.kind == "NUMBER":
            return t.value
        if t.kind == "IDENT":
            return t.text
        raise DSLError(f"expected a value, got {t.text!r}", t.line)

    # statements --------------------------------------------------------
    def parse(self) -> list[Asset]:
        assets = []
        self.skip_nl()
        while self.peek().kind != "EOF":
            assets.append(self.asset())
            self.skip_nl()
        if not assets:
            raise DSLError("no 'asset' block found", 1)
        return assets

    def asset(self) -> Asset:
        kw = self.expect("IDENT")
        if kw.text != "asset":
            raise DSLError(f"expected 'asset', got {kw.text!r}", kw.line)
        name = self.expect("IDENT")
        a = Asset(id=name.text, line=name.line)
        self.expect("PUNCT", "{")
        self.skip_nl()
        while not (self.peek().kind == "PUNCT" and self.peek().text == "}"):
            t = self.peek()
            if t.kind != "IDENT":
                raise DSLError(f"unexpected {t.text!r} in asset body", t.line)
            if t.text == "marker":
                self.marker(a)
            elif t.text == "motif":
                self.motif(a)
            elif t.text == "layer":
                a.layers.append(self.layer())
            elif t.text == "stage":
                self.stage(a)
            elif t.text == "cutdowns":
                self.cutdowns(a)
            elif t.text == "bus":
                self.bus(a)
            elif t.text == "master":
                self.master(a)
            else:
                k, v = self.prop_line()
                a.props[k] = v
            self.skip_nl()
        self.expect("PUNCT", "}")
        return a

    def marker(self, a: Asset):
        self.next()  # 'marker'
        name = self.expect("IDENT").text
        self.expect("PUNCT", "@")
        t = self.next()
        a.markers.append({"name": name, "time_s": self._seconds(t)})

    def motif(self, a: Asset):
        self.next()  # 'motif'
        name = self.expect("IDENT").text
        self.expect("PUNCT", "{")
        self.skip_nl()
        events = []
        while not (self.peek().kind == "PUNCT" and self.peek().text == "}"):
            events.append(self.note_event())
            self.skip_nl()
        self.expect("PUNCT", "}")
        a.motifs[name] = events

    def note_event(self) -> dict:
        t = self.next()
        ev: dict = {}
        if t.kind == "IDENT" and NOTE_RE.match(t.text):
            ev["note"] = t.text
        elif t.kind == "IDENT" and theory.parse_chord(t.text):
            root, quality = theory.parse_chord(t.text)
            ev["chord_root"] = root
            ev["chord"] = quality
        elif t.kind == "NUMBER" and t.unit == "hz":
            ev["freq_hz"] = t.value
        elif t.kind == "IDENT" and t.text == "play":
            raise DSLError(
                "play is a layer-body statement (one per line), not a "
                "notes: entry — write it on its own line inside the layer, "
                "or use slur( play … ) for a slurred motif group", t.line)
        elif t.kind == "NL":
            raise DSLError(
                "notes: needs its first event on the same line "
                "(continue across lines with trailing commas); play "
                "statements are layer-body lines, not notes: entries",
                t.line)
        else:
            raise DSLError(f"expected a note (e.g. C4), chord (e.g. C3min7) "
                           f"or NNNhz, got {t.text!r}", t.line)
        self.expect("PUNCT", "@")
        b = self.next()
        if b.unit not in (None, "b"):
            raise DSLError("note start must be in beats (e.g. 2b)", b.line)
        ev["start_beat"] = b.value
        kw = self.expect("IDENT")
        if kw.text != "for":
            raise DSLError(f"expected 'for', got {kw.text!r}", kw.line)
        d = self.next()
        if d.unit not in (None, "b"):
            raise DSLError("note duration must be in beats", d.line)
        ev["dur_beats"] = d.value
        while self.peek().kind == "IDENT" and self.peek().text in (
                "vel", "voicing", "art", "gen"):
            kw = self.next().text
            if kw == "vel":
                ev["vel"] = self.next().value
            elif kw == "art":
                a = self.expect("IDENT").text
                if a not in ARTICULATIONS:
                    raise DSLError(f"unknown articulation '{a}' "
                                   f"(available: {sorted(ARTICULATIONS)})",
                                   t.line)
                ev["art"] = a
            elif kw == "gen":
                ev["generated"] = self.expect("IDENT").text
            else:
                v = self.expect("IDENT").text
                if v not in theory.VOICINGS:
                    raise DSLError(f"unknown voicing '{v}' "
                                   f"(available: {theory.VOICINGS})", t.line)
                ev["voicing"] = v
        return ev

    def prop_line(self) -> tuple[str, object]:
        """name ':' values... NL — values are kept raw for the compiler."""
        key = self.expect("IDENT").text
        self.expect("PUNCT", ":")
        vals: list[Tok | tuple] = []
        depth = 0
        while True:
            t = self.peek()
            if t.kind == "EOF":
                break
            if t.kind == "NL":
                trailing_comma = (vals and vals[-1].kind == "PUNCT"
                                  and vals[-1].text == ",")
                if depth > 0 or trailing_comma:
                    self.next()
                    continue
                break
            if t.kind == "PUNCT" and t.text == "}" and depth == 0:
                break
            if t.kind == "PUNCT" and t.text == "(":
                depth += 1
            if t.kind == "PUNCT" and t.text == ")":
                depth -= 1
            vals.append(self.next())
        return key, vals

    def layer(self) -> Layer:
        self.next()  # 'layer'
        name = self.expect("IDENT")
        self.expect("PUNCT", ":")
        ltype = self.expect("IDENT").text
        lay = Layer(name=name.text, type=ltype, line=name.line)
        self.expect("PUNCT", "{")
        self.skip_nl()
        while not (self.peek().kind == "PUNCT" and self.peek().text == "}"):
            t = self.peek()
            if t.kind != "IDENT":
                raise DSLError(f"unexpected {t.text!r} in layer body", t.line)
            if t.text == "notes":
                self.next(); self.expect("PUNCT", ":")
                lay.props.setdefault("notes", []).extend(self.note_list())
                if self._pending_plays:
                    lay.props.setdefault("plays", []).extend(
                        self._pending_plays)
                    self._pending_plays = []
            elif t.text == "play":
                self.next()
                lay.props.setdefault("plays", []).append(self.play_stmt())
            elif t.text == "auto":
                self.next()
                tgt = self.expect("IDENT").text
                self.expect("PUNCT", ":")
                lay.props.setdefault("auto", []).append(
                    (tgt, self.breakpoint_list()))
            else:
                k, v = self.prop_line()
                lay.props[k] = v
            self.skip_nl()
        self.expect("PUNCT", "}")
        return lay

    def _one_or_slur(self) -> list[dict]:
        if self.peek().kind == "IDENT" and self.peek().text == "slur":
            self.next()
            self.expect("PUNCT", "(")
            self.skip_nl()
            if self.peek().kind == "IDENT" and self.peek().text == "play":
                # slur of motif expansions: the whole group joins legato
                self._slur_counter += 1
                gid = self._slur_counter
                while True:
                    self.expect("IDENT")          # 'play'
                    st = self.play_stmt()
                    st["slur_group"] = gid
                    self._pending_plays.append(st)
                    self.skip_nl()
                    if self.peek().kind == "PUNCT" \
                            and self.peek().text == ",":
                        self.next()
                        self.skip_nl()
                        continue
                    break
                self.expect("PUNCT", ")")
                return []
            group = [self.note_event()]
            while self.peek().kind == "PUNCT" and self.peek().text == ",":
                self.next()
                self.skip_nl()
                group.append(self.note_event())
            self.expect("PUNCT", ")")
            if len(group) < 2:
                raise DSLError("slur(...) needs at least two notes",
                               self.peek().line)
            self._slur_counter += 1
            for ev in group:
                ev["slur"] = self._slur_counter
            return group
        return [self.note_event()]

    def note_list(self) -> list[dict]:
        events = list(self._one_or_slur())
        while self.peek().kind == "PUNCT" and self.peek().text == ",":
            self.next()
            self.skip_nl()
            events.extend(self._one_or_slur())
        return events

    def play_stmt(self) -> dict:
        name = self.expect("IDENT").text
        self.expect("PUNCT", "@")
        at = self.next()
        st = {"motif": name, "at_beat": at.value, "transpose_st": 0.0,
              "vel_scale": 1.0, "line": at.line}
        while self.peek().kind == "IDENT" and self.peek().text in (
                "legato",
                "transpose", "vel", "invert", "retrograde", "stretch",
                "diatonic"):
            kw = self.next().text
            if kw == "legato":
                st["legato"] = True
            elif kw == "invert":
                st["invert"] = True
            elif kw == "retrograde":
                st["retrograde"] = True
            elif kw == "stretch":
                st["stretch"] = self.next().value
            elif kw == "diatonic":
                st["diatonic"] = int(self.next().value)
            elif kw == "transpose":
                v = self.next()
                if v.unit != "st":
                    raise DSLError("transpose needs semitones, e.g. +12st",
                                   v.line)
                st["transpose_st"] = v.value
            else:
                st["vel_scale"] = self.next().value
        return st

    def breakpoint_list(self) -> list[tuple]:
        pts = []
        while True:
            t = self.next()
            time_s = self._seconds(t)
            self.expect("PUNCT", "=")
            v = self.next()
            if v.kind != "NUMBER":
                raise DSLError("breakpoint value must be a number", v.line)
            pts.append((time_s, v.value, v.unit))
            if self.peek().kind == "PUNCT" and self.peek().text == ",":
                self.next()
                self.skip_nl()        # comma-newline continuation (DSL §1)
                continue
            break
        if len(pts) < 2:
            raise DSLError("automation needs at least two breakpoints", t.line)
        return pts

    def stage(self, a: Asset):
        self.next()  # 'stage'
        self.expect("PUNCT", "{")
        self.skip_nl()
        st: dict = {"mics": {"tree": 0.7, "close": 0.2, "ambient": 0.3},
                    "dims": [18.0, 26.0, 10.0]}
        while not (self.peek().kind == "PUNCT" and self.peek().text == "}"):
            k = self.expect("IDENT").text
            self.expect("PUNCT", ":")
            if k == "hall":
                t = self.next()
                if t.kind != "STRING" or "@" not in t.text:
                    raise DSLError('stage hall: "<ir.wav>@<sha256>" '
                                   '(content-addressed)', t.line)
                f, sha = t.text.rsplit("@", 1)
                st["hall_file"], st["hall_sha256"] = f, sha
            elif k == "mics":
                while self.peek().kind == "IDENT":
                    m = self.next().text
                    if m not in ("tree", "close", "ambient"):
                        raise DSLError(f"unknown mic '{m}' (tree/close/"
                                       f"ambient)", self.peek().line)
                    self.expect("PUNCT", "=")
                    st["mics"][m] = float(self.next().value)
                    if self.peek().kind == "PUNCT" \
                            and self.peek().text == ",":
                        self.next()
            elif k == "size":
                dims = [self.next()]
                for _ in range(2):
                    self.expect("PUNCT", ",")
                    dims.append(self.next())
                for d in dims:
                    if d.unit not in (None, "m"):
                        raise DSLError("stage size: W, L, H in meters",
                                       d.line)
                st["dims"] = [float(d.value) for d in dims]
            else:
                raise DSLError(f"unknown stage property '{k}'",
                               self.peek().line)
            self.skip_nl()
        self.expect("PUNCT", "}")
        if "hall_file" not in st:
            raise DSLError("stage block needs a hall: \"ir@sha\" pin",
                           a.line)
        a.stage = st

    def cutdowns(self, a: Asset):
        self.next()  # 'cutdowns'
        self.expect("PUNCT", "{")
        self.skip_nl()
        while not (self.peek().kind == "PUNCT" and self.peek().text == "}"):
            length = self.next()
            if length.kind != "NUMBER":
                raise DSLError("cutdown line: '15s: keep As to Bs, ...'",
                               length.line)
            self.expect("PUNCT", ":")
            cd = {"length_s": length.value, "segments": []}
            while self.peek().kind != "NL":
                t = self.next()
                if t.kind == "PUNCT" and t.text == ",":
                    continue
                if t.kind == "IDENT" and t.text == "keep":
                    a_t = self.next()
                    to = self.expect("IDENT")
                    if to.text != "to":
                        raise DSLError("keep As to Bs", to.line)
                    b_t = self.next()
                    cd["segments"].append([a_t.value, b_t.value])
                elif t.kind == "IDENT" and t.text == "fade":
                    cd["fade_s"] = self.next().value
                else:
                    raise DSLError(f"unexpected {t.text!r} in cutdown line",
                                   t.line)
            if not cd["segments"]:
                raise DSLError("cutdown needs at least one 'keep'",
                               length.line)
            a.cutdowns.append(cd)
            self.skip_nl()
        self.expect("PUNCT", "}")

    def bus(self, a: Asset):
        self.next()  # 'bus'
        name = self.expect("IDENT").text
        b: dict = {"name": name, "line": self.peek().line}
        self.expect("PUNCT", "{")
        self.skip_nl()
        while not (self.peek().kind == "PUNCT" and self.peek().text == "}"):
            t = self.peek()
            if t.kind == "IDENT" and t.text == "auto":
                self.next()
                tgt = self.expect("IDENT").text
                self.expect("PUNCT", ":")
                b.setdefault("auto", []).append(
                    (tgt, self.breakpoint_list()))
            else:
                k, v = self.prop_line()
                b[k] = v
            self.skip_nl()
        self.expect("PUNCT", "}")
        a.buses.append(b)

    def master(self, a: Asset):
        self.next()  # 'master'
        self.expect("PUNCT", "{")
        self.skip_nl()
        while not (self.peek().kind == "PUNCT" and self.peek().text == "}"):
            t = self.peek()
            if t.kind == "IDENT" and t.text == "auto":
                self.next()
                tgt = self.expect("IDENT").text
                self.expect("PUNCT", ":")
                a.master.setdefault("auto", []).append(
                    (tgt, self.breakpoint_list()))
            else:
                k, v = self.prop_line()
                a.master[k] = v
            self.skip_nl()
        self.expect("PUNCT", "}")


# ------------------------------------------------------------------ compiler
EMOTIONS = {"tension", "awe", "sadness", "triumph", "suspense", "intimacy",
            "urgency", "calm", "fear", "wonder", "cinematic_intensity"}

ARTICULATIONS = {"sustain", "staccato", "spiccato", "pizzicato",
                 "tremolo", "marcato", "legato", "trill"}

# dynamic marks -> 0..1 (documented; raw numbers are accepted alongside)
DYNAMIC_MARKS = {"ppp": 0.10, "pp": 0.22, "p": 0.35, "mp": 0.48,
                 "mf": 0.60, "f": 0.74, "ff": 0.87, "fff": 1.00}

GROOVE_TEMPLATES = {
    # name: (timing[16] in fractions of a 16th at amount=1, accent[16])
    "straight": ([0.0] * 16, [1.0] * 16),
    "swing16": ([0.0, 0.33] * 8, [1.0] * 16),
    "shuffle": ([0.0, 0.0, 0.66, 0.0] * 4,
                [1.0, 0.9, 1.0, 0.9] * 4),
    "laidback": ([0.0, 0.04, 0.08, 0.04, 0.12, 0.04, 0.08, 0.04] * 2,
                 [1.0, 0.92, 0.96, 0.92, 1.12, 0.92, 0.96, 0.92] * 2),
    "pushed": ([0.0, -0.05, -0.10, -0.05] * 4,
               [1.0, 0.95, 1.06, 0.95] * 4),
    "heavy_one": ([0.0] * 16,
                  [1.25, 0.9, 0.92, 0.9, 1.0, 0.9, 0.92, 0.9,
                   1.15, 0.9, 0.92, 0.9, 1.0, 0.9, 0.92, 0.9]),
}

MAJOR = [0, 2, 4, 5, 7, 9, 11]
MINOR = [0, 2, 3, 5, 7, 8, 10]

def _eq_builder(kind):
    def build(args):
        return {"type": kind,
                "freq_hz": args.get("freq", args.get("_0", 1000.0)),
                "gain_db": args.get("gain", args.get("_1", 0.0)),
                "q": args.get("q", 0.7071)}
    return build


_FX_BUILDERS = {
    "peak": _eq_builder("peak"),
    "lowshelf": _eq_builder("lowshelf"),
    "highshelf": _eq_builder("highshelf"),
    "transient": lambda a: {"type": "transient",
                            "attack_db": a.get("attack", a.get("_0", 0.0)),
                            "sustain_db": a.get("sustain", a.get("_1", 0.0))},
    "convolve": lambda a: {"type": "convolve",
                           "file": a.get("file", a.get("_0", "")),
                           "sha256": a.get("sha256", a.get("_1", "")),
                           "mix": a.get("mix", 0.3),
                           "gain_db": a.get("gain", 0.0)},
    "saturate": lambda a: {"type": "saturate",
                           "amount": a.get("amount", a.get("_0", 0.3)),
                           "mix": a.get("mix", 1.0),
                           "warmth": a.get("warmth", 0.3)},
    "lowpass": lambda args: {"type": "filter", "mode": "lowpass",
                             "cutoff_hz": args["_0"], "q": args.get("q", 0.7071)},
    "highpass": lambda args: {"type": "filter", "mode": "highpass",
                              "cutoff_hz": args["_0"], "q": args.get("q", 0.7071)},
    "bandpass": lambda args: {"type": "filter", "mode": "bandpass",
                              "cutoff_hz": args["_0"], "q": args.get("q", 0.9)},
    "delay": lambda args: {"type": "delay", "time_s": args.get("time", args.get("_0", 0.25)),
                           "feedback": args.get("feedback", 0.3),
                           "mix": args.get("mix", 0.3)},
    "reverb": lambda args: {"type": "reverb", "decay_s": args.get("decay", args.get("_0", 1.2)),
                            "mix": args.get("mix", 0.25)},
    "drive": lambda args: {"type": "drive", "amount": args.get("amount", args.get("_0", 0.3))},
    "tremolo": lambda args: {"type": "tremolo", "rate_hz": args.get("rate", args.get("_0", 5.0)),
                             "depth": args.get("depth", 0.5)},
    "gain": lambda args: {"type": "gain", "db": args.get("db", args.get("_0", 0.0))},
    "hall": lambda args: {"type": "hall",
                          "rt60": args.get("rt60", args.get("_0", 2.5)),
                          "damp": args.get("damp", 0.4),
                          "mix": args.get("mix", 0.3)},
    "plate": lambda args: {"type": "plate",
                           "decay": args.get("decay", args.get("_0", 0.7)),
                           "damp": args.get("damp", 0.3),
                           "predelay": args.get("predelay", 0.0),
                           "mod": args.get("mod", 0.0),
                           "mod_rate": args.get("modrate", 1.0),
                           "mix": args.get("mix", 0.3)},
    "comp": lambda args: {"type": "comp",
                          "threshold": args.get("threshold", args.get("_0", -18.0)),
                          "ratio": args.get("ratio", 2.5),
                          "attack": args.get("attack", 0.03),
                          "release": args.get("release", 0.15),
                          "knee": args.get("knee", 6.0),
                          "makeup": args.get("makeup", 0.0)},
    "mbcomp": lambda args: {"type": "mbcomp",
                            "threshold": args.get("threshold", args.get("_0", -20.0)),
                            "ratio": args.get("ratio", 2.0),
                            "low": args.get("low", 180.0),
                            "high": args.get("high", 2800.0),
                            "attack": args.get("attack", 0.04),
                            "release": args.get("release", 0.18),
                            "knee": args.get("knee", 6.0),
                            "makeup": args.get("makeup", 0.0)},
    "fdn": lambda args: {k: v for k, v in {
        "type": "fdn",
        "rt60": args.get("rt60", args.get("_0", 3.0)),
        "rt60_high": args.get("rt60_high"),
        "crossover": args.get("crossover", 2500.0),
        "size": args.get("size", 1.0),
        "mix": args.get("mix", 0.3)}.items() if v is not None},
}


def _toks_to_fx_chain(toks: list[Tok]) -> list[dict]:
    """Parse 'name(arg, k=v, ...), name2(...)' token runs into fx dicts."""
    chain, i = [], 0
    while i < len(toks):
        t = toks[i]
        if t.kind == "PUNCT" and t.text == ",":
            i += 1
            continue
        if t.kind != "IDENT":
            raise DSLError(f"expected fx name, got {t.text!r}", t.line)
        name = t.text
        i += 1
        args: dict = {}
        if i < len(toks) and toks[i].kind == "PUNCT" and toks[i].text == "(":
            i += 1
            pos = 0
            while not (toks[i].kind == "PUNCT" and toks[i].text == ")"):
                if toks[i].kind == "PUNCT" and toks[i].text == ",":
                    i += 1
                    continue
                if (toks[i].kind == "IDENT" and i + 1 < len(toks)
                        and toks[i + 1].kind == "PUNCT" and toks[i + 1].text == "="):
                    key = toks[i].text
                    val = toks[i + 2]
                    args[key] = val.value if val.kind == "NUMBER" else val.text
                    i += 3
                else:
                    v = toks[i]
                    args[f"_{pos}"] = v.value if v.kind == "NUMBER" else v.text
                    pos += 1
                    i += 1
            i += 1
        if name in _FX_BUILDERS:
            chain.append(_FX_BUILDERS[name](args))
        else:  # plugin fx: pass named args straight through
            fx = {"type": name}
            fx.update({k: v for k, v in args.items() if not k.startswith("_")})
            chain.append(fx)
    return chain


def _env_from_toks(toks: list[Tok], line: int) -> dict:
    """'a=0.01s d=0.1s s=0.7 r=0.2s' -> ADSR dict."""
    names = {"a": "attack", "d": "decay", "s": "sustain", "r": "release"}
    env, i = {}, 0
    while i + 2 < len(toks) + 1 and i < len(toks):
        k = toks[i]
        if k.kind != "IDENT" or k.text not in names:
            raise DSLError("env expects 'a= d= s= r='", k.line)
        if not (toks[i+1].kind == "PUNCT" and toks[i+1].text == "="):
            raise DSLError("env expects '='", toks[i+1].line)
        env[names[k.text]] = toks[i+2].value
        i += 3
    for req in names.values():
        if req not in env:
            raise DSLError(f"env missing '{req[0]}='", line)
    return env


def _one(toks, line, want_unit=None, name="value"):
    if len(toks) != 1:
        raise DSLError(f"expected a single {name}", line)
    t = toks[0]
    if t.kind == "NUMBER":
        if want_unit and t.unit not in (None, want_unit):
            raise DSLError(f"{name}: expected unit '{want_unit}'", t.line)
        return t.value
    return t.text


def _transpose(note: str, semitones: float) -> str | float:
    """Returns a freq if fractional, else a transposed note name."""
    from .synth import note_to_freq
    f = note_to_freq(note) * 2.0 ** (semitones / 12.0)
    return f


def _scale_pitch_classes(key_str: str) -> set[int] | None:
    parts = key_str.split()
    if len(parts) != 2:
        return None
    root, mode = parts[0], parts[1].lower()
    off = NOTE_OFFSETS.get(root[0].upper())
    if off is None:
        return None
    if len(root) > 1:
        off += 1 if root[1] == "#" else -1
    iv = MAJOR if mode == "major" else MINOR if mode == "minor" else None
    return {(off + s) % 12 for s in iv} if iv else None


def _note_pc(note: str) -> int:
    pc = NOTE_OFFSETS[note[0].upper()]
    if len(note) > 1 and note[1] in "#b":
        pc += 1 if note[1] == "#" else -1
    return pc % 12


def _apply_emotion(spec: dict, emotion: dict, diags: list[str]):
    """Compile-time macro expansion. Conservative, documented, deterministic:
    emotion only ever scales reverbs, stereo width, fades, and adds a
    darkness filter — it never invents notes or changes the grid."""
    awe = emotion.get("awe", 0.0) + 0.6 * emotion.get("wonder", 0.0)
    calm = emotion.get("calm", 0.0) + 0.5 * emotion.get("intimacy", 0.0)
    dark = (emotion.get("tension", 0.0) + emotion.get("fear", 0.0)
            + 0.7 * emotion.get("suspense", 0.0))
    big = emotion.get("cinematic_intensity", 0.0) + 0.5 * emotion.get("triumph", 0.0)

    master = spec.setdefault("master", {})
    if awe or big:
        w = master.get("stereo_width", 0.7)
        master["stereo_width"] = round(min(1.0, w + 0.25 * awe + 0.15 * big), 3)
        for layer in spec["layers"]:
            for fx in layer.get("fx", []):
                if fx["type"] == "reverb":
                    fx["decay_s"] = round(min(15.0, fx["decay_s"] * (1.0 + 0.8 * awe)), 3)
                    fx["mix"] = round(min(0.7, fx["mix"] + 0.15 * awe), 3)
    if calm:
        master["fade_in_s"] = round(max(master.get("fade_in_s", 0.0), 0.6 * calm), 3)
        master["fade_out_s"] = round(max(master.get("fade_out_s", 0.01), 1.2 * calm), 3)
    if dark > 0.05:
        cutoff = round(9000.0 * (1.0 - 0.65 * min(dark, 1.0)), 1)
        master.setdefault("fx", []).append(
            {"type": "filter", "mode": "lowpass", "cutoff_hz": cutoff})
        diags.append(f"emotion: darkness {dark:.2f} -> master lowpass at {cutoff} Hz")
    if awe or big or calm:
        diags.append("emotion: applied macro expansion "
                     "(reverb/width/fades); see compiled JSON for exact values")


STYLE_DEFAULTS = STYLE_PACKS


def _kv_directive(toks: list[Tok], line: int,
                  bare_key: str | None = None) -> dict:
    out, i = {}, 0
    if bare_key and toks and toks[0].kind == "IDENT" and (
            len(toks) == 1 or toks[1].text != "="):
        out[bare_key] = toks[0].text
        i = 1
    while i < len(toks):
        if toks[i].kind == "PUNCT" and toks[i].text == ",":
            i += 1
            continue
        if i + 2 >= len(toks) or toks[i].kind != "IDENT" \
                or toks[i + 1].text != "=":
            raise DSLError("smart directive expects key=value pairs",
                           toks[i].line if i < len(toks) else line)
        key = toks[i].text
        vals = []
        i += 2
        while i < len(toks):
            t = toks[i]
            if t.kind == "PUNCT" and t.text == ",":
                if i + 1 < len(toks) and toks[i + 1].kind == "NUMBER" \
                        and key == "extensions":
                    i += 1
                    continue
                i += 1
                break
            if t.kind == "IDENT" and i + 1 < len(toks) \
                    and toks[i + 1].text == "=":
                break
            vals.append(t.value if t.kind == "NUMBER" else t.text)
            i += 1
        if key == "extensions":
            out[key] = [int(v) for v in vals]
        else:
            out[key] = vals[0] if len(vals) == 1 else vals
    return out


def _merge_defaults(base: dict, override: dict) -> dict:
    out = {k: dict(v) if isinstance(v, dict) else v
           for k, v in base.items()}
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k].update(v)
        else:
            out[k] = v
    return out


def _read_smart_directives(p: dict, line: int) -> dict:
    style = None
    explicit: dict = {}
    if "style" in p:
        style = _one(p.pop("style"), line)
        if style not in STYLE_DEFAULTS:
            raise DSLError(f"style: unknown '{style}' "
                           f"(available: {sorted(STYLE_DEFAULTS)})", line)
    if "perform" in p:
        explicit["perform"] = _kv_directive(p.pop("perform"), line)
    if "ensemble" in p:
        explicit["ensemble"] = _kv_directive(p.pop("ensemble"), line,
                                             bare_key="family")
    if "voicing" in p:
        explicit["voicing"] = _kv_directive(p.pop("voicing"), line)
    if "space" in p:
        explicit["space"] = _kv_directive(p.pop("space"), line)
    if not style and not explicit:
        return {}
    defaults = STYLE_DEFAULTS.get(style, {})
    intent = _merge_defaults(defaults, explicit)
    if style:
        intent["style"] = style
    return intent


def _read_score_props(p: dict, line: int) -> dict:
    score: dict = {}
    if "meter" in p:
        toks = [t for t in p.pop("meter") if t.kind == "NUMBER"]
        if len(toks) != 2:
            raise DSLError("meter: expected 'BEATS UNIT', e.g. '7 8'", line)
        score["meter"] = {"beats": int(toks[0].value),
                          "unit": int(toks[1].value)}
    if "pickup" in p:
        score["pickup_beats"] = _one(p.pop("pickup"), line, "b", "pickup")
    if "form" in p:
        toks = p.pop("form")
        sections, i = [], 0
        while i < len(toks):
            if toks[i].kind == "PUNCT":
                i += 1
                continue
            if (i + 3 >= len(toks) or toks[i].kind != "IDENT"
                    or toks[i + 1].kind != "NUMBER"
                    or toks[i + 2].text != "for"
                    or toks[i + 3].kind != "NUMBER"):
                raise DSLError("form: name STARTb for DURb, ...",
                               toks[i].line if i < len(toks) else line)
            name = toks[i].text
            start = toks[i + 1].value
            dur = toks[i + 3].value
            sections.append({"name": name, "start_beat": start,
                             "dur_beats": dur,
                             "end_beat": round(start + dur, 6)})
            i += 4
        score["sections"] = sections
    if "repeat" in p:
        toks = p.pop("repeat")
        if len(toks) < 2 or toks[0].kind != "IDENT" \
                or toks[1].kind != "IDENT" or not toks[1].text.startswith("x"):
            raise DSLError("repeat: section xN", line)
        score.setdefault("repeats", []).append({
            "section": toks[0].text,
            "count": int(toks[1].text[1:] or "1"),
        })
    if "polymeter" in p:
        toks = p.pop("polymeter")
        if len(toks) < 3 or toks[0].kind != "IDENT":
            raise DSLError("polymeter: layer BEATS UNIT", line)
        score["polymeter"] = {
            toks[0].text: {"beats": int(toks[1].value),
                           "unit": int(toks[2].value)}
        }
    return score


def _apply_smart_directives(spec: dict, intent: dict, diags: list[str]):
    """Expand high-level musical intent into explicit render-layer IR."""
    if not intent:
        return
    spec["intent"] = intent
    perform = intent.get("perform", {})
    ensemble = intent.get("ensemble", {})
    voicing = intent.get("voicing", {})
    space = intent.get("space", {})
    expressivity = max(0.0, min(1.0, float(perform.get("expressivity", 0.0))))
    size = int(ensemble.get("size", 0) or 0)
    spread = max(0.0, min(1.0, float(ensemble.get("spread", 0.0) or 0.0)))
    octaves = int(ensemble.get("octaves", 0) or 0)
    phrase_report = {}
    for layer in spec["layers"]:
        phrases = _analyze_layer_phrases(layer)
        if phrases:
            phrase_report[layer["name"]] = phrases
        if layer["type"] in ("notes", "instrument", "drums"):
            if expressivity:
                layer.setdefault("humanize", {
                    "timing_s": round(0.018 * expressivity, 5),
                    "vel": round(0.15 * expressivity, 4),
                })
                layer.setdefault("phrasing", round(expressivity, 3))
                layer.setdefault("vel_brightness", round(0.65 * expressivity, 3))
                _apply_performance_phrase_ir(layer, phrases, expressivity)
        if layer["type"] == "notes" and size >= 2:
            layer.setdefault("unison", size)
            layer.setdefault("spread_cents", round(18.0 * spread, 3))
        if layer["type"] == "instrument" and size >= 2:
            layer.setdefault("section", {
                "size": size,
                "spread": spread,
                "detune_c": round(9.0 * max(0.2, spread), 3),
                "timing_s": round(0.012 * max(0.2, expressivity), 5),
            })
        if octaves > 0 and layer["type"] == "notes" and layer.get("notes"):
            extra = []
            for ev in layer["notes"]:
                if "note" in ev:
                    extra.append({**ev, "note": theory.semis_to_note(
                        theory.note_to_semis(ev["note"]) - 12)})
            layer["notes"].extend(extra)
            layer["notes"].sort(key=lambda e: (e["start_beat"],
                                               e.get("note", ""),
                                               e.get("freq_hz", 0)))
        if layer["type"] == "notes" and layer.get("notes"):
            _apply_voicing_extensions(layer, voicing)
    if phrase_report:
        intent.setdefault("analysis", {})["phrases"] = [
            {**p, "layer": lname}
            for lname, ps in sorted(phrase_report.items())
            for p in ps
        ]
    _apply_role_routing(spec, ensemble, space)
    depth = max(0.0, min(1.0, float(space.get("depth", 0.0) or 0.0)))
    if depth:
        master = spec.setdefault("master", {})
        fx = master.setdefault("fx", [])
        fx.append({"type": "hall", "rt60": round(1.2 + 3.8 * depth, 3),
                   "damp": round(0.25 + 0.35 * depth, 3),
                   "mix": round(0.08 + 0.28 * depth, 3)})
        fx.append({"type": "saturate", "amount": round(0.08 + 0.14 * depth, 3),
                   "mix": 0.35, "warmth": 0.35})
    if expressivity:
        spec.setdefault("master", {}).setdefault("fx", []).append({
            "type": "comp", "threshold": -20.0, "ratio": 1.4,
            "attack": 0.04, "release": 0.22, "knee": 6.0, "makeup": 0.0})
    diags.append("smart directives: expanded style/perform/ensemble/voicing/"
                 "space into explicit layer and master IR")


def _analyze_layer_phrases(layer: dict) -> list[dict]:
    if layer.get("type") != "notes" or not layer.get("notes"):
        return []
    notes = [e for e in sorted(layer["notes"], key=lambda x: x["start_beat"])
             if "note" in e]
    if not notes:
        return []
    phrases: list[list[dict]] = [[notes[0]]]
    for prev, ev in zip(notes, notes[1:]):
        gap = ev["start_beat"] - (prev["start_beat"] + prev["dur_beats"])
        if gap >= 1.5:
            phrases.append([ev])
        else:
            phrases[-1].append(ev)
    out = []
    for idx, ph in enumerate(phrases, 1):
        semis = [(theory.note_to_semis(e["note"]), e) for e in ph]
        peak_s, peak = max(semis, key=lambda x: (x[0], x[1]["start_beat"]))
        out.append({
            "id": idx,
            "start_beat": ph[0]["start_beat"],
            "end_beat": round(max(e["start_beat"] + e["dur_beats"]
                                  for e in ph), 6),
            "peak_beat": peak["start_beat"],
            "peak_note": peak["note"],
            "note_count": len(ph),
            "cadence_beat": ph[-1]["start_beat"],
        })
    return out


def _apply_performance_phrase_ir(layer: dict, phrases: list[dict],
                                 expressivity: float):
    if layer.get("type") != "notes" or not layer.get("notes"):
        return
    notes = sorted(layer["notes"], key=lambda e: (e["start_beat"],
                                                  e.get("note", "")))
    if phrases and "dynamic" not in layer:
        pts = []
        for ph in phrases:
            low = round(max(0.1, 0.42 + 0.1 * expressivity), 3)
            high = round(min(1.0, 0.62 + 0.3 * expressivity), 3)
            pts.extend([[ph["start_beat"], low], [ph["peak_beat"], high],
                        [ph["end_beat"], round(max(0.1, low - 0.08), 3)]])
        layer["dynamic"] = sorted(pts, key=lambda p: p[0])
    if "vibrato" not in layer:
        layer["vibrato"] = {"rate_hz": round(4.8 + 1.2 * expressivity, 3),
                            "depth_cents": round(10.0 * expressivity, 3),
                            "delay_s": 0.18}
    next_slur = max([e.get("slur", 0) or 0 for e in notes] + [0])
    for a, b in zip(notes, notes[1:]):
        if "note" not in a or "note" not in b:
            continue
        interval = abs(theory.note_to_semis(a["note"]) -
                       theory.note_to_semis(b["note"]))
        gap = b["start_beat"] - (a["start_beat"] + a["dur_beats"])
        if interval <= 3 and gap <= 0.25:
            if not a.get("slur") and not b.get("slur"):
                next_slur += 1
                a["slur"] = b["slur"] = next_slur
            elif a.get("slur") and not b.get("slur"):
                b["slur"] = a["slur"]
    for ph in phrases:
        for ev in notes:
            if ev.get("start_beat") == ph["peak_beat"] \
                    and ev.get("note") == ph["peak_note"]:
                ev["dur_beats"] = round(ev["dur_beats"]
                                        * (1.0 + 0.08 * expressivity), 6)
    layer["notes"] = sorted(notes, key=lambda e: (e["start_beat"],
                                                  e.get("note", ""),
                                                  e.get("freq_hz", 0)))


def _apply_voicing_extensions(layer: dict, voicing: dict):
    richness = max(0.0, min(1.0, float(voicing.get("richness", 0.0) or 0.0)))
    if richness <= 0:
        return
    extensions = [int(x) for x in voicing.get("extensions", [])]
    if not extensions:
        return
    intervals = {7: 10, 9: 14, 11: 17, 13: 21}
    notes = list(layer.get("notes", []))
    additions = []
    groups: dict[tuple[float, float], list[dict]] = {}
    for ev in notes:
        if "note" in ev:
            groups.setdefault((ev["start_beat"], ev["dur_beats"]), []).append(ev)
    for group in groups.values():
        if len(group) < 3:
            continue
        semis = sorted(theory.note_to_semis(ev["note"]) for ev in group)
        pcs = {s % 12 for s in semis}
        root = semis[0]
        for ext in extensions:
            if ext not in intervals:
                continue
            target = root + intervals[ext]
            if target % 12 in pcs:
                continue
            base = {k: v for k, v in group[0].items()
                    if k not in ("note", "freq_hz")}
            additions.append({**base, "note": theory.semis_to_note(target),
                              "vel": round(group[0].get("vel", 1.0)
                                           * (0.72 + 0.2 * richness), 4)})
            pcs.add(target % 12)
    starts = sorted(groups)
    for a_key, b_key in zip(starts, starts[1:]):
        a_group, b_group = groups[a_key], groups[b_key]
        a_semis = sorted(theory.note_to_semis(e["note"]) for e in a_group)
        b_semis = sorted(theory.note_to_semis(e["note"]) for e in b_group)
        if not a_semis or not b_semis:
            continue
        if abs(b_semis[0] - a_semis[0]) >= 3:
            step = 2 if b_semis[0] > a_semis[0] else -2
            additions.append({
                "note": theory.semis_to_note(a_semis[0] + step),
                "start_beat": round(a_key[0] + a_key[1] * 0.72, 6),
                "dur_beats": round(min(0.5, a_key[1] * 0.22), 6),
                "vel": round(0.55 + 0.25 * richness, 4),
                "generated": "voice_leading",
            })
        moving = min(a_semis, key=lambda s: min(abs(s - t) for t in b_semis))
        target = min(b_semis, key=lambda s: abs(s - moving))
        if abs(target - moving) >= 3:
            mid = moving + (1 if target > moving else -1) * min(2, abs(target - moving) // 2)
            additions.append({
                "note": theory.semis_to_note(mid),
                "start_beat": round(a_key[0] + a_key[1] * 0.72, 6),
                "dur_beats": round(min(0.5, a_key[1] * 0.22), 6),
                "vel": round(0.55 + 0.25 * richness, 4),
                "generated": "voice_leading",
            })
        common = set(s % 12 for s in a_semis) & set(s % 12 for s in b_semis)
        if common:
            sus_pc = sorted(common)[0]
            sus = next(s for s in a_semis if s % 12 == sus_pc)
            additions.append({
                "note": theory.semis_to_note(sus),
                "start_beat": b_key[0],
                "dur_beats": round(min(0.5, b_key[1] * 0.25), 6),
                "vel": round(0.48 + 0.22 * richness, 4),
                "generated": "suspension",
            })
        elif abs(b_semis[0] - a_semis[-1]) <= 7:
            additions.append({
                "note": theory.semis_to_note((b_semis[0] + a_semis[-1]) // 2),
                "start_beat": round(b_key[0] - min(0.5, a_key[1] * 0.2), 6),
                "dur_beats": round(min(0.5, a_key[1] * 0.2), 6),
                "vel": round(0.45 + 0.2 * richness, 4),
                "generated": "passing_tone",
            })
    if additions:
        voicing["voice_leading"] = True
    if additions:
        layer["notes"] = sorted(notes + additions,
                                key=lambda e: (e["start_beat"],
                                               e.get("note", ""),
                                               e.get("freq_hz", 0)))


def _layer_role(layer: dict) -> str:
    name = layer.get("name", "").lower()
    if "bass" in name or "sub" in name:
        return "bass"
    if any(x in name for x in ("lead", "melody", "theme", "top")):
        return "melody"
    notes = [e for e in layer.get("notes", []) if "note" in e]
    if notes:
        avg = sum(theory.note_to_semis(e["note"]) for e in notes) / len(notes)
        if avg < theory.note_to_semis("C3"):
            return "bass"
        if avg >= theory.note_to_semis("C5"):
            return "melody"
    return "harmony"


def _apply_role_routing(spec: dict, ensemble: dict, space: dict):
    if not ensemble and not space:
        return
    buses = spec.setdefault("buses", [])
    existing = {b["name"] for b in buses}
    role_defs = {
        "af_bass": {"name": "af_bass", "gain_db": -0.5,
                    "fx": [{"type": "peak", "freq_hz": 90.0,
                            "gain_db": 1.5, "q": 0.9}]},
        "af_harmony": {"name": "af_harmony", "gain_db": -1.5,
                       "fx": [{"type": "hall", "rt60": 1.8,
                               "damp": 0.35, "mix": 0.12}]},
        "af_melody": {"name": "af_melody", "gain_db": 0.0,
                      "fx": [{"type": "delay", "time_s": 0.18,
                              "feedback": 0.12, "mix": 0.08}]},
        "af_space": {"name": "af_space", "gain_db": 0.0,
                     "fx": [{"type": "hall",
                             "rt60": round(1.5 + 3.0 * float(space.get("depth", 0.4) or 0.4), 3),
                             "damp": 0.45,
                             "mix": round(0.16 + 0.2 * float(space.get("depth", 0.4) or 0.4), 3)}]},
    }
    for name, b in role_defs.items():
        if name not in existing:
            buses.append(b)
            existing.add(name)
    for layer in spec.get("layers", []):
        if layer.get("bus"):
            continue
        role = _layer_role(layer)
        layer["role"] = role
        layer["bus"] = {"bass": "af_bass", "melody": "af_melody"}.get(
            role, "af_harmony")


def compile_asset(a: Asset, variant=None) -> tuple[dict, list[str]]:
    diags: list[str] = []
    _apply_vary(a, variant)
    spec: dict = {"id": a.id, "layers": []}
    if variant is not None:
        spec["variant"] = str(variant)
    p = a.props

    def take(key, default=None):
        return p.pop(key, default)

    spec["kind"] = _one(take("kind", [Tok("IDENT", "sfx", a.line)]), a.line)
    spec["duration_s"] = _one(take("duration"), a.line, "s", "duration")
    smart_intent = _read_smart_directives(p, a.line)
    score = _read_score_props(p, a.line)
    if score:
        spec["score"] = score
    if "samplerate" in p:
        spec["sample_rate"] = int(_one(take("samplerate"), a.line))
    if "bitdepth" in p:
        spec["bit_depth"] = int(_one(take("bitdepth"), a.line))
    if "tempo" in p:
        toks = [t for t in take("tempo") if not (t.kind == "PUNCT"
                                                 and t.text == ",")]
        pts, i = [], 0
        while i < len(toks):
            if (i + 2 < len(toks) and toks[i + 1].kind == "PUNCT"
                    and toks[i + 1].text == "="):
                if toks[i].unit not in (None, "b"):
                    raise DSLError("tempo map points are 'BEATb=BPM'",
                                   toks[i].line)
                pts.append([toks[i].value, toks[i + 2].value])
                i += 3
            else:
                if toks[i].unit not in (None, "bpm"):
                    raise DSLError("tempo: expected NNNbpm", toks[i].line)
                pts.append([0.0, toks[i].value])
                i += 1
        pts.sort(key=lambda x: x[0])
        spec["bpm"] = pts[0][1]
        if len(pts) > 1:
            spec["tempo_map"] = pts
    if "swing" in p:
        spec["swing"] = _one(take("swing"), a.line)
    if "library" in p:
        toks = take("library")
        if len(toks) != 1 or toks[0].kind != "STRING":
            raise DSLError('library: expected "name@manifest_hash" '
                           '(quoted string)', a.line)
        ref = toks[0].text
        if "@" not in ref:
            raise DSLError("library: format is name@manifest_hash — the "
                           "pin is mandatory (content-addressed orchestra)",
                           a.line)
        name, pin = ref.split("@", 1)
        spec["library"] = {"name": name, "manifest_sha256": pin}
    if "loopsafe" in p:
        spec["loop_safe"] = _one(take("loopsafe"), a.line) in ("on", "true", 1.0)
    if "groove" in p:
        toks = take("groove")
        if not toks or toks[0].kind != "IDENT":
            raise DSLError("groove: expected a template name", a.line)
        gname = toks[0].text
        if gname not in GROOVE_TEMPLATES:
            raise DSLError(f"groove: unknown template '{gname}' "
                           f"(available: {sorted(GROOVE_TEMPLATES)})", toks[0].line)
        amount = toks[1].value if len(toks) > 1 and toks[1].kind == "NUMBER" else 1.0
        timing, accent = GROOVE_TEMPLATES[gname]
        spec["groove"] = {
            "name": gname, "amount": amount,
            "timing": [round(t * amount, 4) for t in timing],
            "accent": [round(1.0 + (x - 1.0) * amount, 4) for x in accent],
        }

    key_str = None
    key_map: list = []
    if "key" in p:
        toks = [t for t in take("key") if not (t.kind == "PUNCT"
                                               and t.text == ",")]
        i = 0
        while i < len(toks):
            if (i + 1 < len(toks) and toks[i + 1].kind == "PUNCT"
                    and toks[i + 1].text == "="):
                beat = toks[i].value
                root = toks[i + 2].text
                mode = toks[i + 3].text if i + 3 < len(toks) \
                    and toks[i + 3].kind == "IDENT" else "major"
                key_map.append([beat, root, mode])
                i += 4
            else:
                root = toks[i].text
                mode = toks[i + 1].text if i + 1 < len(toks) else "major"
                key_map.append([0.0, root, mode])
                i += 2
        key_map.sort(key=lambda x: x[0])
        key_str = f"{key_map[0][1]} {key_map[0][2]}"
        spec["key"] = key_str
        if len(key_map) > 1:
            spec["key_map"] = key_map
    scale = _scale_pitch_classes(key_str) if key_str else None

    emotion = {}
    if "emotion" in p:
        toks = take("emotion")
        i = 0
        while i < len(toks):
            if toks[i].kind == "PUNCT":
                i += 1
                continue
            name = toks[i].text
            if name not in EMOTIONS:
                diags.append(f"emotion '{name}' is not a known tag "
                             f"(known: {sorted(EMOTIONS)}); kept as metadata")
            if not (toks[i+1].kind == "PUNCT" and toks[i+1].text == "="):
                raise DSLError("emotion expects name=value pairs", toks[i].line)
            emotion[name] = toks[i+2].value
            i += 3
        spec["emotion"] = emotion

    intensity = None
    if "intensity" in p:
        toks = take("intensity")
        pts, i = [], 0
        while i + 2 < len(toks) + 1 and i < len(toks):
            if toks[i].kind == "PUNCT":
                i += 1
                continue
            t_s = toks[i].value
            v = toks[i+2].value
            pts.append([t_s, round(-14.0 * (1.0 - max(0.0, min(1.0, v))), 3)])
            i += 3
        intensity = pts
        spec["intensity_curve"] = [[pt[0], round(1.0 + pt[1] / 14.0, 3)] for pt in pts]

    if p:
        diags.append(f"unknown asset properties ignored: {sorted(p)}")

    spec["markers"] = a.markers
    if a.cutdowns:
        spec["cutdowns"] = a.cutdowns
    if a.stage:
        spec["stage"] = a.stage

    for lay in a.layers:
        spec.setdefault("_meta", {}).setdefault("lines", {})[
            lay.name] = lay.line
        spec["layers"].append(_compile_layer(lay, a.motifs, scale, diags,
                                             key_map=key_map,
                                             variant=variant))

    if a.buses:
        spec["buses"] = []
        for braw in a.buses:
            b = dict(braw)
            bline = b.pop("line", a.line)
            out_b: dict = {"name": b.pop("name")}
            if "gain" in b:
                out_b["gain_db"] = _one(b.pop("gain"), bline, "db", "gain")
            if "fx" in b:
                out_b["fx"] = _toks_to_fx_chain(b.pop("fx"))
            if "duck" in b:
                toks = b.pop("duck")
                d, i = {}, 0
                keymap = {"source": "source", "amount": "amount_db",
                          "threshold": "threshold_db", "attack": "attack_s",
                          "release": "release_s"}
                while i < len(toks):
                    k = toks[i].text
                    if k not in keymap or i + 2 > len(toks) \
                            or toks[i + 1].text != "=":
                        raise DSLError(
                            "duck expects 'source=<layer|bus:name> "
                            "amount=…db attack=…s release=…s "
                            "threshold=…db'", toks[i].line)
                    val = toks[i + 2]
                    if keymap[k] == "source" and i + 4 < len(toks) \
                            and toks[i + 3].text == ":":
                        d["source"] = f"{val.text}:{toks[i + 4].text}"
                        i += 5
                    else:
                        d[keymap[k]] = (val.value if val.kind == "NUMBER"
                                        else val.text)
                        i += 3
                d.setdefault("source", "")
                out_b["duck"] = d
            for tgt, pts in b.pop("auto", []):
                out_b.setdefault("automation", []).append(
                    _auto_block(tgt, pts))
            if b:
                diags.append(f"bus {out_b['name']}: unknown properties "
                             f"ignored: {sorted(b)}")
            spec["buses"].append(out_b)

    master: dict = {}
    m = dict(a.master)
    if "width" in m:
        master["stereo_width"] = _one(m.pop("width"), a.line)
    if "peak" in m:
        master["target_peak_dbfs"] = _one(m.pop("peak"), a.line, "db", "peak")
    if "lufs" in m:
        master["target_lufs"] = _one(m.pop("lufs"), a.line)
    if "fadein" in m:
        master["fade_in_s"] = _one(m.pop("fadein"), a.line, "s")
    if "fadeout" in m:
        master["fade_out_s"] = _one(m.pop("fadeout"), a.line, "s")
    if "fx" in m:
        master["fx"] = _toks_to_fx_chain(m.pop("fx"))
    for tgt, pts in m.pop("auto", []):
        master.setdefault("automation", []).append(_auto_block(tgt, pts))
    if m:
        diags.append(f"unknown master properties ignored: {sorted(m)}")
    if intensity:
        master.setdefault("automation", []).append(
            {"target": "gain_db", "points": intensity,
             "from_intensity": True})
    if master:
        spec["master"] = master

    if emotion:
        _apply_emotion(spec, emotion, diags)
    if smart_intent:
        _apply_smart_directives(spec, smart_intent, diags)

    # advisory checks
    for lay in spec["layers"]:
        g = lay.get("gain_db", 0)
        if g > 0:
            diags.append(f"layer '{lay.get('name')}': gain {g:+.1f} dB is hot; "
                         f"consider <= 0 dB and use master loudness instead")
    return spec, diags


def _auto_block(tgt: str, pts: list[tuple]) -> dict:
    target = {"gain": "gain_db", "cutoff": "cutoff_hz", "scan": "scan"}.get(tgt, tgt)
    return {"target": target, "points": [[t, v] for t, v, _u in pts]}


def _resolve_vary(toks, seed_str: str, line: int):
    """Replace vary(a, b, c) in a prop token run with one alternative,
    chosen by a stable SHA-256 of variant|asset|scope|prop (CRC32 fails to
    flip on near-identical sequential tags — measured, not assumed).
    Variant None picks alternative 0 (the canonical render)."""
    out, i = [], 0
    while i < len(toks):
        t = toks[i]
        if t.kind == "IDENT" and t.text == "vary" and i + 1 < len(toks) \
                and toks[i + 1].kind == "PUNCT" and toks[i + 1].text == "(":
            depth, j = 1, i + 2
            alts, cur = [], []
            while j < len(toks) and depth:
                tj = toks[j]
                if tj.kind == "PUNCT" and tj.text == "(":
                    depth += 1
                elif tj.kind == "PUNCT" and tj.text == ")":
                    depth -= 1
                    if depth == 0:
                        break
                if depth == 1 and tj.kind == "PUNCT" and tj.text == ",":
                    alts.append(cur)
                    cur = []
                else:
                    cur.append(tj)
                j += 1
            if depth:
                raise DSLError("vary(...): unclosed parenthesis", t.line)
            alts.append(cur)
            if len(alts) < 2 or any(not a for a in alts):
                raise DSLError("vary(...) needs 2+ non-empty alternatives",
                               t.line)
            if seed_str.startswith("|"):     # variant None -> canonical
                pick = 0
            else:
                import hashlib
                pick = int.from_bytes(
                    hashlib.sha256(seed_str.encode()).digest()[:4],
                    "big") % len(alts)
            out.extend(alts[pick])
            i = j + 1
        else:
            out.append(t)
            i += 1
    return out


def _apply_vary(a, variant):
    """Resolve every vary() in asset/layer/bus/master props."""
    tag = "" if variant is None else str(variant)
    def fix(container, scope):
        for key, val in list(container.items()):
            if isinstance(val, list) and val and hasattr(val[0], "kind"):
                container[key] = _resolve_vary(
                    val, f"{tag}|{a.id}|{scope}|{key}", a.line)
    fix(a.props, "asset")
    fix(a.master, "master")
    for lay in a.layers:
        fix(lay.props, f"layer:{lay.name}")
    for b in a.buses:
        fix({k: v for k, v in b.items()}, f"bus:{b.get('name')}")
        for key, val in list(b.items()):
            if isinstance(val, list) and val and hasattr(val[0], "kind"):
                b[key] = _resolve_vary(
                    val, f"{tag}|{a.id}|bus:{b.get('name')}|{key}", a.line)


def _key_at(key_map, beat: float):
    """(root_pc, interval_list) of the key in force at a beat, or None."""
    if not key_map:
        return None
    root, mode = key_map[0][1], key_map[0][2]
    for b, r, mo in key_map:
        if b <= beat:
            root, mode = r, mo
    off = NOTE_OFFSETS.get(root[0].upper())
    if off is None:
        return None
    if len(root) > 1:
        off += 1 if root[1] == "#" else -1
    iv = MAJOR if mode.lower() == "major" else MINOR
    return off % 12, iv


def _expand_chords(notes: list[dict], arp: dict | None,
                   layer_name: str, variant=None) -> list[dict]:
    """Chord events -> explicit note events; with `arp`, a sequenced
    pattern over the chord tones (compile-time, deterministic: the
    'random' order is seeded from the layer name and event index)."""
    import zlib
    out = []
    for i, ev in enumerate(notes):
        if "chord_root" not in ev:
            out.append(ev)
            continue
        semis = theory.chord_semis(ev["chord_root"], ev["chord"],
                                   ev.get("voicing", "close"))
        base = {k: v for k, v in ev.items()
                if k not in ("chord_root", "chord", "voicing")}
        if arp is None:
            for s in semis:
                out.append({**base, "note": theory.semis_to_note(s)})
            continue
        tones = list(semis)
        for o in range(1, int(arp["octaves"])):
            tones += [s + 12 * o for s in semis]
        pat = arp["pattern"]
        if pat == "down":
            order = sorted(tones, reverse=True)
        elif pat == "updown":
            asc = sorted(tones)
            order = asc + asc[-2:0:-1]
        elif pat == "downup":
            dsc = sorted(tones, reverse=True)
            order = dsc + dsc[-2:0:-1]
        elif pat == "random":
            import numpy as _np
            seed = zlib.crc32(
                f"{'' if variant is None else variant}|{layer_name}:{i}"
                .encode())
            order = list(_np.random.default_rng(seed).permutation(
                sorted(tones)))
        else:
            order = sorted(tones)
        rate = float(arp["rate_beats"])
        gate = float(arp["gate"])
        nsteps = max(1, int(round(ev["dur_beats"] / rate)))
        for k in range(nsteps):
            out.append({**base,
                        "note": theory.semis_to_note(int(order[k % len(order)])),
                        "start_beat": round(ev["start_beat"] + k * rate, 6),
                        "dur_beats": round(rate * gate, 6)})
    return out


def _compile_layer(lay: Layer, motifs: dict, scale, diags: list[str],
                   key_map: list | None = None, variant=None) -> dict:
    ltype = "sample" if lay.type == "audio" else lay.type
    out: dict = {"name": lay.name, "type": ltype}
    if lay.type == "audio":
        out["source_kind"] = "audio"
    p = dict(lay.props)
    line = lay.line

    simple = {"osc": ("osc", None), "voice": ("voice", None),
              "color": ("color", None), "shape": ("shape", None),
              "curve": ("curve", None), "material": ("material", None)}
    for k, (jk, _u) in simple.items():
        if k in p:
            out[jk] = _one(p.pop(k), line)
    units = {"gain": ("gain_db", "db"), "pan": ("pan", None),
             "start": ("start_s", "s"), "detune": ("detune_cents", "c"),
             "duration": ("duration_s", "s"), "loop": ("loop_beats", "b"),
             "from": ("f_start_hz", "hz"), "to": ("f_end_hz", "hz"),
             "fmratio": ("fm_ratio", None), "fmindex": ("fm_index", None),
             "unison": ("unison", None), "spread": ("spread_cents", "c"),
             "bandwidth": ("bandwidth_cents", "c"),
             "harmonics": ("harmonics", None), "damping": ("damping", None),
             "brightness": ("brightness", None),
             "pluckpos": ("pluck_pos", None),
             "modedecay": ("mode_decay_s", "s")}
    for k, (jk, u) in units.items():
        if k in p:
            out[jk] = _one(p.pop(k), line, u, k)
    if "pattern" in p:
        ptoks = p.pop("pattern")
        if ptoks and ptoks[0].kind == "IDENT" and ptoks[0].text == "euclid":
            nums = [t.value for t in ptoks if t.kind == "NUMBER"]
            if len(nums) not in (2, 3):
                raise DSLError("euclid(k, n[, rotate])", ptoks[0].line)
            out["pattern"] = theory.bjorklund(int(nums[0]), int(nums[1]),
                                              int(nums[2]) if len(nums) == 3
                                              else 0)
        else:
            out["pattern"] = "".join(t.text for t in ptoks)
    if "env" in p:
        toks = p.pop("env")
        out["env"] = _env_from_toks(toks, line)
    if "fx" in p:
        out["fx"] = _toks_to_fx_chain(p.pop("fx"))
    if "dynamic" in p:
        toks = p.pop("dynamic")
        pts, i = [], 0
        while i < len(toks):
            t = toks[i]
            if t.kind == "PUNCT" and t.text == ",":
                i += 1
                continue
            if (t.kind != "NUMBER" or t.unit not in (None, "b")
                    or i + 2 >= len(toks)
                    or toks[i + 1].text != "="):
                raise DSLError("dynamic: beats=mark pairs, e.g. "
                               "'0b=pp, 8b=f, 12b=0.5'", t.line)
            v_t = toks[i + 2]
            if v_t.kind == "IDENT":
                if v_t.text not in DYNAMIC_MARKS:
                    raise DSLError(f"unknown dynamic mark '{v_t.text}' "
                                   f"(known: {sorted(DYNAMIC_MARKS)})",
                                   v_t.line)
                v = DYNAMIC_MARKS[v_t.text]
            elif v_t.kind == "NUMBER" and v_t.unit is None:
                v = max(0.0, min(1.0, v_t.value))
            else:
                raise DSLError("dynamic value: a mark (pp..fff) or 0..1",
                               v_t.line)
            pts.append([t.value, round(v, 3)])
            i += 3
        if len(pts) < 1:
            raise DSLError("dynamic: needs at least one point", line)
        out["dynamic"] = pts
    if "humanize" in p:
        toks = p.pop("humanize")
        if len(toks) == 1 and toks[0].kind == "NUMBER":
            x = max(0.0, min(1.0, toks[0].value))   # macro -> explicit values
            out["humanize"] = {"timing_s": round(0.018 * x, 5),
                               "vel": round(0.15 * x, 4)}
        else:
            d, i = {}, 0
            keymap = {"time": ("timing_s", None), "vel": ("vel", None)}
            while i + 2 < len(toks) + 1 and i < len(toks):
                k = toks[i].text
                if k not in keymap or toks[i+1].text != "=":
                    raise DSLError("humanize expects a 0..1 amount or "
                                   "'time=… vel=…'", toks[i].line)
                d[keymap[k][0]] = toks[i+2].value
                i += 3
            out["humanize"] = d
    if "vibrato" in p:
        toks = p.pop("vibrato")
        d, i = {}, 0
        keymap = {"rate": "rate_hz", "depth": "depth_cents", "delay": "delay_s"}
        while i + 2 < len(toks) + 1 and i < len(toks):
            k = toks[i].text
            if k not in keymap or toks[i+1].text != "=":
                raise DSLError("vibrato expects 'rate=… depth=…c delay=…s'",
                               toks[i].line)
            d[keymap[k]] = toks[i+2].value
            i += 3
        out["vibrato"] = d
    if "glide" in p:
        out["glide_s"] = _one(p.pop("glide"), line, "s", "glide")
    if "velbright" in p:
        out["vel_brightness"] = _one(p.pop("velbright"), line)
    if "modes" in p:
        toks = [t for t in p.pop("modes") if t.kind == "NUMBER"]
        if len(toks) % 3 != 0 or not toks:
            raise DSLError("modes: comma-separated 'ratio amp t60' triplets",
                           line)
        out["modes"] = [[toks[i].value, toks[i + 1].value, toks[i + 2].value]
                        for i in range(0, len(toks), 3)]
    if "scan" in p:
        out["scan"] = _one(p.pop("scan"), line)
    if "source" in p:
        out["source"] = _one(p.pop("source"), line)
    if "srcdur" in p:
        out["source_dur_s"] = _one(p.pop("srcdur"), line, "s", "srcdur")
    if "grainsize" in p:
        out["grain_s"] = _one(p.pop("grainsize"), line, "s", "grainsize")
    if "density" in p:
        out["density"] = _one(p.pop("density"), line)
    if "pitchspread" in p:
        out["pitch_spread_cents"] = _one(p.pop("pitchspread"), line, "c",
                                         "pitchspread")
    if "scatter" in p:
        out["scatter"] = _one(p.pop("scatter"), line)
    if "pressure" in p:
        out["pressure"] = _one(p.pop("pressure"), line)
    if "bowpos" in p:
        out["bow_position"] = _one(p.pop("bowpos"), line)
    if "file" in p:
        out["file"] = _one(p.pop("file"), line)
    if "sha256" in p:
        out["sha256"] = _one(p.pop("sha256"), line)
    if "pitch" in p:
        out["pitch_st"] = _one(p.pop("pitch"), line, "st", "pitch")
    if "preserve" in p:
        out["preserve_channels"] = _one(p.pop("preserve"), line) in (
            "stereo", "channels", "true", 1.0)
    if "bus" in p:
        out["bus"] = _one(p.pop("bus"), line)
    if "model" in p:
        out["model"] = _one(p.pop("model"), line)
    if "instrument" in p:
        out["instrument"] = _one(p.pop("instrument"), line)
    if "section" in p:
        toks = p.pop("section")
        sec = {"size": 4, "spread": 0.6, "detune_c": 7.0, "timing_s": 0.009}
        i = 0
        keymap = {"size": ("size", None), "spread": ("spread", None),
                  "detune": ("detune_c", "c"), "timing": ("timing_s", "s")}
        while i + 2 < len(toks) + 1 and i < len(toks):
            t = toks[i]
            if (t.kind != "IDENT" or t.text not in keymap
                    or i + 2 >= len(toks) + 1
                    or toks[i + 1].text != "="):
                raise DSLError("section: size=N [spread=0..1] [detune=Nc] "
                               "[timing=Ns]", t.line)
            jk, unit = keymap[t.text]
            v = toks[i + 2]
            if unit and v.unit not in (None, unit):
                raise DSLError(f"section {t.text}: unit must be {unit}",
                               v.line)
            sec[jk] = int(v.value) if jk == "size" else float(v.value)
            i += 3
        out["section"] = sec
    if "legato" in p:
        out["legato_s"] = _one(p.pop("legato"), line, "s", "legato")
    if "seat" in p:
        toks = p.pop("seat")
        if (len(toks) != 3 or toks[0].kind != "NUMBER"
                or toks[0].unit not in (None, "deg")
                or toks[1].text != "@" or toks[2].kind != "NUMBER"
                or toks[2].unit not in (None, "m")):
            raise DSLError("seat: <azimuth>deg @ <distance>m "
                           "(e.g. seat: -12deg @ 4m)", line)
        out["seat"] = {"az_deg": float(toks[0].value),
                       "dist_m": float(toks[2].value)}
    if "phrasing" in p:
        out["phrasing"] = _one(p.pop("phrasing"), line)
    if "articulation" in p:
        out["articulation"] = _one(p.pop("articulation"), line)
    if "intensity" in p:
        out["intensity"] = _one(p.pop("intensity"), line)
    for k, jk in (("tune", "tune_st"), ("decay", "decay"),
                  ("snap", "snap"), ("bend", "bend")):
        if k in p:
            out[jk] = _one(p.pop(k), line, "st" if k == "tune" else None, k)
    arp = None
    if "arp" in p:
        toks = p.pop("arp")
        if not toks or toks[0].kind != "IDENT" or toks[0].text not in (
                "up", "down", "updown", "downup", "random"):
            raise DSLError("arp: pattern up|down|updown|downup|random "
                           "[rate=…b octaves=N gate=0..1]", line)
        arp = {"pattern": toks[0].text, "rate_beats": 0.25, "octaves": 1,
               "gate": 0.85}
        i = 1
        while i + 2 < len(toks) + 1 and i < len(toks):
            k = toks[i].text
            if k not in ("rate", "octaves", "gate") or toks[i + 1].text != "=":
                raise DSLError("arp options: rate=…b octaves=N gate=0..1",
                               toks[i].line)
            key = {"rate": "rate_beats", "octaves": "octaves",
                   "gate": "gate"}[k]
            arp[key] = toks[i + 2].value
            i += 3

    notes = list(p.pop("notes", []))
    next_slur = [max([e.get("slur", 0) or 0 for e in notes] + [0])]
    slur_group_ids: dict = {}
    for play in p.pop("plays", []):
        m = motifs.get(play["motif"])
        if m is None:
            raise DSLError(f"unknown motif '{play['motif']}'", play["line"])
        evs = [dict(e) for e in m]
        if play.get("retrograde"):
            evs = theory.retrograde(evs)
        if play.get("invert"):
            evs = theory.invert(evs)
        if play.get("stretch"):
            evs = theory.stretch(evs, float(play["stretch"]))
        if play.get("diatonic"):
            rk = _key_at(key_map, play["at_beat"])
            if rk is None:
                raise DSLError("diatonic transform needs an asset key",
                               play["line"])
            root_pc, iv = rk
            for ev in evs:
                for kk in ("note", "chord_root"):
                    if kk in ev:
                        ev[kk] = theory.diatonic_transpose(
                            ev[kk], int(play["diatonic"]), root_pc, iv)
        if play.get("slur_group"):
            gid = ("g", play["slur_group"])
            if gid not in slur_group_ids:
                next_slur[0] += 1
                slur_group_ids[gid] = next_slur[0]
            for ev2 in evs:
                ev2["slur"] = slur_group_ids[gid]
        elif play.get("legato"):
            next_slur[0] += 1
            for ev2 in evs:
                ev2["slur"] = next_slur[0]
        for ev2 in evs:
            ev2["start_beat"] = round(ev2["start_beat"] + play["at_beat"], 6)
            if "vel" in ev2 or play["vel_scale"] != 1.0:
                ev2["vel"] = round(ev2.get("vel", 1.0) * play["vel_scale"], 4)
            if play["transpose_st"]:
                if "note" in ev2:
                    ev2["freq_hz"] = round(_transpose(ev2.pop("note"),
                                                      play["transpose_st"]), 4)
                elif "chord_root" in ev2:
                    st = play["transpose_st"]
                    if st != int(st):
                        raise DSLError("chords need whole-semitone "
                                       "transpose", play["line"])
                    ev2["chord_root"] = theory.semis_to_note(
                        theory.note_to_semis(ev2["chord_root"]) + int(st))
            notes.append(ev2)
    expanded = []
    for ev in notes:
        if ev.get("art") != "trill":
            expanded.append(ev)
            continue
        if "note" not in ev:
            raise DSLError("trill needs a named note (not a frequency or "
                           "chord)", lay.line)
        rk = _key_at(key_map, ev["start_beat"])
        if rk is None:
            raise DSLError("trill needs an asset key (key: ...) for its "
                           "diatonic upper neighbor", lay.line)
        root_pc, iv = rk
        upper = theory.diatonic_transpose(ev["note"], 1, root_pc, iv)
        step = 0.125
        n_steps = max(2, int(round(ev["dur_beats"] / step)))
        for k in range(n_steps):
            expanded.append({**{kk: v for kk, v in ev.items()
                                if kk != "art"},
                             "note": upper if k % 2 else ev["note"],
                             "start_beat": round(ev["start_beat"]
                                                 + k * step, 6),
                             "dur_beats": step})
        diags.append(f"layer '{lay.name}': trill on {ev['note']} expanded "
                     f"to {n_steps} alternating notes with {upper} "
                     f"(0.125b steps, key-aware)")
    notes = expanded
    notes = _expand_chords(notes, arp, lay.name,
                           variant=variant)
    if notes:
        out["notes"] = sorted(notes, key=lambda e: (e["start_beat"],
                                                    e.get("note", ""),
                                                    e.get("freq_hz", 0)))
        if scale:
            bad = sorted({ev["note"] for ev in notes
                          if "note" in ev and _note_pc(ev["note"]) not in scale})
            if bad:
                diags.append(f"layer '{lay.name}': notes outside the declared "
                             f"key: {bad} (intentional chromaticism is fine — "
                             f"this is advisory)")
    if "note" in p:
        out["note"] = _one(p.pop("note"), line)
    for tgt, pts in p.pop("auto", []):
        out.setdefault("automation", []).append(_auto_block(tgt, pts))
    if p:
        diags.append(f"layer '{lay.name}': unknown properties ignored: {sorted(p)}")
    return out


def compile_dsl(src: str, variant=None) -> tuple[list[dict], list[str]]:
    """DSL text -> ([compiled JSON specs], diagnostics). Raises DSLError.
    `variant` resolves vary() choices and reseeds all stochastic paths."""
    assets = parse_assets(src)
    specs, diags = [], []
    for a in assets:
        spec, d = compile_asset(a, variant=variant)
        specs.append(spec)
        diags.extend(f"{a.id}: {msg}" for msg in d)
    return specs, diags
