"""AudioForge — deterministic audio-asset generation.

Authoring surface: the .af DSL (audioforge.dsl) or raw JSON specs.
Engine ground truth: the compiled JSON spec, hashed for reproducibility.
Integration surface: audioforge.sdk.AudioForge.
"""
from .catalog import Catalog, Instrument, Library
from .determinism import ENGINE_VERSION, spec_hash
from .dsl import DSL_VERSION, DSLError, compile_dsl
from .plugins import (register_drum_voice, register_exporter, register_fx,
                      register_oscillator, register_validator)
from .render import render, render_to_wav, verify
from .schema import SpecError, validate_spec
from .sdk import AudioAsset, AudioForge, CompileResult, Diagnostic

__all__ = [
    "ENGINE_VERSION", "DSL_VERSION", "spec_hash",
    "compile_dsl", "DSLError",
    "render", "render_to_wav", "verify",
    "validate_spec", "SpecError",
    "AudioForge", "AudioAsset", "CompileResult", "Diagnostic",
    "Catalog", "Instrument", "Library",
    "register_oscillator", "register_fx", "register_drum_voice",
    "register_exporter", "register_validator",
]
