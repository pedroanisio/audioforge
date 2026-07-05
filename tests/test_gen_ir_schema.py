"""Tests for the IR-schema generator + drift gate (roadmap item AF-R05).

Proves docs/ir.schema.json is a GENERATED artifact, not a hand-authored one:
the generator reproduces it byte-for-byte from ``ir_json_schema()``; ``--check``
passes when in sync and fails (non-zero, with a unified diff) on drift; and the
serializer is byte-stable/idempotent. These are the gates AF-R05's DoD requires.
"""
from __future__ import annotations

import json
from pathlib import Path

from audioforge.ir_schema import ir_json_schema
from audioforge.tools import gen_ir_schema as gen

ROOT = Path(__file__).resolve().parents[1]
PUBLISHED = ROOT / "docs" / "ir.schema.json"


def test_render_matches_published_schema_byte_for_byte():
    # The committed artifact IS the generator's canonical output.
    assert gen.render_schema() == PUBLISHED.read_text(encoding="utf-8")


def test_render_parses_to_the_runtime_source():
    assert json.loads(gen.render_schema()) == ir_json_schema()


def test_render_is_idempotent_and_key_sorted():
    once = gen.render_schema()
    assert gen.render_schema() == once  # deterministic across calls
    keys = list(json.loads(once).keys())
    assert keys == sorted(keys)  # sort_keys=True -> insertion-order independent


def test_write_is_byte_stable(tmp_path):
    p = tmp_path / "ir.schema.json"
    gen.write(p)
    before = p.read_text(encoding="utf-8")
    gen.write(p)
    assert p.read_text(encoding="utf-8") == before == gen.render_schema()


def test_check_passes_when_in_sync(tmp_path):
    p = tmp_path / "ir.schema.json"
    gen.write(p)
    ok, diff = gen.check(p)
    assert ok is True
    assert diff == ""


def test_check_fails_with_unified_diff_on_drift(tmp_path):
    p = tmp_path / "ir.schema.json"
    gen.write(p)
    # a hand-edit that drifts the artifact away from the runtime source
    p.write_text(gen.render_schema().replace('"integer"', '"string"', 1), encoding="utf-8")
    ok, diff = gen.check(p)
    assert ok is False
    assert "---" in diff and "+++" in diff  # a real unified diff


def test_check_fails_when_file_absent(tmp_path):
    ok, diff = gen.check(tmp_path / "missing.json")
    assert ok is False


def test_main_check_is_zero_on_the_committed_tree():
    # docs/ir.schema.json must be in sync with ir_json_schema() on a clean tree.
    assert gen.main(["--check"]) == 0


def test_main_check_is_nonzero_and_loud_on_drift(tmp_path, monkeypatch, capsys):
    drifted = tmp_path / "ir.schema.json"
    drifted.write_text("{}\n", encoding="utf-8")
    monkeypatch.setattr(gen, "PUBLISHED_SCHEMA", drifted)
    rc = gen.main(["--check"])
    assert rc == 1
    assert "STALE" in capsys.readouterr().err


def test_main_write_regenerates_the_target(tmp_path, monkeypatch):
    target = tmp_path / "ir.schema.json"
    monkeypatch.setattr(gen, "PUBLISHED_SCHEMA", target)
    assert gen.main(["--write"]) == 0
    assert target.read_text(encoding="utf-8") == gen.render_schema()


def test_main_defaults_to_write(tmp_path, monkeypatch):
    target = tmp_path / "ir.schema.json"
    monkeypatch.setattr(gen, "PUBLISHED_SCHEMA", target)
    assert gen.main([]) == 0
    assert target.exists()
