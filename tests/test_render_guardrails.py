"""Guardrails against silent-failure renders.

A spec can be structurally valid yet produce audio that is mostly silent — a
lane muted by automation, or a filter automated into removing all signal (e.g.
`auto cutoff` driving a highpass up to Nyquist). The engine's stance is that
such failures must be loud, not silent. These tests lock two catches:

  * post-render dead-air detection in the analysis pass, and
  * a compile-time warning when `auto cutoff` targets a highpass.
"""
from __future__ import annotations

import numpy as np

from audioforge.analysis import analyze_audio
from audioforge.sdk import AudioForge

SR = 48000


def _stereo(mono: np.ndarray) -> np.ndarray:
    return np.stack([mono, mono], axis=1)


def _tone(seconds: float, amp: float = 0.3, freq: float = 220.0) -> np.ndarray:
    t = np.arange(int(seconds * SR)) / SR
    return amp * np.sin(2 * np.pi * freq * t)


# --- dead-air detection ---------------------------------------------------- #
def test_continuous_audio_has_no_dead_air():
    rep = analyze_audio(_stereo(_tone(30)), SR)
    assert rep["longest_silence_s"] == 0.0
    assert not any(r["code"] == "dead_air" for r in rep["recommendations"])


def test_dropout_render_is_flagged():
    # loud 3 s, silent 7 s, repeated — the shape the filter bug produced
    blocks = []
    for _ in range(5):
        blocks.append(_tone(3))
        blocks.append(np.zeros(int(7 * SR)))
    rep = analyze_audio(_stereo(np.concatenate(blocks)), SR)
    assert rep["longest_silence_s"] >= 6.0
    dead = [r for r in rep["recommendations"] if r["code"] == "dead_air"]
    assert dead and dead[0]["severity"] == "warning"


def test_uniformly_quiet_audio_is_not_flagged():
    # audible but low (-35 dBFS) throughout — must not false-positive
    rep = analyze_audio(_stereo(_tone(30, amp=0.018)), SR)
    assert not any(r["code"] == "dead_air" for r in rep["recommendations"])


# --- auto cutoff footgun warning ------------------------------------------- #
def _spec(chain: str) -> str:
    return f"""asset g {{
  kind: loop
  duration: 4s
  tempo: 128bpm
  key: A minor
  layer s : notes {{
    osc: saw
    gain: -8db
    env: a=0.005s d=0.1s s=0.3 r=0.05s
    notes: A2 @ 0b for 4b
    fx: {chain}
    auto cutoff: 0s=200, 4s=19000
  }}
  master {{
    peak: -1db
  }}
}}"""


def _cutoff_warnings(chain: str):
    asset = AudioForge().compile(_spec(chain)).assets[0]
    return [d for d in asset.validate() if "auto cutoff" in d.message]


def test_highpass_first_warns():
    w = _cutoff_warnings("highpass(30hz), lowpass(18000hz)")
    assert w and w[0].severity == "warning"
    assert "highpass" in w[0].message


def test_lowpass_first_is_clean():
    assert not _cutoff_warnings("lowpass(18000hz), highpass(30hz)")


def test_no_filter_automation_is_clean():
    src = """asset g {
  kind: loop
  duration: 4s
  tempo: 128bpm
  key: A minor
  layer s : notes {
    osc: saw
    gain: -8db
    env: a=0.005s d=0.1s s=0.3 r=0.05s
    notes: A2 @ 0b for 4b
    fx: highpass(30hz)
  }
  master {
    peak: -1db
  }
}"""
    asset = AudioForge().compile(src).assets[0]
    assert not [d for d in asset.validate() if "auto cutoff" in d.message]
