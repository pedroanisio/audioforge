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

import math
import re
from dataclasses import dataclass, field

from . import theory
from .ir_schema import INTENT_RENDER_ENUMS
from .lark_parser import parse_assets
from .schema import IR_ARTICULATIONS, BPM_MIN, TEMPO_MAP_BPM_MAX
from .synth import NOTE_OFFSETS
from .styles import STYLE_PACKS
from .theory import NOTE_RE
from .version import DSL_VERSION, ENGINE_VERSION


class DSLError(ValueError):
    def __init__(self, msg: str, line: int | None = None):
        super().__init__(f"line {line}: {msg}" if line else msg)
        self.line = line


# `lark_parser.LARK_GRAMMAR` is the one executable grammar and `parse_assets`
# the one parser. `Tok`/`Layer`/`Asset` below are the AST shapes that grammar's
# tree-walker produces and the compiler consumes; `NOTE_RE` is shared pitch
# validation. The old regex lexer and recursive-descent parser were removed when
# Lark became the single path (audit finding F9).
# Render-affecting intent vocabulary is single-sourced from the published IR
# schema (audit finding F5); the compiler holds it as {field: set} for fast
# membership checks. `NOTE_RE` (pitch spelling) is imported from `theory` so the
# DSL and the IR validator share one definition (audit finding F13).
INTENT_RENDER_FIELDS = {field: set(values)
                        for field, values in INTENT_RENDER_ENUMS.items()}
INTENT_METADATA_FIELDS = {"affect", "avoid", "repair", "style_text"}
INTENT_FIELDS = set(INTENT_RENDER_FIELDS) | INTENT_METADATA_FIELDS


@dataclass
class Tok:
    """A property-value token, as produced by the Lark tree-walker and consumed
    by the compiler. `kind` is one of NUMBER | IDENT | STRING | PUNCT."""
    kind: str
    text: str
    line: int
    value: float | None = None
    unit: str | None = None


# -------------------------------------------------------------------- AST
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
    intent: dict = field(default_factory=dict)
    markers: list = field(default_factory=list)
    motifs: dict = field(default_factory=dict)
    layers: list = field(default_factory=list)
    buses: list = field(default_factory=list)
    cutdowns: list = field(default_factory=list)
    stage: dict | None = None
    master: dict = field(default_factory=dict)
    line: int = 0


# ------------------------------------------------------------------ compiler
EMOTIONS = {"tension", "awe", "sadness", "triumph", "suspense", "intimacy",
            "urgency", "calm", "fear", "wonder", "cinematic_intensity"}

# Authoring articulations are the IR validator's set plus `trill`, which is
# authoring-only and compiles away. Deriving the relationship structurally keeps
# the two sets from drifting (audit finding F6).
ARTICULATIONS = IR_ARTICULATIONS | {"trill"}

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
    "ladder": lambda a: {"type": "ladder",
                         "cutoff_hz": a.get("cutoff", a.get("_0", 1000.0)),
                         "resonance": a.get("resonance", a.get("res", 0.5)),
                         "drive": a.get("drive", 0.0),
                         "mix": a.get("mix", 1.0)},
    "tape": lambda a: {"type": "tape",
                       "drive": a.get("drive", a.get("_0", 0.4)),
                       "flutter": a.get("flutter", 0.3),
                       "tone": a.get("tone", 0.5),
                       "mix": a.get("mix", 1.0)},
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
    while i + 1 < len(toks):   # at least two tokens (key, value) remain
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


def _read_hold_events(toks: list[Tok], line: int) -> list[dict]:
    holds = []
    i = 0
    while i < len(toks):
        if toks[i].kind == "PUNCT" and toks[i].text == ",":
            i += 1
            continue
        if i + 2 >= len(toks) or toks[i + 1].text != "=":
            raise DSLError("fermata expects BEATb=DURATIONs pairs",
                           toks[i].line if i < len(toks) else line)
        beat, duration = toks[i], toks[i + 2]
        if beat.kind != "NUMBER" or beat.unit not in (None, "b"):
            raise DSLError("fermata beat must use beats, e.g. 4b",
                           beat.line)
        if duration.kind != "NUMBER" or duration.unit not in (None, "s"):
            raise DSLError("fermata duration must use seconds, e.g. 1.5s",
                           duration.line)
        holds.append({
            "beat": round(float(beat.value), 6),
            "duration_s": round(float(duration.value), 6),
        })
        i += 3
    return sorted(holds, key=lambda h: h["beat"])


def _intent_token_value(tok: Tok):
    if tok.kind == "NUMBER":
        return tok.value
    return tok.text


def _intent_scalar(toks: list[Tok], line: int, field: str) -> str:
    vals = [t for t in toks if not (t.kind == "PUNCT" and t.text == ",")]
    if len(vals) != 1 or vals[0].kind not in {"IDENT", "STRING", "NUMBER"}:
        raise DSLError(f"intent.{field}: expected a single value", line)
    value = _intent_token_value(vals[0])
    return str(value)


def _intent_list(toks: list[Tok], line: int, field: str) -> list[str]:
    vals = []
    for tok in toks:
        if tok.kind == "PUNCT" and tok.text == ",":
            continue
        if tok.kind not in {"IDENT", "STRING", "NUMBER"}:
            raise DSLError(f"intent.{field}: expected comma-separated values",
                           tok.line)
        vals.append(str(_intent_token_value(tok)))
    if not vals:
        raise DSLError(f"intent.{field}: expected at least one value", line)
    return vals


def _read_structured_intent(raw: dict, line: int) -> dict:
    """Parse the typed intent block into semantic IR.

    The render-affecting fields are deliberately closed enums. Metadata fields
    are preserved for agents and repair loops, but have no direct render effect.
    """
    render_affecting: dict[str, str] = {}
    metadata: dict[str, object] = {}
    authored: list[dict] = []
    for field in sorted(raw):
        toks = raw[field]
        if field in INTENT_RENDER_FIELDS:
            value = _intent_scalar(toks, line, field).lower()
            allowed = INTENT_RENDER_FIELDS[field]
            if value not in allowed:
                raise DSLError(
                    f"intent.{field}: expected one of {sorted(allowed)}",
                    toks[0].line if toks else line,
                )
            render_affecting[field] = value
            authored.append({"field": field, "value": value})
        elif field == "avoid":
            values = _intent_list(toks, line, field)
            metadata[field] = values
            authored.append({"field": field, "value": values})
        else:
            value = _intent_scalar(toks, line, field)
            metadata[field] = value
            authored.append({"field": field, "value": value})
    return {
        "render_affecting": render_affecting,
        "metadata": metadata,
        "expansions": [],
        "authored": authored,
    }


def _semantic_sidecar(a: Asset, smart_intent: dict) -> dict:
    """Capture authored high-level constructs that compile away.

    This is provenance/semantic data: it is excluded from render hashing but lets
    decompile stay at the same authoring altitude when the IR came from DSL.
    """
    semantic: dict = {}
    if smart_intent and "style" not in smart_intent:
        semantic["smart_directives"] = [
            key for key in ("style", "perform", "ensemble", "voicing", "space")
            if key in smart_intent
        ]
    if a.motifs:
        semantic["motifs"] = {
            name: [dict(ev) for ev in events]
            for name, events in sorted(a.motifs.items())
        }
    layers: dict = {}
    for lay in a.layers:
        lsem: dict = {"props": sorted(lay.props)}
        if "notes" in lay.props:
            lsem["notes"] = [dict(ev) for ev in lay.props.get("notes", [])]
        if "plays" in lay.props:
            lsem["plays"] = [dict(play) for play in lay.props.get("plays", [])]
        if len(lsem) > 1:
            layers[lay.name] = lsem
    if layers:
        semantic["layers"] = layers
    if a.master:
        semantic["master_props"] = sorted(a.master)
    return semantic


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


def _read_notation_props(p: dict, line: int) -> dict:
    notation: dict = {}
    if "tuning" in p:
        toks = p.pop("tuning")
        if not toks or toks[0].text != "edo":
            raise DSLError("tuning: expected 'edo divisions=N base=A4 hz=440'",
                           toks[0].line if toks else line)
        out = {"system": "edo"}
        i = 1
        while i < len(toks):
            if toks[i].kind == "PUNCT":
                i += 1
                continue
            key = toks[i].text
            if i + 2 >= len(toks) or toks[i + 1].text != "=":
                raise DSLError("tuning: expected key=value pairs", toks[i].line)
            val = toks[i + 2]
            out[{"divisions": "divisions", "base": "base_note",
                 "hz": "base_hz"}.get(key, key)] = (
                int(val.value) if key == "divisions"
                else float(val.value) if key == "hz"
                else val.text
            )
            i += 3
        notation["tuning"] = out
    if "tuplet" in p:
        toks = p.pop("tuplet")
        if len(toks) < 7:
            raise DSLError("tuplet: layer STARTb for DURb ratio=N:M", line)
        ratio_idx = next((i for i, t in enumerate(toks)
                          if t.kind == "IDENT" and t.text == "ratio"), -1)
        if ratio_idx < 0 or toks[ratio_idx + 1].text != "=":
            raise DSLError("tuplet: missing ratio=N:M", line)
        notation.setdefault("tuplets", []).append({
            "layer": toks[0].text,
            "start_beat": toks[1].value,
            "dur_beats": toks[3].value,
            "ratio": [int(toks[ratio_idx + 2].value),
                      int(toks[ratio_idx + 4].value)],
        })
    if "lyrics" in p:
        toks = p.pop("lyrics")
        if len(toks) < 3 or toks[2].kind != "STRING":
            raise DSLError('lyrics: layer STARTb "text" [phonemes=...]', line)
        lyric = {"layer": toks[0].text, "start_beat": toks[1].value,
                 "text": toks[2].text}
        for i, tok in enumerate(toks):
            if tok.kind == "IDENT" and tok.text == "phonemes" \
                    and i + 2 < len(toks) and toks[i + 1].text == "=":
                lyric["phonemes"] = toks[i + 2].text.split("_")
        notation.setdefault("lyrics", []).append(lyric)
    return notation


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
    if perform.get("rubato"):
        _apply_rubato_tempo_map(spec, perform, phrase_report, diags)
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


def _append_unique_master_fx(master: dict, fx: dict):
    chain = master.setdefault("fx", [])
    if fx not in chain:
        chain.append(fx)


def _base_tempo_points(spec: dict) -> list[list[float]]:
    return [[float(b), float(v)] for b, v in
            (spec.get("tempo_map") or [[0.0, float(spec.get("bpm", 120.0))]])]


def _tempo_at(points: list[list[float]], beat: float) -> float:
    if not points:
        return 120.0
    if beat <= points[0][0]:
        return points[0][1]
    for (b0, v0), (b1, v1) in zip(points, points[1:]):
        if b0 <= beat <= b1:
            if b1 == b0:
                return v1
            x = (beat - b0) / (b1 - b0)
            return v0 + (v1 - v0) * x
    return points[-1][1]


def _rubato_multiplier(shape: str, x: float, amount: float) -> float:
    x = max(0.0, min(1.0, x))
    if shape in {"ritard", "rit", "release"}:
        return 1.0 - amount * (x * x)
    if shape in {"accelerando", "accel", "push"}:
        return 1.0 + amount * (x * x)
    if shape in {"sigh", "push_pull"}:
        return 1.0 + amount * math.sin(2.0 * math.pi * x)
    # arch/default: slower edges, faster phrase center.
    return 1.0 + amount * (2.0 * math.sin(math.pi * x) - 1.0)


def _rubato_value(value) -> str:
    if isinstance(value, list):
        return str(value[0]) if value else "arch"
    return str(value)


def _rubato_float(perform: dict, key: str, default: float,
                  *, minimum: float, maximum: float) -> float:
    value = perform.get(key, default)
    if isinstance(value, list):
        value = value[0] if value else default
    out = float(value)
    return max(minimum, min(maximum, out))


def _rubato_segment_beats(perform: dict) -> float:
    value = perform.get("segment", 0.25)
    if isinstance(value, list):
        value = value[0] if value else 0.25
    return max(0.05, min(1.0, float(value)))


def _apply_rubato_tempo_map(spec: dict, perform: dict,
                            phrase_report: dict[str, list[dict]],
                            diags: list[str]):
    shape = _rubato_value(perform.get("rubato", "arch")).lower()
    amount = _rubato_float(perform, "amount", 0.12, minimum=0.0, maximum=0.35)
    segment = _rubato_segment_beats(perform)
    phrases = [
        ph for _lname, layer_phrases in sorted(phrase_report.items())
        for ph in layer_phrases
        if ph["end_beat"] > ph["start_beat"]
    ]
    if not phrases:
        diags.append("perform.rubato: no note phrases found; no tempo_map "
                     "points were generated")
        return
    base_points = _base_tempo_points(spec)
    compiled: dict[float, float] = {
        round(float(b), 6): float(v) for b, v in base_points
    }
    for ph in phrases:
        start = float(ph["start_beat"])
        end = float(ph["end_beat"])
        dur = max(1e-9, end - start)
        steps = max(1, int(math.ceil(dur / segment)))
        for idx in range(steps + 1):
            beat = round(start + dur * idx / steps, 6)
            x = (beat - start) / dur
            bpm = _tempo_at(base_points, beat) * _rubato_multiplier(
                shape, x, amount)
            compiled[beat] = round(max(BPM_MIN, min(TEMPO_MAP_BPM_MAX, bpm)), 6)
        for key in ("peak_beat", "cadence_beat"):
            beat = round(float(ph[key]), 6)
            x = (beat - start) / dur
            bpm = _tempo_at(base_points, beat) * _rubato_multiplier(
                shape, x, amount)
            compiled[beat] = round(max(BPM_MIN, min(TEMPO_MAP_BPM_MAX, bpm)), 6)
    points = [[b, compiled[b]] for b in sorted(compiled)]
    if points[0][0] != 0.0:
        points.insert(0, [0.0, _tempo_at(base_points, 0.0)])
    spec["tempo_map"] = points
    max_error = min(0.002, round((segment ** 3) * 0.001, 6))
    perform["rubato_compiled"] = {
        "target": "tempo_map",
        "shape": shape,
        "amount": amount,
        "base_bpm": float(spec.get("bpm", points[0][1])),
        "segment_beats": segment,
        "max_segment_error_s": max_error,
        "point_count": len(points),
        "phrases": len(phrases),
    }
    diags.append("perform.rubato: compiled phrase curve to dense tempo_map "
                 f"points (max segment error <= {max_error:.3g}s)")


def _apply_structured_intent(spec: dict, structured: dict, diags: list[str]):
    """Expand typed intent fields into explicit render IR.

    Only ``render_affecting`` fields mutate layers/master. Metadata is stored
    under ``intent.structured.metadata`` and is excluded from render hashing.
    """
    if not structured:
        return
    intent = spec.setdefault("intent", {})
    intent["structured"] = structured
    render = structured.get("render_affecting", {})
    expansions = structured.setdefault("expansions", [])

    density = render.get("density")
    if density:
        delta = {"sparse": -1.5, "balanced": 0.0, "dense": 0.8}[density]
        affected = []
        if delta:
            for layer in spec.get("layers", []):
                if layer.get("type") in {"notes", "instrument", "drums", "tone"}:
                    layer["gain_db"] = round(float(layer.get("gain_db", 0.0))
                                             + delta, 3)
                    affected.append(layer.get("name", layer.get("type")))
        expansions.append({
            "field": "density",
            "strategy": "layer_gain_db_delta",
            "delta_db": delta,
            "layers": affected,
        })
        ensemble_size = int(
            spec.get("intent", {}).get("ensemble", {}).get("size", 0) or 0
        )
        if density == "sparse" and ensemble_size > 6:
            diags.append(
                "intent conflict: density=sparse with ensemble size "
                f"{ensemble_size}; sparse layer gain expansion was kept, "
                "but arrangement size may need agent review"
            )

    contour = render.get("contour")
    if contour and contour != "flat":
        duration = round(float(spec.get("duration_s", 0.0)), 6)
        midpoint = round(duration / 2.0, 6)
        points_by_contour = {
            "arch": [[0.0, -2.0], [midpoint, 0.0], [duration, -2.0]],
            "rise": [[0.0, -2.0], [duration, 0.0]],
            "fall": [[0.0, 0.0], [duration, -2.0]],
        }
        points = points_by_contour[contour]
        spec.setdefault("master", {}).setdefault("automation", []).append({
            "target": "gain_db",
            "points": points,
            "from_intent": "contour",
        })
        expansions.append({
            "field": "contour",
            "strategy": "master_gain_automation",
            "points": points,
        })

    texture = render.get("texture")
    if texture and texture != "neutral":
        master = spec.setdefault("master", {})
        texture_fx = {
            "smooth": {"type": "filter", "mode": "lowpass",
                       "cutoff_hz": 6500.0, "q": 0.7071},
            "airy": {"type": "filter", "mode": "highpass",
                     "cutoff_hz": 120.0, "q": 0.7071},
            "warm": {"type": "filter", "mode": "lowpass",
                     "cutoff_hz": 9200.0, "q": 0.7071},
            "bright": {"type": "highshelf", "freq_hz": 5500.0,
                       "gain_db": 1.2},
        }[texture]
        _append_unique_master_fx(master, texture_fx)
        expansions.append({
            "field": "texture",
            "strategy": "master_fx",
            "fx": texture_fx,
        })

    metadata = structured.get("metadata", {})
    avoid = set(metadata.get("avoid", []))
    peak = spec.get("master", {}).get("target_peak_dbfs")
    if "clipping" in avoid and peak is not None and float(peak) > -0.5:
        diags.append(
            "intent conflict: avoid=clipping with master peak above -0.5 dBFS; "
            "peak was preserved for explicit user control"
        )
    if render:
        diags.append(
            "intent block: expanded render-affecting density/contour/texture "
            "fields into explicit IR"
        )


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
        elif abs(b_semis[0] - a_semis[-1]) <= 7 \
                and b_key[0] - min(0.5, a_key[1] * 0.2) >= 0.0:
            # an anticipation cannot precede beat 0 (merged from _tmp: jazz
            # style + chord at 0b otherwise compiled a passing tone to -0.5b)
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


def _event_freq_hz(ev: dict) -> float | None:
    if "freq_hz" in ev:
        return float(ev["freq_hz"])
    if "note" not in ev:
        return None
    return 440.0 * 2.0 ** (
        (theory.note_to_semis(ev["note"]) - theory.note_to_semis("A4")) / 12.0
    )


def _append_authored_expression(spec: dict, layer: dict, field: str, value):
    semantic = spec.setdefault("_meta", {}).setdefault("semantic", {})
    authored = semantic.setdefault("authored_expression", [])
    if any(e.get("layer") == layer.get("name") and e.get("field") == field
           for e in authored):
        return
    authored.append({
        "layer": layer.get("name"),
        "field": field,
        "source": "legacy_performance_field",
        "value": value,
    })


def _vibrato_curve(vibrato: dict, dur_s: float) -> dict:
    rate_hz = float(vibrato.get("rate_hz", 5.0))
    depth = float(vibrato.get("depth_cents", 12.0))
    delay_s = float(vibrato.get("delay_s", 0.25))
    fade_s = float(vibrato.get("fade_s", 0.35))
    curve_rate = 250.0
    n = max(1, int(math.ceil(max(dur_s, 0.0) * curve_rate)) + 1)
    values = []
    for idx in range(n):
        t = idx / curve_rate
        amount = max(0.0, min(1.0, (t - delay_s) / max(fade_s, 1e-3)))
        cents = depth * amount * math.sin(2.0 * math.pi * rate_hz * t)
        values.append(round(cents, 6))
    return {
        "target": "pitch_cents",
        "source": "vibrato",
        "time_basis": "note_seconds",
        "t0": 0.0,
        "rate_hz": curve_rate,
        "values": values,
    }


def _glide_curve(prev_freq: float, freq: float, glide_s: float,
                 dur_s: float) -> dict:
    start_cents = 1200.0 * math.log2(prev_freq / freq)
    end_s = round(min(float(glide_s), max(float(dur_s), 0.0)), 6)
    if end_s <= 0.0:
        end_s = round(float(glide_s), 6)
    return {
        "target": "pitch_cents",
        "source": "glide_s",
        "time_basis": "note_seconds",
        "points": [[0.0, round(start_cents, 6)], [end_s, 0.0]],
    }


def _lower_legacy_performance_curves(spec: dict, diags: list[str]):
    from .sequencer import TempoMap, TimelineMap

    bpm = float(spec.get("bpm", 120.0))
    tempo = TempoMap(spec.get("tempo_map") or [[0.0, bpm]])
    timeline = TimelineMap(tempo, spec.get("holds"))
    for layer in spec.get("layers", []):
        if layer.get("type") not in ("notes", "instrument"):
            continue
        dynamic = layer.get("dynamic")
        existing_dynamic_auto = [
            au for au in layer.get("automation", [])
            if isinstance(au, dict) and au.get("target") == "dynamic"
        ]
        if dynamic and existing_dynamic_auto:
            for au in existing_dynamic_auto:
                au.setdefault("time_basis", "layer_beats")
            _append_authored_expression(spec, layer, "dynamic", dynamic)
        elif dynamic:
            layer.setdefault("automation", []).append({
                "target": "dynamic",
                "time_basis": "layer_beats",
                "points": [[float(t), float(v)] for t, v in dynamic],
            })
            _append_authored_expression(spec, layer, "dynamic", dynamic)

        vibrato = layer.get("vibrato")
        glide_s = float(layer.get("glide_s", 0.0) or 0.0)
        if vibrato:
            _append_authored_expression(spec, layer, "vibrato", vibrato)
        if glide_s > 0.0:
            _append_authored_expression(spec, layer, "glide_s", glide_s)

        prev_freq = None
        prev_start = None
        events = sorted(layer.get("notes", []),
                        key=lambda e: (e["start_beat"], e.get("note", ""),
                                       e.get("freq_hz", 0.0)))
        for ev in events:
            freq = _event_freq_hz(ev)
            if freq is None:
                continue
            start = float(ev["start_beat"])
            dur = float(ev["dur_beats"])
            dur_s = max(0.0, timeline.sec(start + dur) - timeline.sec(start))
            if (glide_s > 0.0 and prev_freq is not None
                    and prev_start is not None and prev_start < start
                    and abs(prev_freq - freq) > 1e-9):
                ev.setdefault("curves", []).append(
                    _glide_curve(prev_freq, freq, glide_s, dur_s))
            if vibrato:
                ev.setdefault("curves", []).append(_vibrato_curve(vibrato, dur_s))
            prev_freq = freq
            prev_start = start
        if dynamic or vibrato or glide_s > 0.0:
            diags.append(
                f"layer '{layer.get('name')}': lowered legacy performance "
                "fields to explicit curves")


def compile_asset(a: Asset, variant=None) -> tuple[dict, list[str]]:
    diags: list[str] = []
    _apply_vary(a, variant)
    spec: dict = {
        "id": a.id,
        "layers": [],
        "_meta": {
            "dsl_version": DSL_VERSION,
            "engine_version": ENGINE_VERSION,
        },
    }
    if variant is not None:
        spec["variant"] = str(variant)
    p = a.props

    def take(key, default=None):
        return p.pop(key, default)

    spec["kind"] = _one(take("kind", [Tok("IDENT", "sfx", a.line)]), a.line)
    spec["duration_s"] = _one(take("duration"), a.line, "s", "duration")
    smart_intent = _read_smart_directives(p, a.line)
    structured_intent = (
        _read_structured_intent(a.intent, a.line) if a.intent else {}
    )
    semantic = _semantic_sidecar(a, smart_intent)
    if semantic:
        spec.setdefault("_meta", {})["semantic"] = semantic
    score = _read_score_props(p, a.line)
    if score:
        spec["score"] = score
    notation = _read_notation_props(p, a.line)
    if notation:
        spec["notation"] = notation
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
    holds = []
    if "fermata" in p:
        holds.extend(_read_hold_events(take("fermata"), a.line))
    if "hold" in p:
        holds.extend(_read_hold_events(take("hold"), a.line))
    if holds:
        merged: dict[float, float] = {}
        for hold in holds:
            merged[hold["beat"]] = merged.get(hold["beat"], 0.0) \
                + hold["duration_s"]
        spec["holds"] = [
            {"beat": beat, "duration_s": round(duration, 6)}
            for beat, duration in sorted(merged.items())
        ]
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
        while i + 1 < len(toks):   # at least two tokens (key, value) remain
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
    if structured_intent:
        _apply_structured_intent(spec, structured_intent, diags)
    _lower_legacy_performance_curves(spec, diags)

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
    fix(a.intent, "intent")
    fix(a.master, "master")
    for lay in a.layers:
        fix(lay.props, f"layer:{lay.name}")
    for b in a.buses:
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


def _parse_canonical_curve_specs(groups: list[list[Tok]],
                                 line: int) -> list[tuple[int, dict]]:
    out = []
    for toks in groups:
        if len(toks) < 7:
            raise DSLError("curves: note N target basis=<basis> points", line)
        i = 0
        if toks[i].kind != "IDENT" or toks[i].text != "note":
            raise DSLError("curves: expected 'note N target ...'", toks[i].line)
        idx_tok = toks[i + 1]
        if idx_tok.kind != "NUMBER" or idx_tok.unit is not None:
            raise DSLError("curves: note index must be an integer", idx_tok.line)
        note_idx = int(idx_tok.value)
        target_tok = toks[i + 2]
        if target_tok.kind != "IDENT":
            raise DSLError("curves: target must be an identifier", target_tok.line)
        if (toks[i + 3].text != "basis" or toks[i + 4].text != "="
                or toks[i + 5].kind != "IDENT"):
            raise DSLError("curves: expected basis=<time_basis>", toks[i + 3].line)
        curve = {"target": target_tok.text, "time_basis": toks[i + 5].text}
        i = 6
        if i < len(toks) and toks[i].kind == "IDENT" and toks[i].text == "sampled":
            i += 1
            values = None
            while i < len(toks):
                if toks[i].text == ",":
                    i += 1
                    continue
                key = toks[i]
                if key.kind != "IDENT" or i + 2 >= len(toks) or toks[i + 1].text != "=":
                    raise DSLError("curves sampled: expected key=value", key.line)
                if key.text == "values":
                    values = []
                    i += 2
                    while i < len(toks):
                        if toks[i].text == ",":
                            i += 1
                            continue
                        if toks[i].kind != "NUMBER":
                            break
                        values.append(float(toks[i].value))
                        i += 1
                    continue
                val = toks[i + 2]
                if val.kind != "NUMBER":
                    raise DSLError("curves sampled: value must be numeric", val.line)
                if key.text == "t0":
                    curve["t0"] = float(val.value)
                elif key.text == "rate":
                    curve["rate_hz"] = float(val.value)
                else:
                    raise DSLError(f"curves sampled: unknown key '{key.text}'",
                                   key.line)
                i += 3
            if values is None:
                raise DSLError("curves sampled: missing values=", line)
            curve["values"] = values
        else:
            points = []
            while i < len(toks):
                if toks[i].text == ",":
                    i += 1
                    continue
                if (i + 2 >= len(toks) or toks[i].kind != "NUMBER"
                        or toks[i + 1].text != "="
                        or toks[i + 2].kind != "NUMBER"):
                    raise DSLError("curves: expected time=value point",
                                   toks[i].line)
                point = [float(toks[i].value), float(toks[i + 2].value)]
                i += 3
                if i + 1 < len(toks) and toks[i].text == "@":
                    if toks[i + 1].kind != "IDENT":
                        raise DSLError("curves: shape after @ must be an identifier",
                                       toks[i].line)
                    point.append(toks[i + 1].text)
                    i += 2
                points.append(point)
            curve["points"] = points
        out.append((note_idx, curve))
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
             "tension": ("tension", None), "strike": ("strike", None),
             "lip": ("lip", None),
             "coupling": ("coupling", None), "buzz": ("buzz", None),
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
            while i + 1 < len(toks):   # at least two tokens (key, value) remain
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
        while i + 1 < len(toks):   # at least two tokens (key, value) remain
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
        while i + 1 < len(toks):   # at least two tokens (key, value) remain
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
        while i + 1 < len(toks):   # at least two tokens (key, value) remain
            k = toks[i].text
            if k not in ("rate", "octaves", "gate") or toks[i + 1].text != "=":
                raise DSLError("arp options: rate=…b octaves=N gate=0..1",
                               toks[i].line)
            key = {"rate": "rate_beats", "octaves": "octaves",
                   "gate": "gate"}[k]
            arp[key] = toks[i + 2].value
            i += 3

    notes = list(p.pop("notes", []))
    curve_specs = (_parse_canonical_curve_specs(p.pop("curves"), line)
                   if "curves" in p else [])
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
            if play.get("art") and "art" not in ev2:    # phrase-level art stamp
                ev2["art"] = play["art"]
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
    for note_idx, curve in curve_specs:
        if note_idx < 0 or note_idx >= len(notes):
            raise DSLError(f"curves: note index {note_idx} out of range", line)
        notes[note_idx].setdefault("curves", []).append(curve)
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
