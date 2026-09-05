"""Resampler cost curve stays bounded (RM-E-005, HARNESS-PERF-002).

Absolute times depend on the machine, so this test pins ratios (documented in
docs/MIGRATION_3.md, "Render cost of anti-alias resampling") and a loose wall-clock
ceiling; the harness pins the absolute reference-machine budget.
"""
import time

import numpy as np

from audioforge.sampler import Region, render_region

SR = 48000


def _cost_ms(semitones: int, source: np.ndarray) -> float:
    region = Region(pitch_keycenter=60, ampeg_attack=0.001, ampeg_release=0.1)
    best = float("inf")
    for _ in range(3):
        t0 = time.perf_counter()
        render_region(region, source, SR, 60 + semitones, SR, SR)
        best = min(best, time.perf_counter() - t0)
    return best * 1000.0


def test_resampler_cost_grows_with_transposition_but_stays_bounded():
    source = np.sin(2 * np.pi * 440 * np.arange(SR * 2) / SR)
    unity, octave, two_octaves = (_cost_ms(s, source) for s in (0, 12, 24))
    assert two_octaves < 2000, f"two-octave transposition of a 1 s note took {two_octaves:.0f} ms"
    assert octave / unity < 4.0, f"+12 semitone cost ratio {octave / unity:.1f}x exceeds the documented curve"
    assert two_octaves / unity < 8.0, f"+24 semitone cost ratio {two_octaves / unity:.1f}x exceeds the documented curve"
