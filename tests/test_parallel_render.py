"""Layer-parallel rendering must preserve the byte-identical contract.

The engine's core guarantee is reproducibility: same spec -> same audio bytes.
Rendering layers across threads is only legitimate if it changes nothing about
the output. These tests pin that: any `jobs` count yields identical audio, the
result is repeatable, and the `jobs` knob is wired through render / render_to_wav
/ the AUDIOFORGE_JOBS env var / the CLI `--jobs` flag.
"""
import copy
import json
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from audioforge import cli  # noqa: E402
from audioforge.render import (  # noqa: E402
    _layer_signals, _resolve_jobs, render, render_to_wav,
)
from audioforge.schema import validate_spec  # noqa: E402
from audioforge.determinism import spec_hash  # noqa: E402
from audioforge import sequencer  # noqa: E402

# A multi-layer, multi-type synth spec (no external library needed): exercises
# tone/notes/drums/noise/grain, a bus with fx, and master fx — the full
# accumulate path the parallel section feeds.
SPEC = {
    "id": "par_test",
    "kind": "cue",
    "duration_s": 1.6,
    "bpm": 120,
    "buses": [{"name": "rhythm", "gain_db": -2.0,
               "fx": [{"type": "reverb", "decay": 1.0, "mix": 0.12}]}],
    "layers": [
        {"name": "pad", "type": "tone", "osc": "pad", "note": "A3",
         "gain_db": -6,
         "env": {"attack": 0.3, "decay": 0.2, "sustain": 0.8, "release": 0.6}},
        {"name": "arp", "type": "notes", "osc": "triangle", "gain_db": -4,
         "env": {"attack": 0.004, "decay": 0.2, "sustain": 0.0,
                 "release": 0.08},
         "notes": [{"note": "C5", "start_beat": 0.0, "dur_beats": 0.5},
                   {"note": "E5", "start_beat": 0.5, "dur_beats": 0.5},
                   {"note": "G5", "start_beat": 1.0, "dur_beats": 1.0,
                    "vel": 1.1}]},
        {"name": "beat", "type": "drums", "voice": "kick",
         "pattern": "X...X...X...X...", "bus": "rhythm"},
        {"name": "hat", "type": "drums", "voice": "hat",
         "pattern": "x.x.x.x.x.x.x.x.", "bus": "rhythm"},
        {"name": "air", "type": "noise", "color": "pink", "gain_db": -12,
         "env": {"attack": 0.4, "decay": 0.4, "sustain": 0.2,
                 "release": 0.3}},
        {"name": "tex", "type": "grain", "source": "sine", "note": "A4",
         "gain_db": -14,
         "env": {"attack": 0.3, "decay": 0.3, "sustain": 0.7,
                 "release": 0.4}},
    ],
    "master": {"target_peak_dbfs": -1.5, "fade_out_s": 0.05,
               "stereo_width": 0.7,
               "fx": [{"type": "reverb", "decay": 1.2, "mix": 0.15}]},
}

ONE_LAYER = {
    "id": "one_layer",
    "kind": "cue",
    "duration_s": 1.0,
    "bpm": 120,
    "layers": [
        {"name": "air", "type": "noise", "color": "white", "gain_db": -6,
         "env": {"attack": 0.1, "decay": 0.2, "sustain": 0.5,
                 "release": 0.2}},
    ],
    "master": {"target_peak_dbfs": -1.5, "fade_out_s": 0.05},
}


def _render(spec, **kw):
    return render(copy.deepcopy(spec), **kw)[0]


@pytest.fixture(autouse=True)
def _clean_jobs_env(monkeypatch):
    """Keep AUDIOFORGE_JOBS unset by default so tests are isolated even if an
    earlier test (or the CLI under test) wrote it into the real environment."""
    monkeypatch.delenv("AUDIOFORGE_JOBS", raising=False)
    yield


# --------------------------------------------------------------------------
# The contract: parallel == serial, byte-for-byte.
# --------------------------------------------------------------------------
@pytest.mark.parametrize("jobs", [2, 3, 4, 8, 32])
def test_parallel_audio_byte_identical_to_serial(jobs):
    serial = _render(SPEC, jobs=1)
    par = _render(SPEC, jobs=jobs)
    assert par.shape == serial.shape
    assert np.array_equal(serial, par), f"jobs={jobs} diverged from serial"


def test_parallel_meta_identical_to_serial():
    _, _, m1 = render(copy.deepcopy(SPEC), jobs=1)
    _, _, m4 = render(copy.deepcopy(SPEC), jobs=4)
    # spec hash + loudness measurements are part of the deterministic contract
    assert m1["spec_hash"] == m4["spec_hash"]
    assert m1.get("loudness") == m4.get("loudness")


def test_parallel_repeatable():
    a = _render(SPEC, jobs=4)
    b = _render(SPEC, jobs=4)
    assert np.array_equal(a, b)


def test_default_equals_explicit_serial():
    assert np.array_equal(_render(SPEC), _render(SPEC, jobs=1))


def test_single_layer_parallel_equals_serial():
    # parallel is a no-op for one layer, but must still match exactly
    assert np.array_equal(_render(ONE_LAYER, jobs=1),
                          _render(ONE_LAYER, jobs=8))


def test_jobs_exceeding_layer_count_is_safe():
    assert np.array_equal(_render(SPEC, jobs=1), _render(SPEC, jobs=999))


# --------------------------------------------------------------------------
# _resolve_jobs
# --------------------------------------------------------------------------
def test_resolve_jobs_default_is_serial(monkeypatch):
    monkeypatch.delenv("AUDIOFORGE_JOBS", raising=False)
    assert _resolve_jobs(None) == 1


def test_resolve_jobs_reads_env(monkeypatch):
    monkeypatch.setenv("AUDIOFORGE_JOBS", "4")
    assert _resolve_jobs(None) == 4


def test_resolve_jobs_bad_env_falls_back_to_serial(monkeypatch):
    monkeypatch.setenv("AUDIOFORGE_JOBS", "not-a-number")
    assert _resolve_jobs(None) == 1


def test_resolve_jobs_explicit_overrides_env(monkeypatch):
    monkeypatch.setenv("AUDIOFORGE_JOBS", "2")
    assert _resolve_jobs(8) == 8


@pytest.mark.parametrize("bad", [0, -1, -7])
def test_resolve_jobs_clamps_to_minimum_one(bad):
    assert _resolve_jobs(bad) == 1


def test_env_var_drives_render(monkeypatch):
    serial = _render(SPEC, jobs=1)
    monkeypatch.setenv("AUDIOFORGE_JOBS", "4")
    assert np.array_equal(_render(SPEC), serial)   # jobs=None -> env


# --------------------------------------------------------------------------
# _layer_signals helper
# --------------------------------------------------------------------------
def test_layer_signals_serial_and_parallel_match():
    spec = validate_spec(copy.deepcopy(SPEC))
    root = spec_hash(spec)
    sr = int(spec.get("sample_rate", 48000))
    total_n = int(spec["duration_s"] * sr)
    tm = sequencer.TempoMap(spec.get("tempo_map") or [[0.0, spec["bpm"]]])
    args = (spec, total_n, sr, tm, 0.0, root, spec.get("groove"))

    prepped_s, sigs_s = _layer_signals(*args, report={}, jobs=1)
    prepped_p, sigs_p = _layer_signals(*args, report={}, jobs=4)

    assert len(sigs_s) == len(sigs_p) == len(spec["layers"])
    # order preserved AND each layer's signal identical regardless of jobs
    for i, (a, b) in enumerate(zip(sigs_s, sigs_p)):
        assert np.array_equal(a, b), f"layer {i} signal diverged"
    assert [l.get("name") for l in prepped_p] == \
           [l.get("name") for l in spec["layers"]]


# --------------------------------------------------------------------------
# render_to_wav + CLI plumbing
# --------------------------------------------------------------------------
def test_render_to_wav_jobs_same_output_hash(tmp_path):
    m1 = render_to_wav(copy.deepcopy(SPEC), tmp_path / "serial", jobs=1)
    m4 = render_to_wav(copy.deepcopy(SPEC), tmp_path / "par", jobs=4)
    assert m1["output_sha256"] == m4["output_sha256"]


CLI_AF = """asset cli_par {
  kind: cue
  duration: 1.2s
  tempo: 120bpm
  layer arp : notes {
    osc: triangle
    env: a=0.004s d=0.2s s=0.0 r=0.08s
    notes: C5 @ 0b for 0.5b, E5 @ 0.5b for 0.5b, G5 @ 1b for 1b
  }
  layer beat : drums {
    voice: kick
    pattern: X...X...X...X...
  }
  master {
    lufs: -16
    peak: -1db
  }
}
"""


def _cli_render_hash(tmp_path, jobs, capsys):
    af = tmp_path / "c.af"
    af.write_text(CLI_AF)
    out = tmp_path / f"out{jobs}"
    assert cli.main(["render", str(af), "-o", str(out), "--jobs",
                     str(jobs)]) == 0
    capsys.readouterr()                       # drain the manifest JSON
    manifest = json.loads((out / "cli_par.manifest.json").read_text())
    return manifest["output_sha256"]


def test_cli_jobs_flag_byte_identical(tmp_path, capsys):
    h1 = _cli_render_hash(tmp_path, 1, capsys)
    h4 = _cli_render_hash(tmp_path, 4, capsys)
    assert h1 == h4


# --------------------------------------------------------------------------
# The real workload: sampled instruments + the library-preload branch. Proves
# parallel rendering of multiple instrument layers is byte-identical too.
# --------------------------------------------------------------------------
INSTRUMENT_AF = """asset p2par {{
  kind: cue
  duration: 4s
  tempo: 120bpm
  library: "minilib@{pin}"
  layer vln1 : instrument {{
    instrument: testviolin
    gain: -3db
    notes: C4 @ 0b for 2b, G4 @ 2b for 2b
  }}
  layer vln2 : instrument {{
    instrument: testviolin
    gain: -6db
    notes: G4 @ 0b for 2b, C4 @ 2b for 2b
  }}
  master {{
    peak: -1db
    fadeout: 0.05s
  }}
}}
"""


def test_parallel_sampled_instruments_byte_identical(tmp_path, monkeypatch):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from test_sampler import build_library          # reuse the in-test minilib
    from audioforge import AudioForge

    pin = build_library(tmp_path / "minilib")
    src = INSTRUMENT_AF.format(pin=pin)

    serial = AudioForge().compile(src).assets[0].render()[0]   # jobs default 1
    monkeypatch.setenv("AUDIOFORGE_JOBS", "4")
    par = AudioForge().compile(src).assets[0].render()[0]      # jobs=4 via env
    assert np.array_equal(serial, par)
