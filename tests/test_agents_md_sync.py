"""Gate AGENTS.md's CLI-verb list against cli.py (roadmap item AF-R03).

AGENTS.md is a hand-maintained mirror of the live CLI surface. This test makes
the mirror honest: the verbs documented in AGENTS.md's `<!-- cli-verbs -->` table
must exactly equal the subparsers registered in cli.py — so a verb cannot be
added or removed without this file failing.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
AGENTS = REPO / "AGENTS.md"
CLI = REPO / "audioforge" / "cli.py"


def _cli_verbs() -> set[str]:
    return set(re.findall(r'add_parser\(\s*"([a-z0-9][a-z0-9_-]*)"', CLI.read_text(encoding="utf-8")))


def _documented_verbs() -> set[str]:
    text = AGENTS.read_text(encoding="utf-8")
    block = re.search(r"<!-- BEGIN cli-verbs -->(.*?)<!-- END cli-verbs -->", text, re.S)
    assert block, "AGENTS.md must delimit its CLI-verb table with <!-- BEGIN/END cli-verbs -->"
    return set(re.findall(r"^\|\s*`([a-z0-9][a-z0-9_-]*)`\s*\|", block.group(1), re.M))


def test_agents_md_exists_with_disclaimer_frontmatter():
    assert AGENTS.is_file(), "AGENTS.md must exist (AF-R03; CLAUDE.md points to it)"
    head = AGENTS.read_text(encoding="utf-8").splitlines()[:12]
    assert head[0] == "---" and any("disclaimer:" in ln for ln in head), (
        "AGENTS.md must carry the Rule-5 disclaimer frontmatter"
    )


def test_every_cli_verb_is_documented():
    missing = _cli_verbs() - _documented_verbs()
    assert not missing, f"cli.py verbs undocumented in AGENTS.md: {sorted(missing)}"


def test_no_phantom_verbs_documented():
    phantom = _documented_verbs() - _cli_verbs()
    assert not phantom, f"AGENTS.md documents verbs that do not exist in cli.py: {sorted(phantom)}"


def test_verb_sets_are_exactly_equal():
    assert _documented_verbs() == _cli_verbs()


def test_claude_md_pointer_now_resolves():
    # CLAUDE.md references AGENTS.md as the programmatic reference; it must exist.
    claude = (REPO / "CLAUDE.md").read_text(encoding="utf-8")
    assert "AGENTS.md" in claude and AGENTS.is_file()
