"""Shared fixtures.

Every test runs against a real ``.shadowmd`` repo created in a tmp directory, so
the atomic-IO, locking and journal paths are exercised for real (no mocks of the
filesystem). Tests are deterministic and isolated: each gets a fresh tmp tree.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from shadowmd.repo import ShadowRepository


@pytest.fixture()
def workdir(tmp_path: Path) -> Path:
    return tmp_path


@pytest.fixture()
def repo(workdir: Path) -> ShadowRepository:
    return ShadowRepository.init(workdir)


@pytest.fixture()
def write_file(workdir: Path):
    def _write(name: str, content: str) -> str:
        path = workdir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return name

    return _write


@pytest.fixture()
def injected(repo: ShadowRepository, write_file):
    """A repo with one injected file ``article.md`` and an initial snapshot."""
    write_file("article.md", "# Title\n\nIntro paragraph.\n")
    repo.inject("article.md")
    return repo
