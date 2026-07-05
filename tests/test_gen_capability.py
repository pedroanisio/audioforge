"""Tests for the capability-manifest generator + drift gate (roadmap item AF-R07).

Proves docs/capability-manifest.json and docs/DIAGNOSTIC_CODES.md are generated
artifacts (byte-parity + drift gate), that every diagnostic code is documented,
and that per-capability status is DERIVED by predicate, not hand-labelled.
"""
from __future__ import annotations

import json
from pathlib import Path

from audioforge.capabilities import capability_manifest
from audioforge.schema import FX_TYPES, NATIVE_FX_TYPES, NATIVE_OSC_SHAPES, OSC_SHAPES
from audioforge.tools import gen_capability as gen

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "docs" / "capability-manifest.json"
CODES_DOC = ROOT / "docs" / "DIAGNOSTIC_CODES.md"


def test_manifest_committed_and_byte_identical():
    assert MANIFEST.is_file(), "docs/capability-manifest.json must be committed (AF-R07)"
    assert MANIFEST.read_text(encoding="utf-8") == gen.render_manifest()


def test_codes_doc_committed_and_byte_identical():
    assert CODES_DOC.is_file()
    assert CODES_DOC.read_text(encoding="utf-8") == gen.render_codes_doc()


def test_manifest_parses_to_runtime_source():
    assert json.loads(gen.render_manifest()) == capability_manifest()


def test_check_passes_on_committed_tree():
    ok, diff = gen.check()
    assert ok, f"manifest --check must pass on a clean tree:\n{diff}"


def test_check_fails_on_manifest_drift(tmp_path, monkeypatch):
    stale = tmp_path / "capability-manifest.json"
    stale.write_text("{}\n", encoding="utf-8")
    monkeypatch.setattr(gen, "MANIFEST", stale)
    ok, diff = gen.check()
    assert not ok and diff


def test_every_diagnostic_code_is_documented():
    doc = CODES_DOC.read_text(encoding="utf-8")
    for code in capability_manifest()["diagnostic_codes"]:
        assert f"`{code}`" in doc, f"diagnostic code {code!r} is undocumented in DIAGNOSTIC_CODES.md"


def test_status_is_derived_by_predicate_not_hardcoded():
    statuses = capability_manifest()["statuses"]["by_capability"]
    osc = statuses["oscillators"]
    fx = statuses["fx_types"]
    # every native voice is experimental; every pure-Python voice is stable
    for n in NATIVE_OSC_SHAPES:
        assert osc[n] == "experimental", n
    for n in OSC_SHAPES - NATIVE_OSC_SHAPES:
        assert osc[n] == "stable", n
    for n in NATIVE_FX_TYPES:
        assert fx[n] == "experimental", n
    for n in FX_TYPES - NATIVE_FX_TYPES:
        assert fx[n] == "stable", n
    # the predicate is recorded in-band
    assert "experimental" in capability_manifest()["statuses"]["predicate"]


def test_status_keys_cover_the_full_registries():
    osc = capability_manifest()["statuses"]["by_capability"]["oscillators"]
    assert set(osc) == set(OSC_SHAPES) | set(NATIVE_OSC_SHAPES)


def test_write_is_byte_stable(tmp_path, monkeypatch):
    m = tmp_path / "capability-manifest.json"
    d = tmp_path / "DIAGNOSTIC_CODES.md"
    monkeypatch.setattr(gen, "MANIFEST", m)
    monkeypatch.setattr(gen, "CODES_DOC", d)
    gen.write()
    before_m, before_d = m.read_text(), d.read_text()
    gen.write()
    assert m.read_text() == before_m and d.read_text() == before_d


def test_main_check_zero_on_committed_tree():
    assert gen.main(["--check"]) == 0


def test_main_check_nonzero_on_drift(tmp_path, monkeypatch, capsys):
    stale = tmp_path / "capability-manifest.json"
    stale.write_text("{}\n", encoding="utf-8")
    monkeypatch.setattr(gen, "MANIFEST", stale)
    assert gen.main(["--check"]) == 1
    assert "STALE" in capsys.readouterr().err


def test_main_write_regenerates_both(tmp_path, monkeypatch):
    m = tmp_path / "capability-manifest.json"
    d = tmp_path / "DIAGNOSTIC_CODES.md"
    monkeypatch.setattr(gen, "MANIFEST", m)
    monkeypatch.setattr(gen, "CODES_DOC", d)
    assert gen.main(["--write"]) == 0
    assert m.is_file() and d.is_file()
