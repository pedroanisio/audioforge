"""Prebuilt cue library: registry, parameters, DSL, rendering contract."""
import json
import wave

import numpy as np
import pytest

from audioforge import AudioForge
from audioforge.cues import (CATEGORIES, KINDS, LOUDNESS, CueError, cue_dsl, get_cue,
                             list_cues, normalize_key, parse_params, render_cue,
                             resolve_params, sidecar_path)


def _read(path):
    with wave.open(str(path)) as w:
        n, sw, sr = w.getnframes(), w.getsampwidth(), w.getframerate()
        raw = w.readframes(n)
    if sw == 3:
        b = np.frombuffer(raw, np.uint8).reshape(-1, 3)
        i = b[:, 0].astype(np.int32) | (b[:, 1].astype(np.int32) << 8) | (b[:, 2].astype(np.int32) << 16)
        x = np.where(i >= 1 << 23, i - (1 << 24), i) / 8388608.0
    else:
        x = np.frombuffer(raw, "<i2") / 32768.0
    return x.reshape(-1, 2), sr


def test_registry_shape():
    cues = list_cues()
    assert len(cues) >= 30
    assert len({c.id for c in cues}) == len(cues)
    for c in cues:
        assert c.kind in KINDS and c.category in CATEGORIES
        assert c.id.startswith(c.category + "/")
        assert {"duration", "seed"} <= set(c.param_map)
        assert c.title and c.description
    assert {c.category for c in cues} == set(CATEGORIES)
    assert list_cues(category="bed") and all(c.kind == "music" for c in list_cues(category="bed"))
    assert all(c.kind == "sound-effect" for c in list_cues(category="transition"))


def test_unknown_cue_suggests_neighbours():
    with pytest.raises(CueError, match="did you mean bed/documentary-airy"):
        get_cue("bed/documentary")


@pytest.mark.parametrize("text,key", [("A minor", "A minor"), ("am", "A minor"),
                                      ("f# major", "F# major"), ("Eb", "Eb major"),
                                      ("C min", "C minor")])
def test_normalize_key(text, key):
    assert normalize_key(text) == key


def test_parse_and_validate_params():
    assert parse_params("duration=12, bpm=90; key='F# minor'") == {
        "duration": "12", "bpm": "90", "key": "F# minor"}
    cue = get_cue("bed/documentary-airy")
    r = resolve_params(cue, "duration=12 key=am")
    assert r["duration"] == 12.0 and r["key"] == "A minor" and r["bpm"] == 96.0
    with pytest.raises(CueError, match="unknown parameter"):
        resolve_params(cue, "tempo=90")
    with pytest.raises(CueError, match="above the maximum"):
        resolve_params(cue, "intensity=2")
    with pytest.raises(CueError, match="not a valid float"):
        resolve_params(cue, "bpm=fast")
    with pytest.raises(CueError, match="name=value"):
        parse_params("duration")
    with pytest.raises(CueError, match="not one of"):
        resolve_params(get_cue("transition/whoosh"), "direction=left")


def test_every_cue_compiles_across_its_ranges():
    forge = AudioForge()
    for c in list_cues():
        dp = c.param_map["duration"]
        variants = [{}, {"duration": dp.min}, {"duration": dp.max}]
        if "intensity" in c.param_map:
            variants += [{"intensity": 0}, {"intensity": 1}]
        if "key" in c.param_map:
            variants.append({"key": "F# minor"})
        for v in variants:
            res = forge.compile(cue_dsl(c.id, v))
            assert res.ok, (c.id, v, [d.message for d in res.diagnostics])
            assert not [d for d in res.diagnostics if d.severity == "error"]


def test_dsl_is_deterministic_and_seed_is_a_performance_seed():
    a = cue_dsl("transition/glitch", "seed=3")
    assert a == cue_dsl("transition/glitch", "seed=3")
    assert a != cue_dsl("transition/glitch", "seed=4")
    assert "seed: 3" in a


# one representative per category, rendered short
CASES = [("bed/documentary-airy", "duration=6.25"), ("sting/logo", ""),
         ("transition/whoosh", "duration=0.7"), ("ui/click", ""),
         ("foley/paper-tap", ""), ("ambience/room-tone", "duration=4")]


@pytest.mark.parametrize("cue_id,params", CASES)
def test_render_meets_duration_and_loudness_contract(tmp_path, cue_id, params):
    from audioforge.dynamics import _true_peak_per_sample
    from audioforge.loudness import integrated_lufs
    out = tmp_path / "cue.wav"
    info = render_cue(cue_id, params, out)
    x, sr = _read(out)
    assert sr == 48000 and x.shape[0] == round(info["params"]["duration"] * sr)
    assert info["sha256"] and sidecar_path(out).is_file()
    side = json.loads(sidecar_path(out).read_text())
    assert side["cue"] == cue_id and side["sha256"] == info["sha256"]
    want = LOUDNESS[get_cue(cue_id).category]
    tp = 20 * np.log10(_true_peak_per_sample(x).max())
    assert tp <= want["peak"] + 0.1
    if "lufs" in want:
        assert abs(integrated_lufs(x, sr) - want["lufs"]) < 1.5
    else:
        assert tp > want["peak"] - 0.5                      # peak-normalized


def test_render_is_byte_reproducible_and_seed_changes_take(tmp_path):
    a = render_cue("bed/lofi-chill", "duration=5", tmp_path / "a.wav")
    b = render_cue("bed/lofi-chill", "duration=5", tmp_path / "b.wav")
    c = render_cue("bed/lofi-chill", "duration=5 seed=9", tmp_path / "c.wav")
    assert a["sha256"] == b["sha256"]
    assert c["sha256"] != a["sha256"]


def test_render_16_bit(tmp_path):
    info = render_cue("ui/pop", "", tmp_path / "p.wav", sample_rate=44100, bit_depth=16)
    x, sr = _read(tmp_path / "p.wav")
    assert sr == 44100 and info["bit_depth"] == 16 and x.shape[0] == round(0.1 * 44100)


def test_every_cue_is_in_the_catalog_doc():
    from pathlib import Path
    doc = (Path(__file__).resolve().parents[1] / "docs" / "CUES.md").read_text()
    missing = [c.id for c in list_cues() if f"`{c.id}`" not in doc]
    assert not missing, f"docs/CUES.md catalog lacks: {missing}"
