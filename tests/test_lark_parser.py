import tomllib
from pathlib import Path

import pytest

from audioforge.dsl import DSLError, Parser, compile_dsl, tokenize


ROOT = Path(__file__).resolve().parents[1]
AF_CORPUS = (
    sorted((ROOT / "static" / "fixtures").glob("*.af"))
    + sorted((ROOT / "static" / "samples").glob("*.af"))
)


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


def test_lark_parser_matches_legacy_ast_shape():
    from audioforge.lark_parser import parse_assets

    legacy = Parser(tokenize(SRC)).parse()
    parsed = parse_assets(SRC)

    assert parsed == legacy


def test_lark_tokenizer_matches_legacy_token_stream():
    from audioforge.lark_parser import lark_tokenize

    legacy = [(t.kind, t.text, t.line, t.value, t.unit) for t in tokenize(SRC)]
    parsed = [(t.kind, t.text, t.line, t.value, t.unit) for t in lark_tokenize(SRC)]

    assert parsed == legacy


@pytest.mark.parametrize("path", AF_CORPUS, ids=lambda p: str(p.relative_to(ROOT)))
def test_lark_parser_matches_legacy_ast_for_checked_in_af_corpus(path):
    from audioforge.lark_parser import parse_assets

    src = path.read_text()

    try:
        legacy = Parser(tokenize(src)).parse()
    except DSLError as exc:
        with pytest.raises(DSLError) as parsed:
            parse_assets(src)
        assert str(parsed.value) == str(exc)
    else:
        assert parse_assets(src) == legacy


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


def test_compile_dsl_does_not_use_legacy_regex_tokenizer(monkeypatch):
    import audioforge.dsl as dsl

    def fail_tokenize(_src):
        raise AssertionError("legacy tokenizer should not be used by compile_dsl")

    monkeypatch.setattr(dsl, "tokenize", fail_tokenize)

    specs, _diags = compile_dsl(SRC)

    assert specs[0]["id"] == "lark_ready"


def test_lark_parser_reports_line_numbered_errors():
    from audioforge.lark_parser import parse_assets
    from audioforge.dsl import DSLError

    with pytest.raises(DSLError, match=r"line 3:"):
        parse_assets("asset bad {\n  layer x : notes {\n    notes:\n  }\n}\n")


def test_intent_block_accepts_typed_and_metadata_fields():
    from audioforge.lark_parser import parse_assets

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
    from audioforge.lark_parser import parse_assets
    from audioforge.dsl import DSLError

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


def test_lark_parser_rejects_unbalanced_blocks_before_legacy_parse():
    from audioforge.lark_parser import parse_assets
    from audioforge.dsl import DSLError

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
    assert "Lark-backed syntax gate" in gaps
