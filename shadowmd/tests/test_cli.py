from __future__ import annotations

import sys
from pathlib import Path

import pytest

from shadowmd.cli import main


@pytest.fixture()
def project(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert main(["init"]) == 0
    (tmp_path / "article.md").write_text("# Title\n\nIntro.\n", encoding="utf-8")
    return tmp_path


def test_init_and_inject_and_status(project, capfd):
    assert main(["inject", "article.md"]) == 0
    assert main(["status"]) == 0
    out = capfd.readouterr().out
    assert "article.md" in out
    assert "clean" in out


def test_append_log_timeline(project, capfd):
    main(["inject", "article.md"])
    capfd.readouterr()
    assert main(["append", "article.md", "More."]) == 0
    assert main(["log"]) == 0
    log = capfd.readouterr().out
    assert "inject" in log
    assert main(["timeline", "article.md"]) == 0
    assert "article.md" in capfd.readouterr().out


def test_diff_against_index_and_violation_exit_code(project, capfd):
    main(["inject", "article.md"])
    capfd.readouterr()
    # external tamper
    target = Path(project) / "article.md"
    target.chmod(0o644)
    target.write_text("tampered\n")
    # diff --against-index shows the drift
    assert main(["diff", "article.md", "--against-index"]) == 0
    assert "tampered" in capfd.readouterr().out
    # a mutation now fails with the integrity exit code
    assert main(["append", "article.md", "x"]) == 2


def test_repair_and_absorb_cli(project, capfd):
    main(["inject", "article.md"])
    target = Path(project) / "article.md"
    target.chmod(0o644)
    target.write_text("tampered\n")
    assert main(["repair", "article.md", "--restore-projection"]) == 0
    assert main(["verify-projection", "article.md"]) == 0

    target.chmod(0o644)
    target.write_text("keep this\n")
    assert main(["absorb", "article.md", "-m", "manual"]) == 0
    assert main(["verify-projection", "article.md"]) == 0


def test_restore_cli(project, capfd):
    main(["inject", "article.md"])
    main(["snapshot", "-m", "base"])
    capfd.readouterr()
    # capture base snapshot id from log
    main(["log"])
    base_line = capfd.readouterr().out.strip().splitlines()[-1]
    base_id = base_line.split()[1]

    main(["append", "article.md", "CHANGE"])
    assert main(["restore", "article.md", "--snapshot", base_id]) == 0
    assert "CHANGE" not in (Path(project) / "article.md").read_text()


def test_mv_and_rm_cli(project, capfd):
    main(["inject", "article.md"])
    assert main(["mv", "article.md", "essay.md"]) == 0
    assert (Path(project) / "essay.md").exists()
    assert not (Path(project) / "article.md").exists()
    assert main(["rm", "essay.md"]) == 0
    assert not (Path(project) / "essay.md").exists()


def test_transaction_cli(project, capfd):
    main(["inject", "article.md"])
    capfd.readouterr()
    main(["log"])
    before = len(capfd.readouterr().out.strip().splitlines())
    main(["begin", "-m", "group"])
    main(["append", "article.md", "a"])
    main(["append", "article.md", "b"])
    main(["commit"])
    capfd.readouterr()
    main(["log"])
    after = len(capfd.readouterr().out.strip().splitlines())
    assert after == before + 1  # one snapshot for the group


def test_edit_cli(project, capfd, monkeypatch, tmp_path):
    editor = tmp_path / "fake_editor.py"
    editor.write_text(
        "import sys\n"
        "open(sys.argv[1], 'a', encoding='utf-8').write('EDITED\\n')\n"
    )
    monkeypatch.setenv("SHADOWMD_EDITOR", f"{sys.executable} {editor}")
    main(["inject", "article.md"])
    assert main(["edit", "article.md"]) == 0
    assert "EDITED" in (Path(project) / "article.md").read_text()


def test_fsck_and_gc_cli(project, capfd):
    main(["inject", "article.md"])
    capfd.readouterr()
    assert main(["fsck"]) == 0
    assert "OK" in capfd.readouterr().out
    assert main(["gc", "--dry-run"]) == 0


def test_apply_cli(project, capfd, tmp_path):
    main(["inject", "article.md"])
    from shadowmd import diff as diffmod

    old = (Path(project) / "article.md").read_bytes()
    new = old + b"patched line\n"
    patch = tmp_path / "p.diff"
    patch.write_text(diffmod.unified(old, new))
    assert main(["apply", "article.md", str(patch)]) == 0
    assert b"patched line" in (Path(project) / "article.md").read_bytes()


def test_cat_cli(project, capfd):
    main(["inject", "article.md"])
    capfd.readouterr()
    main(["log"])
    sid = capfd.readouterr().out.strip().splitlines()[-1].split()[1]
    assert main(["cat", "article.md", "--snapshot", sid]) == 0
    assert "Title" in capfd.readouterr().out


def test_error_exit_code_for_unknown_repo(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    # no init here -> discovery fails -> generic error exit
    assert main(["status"]) == 1


def test_unlock_stale_cli(project, capfd):
    main(["inject", "article.md"])
    assert main(["unlock", "--stale"]) == 0
