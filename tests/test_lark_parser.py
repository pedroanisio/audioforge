"""Behavior of the single Lark front end (`audioforge.lark_parser`).

Byte-level AST regression across the full construct battery and every `.af`
fixture lives in `test_lark_single_path.py` (golden snapshot). This module
covers the parser's externally promised behavior: it is the runtime dependency,
it produces line-numbered diagnostics, it validates intent fields at parse time,
and it is the authoritative source the published grammar derives from.
"""
try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10: tomllib arrived in 3.11
    import tomli as tomllib
from pathlib import Path

import pytest

from audioforge.dsl import DSLError, compile_dsl
from audioforge.lark_parser import parse_assets


ROOT = Path(__file__).resolve().parents[1]


SRC = """
asset lark_ready {
  kind: cue
  duration: 4s
  tempo: 100bpm
  key: C major
  meter: 7 8
  pickup: 1b
  form: intro 0b for 7b, verse 7b for 14b
  repeat: verse x2
  polymeter: drums 3 4
  style: cinematic
  perform: style=cinematic expressivity=0.6
  intent {
    density: sparse
    contour: arch
    texture: smooth
    affect: tense
    avoid: clipping, noise
    repair: "make the melody less rough"
  }
  marker hit @ 2s

  motif hook {
    C4 @ 0b for 1b vel 0.8
    E4 @ 1b for 1b
  }

  layer pad : notes {
    osc: saw
    env: a=0.01s d=0.1s s=0.7 r=0.2s
    notes: slur(
      C4 @ 0b for 1b,
      D4 @ 1b for 1b), E4 @ 2b for 1b
    play hook @ 0b legato transpose +12st
    auto gain: 0s=-12db,
      1s=-6db
  }

  bus verb {
    fx: reverb(decay=1.2, mix=0.3)
  }

  master {
    peak: -1db
  }
}
"""


def test_lark_is_runtime_dependency():
    data = tomllib.loads((ROOT / "pyproject.toml").read_text())

    assert any(dep.partition(">=")[0] == "lark" for dep in data["project"]["dependencies"])


def test_compile_dsl_uses_lark_parser(monkeypatch):
    import audioforge.dsl as dsl

    called = False
    real_parse_assets = dsl.parse_assets

    def spy(src):
        nonlocal called
        called = True
        return real_parse_assets(src)

    monkeypatch.setattr(dsl, "parse_assets", spy)

    specs, diags = compile_dsl(SRC)

    assert called
    assert specs[0]["id"] == "lark_ready"
    assert isinstance(diags, list)


def test_lark_parser_reports_line_numbered_errors():
    with pytest.raises(DSLError, match=r"line 3:"):
        parse_assets("asset bad {\n  layer x : notes {\n    notes:\n  }\n}\n")


def test_intent_block_accepts_typed_and_metadata_fields():
    parsed = parse_assets(SRC)

    intent = parsed[0].intent
    assert intent["density"][0].text == "sparse"
    assert intent["contour"][0].text == "arch"
    assert intent["texture"][0].text == "smooth"
    assert intent["affect"][0].text == "tense"
    assert [t.text for t in intent["avoid"] if t.kind == "IDENT"] == [
        "clipping",
        "noise",
    ]
    assert intent["repair"][0].text == "make the melody less rough"


def test_intent_block_rejects_unknown_fields_at_parse_time():
    with pytest.raises(DSLError, match="unknown intent field 'moodish'"):
        parse_assets(
            """
asset bad_intent {
  kind: cue
  duration: 1s
  intent {
    moodish: vague
  }
  layer tone : tone { osc: sine note: C4 }
}
"""
        )


def test_lark_parser_rejects_unbalanced_blocks():
    with pytest.raises(DSLError, match=r"line 1: invalid DSL syntax"):
        parse_assets("asset bad {\n  kind: cue\n")


def test_exported_grammar_and_docs_name_lark_as_authoritative_source():
    from audioforge.grammar import dsl_ebnf, dsl_gbnf

    assert "Generated from audioforge/lark_parser.py" in dsl_ebnf()
    assert "Generated from audioforge/lark_parser.py" in dsl_gbnf()

    spec = (ROOT / "docs" / "DSL_SPEC.md").read_text()
    assert "Lark grammar" in spec
    assert "audioforge.lark_parser" in spec

    gaps = (ROOT / "docs" / "DSL_GAP_SPEC.md").read_text()
    assert "hand-rolled parser to `lark`" not in gaps
    # Lark is named as the single parser, with the published artifacts derived
    # from it (the legacy recursive-descent parser is gone — audit F9).
    assert "Single Lark grammar/parser" in gaps
    assert "audioforge.lark_parser" in gaps
