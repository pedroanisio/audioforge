"""Typed agent tool facade over AudioForge SDK operations."""
from __future__ import annotations

from .analysis import analyze_audio
from .decompile import decompile_diagnostics, spec_to_dsl
from .interop import export_midi_bytes, export_musicxml, interop_diagnostics
from .repair import plan_repair
from .schema import SpecError, validate_spec
from .sdk import AudioForge
from .version import DSL_VERSION, ENGINE_VERSION

TOOL_SCHEMA_VERSION = "audioforge.agent-tools/1"


def _diag(severity: str, message: str, path: str | None = None) -> dict:
    out = {"severity": severity, "message": message}
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
            "response": {"required": ["schema", "ok", "diagnostics", "artifacts"]},
        }
        for name in ops
    }
    schemas["analyze"]["request"] = {
        "type": "object", "required": ["audio", "sample_rate"],
        "properties": {"audio": {"type": "array"}, "sample_rate": {"type": "integer", "minimum": 1},
                       "context": {"type": "object", "description": "Compiled spec or declared analysis expectations"}},
    }
    return schemas


def run_tool(operation: str, request: dict) -> dict:
    try:
        if operation == "compile":
            res = AudioForge().compile(request.get("dsl", ""))
            return _response(
                res.ok,
                artifacts=[{"id": a.id, "spec": a.spec} for a in res.assets],
                diagnostics=[d.__dict__ for d in res.diagnostics],
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
            else:
                data = export_midi_bytes(spec).hex()
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
                return _response(False, diagnostics=[d.__dict__ for d in res.diagnostics])
            return _response(True, artifacts=[{"id": a.id, "renderable": True}
                                             for a in res.assets])
        if operation == "import":
            return _response(False, diagnostics=[_diag("error", "import expects CLI file input")])
        return _response(False, diagnostics=[_diag("error", f"unknown tool '{operation}'")])
    except (KeyError, SpecError, ValueError) as exc:
        return _response(False, diagnostics=[_diag("error", str(exc))])
