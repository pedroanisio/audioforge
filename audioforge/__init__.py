"""AudioForge — deterministic audio-asset generation.

Authoring surface: the .af DSL (audioforge.dsl) or raw JSON specs.
Engine ground truth: the compiled JSON spec, hashed for reproducibility.
Integration surface: audioforge.sdk.AudioForge.
"""
from .catalog import Catalog, Instrument, Library
from .analysis import analyze_audio
from .capabilities import capability_manifest
from .compose import Composer, hall, reverb
from .decompile import spec_to_dsl
from .determinism import ENGINE_VERSION, spec_hash
from .dsl import DSL_VERSION, DSLError, compile_dsl
from .grammar import dsl_ebnf, dsl_gbnf
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
    "Catalog", "Instrument", "Library", "Composer", "hall", "reverb",
    "capability_manifest", "dsl_ebnf", "dsl_gbnf", "analyze_audio",
    "spec_to_dsl",
    "register_oscillator", "register_fx", "register_drum_voice",
    "register_exporter", "register_validator",
]
