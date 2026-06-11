import sys
import re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from audioforge import DSL_VERSION, ENGINE_VERSION  # noqa: E402
from audioforge.grammar import dsl_ebnf, dsl_gbnf  # noqa: E402


ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "docs" / "DSL_SPEC.md"
README = ROOT / "README.md"
RELEASE_NOTES = ROOT / "docs" / "RELEASE_NOTES.md"


def _documented_versions(text: str) -> tuple[str, str]:
    match = re.search(r"\*\*DSL ([^ ]+) · Engine ([^*]+)\*\*", text)
    assert match, "expected '**DSL X · Engine Y**' version banner"
    return match.group(1), match.group(2)


def test_dsl_spec_review_regressions_stay_fixed():
    text = SPEC.read_text()
    assert "same engine version" in text
    assert "Same DSL text -> same IR" not in text
    assert "eight types" not in text
    assert "where `PITCH` is a note, frequency, or chord symbol" in text
    assert ". where `PITCH`" not in text
    assert "min7b5/m7b5" not in text
    assert "§7a" not in text
    assert "§11a" not in text
    assert "## 7a." not in text
    assert "## 11a." not in text
    assert "metadata for agents" not in text
    assert "silently skipped" not in text
    assert "Known gap" not in text
    for stale in ("Tier N", "Tier S", "architecture plan"):
        assert stale not in text
    assert re.search(r"\bP3'?s?\b", text) is None
    for row in ("| `deg` |", "| `m` |"):
        assert row in text
    for directive in ("style", "perform", "ensemble", "voicing", "space"):
        assert f"| `{directive}:` |" in text


def test_exported_grammar_lists_agent_directives_and_layer_kinds():
    ebnf = dsl_ebnf()
    gbnf = dsl_gbnf()
    assert "asset_item       = smart_directive" in ebnf
    assert "smart-directive" in gbnf
    for directive in ("style", "perform", "ensemble", "voicing", "space"):
        assert directive in ebnf
        assert directive in gbnf
    for kind in ("audio", "instrument", "foley"):
        assert f'"{kind}"' in ebnf
        assert f'"{kind}"' in gbnf


def test_dsl_docs_are_consolidated_to_reference_and_gap_spec():
    docs = {p.name for p in (ROOT / "docs").glob("*.md")}
    assert "DSL_SPEC.md" in docs
    assert "DSL_GAP_SPEC.md" in docs
    for stale in (
        "DSL_SPEC_old.md",
        "PROPOSAL_north_star_studio_dsl_ir.md",
        "PROPOSAL_smart_music_dsl.md",
        "DECISION_dsl_language_constructs.md",
        "SPEC_smart_dsl_universal_music_architecture.md",
    ):
        assert stale not in docs


def test_documented_versions_match_runtime_source_of_truth():
    spec_dsl, spec_engine = _documented_versions(SPEC.read_text())
    assert spec_dsl == DSL_VERSION
    assert spec_engine == ENGINE_VERSION

    readme = README.read_text()
    assert f"Engine {ENGINE_VERSION} · DSL {DSL_VERSION}" in readme


def test_dsl_version_changes_are_recorded_in_release_notes():
    notes = RELEASE_NOTES.read_text()
    assert f"DSL {DSL_VERSION}" in notes
    assert f"Engine {ENGINE_VERSION}" in notes
    assert "migration" in notes.lower()
