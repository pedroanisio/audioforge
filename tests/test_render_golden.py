"""Tests for the golden-audio oracle (roadmap item AF-R06).

Proves the corpus hash lock is committed (no WAVs), covers every corpus spec,
gates real drift while tolerating cross-env float drift, and that the cosmetic
vs real classifier is exercised against a closed ground truth.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from audioforge.tools import render_golden as gold

ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "tests" / "golden" / "audio.lock.json"
CORPUS = ROOT / "tests" / "golden" / "audio"


def test_lock_committed_and_no_wavs():
    assert LOCK.is_file(), "tests/golden/audio.lock.json must be committed (AF-R06)"
    lock = json.loads(LOCK.read_text())
    assert lock["specs"], "lock must cover the corpus"
    assert "numeric_env" in lock and "cosmetic_eps_dbfs" in lock
    assert not list(CORPUS.glob("*.wav")), "rendered WAVs must NOT be committed — regenerate them"


def test_lock_covers_every_corpus_spec():
    lock = json.loads(LOCK.read_text())
    assert set(lock["specs"]) == {p.stem for p in CORPUS.glob("*.af")}


def test_check_passes_on_committed_tree():
    ok, report = gold.check_lock()
    assert ok, "golden --check must pass on a clean tree:\n" + "\n".join(report)


def test_check_flags_structural_drift_regardless_of_env(tmp_path, monkeypatch):
    lock = json.loads(LOCK.read_text())
    stem = sorted(lock["specs"])[0]
    lock["specs"][stem]["frames"] = 123  # a frame-count change is structural
    lock["specs"][stem]["output_sha256"] = "0" * 64
    lock["numeric_env"] = {"numpy": "0.0.0"}  # force env mismatch
    tampered = tmp_path / "audio.lock.json"
    tampered.write_text(json.dumps(lock))
    monkeypatch.setattr(gold, "LOCK", tampered)
    ok, report = gold.check_lock()
    assert not ok and any("structural" in r for r in report)


def test_check_same_env_hash_change_is_real(tmp_path, monkeypatch):
    # keep the real numeric_env (same env) but tamper only the hash -> real drift
    lock = json.loads(LOCK.read_text())
    stem = sorted(lock["specs"])[0]
    lock["specs"][stem]["output_sha256"] = "0" * 64
    tampered = tmp_path / "audio.lock.json"
    tampered.write_text(json.dumps(lock))
    monkeypatch.setattr(gold, "LOCK", tampered)
    ok, report = gold.check_lock()
    assert not ok, "same-env hash mismatch (frames unchanged) must be a real failure"


def test_check_cross_env_hash_change_is_advisory(tmp_path, monkeypatch):
    lock = json.loads(LOCK.read_text())
    stem = sorted(lock["specs"])[0]
    lock["specs"][stem]["output_sha256"] = "0" * 64  # hash differs, frames intact
    lock["numeric_env"] = {"numpy": "0.0.0", "platform": "other"}  # env mismatch
    tampered = tmp_path / "audio.lock.json"
    tampered.write_text(json.dumps(lock))
    monkeypatch.setattr(gold, "LOCK", tampered)
    ok, report = gold.check_lock()  # not strict
    assert ok and any("cosmetic" in r for r in report), report
    ok_strict, _ = gold.check_lock(strict=True)
    assert not ok_strict, "--strict must fail even cross-env"


def test_classify_drift_cosmetic_vs_real():
    ref = np.linspace(-0.5, 0.5, 4800)
    sub = ref + gold.COSMETIC_EPS_LINEAR * 0.1  # every sample below ε
    v = gold.classify_drift(ref, sub)
    assert v["verdict"] == "cosmetic" and v["first_index"] == -1

    sup = ref.copy()
    sup[100] += gold.COSMETIC_EPS_LINEAR * 100  # one sample well above ε
    v = gold.classify_drift(ref, sup)
    assert v["verdict"] == "real" and v["first_index"] == 100

    # a length change is structural
    assert gold.classify_drift(ref, ref[:-1])["verdict"] == "real"


def test_update_is_deterministic():
    assert gold.render_lock_bytes() == gold.render_lock_bytes()


def test_main_check_passes_on_committed_tree():
    assert gold.main(["--check"]) == 0


def test_main_update_then_check_roundtrip(tmp_path, monkeypatch):
    lock = tmp_path / "audio.lock.json"
    monkeypatch.setattr(gold, "LOCK", lock)
    assert gold.main(["--update"]) == 0
    assert lock.is_file()
    assert gold.main(["--check"]) == 0  # freshly pinned in this env -> passes


def test_main_check_nonzero_on_real_drift(tmp_path, monkeypatch):
    lock = tmp_path / "audio.lock.json"
    monkeypatch.setattr(gold, "LOCK", lock)
    gold.main(["--update"])
    data = json.loads(lock.read_text())
    stem = sorted(data["specs"])[0]
    data["specs"][stem]["output_sha256"] = "0" * 64  # same env, hash mismatch -> real
    lock.write_text(json.dumps(data))
    assert gold.main(["--check"]) == 1
