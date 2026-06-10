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


def run_extra_validators(spec: dict) -> list[str]:
    out: list[str] = []
    for name, fn in sorted(VALIDATORS.items()):
        out.extend(f"[{name}] {msg}" for msg in fn(spec))
    return out
