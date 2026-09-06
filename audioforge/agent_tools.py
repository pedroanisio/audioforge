"""Typed agent tool facade over AudioForge SDK operations."""
from __future__ import annotations

from .analysis import analyze_audio
from .decompile import decompile_diagnostics, spec_to_dsl
from .interop import export_midi_bytes, export_musicxml, export_notated_musicxml, interop_diagnostics
from .repair import plan_repair
from .schema import SpecError, validate_spec
from .sdk import AudioForge
from .version import DSL_VERSION, ENGINE_VERSION

TOOL_SCHEMA_VERSION = "audioforge.agent-tools/1"


def _diag(severity: str, message: str, path: str | None = None,
          code: str | None = None) -> dict:
    """Envelope diagnostic (ADR-0008): always carries ``code`` (registered or null)."""
    from .sdk import infer_diagnostic_code
    out = {"severity": severity, "message": message,
           "code": code if code is not None else infer_diagnostic_code(message)}
    if path:
        out["path"] = path
    return out


def _response(ok: bool, *, artifacts=None, diagnostics=None) -> dict:
    return {
        "schema": TOOL_SCHEMA_VERSION,
        "engine_version": ENGINE_VERSION,
        "dsl_version": DSL_VERSION,
        "ok": ok,
        "diagnostics": diagnostics or [],
        "artifacts": artifacts or [],
    }


def tool_schemas() -> dict:
    ops = ["compile", "validate", "plan", "render", "analyze", "decompile",
           "import", "export", "repair"]
    schemas = {
        name: {
            "schema": TOOL_SCHEMA_VERSION,
            "request": {"type": "object"},
            "response": {"required": ["schema", "ok", "diagnostics", "artifacts"],
                         "diagnostic": {"required": ["severity", "message", "code"],
                                        "code": "a capability_manifest()['diagnostic_codes'] key, or null (ADR-0008)"}},
        }
        for name in ops
    }
    schemas["analyze"]["request"] = {
        "type": "object", "required": ["audio", "sample_rate"],
        "properties": {"audio": {"type": "array"}, "sample_rate": {"type": "integer", "minimum": 1},
                       "context": {"type": "object", "description": "Compiled spec or declared analysis expectations"}},
    }
    schemas["export"]["request"] = {
        "type": "object", "required": ["spec"],
        "properties": {"spec": {"type": "object"},
                       "format": {"enum": ["midi", "musicxml", "musicxml_notated"]},
                       "grid": {"type": "number", "exclusiveMinimum": 0, "multipleOf": .03125, "default": .25}},
    }
    return schemas


def run_tool(operation: str, request: dict) -> dict:
    try:
        if operation == "compile":
            res = AudioForge().compile(request.get("dsl", ""))
            return _response(
                res.ok,
                artifacts=[{"id": a.id, "spec": a.spec} for a in res.assets],
                diagnostics=[d.as_dict() for d in res.diagnostics],
            )
        if operation == "validate":
            asset = AudioForge().load_spec(request["spec"])
            diagnostics = asset.validate(resolve=request.get("resolve", True))
            return _response(not any(d.severity == "error" for d in diagnostics),
                             diagnostics=[d.as_dict() for d in diagnostics])
        if operation == "plan":
            from .plan import build_render_plan
            result = build_render_plan(request["spec"])
            return _response(
                True,
                artifacts=[{
                    "plan": result.plan,
                    "plan_hash": result.plan_hash,
                }],
                diagnostics=result.diagnostics,
            )
        if operation == "decompile":
            spec = request["spec"]
            return _response(
                True,
                artifacts=[{"dsl": spec_to_dsl(spec)}],
                diagnostics=[
                    _diag("warning", msg) for msg in decompile_diagnostics(spec)
                ],
            )
        if operation == "export":
            spec = request["spec"]
            fmt = request.get("format", "midi")
            if fmt == "musicxml":
                data = export_musicxml(spec)
            elif fmt == "musicxml_notated":
                data = export_notated_musicxml(spec, grid=float(request.get("grid", .25)))
            elif fmt == "midi":
                data = export_midi_bytes(spec).hex()
            else:
                raise ValueError(f"unknown interop format: {fmt}")
            return _response(
                True,
                artifacts=[{"format": fmt, "data": data}],
                diagnostics=interop_diagnostics(spec, fmt),
            )
        if operation == "repair":
            return _response(True, artifacts=[plan_repair(request)])
        if operation == "analyze":
            report = analyze_audio(request["audio"], int(request["sample_rate"]),
                                   context=request.get("context"))
            return _response(True, artifacts=[{"analysis": report}])
        if operation == "render":
            res = AudioForge().compile(request.get("dsl", ""))
            if not res.ok:
                return _response(False, diagnostics=[d.as_dict() for d in res.diagnostics])
            return _response(True, artifacts=[{"id": a.id, "renderable": True}
                                             for a in res.assets])
        if operation == "import":
            return _response(False, diagnostics=[_diag("error", "import expects CLI file input")])
        return _response(False, diagnostics=[_diag("error", f"unknown tool '{operation}'")])
    except (KeyError, SpecError, ValueError) as exc:
        return _response(False, diagnostics=[_diag("error", str(exc))])
