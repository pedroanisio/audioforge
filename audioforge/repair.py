"""Deterministic agent repair planner for DSL edits."""
from __future__ import annotations

import copy

from .sdk import AudioForge

REPAIR_SCHEMA = "audioforge.repair-plan/1"


def _codes(analysis: dict) -> set[str]:
    return {r.get("code", "") for r in analysis.get("recommendations", [])}


def _insert_before_master_end(dsl: str, line: str) -> str:
    marker = "\n  master {"
    if marker in dsl:
        start = dsl.index(marker)
        try:
            end = dsl.index("\n  }", start)
        except ValueError:
            end = dsl.index("}", start)
            return dsl[:end] + "\n" + line + "\n  " + dsl[end:]
        return dsl[:end] + "\n" + line + dsl[end:]
    idx = dsl.rfind("\n}")
    return dsl[:idx] + "\n  master {\n" + line + "\n  }\n" + dsl[idx:]


def apply_repair(dsl: str, suggestion: dict) -> str:
    op = suggestion.get("operation")
    if op == "insert_master_fx":
        fx = suggestion["fx"]
        if fx["type"] == "filter":
            text = (
                f"    fx: {fx['mode']}({fx['cutoff_hz']}hz, q={fx.get('q', 0.7071)})"
            )
        else:
            text = f"    fx: gain({fx.get('db', 0)}db)"
        return _insert_before_master_end(dsl, text)
    if op == "set_master_peak":
        return _insert_before_master_end(dsl, f"    peak: {suggestion['peak_db']}db")
    return dsl


def plan_repair(request: dict) -> dict:
    """Return reproducible repair suggestions and a compile verification trace."""
    dsl = request.get("dsl", "")
    feedback = str(request.get("feedback", "")).lower()
    analysis = request.get("analysis", {}) or {}
    codes = _codes(analysis)
    suggestions = []
    if "very_bright" in codes or "rough" in feedback:
        suggestions.append({
            "operation": "insert_master_fx",
            "reason": "reduce excessive brightness or rough melody edge",
            "fx": {"type": "filter", "mode": "lowpass",
                   "cutoff_hz": 6500, "q": 0.7071},
        })
    if "mono_image" in codes:
        suggestions.append({
            "operation": "insert_master_fx",
            "reason": "widen mono image with explicit gain-neutral stereo cue",
            "fx": {"type": "gain", "db": 0},
        })
    if "clipping" in codes:
        suggestions.append({
            "operation": "set_master_peak",
            "reason": "lower peak target to avoid clipping",
            "peak_db": -1,
        })
    if not suggestions:
        suggestions.append({
            "operation": "noop",
            "reason": "no supported repair recommendation matched",
        })
    ranked = sorted(copy.deepcopy(suggestions),
                    key=lambda s: (s["operation"], s["reason"]))
    patched = apply_repair(dsl, ranked[0])
    result = AudioForge().compile(patched)
    return {
        "schema": REPAIR_SCHEMA,
        "suggestions": ranked,
        "trace": {
            "inputs": {
                "feedback": request.get("feedback", ""),
                "analysis_codes": sorted(codes),
            },
            "verification": {
                "compile_ok": result.ok,
                "diagnostics": [d.__dict__ for d in result.diagnostics],
            },
        },
    }
