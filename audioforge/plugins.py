"""Plugin architecture.

Extension points are plain registries with decorator registration. A plugin
is any imported module that calls these decorators. Determinism contract for
plugins: a plugin callable receives an explicitly seeded RNG when it needs
randomness and MUST NOT use any other entropy source; plugin names become
part of specs, so spec hashing covers plugin selection automatically.

Extension points:
  oscillator(name)  -> f(freq, n, sr, **params) -> np.ndarray
  fx(name)          -> f(x, sr, params: dict, rng) -> np.ndarray
  drum_voice(name)  -> f(sr, rng) -> np.ndarray
  exporter(name)    -> f(stereo, sr, meta, out_dir) -> dict (files written)
  validator(name)   -> f(spec: dict) -> list[str] (diagnostics, empty = ok)
"""
from __future__ import annotations

from typing import Callable

OSCILLATORS: dict[str, Callable] = {}
FX: dict[str, Callable] = {}
DRUM_VOICES: dict[str, Callable] = {}
EXPORTERS: dict[str, Callable] = {}
VALIDATORS: dict[str, Callable] = {}


def _make_register(registry: dict, kind: str):
    def register(name: str):
        def deco(fn: Callable):
            if name in registry:
                raise ValueError(f"{kind} plugin '{name}' already registered")
            registry[name] = fn
            return fn
        return deco
    return register


register_oscillator = _make_register(OSCILLATORS, "oscillator")
register_fx = _make_register(FX, "fx")
register_drum_voice = _make_register(DRUM_VOICES, "drum_voice")
register_exporter = _make_register(EXPORTERS, "exporter")
register_validator = _make_register(VALIDATORS, "validator")


def _coverage_validator(spec: dict) -> list[str]:
    """Advisory: declared duration / markers extending past the last
    event. Added after the cancoes_sertao_III incident — a fixture
    declared 275s with climax markers but wrote no events past 170s;
    the faithful render was 40% silence."""
    out = []
    dur = spec.get("duration_s", 0)
    tm = spec.get("tempo_map") or []
    bpm0 = (tm[0][1] if tm and isinstance(tm[0], (list, tuple))
            else spec.get("bpm") or spec.get("tempo_bpm") or 120.0)
    last = 0.0
    for layer in spec.get("layers", []):
        for ev in (layer.get("notes") or []):
            t = (ev.get("start_beat", 0) + ev.get("dur_beats", 0)) \
                * 60.0 / bpm0
            last = max(last, t)
        if layer.get("type") in ("tone", "sample", "foley"):
            last = max(last, layer.get("start_s", 0.0) + 1.0)
    if dur and last and dur - last > 15.0:
        out.append(f"events end at ~{last:.0f}s but duration is "
                   f"{dur:.0f}s — the final {dur - last:.0f}s will "
                   f"render (near-)silent")
    # interior gaps: merge event intervals, find holes (a lone final
    # chord must not hide a silent middle)
    iv = []
    for layer in spec.get("layers", []):
        for ev in (layer.get("notes") or []):
            a = ev.get("start_beat", 0) * 60.0 / bpm0
            iv.append((a, a + ev.get("dur_beats", 0) * 60.0 / bpm0))
        if layer.get("type") in ("tone", "sample", "foley"):
            iv.append((layer.get("start_s", 0.0),
                       layer.get("start_s", 0.0) + 2.0))
    iv.sort()
    cov_end, holes = 0.0, []
    for a, b in iv:
        if a - cov_end > 20.0:
            holes.append((cov_end, a))
        cov_end = max(cov_end, b)
    for a, b in holes:
        out.append(f"no events between ~{a:.0f}s and ~{b:.0f}s "
                   f"({b - a:.0f}s of (near-)silence mid-piece)")
    for mk in (spec.get("markers") or []):
        t = mk.get("time_s", 0)
        if (last and t > last + 5.0) or any(a + 5 < t < b - 5
                                            for a, b in holes):
            out.append(f"marker '{mk.get('name')}' at {t:.0f}s has no "
                       f"music under it — declared structure, no events")
    return out


VALIDATORS["coverage"] = _coverage_validator


def run_extra_validators(spec: dict) -> list[str]:
    out: list[str] = []
    for name, fn in sorted(VALIDATORS.items()):
        out.extend(f"[{name}] {msg}" for msg in fn(spec))
    return out
