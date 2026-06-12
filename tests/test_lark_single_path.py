"""Lark is the single parsing path — regression + structural guards.

Background: AudioForge once had two parsers for one language (the audit's
finding F9): a hand-rolled recursive-descent `Parser` over a regex tokenizer,
behind a coarse Lark *validation* gate whose parse tree was discarded. The two
grammars could drift silently. That has been collapsed: `lark_parser.LARK_GRAMMAR`
is the one executable grammar and `parse_assets` walks its tree straight into the
AST. The legacy parser is gone.

This module locks the consolidation in two ways:

1. **Golden AST regression** — a comprehensive synthetic battery plus every
   checked-in `.af` file is parsed and compared against a committed snapshot
   (`tests/golden/dsl_ast.json`). The snapshot was generated while the legacy
   parser still existed and was proven byte-identical to it, so it encodes the
   historical behavior without depending on the deleted code. Regenerate
   deliberately with `AF_REGEN_GOLDEN=1` and review the diff.
2. **Structural single-path guards** — there is no second tokenizer/parser and
   `compile_dsl` reaches the AST only through `parse_assets`.
"""
import hashlib
import json
import os
import subprocess
from pathlib import Path

import pytest

from audioforge.dsl import compile_dsl
from audioforge.lark_parser import parse_assets

ROOT = Path(__file__).resolve().parents[1]
GOLDEN = Path(__file__).resolve().parent / "golden" / "dsl_ast.json"


# Comprehensive construct coverage. Every alternative the grammar admits should
# appear at least once here so the golden snapshot pins it.
BATTERY = {
    "props_scalar": """asset a {
  kind: cue
  duration: 8s
  tempo: 120bpm
  key: C major
  meter: 7 8
  pickup: 1b
  form: intro 0b for 7b, verse 7b for 14b
  repeat: verse x2
  polymeter: drums 3 4
  style: cinematic
  perform: style=cinematic expressivity=0.6
  fermata: 4b = 2s
  hold: 8b = 1s, 16b = 2s
  layer t : tone { osc: sine note: C4 }
}
""",
    "marker_motif": """asset b {
  kind: cue
  duration: 4s
  marker hit @ 2s
  motif hook {
    C4 @ 0b for 1b vel 0.8
    C3min7 @ 1b for 2b voicing drop2
    440hz @ 3b for 1b
    E4 @ 4b for 1b art staccato gen arp
  }
  layer t : tone { osc: sine note: C4 }
}
""",
    "intent_full": """asset c {
  kind: cue
  duration: 2s
  intent {
    density: sparse
    contour: arch
    texture: smooth
    affect: tense
    avoid: clipping, noise
    repair: "smooth it out"
    style_text: "epic"
  }
  layer t : tone { osc: sine note: C4 }
}
""",
    "layer_full": """asset d {
  kind: cue
  duration: 8s
  tempo: 100bpm
  layer pad : notes {
    osc: saw
    env: a=0.01s d=0.1s s=0.7 r=0.2s
    fx: lowpass(800hz, q=0.7)
    notes: slur(C4 @ 0b for 1b, D4 @ 1b for 1b), E4 @ 2b for 1b
    play hook @ 0b legato transpose +12st art sustain
    play hook @ 4b invert retrograde stretch 1.5 diatonic -2 vel 0.8
    auto gain: 0s=-12db, 1s=-6db
  }
  motif hook { C4 @ 0b for 1b }
  bus verb { fx: reverb(decay=1.2, mix=0.3)
    auto wet: 0s=0.1, 2s=0.5 }
  master { peak: -1db
    auto gain: 0s=0db, 4s=-3db }
}
""",
    "slur_plays": """asset e {
  kind: cue
  duration: 8s
  layer l : notes {
    notes: slur(play m @ 0b legato, play m @ 2b transpose +5st)
  }
  motif m { C4 @ 0b for 1b }
}
""",
    "stage_cutdowns": """asset f {
  kind: cue
  duration: 30s
  stage {
    hall: "cathedral.wav@abc123"
    mics: tree=0.8, close=0.3, ambient=0.4
    size: 20m, 30m, 12m
  }
  cutdowns {
    15s: keep 0s to 15s, fade 1s
    10s: keep 5s to 15s
  }
  layer t : tone { osc: sine note: C4 }
}
""",
    "edge_cases": """# leading comment
asset g {
  kind: cue   # inline comment
  duration: 2s
  empty_prop:
  negs: -1.5 -2db +3st
  paren: env(a=0.1, b=(1, 2))
  layer t : tone { osc: sine note: C4 }
}
""",
    # Reserved keywords (for/vel/art/slur/play/to/keep/fade/legato/transpose)
    # must still parse as ordinary identifiers inside free-form property values;
    # this pins the Earley dynamic-lexer behavior the consolidation relies on.
    "keywords_as_values": """asset h {
  kind: cue
  duration: 2s
  note_about: for vel art slur play to keep fade legato transpose diatonic
  layer t : tone { osc: sine note: C4 }
}
""",
}


def _af_cases() -> dict[str, str]:
    cases = {}
    result = subprocess.run(
        ["git", "ls-files", "--", "*.af"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    for name in sorted(line for line in result.stdout.splitlines() if line):
        path = ROOT / name
        cases[name] = path.read_text()
    return cases


def _all_cases() -> dict[str, str]:
    return {**BATTERY, **_af_cases()}


def _snapshot(src: str) -> str:
    """Stable textual form of the parse outcome (AST repr or error string)."""
    try:
        return "AST::" + repr(parse_assets(src))
    except Exception as exc:  # DSLError and friends — pin the message too
        return f"{type(exc).__name__}::{exc}"


def _stored_form(name: str, src: str) -> str:
    """Battery cases keep the full snapshot (small + debuggable on diff); the
    larger checked-in `.af` files are pinned by hash to keep the golden small."""
    snap = _snapshot(src)
    if name in BATTERY:
        return snap
    return "sha256:" + hashlib.sha256(snap.encode()).hexdigest()


def _build_golden() -> dict[str, str]:
    return {name: _stored_form(name, src) for name, src in _all_cases().items()}


@pytest.fixture(scope="module")
def golden() -> dict[str, str]:
    if os.environ.get("AF_REGEN_GOLDEN"):
        GOLDEN.parent.mkdir(parents=True, exist_ok=True)
        GOLDEN.write_text(json.dumps(_build_golden(), indent=2, sort_keys=True) + "\n")
    assert GOLDEN.exists(), "golden snapshot missing; run with AF_REGEN_GOLDEN=1"
    return json.loads(GOLDEN.read_text())


@pytest.mark.parametrize("name", sorted(_all_cases()))
def test_parse_matches_golden_ast(name, golden):
    src = _all_cases()[name]
    assert name in golden, f"{name} absent from golden; regen with AF_REGEN_GOLDEN=1"
    assert _stored_form(name, src) == golden[name]


def test_golden_covers_every_case(golden):
    assert set(golden) == set(_all_cases())


def test_compile_dsl_routes_through_parse_assets(monkeypatch):
    import audioforge.dsl as dsl

    calls = []
    real = dsl.parse_assets

    def spy(src):
        calls.append(src)
        return real(src)

    monkeypatch.setattr(dsl, "parse_assets", spy)
    src = (ROOT / "static" / "samples" / "transition_sweep.af").read_text()
    specs, diags = compile_dsl(src)
    assert calls, "compile_dsl did not reach parse_assets"
    assert specs and specs[0]["id"]
    assert isinstance(diags, list)


def test_no_second_parser_or_tokenizer_remains():
    """The legacy regex tokenizer and recursive-descent parser are gone — one
    grammar, one walk (audit finding F9 closed)."""
    dsl_src = (ROOT / "audioforge" / "dsl.py").read_text()
    assert "class Parser" not in dsl_src
    assert "def tokenize(" not in dsl_src
    assert "TOKEN_RE" not in dsl_src
    lark_src = (ROOT / "audioforge" / "lark_parser.py").read_text()
    assert "TOKEN_GRAMMAR" not in lark_src
    assert "def lark_tokenize" not in lark_src
    # exactly one Lark grammar object is constructed
    assert lark_src.count("Lark(") == 1
