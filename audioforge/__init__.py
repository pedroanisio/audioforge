"""AudioForge — deterministic audio-asset generation.

Authoring surface: the .af DSL (audioforge.dsl) or raw JSON specs.
Engine ground truth: the compiled JSON spec, hashed for reproducibility.
Integration surface: audioforge.sdk.AudioForge.
"""
from .catalog import Catalog, Instrument, Library
from .analysis import analyze_audio
from .capabilities import capability_manifest, capability_manifest_schema
from .compose import Composer, hall, reverb
from .decompile import spec_to_dsl
from .determinism import spec_hash
from .dsl import DSLError, compile_dsl
from .grammar import dsl_ebnf, dsl_gbnf
from .interop import (export_midi_bytes, export_musicxml, import_midi_bytes,
                      import_musicxml)
from .plugins import (register_drum_voice, register_exporter, register_fx,
                      register_oscillator, register_validator)
from .render import render, render_to_wav, verify
from .repair import apply_repair, plan_repair
from .agent_tools import run_tool, tool_schemas
from .plan import (RENDER_PLAN_SCHEMA_VERSION, build_render_plan,
                   explain_plan, plan_hash, validate_render_plan,
                   verify_plan_for_spec)
from .schema import SpecError, validate_spec
from .sdk import AudioAsset, AudioForge, CompileResult, Diagnostic
from .styles import list_style_packs, style_pack
from .version import DSL_VERSION, ENGINE_VERSION, version_banner, version_contract

__all__ = [
    "ENGINE_VERSION", "DSL_VERSION", "spec_hash",
    "compile_dsl", "DSLError",
    "render", "render_to_wav", "verify",
    "validate_spec", "SpecError",
    "AudioForge", "AudioAsset", "CompileResult", "Diagnostic",
    "Catalog", "Instrument", "Library", "Composer", "hall", "reverb",
    "capability_manifest", "capability_manifest_schema",
    "dsl_ebnf", "dsl_gbnf", "analyze_audio",
    "spec_to_dsl", "plan_repair", "apply_repair", "run_tool", "tool_schemas",
    "RENDER_PLAN_SCHEMA_VERSION", "build_render_plan", "plan_hash",
    "validate_render_plan", "verify_plan_for_spec", "explain_plan",
    "export_midi_bytes", "import_midi_bytes", "export_musicxml",
    "import_musicxml", "list_style_packs", "style_pack",
    "version_banner", "version_contract",
    "register_oscillator", "register_fx", "register_drum_voice",
    "register_exporter", "register_validator",
]
