"""Drift-map Finding #4 — the CLI parser and the docs CLI block must agree.

Every subcommand registered in `audioforge/cli.py` must be documented in the
`## CLI` block of `docs/DSL_SPEC.md`. The static report flagged `score` (and,
on inspection, `repair`) as present in the parser but missing from the docs.
This test fails the moment a new command is added to the parser without a
matching docs line.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "audioforge" / "cli.py"
SPEC = ROOT / "docs" / "DSL_SPEC.md"

# Commands intentionally excluded from the user-facing CLI reference, if any.
_DOC_EXEMPT: set[str] = set()


def _parser_commands() -> set[str]:
    """The authoritative command registry: every `sub.add_parser("name")`."""
    src = CLI.read_text()
    return set(re.findall(r'add_parser\(\s*"([a-z0-9][a-z0-9-]*)"', src))


def _documented_commands() -> set[str]:
    """Commands shown in the docs `## CLI` fenced block as `audioforge <cmd>`."""
    text = SPEC.read_text()
    m = re.search(r"##\s*\d+\.\s*CLI\s*\n+```(.*?)```", text, re.DOTALL)
    assert m, "could not find the '## CLI' fenced command block in DSL_SPEC.md"
    block = m.group(1)
    return set(re.findall(r"^audioforge\s+([a-z0-9-]+)", block, re.MULTILINE))


def test_parser_has_commands():
    cmds = _parser_commands()
    # sanity: the parser really did register a meaningful command set
    assert {"validate", "compile", "render", "score", "repair"} <= cmds


def test_every_cli_command_is_documented():
    parser = _parser_commands()
    documented = _documented_commands()
    missing = sorted((parser - documented) - _DOC_EXEMPT)
    assert not missing, (
        f"CLI commands present in cli.py but absent from docs/DSL_SPEC.md "
        f"'## CLI' block (Finding #4): {missing}"
    )


def test_docs_do_not_invent_commands():
    """The docs must not list commands the parser does not implement."""
    parser = _parser_commands()
    documented = _documented_commands()
    phantom = sorted(documented - parser)
    assert not phantom, (
        f"docs/DSL_SPEC.md documents commands the CLI does not implement: "
        f"{phantom}"
    )


if __name__ == "__main__":
    test_parser_has_commands()
    test_every_cli_command_is_documented()
    test_docs_do_not_invent_commands()
    print("PASS  cli.py commands and docs CLI block agree")
