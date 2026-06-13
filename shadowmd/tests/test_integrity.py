from __future__ import annotations

import pytest

from shadowmd.errors import ProjectionViolation


def _force_external_write(workdir, name, content):
    """Simulate a careless direct edit despite the 0444 bit."""
    target = workdir / name
    target.chmod(0o644)
    target.write_text(content, encoding="utf-8")


def test_external_change_is_detected(injected, workdir):
    _force_external_write(workdir, "article.md", "tampered\n")
    with pytest.raises(ProjectionViolation) as exc:
        injected.verify("article.md")
    assert exc.value.path == "article.md"
    assert exc.value.expected != exc.value.actual


def test_mutation_blocked_on_drift(injected, workdir):
    _force_external_write(workdir, "article.md", "tampered\n")
    with pytest.raises(ProjectionViolation):
        injected.append("article.md", "more")


def test_repair_discards_external_change(injected, workdir):
    canonical = injected.current_content("article.md")
    _force_external_write(workdir, "article.md", "tampered\n")
    injected.repair("article.md")
    assert (workdir / "article.md").read_bytes() == canonical
    injected.verify("article.md")  # no longer raises


def test_absorb_keeps_external_change(injected, workdir):
    _force_external_write(workdir, "article.md", "manual emergency edit\n")
    changed = injected.absorb("article.md", "emergency")
    assert changed
    injected.verify("article.md")
    assert (workdir / "article.md").read_text() == "manual emergency edit\n"
    # absorption is journaled distinctly
    ops = [e["operation"] for e in injected.journal.read_all()]
    assert "absorb" in ops


def test_absorb_noop_when_no_drift(injected):
    assert injected.absorb("article.md", "noop") is False
