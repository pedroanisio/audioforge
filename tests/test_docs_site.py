"""Docs-site + ADR gates (roadmap items AF-R11 and AF-R12)."""
from __future__ import annotations

import re
from pathlib import Path

from audioforge.tools import gen_docs

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
ADR = DOCS / "adr"
MKDOCS = ROOT / "mkdocs.yml"
MAKEFILE = ROOT / "Makefile"


# --- AF-R11: docs site -----------------------------------------------------
def test_mkdocs_config_exists():
    assert MKDOCS.is_file(), "mkdocs.yml must exist (AF-R11)"


def test_generated_pages_are_byte_identical():
    assert (DOCS / "reference.md").read_text(encoding="utf-8") == gen_docs.render_reference()
    assert (DOCS / "capabilities.md").read_text(encoding="utf-8") == gen_docs.render_capabilities()


def test_gen_docs_check_passes_on_committed_tree():
    ok, report = gen_docs.check()
    assert ok, "docs-gen --check must pass on a clean tree:\n" + "\n".join(report)


def test_gen_docs_check_fails_on_stale_page(tmp_path, monkeypatch):
    stale = tmp_path / "reference.md"
    stale.write_text("stale\n", encoding="utf-8")
    monkeypatch.setattr(gen_docs, "REFERENCE", stale)
    ok, _ = gen_docs.check()
    assert not ok


def test_every_nav_page_exists():
    pages = gen_docs._nav_pages()
    assert len(pages) >= 10
    for page in pages:
        assert (DOCS / page).is_file(), f"mkdocs nav references missing page: docs/{page}"


def test_make_check_includes_docs_gen_check():
    check_line = next(ln for ln in MAKEFILE.read_text().splitlines() if re.match(r"^check\s*:", ln))
    assert "docs-gen-check" in check_line


def test_main_check_zero_on_committed_tree():
    assert gen_docs.main(["--check"]) == 0


def test_main_check_nonzero_on_drift(tmp_path, monkeypatch, capsys):
    stale = tmp_path / "reference.md"
    stale.write_text("stale\n", encoding="utf-8")
    monkeypatch.setattr(gen_docs, "REFERENCE", stale)
    assert gen_docs.main(["--check"]) == 1
    assert "STALE" in capsys.readouterr().err


def test_main_write_regenerates(tmp_path, monkeypatch):
    ref, cap = tmp_path / "reference.md", tmp_path / "capabilities.md"
    monkeypatch.setattr(gen_docs, "REFERENCE", ref)
    monkeypatch.setattr(gen_docs, "CAPABILITIES", cap)
    assert gen_docs.main(["--write"]) == 0
    assert ref.is_file() and cap.is_file()


# --- AF-R12: ADRs ----------------------------------------------------------
def test_adr_dir_has_template_and_records():
    assert (ADR / "adr-template.md").is_file(), "docs/adr/adr-template.md must exist (AF-R12)"
    records = [p for p in ADR.glob("[0-9]*.md")]
    assert len(records) >= 4, f"expected >=4 backfilled ADRs, found {len(records)}"


def test_each_adr_has_required_sections_and_frontmatter():
    for adr in ADR.glob("[0-9]*.md"):
        text = adr.read_text(encoding="utf-8")
        assert text.startswith("---") and "disclaimer:" in text[:400], f"{adr.name}: no frontmatter"
        for section in ("## Context", "## Decision", "## Consequences"):
            assert section in text, f"{adr.name}: missing '{section}'"
        assert "**Status:**" in text, f"{adr.name}: missing Status"


def test_at_least_one_adr_is_referenced_from_code():
    # ADR-0005 governs the IR source-of-truth; ir_schema.py cites it.
    assert "ADR-0005" in (ROOT / "audioforge" / "ir_schema.py").read_text(encoding="utf-8")


def test_adoption_rule_is_documented():
    assert "docs/adr/" in (ROOT / "AGENTS.md").read_text(encoding="utf-8")
