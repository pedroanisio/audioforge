"""Deterministic render-plan artifacts.

The render plan is derived data between validation/resource resolution and
rendering. It records route decisions and evidence without becoming authored
musical intent.
"""
from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass
from typing import Any

import numpy as np

from .determinism import canonical_json, rng_for, spec_hash
from .schema import ROUTING_FALLBACK_MODES, SpecError, validate_spec
from .version import ENGINE_VERSION

RENDER_PLAN_SCHEMA_VERSION = "audioforge.render-plan/1"
ROUTE_SAMPLE = "sample"
ROUTE_SYNTHETIC_FALLBACK = "synthetic_fallback"
ROUTE_SYNTH_NATIVE = "synth_native"
ROUTE_INPAINT = "inpaint"
RENDER_PLAN_ROUTES = {
    ROUTE_SAMPLE,
    ROUTE_SYNTHETIC_FALLBACK,
    ROUTE_SYNTH_NATIVE,
    ROUTE_INPAINT,
}
PLAN_DIAGNOSTIC_CODES = {
    "render_plan_stale",
    "render_plan_schema",
    "render_plan_missing_evidence",
    "render_plan_policy_fallback_forbid",
    "render_plan_policy_fallback_warn",
    "render_plan_stretch_warn",
    "render_plan_inpaint_unavailable",
}


@dataclass
class RenderPlanResult:
    plan: dict
    plan_hash: str
    diagnostics: list[dict]


def _diag(severity: str, code: str, message: str,
          path: str | None = None) -> dict:
    out = {"severity": severity, "code": code, "message": message}
    if path:
        out["path"] = path
    return out


def normalize_routing_policy(spec: dict) -> dict:
    routing = spec.get("routing") or {}
    fallbacks = routing.get("fallbacks", "allow")
    if fallbacks not in ROUTING_FALLBACK_MODES:
        raise SpecError(
            "spec.routing.fallbacks: expected one of "
            f"{sorted(ROUTING_FALLBACK_MODES)}")
    out = {"fallbacks": fallbacks}
    if "stretch_warn_semitones" in routing:
        value = routing["stretch_warn_semitones"]
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise SpecError("spec.routing.stretch_warn_semitones: number")
        if value < 0:
            raise SpecError(
                "spec.routing.stretch_warn_semitones: must be >= 0")
        out["stretch_warn_semitones"] = float(value)
    else:
        out["stretch_warn_semitones"] = None
    return out


def canonical_plan_payload(plan: dict) -> dict:
    return {k: v for k, v in plan.items() if k != "plan_hash"}


def canonical_plan_json(plan: dict) -> str:
    return canonical_json(canonical_plan_payload(plan))


def plan_hash(plan: dict) -> str:
    return hashlib.sha256(canonical_plan_json(plan).encode("utf-8")).hexdigest()


def plan_sha256_file_payload(plan: dict) -> str:
    return hashlib.sha256(
        (json.dumps(with_plan_hash(plan), indent=2, sort_keys=True)
         + "\n").encode("utf-8")
    ).hexdigest()


def with_plan_hash(plan: dict) -> dict:
    out = copy.deepcopy(plan)
    out["plan_hash"] = plan_hash(out)
    return out


def dumps_plan(plan: dict) -> str:
    return json.dumps(with_plan_hash(plan), indent=2, sort_keys=True) + "\n"


def load_plan_json(text: str) -> dict:
    plan = json.loads(text)
    validate_render_plan(plan)
    return plan


def _layer_name(layer: dict, idx: int) -> str:
    return str(layer.get("name", f"layer{idx}"))


def _note_id(layer_name: str, note_index: int) -> str:
    return f"seg:{layer_name}:{note_index}"


def _midi_for_event(ev: dict) -> float:
    from . import synth
    from .sampler import freq_to_midi

    freq = ev.get("freq_hz") or synth.note_to_freq(ev["note"])
    return float(freq_to_midi(freq))


def _velocity127(vel: float) -> int:
    return int(np.clip(round(float(vel) * 127), 1, 127))


def _region_identity(region) -> dict:
    return {
        "sample": region.sample,
        "key_range": [region.lokey, region.hikey],
        "pitch_keycenter": region.pitch_keycenter,
        "velocity_range": [region.lovel, region.hivel],
        "seq_length": region.seq_length,
        "seq_position": region.seq_position,
        "tune_cents": region.tune,
        "transpose": region.transpose,
    }


def _library_entry(lib, ref: dict) -> dict:
    manifest = lib.manifest
    return {
        "name": manifest.get("name", ref.get("name")),
        "manifest_sha256": manifest.get("manifest_sha256",
                                        ref.get("manifest_sha256")),
        "version": manifest.get("version", ""),
        "license": manifest.get("license", ""),
    }


def _rng_for_note(root: str, layer_index: int, layer_name: str,
                  layer_type: str, note_index: int, section: bool):
    sub = f"note{note_index}"
    if section:
        sub = f"player0:{sub}"
    return rng_for(root, f"{layer_index}:{layer_name}", layer_type, sub)


def _instrument_segment(spec_hash_value: str, layer: dict, layer_index: int,
                        note_index: int, ev: dict, lib, policy: dict,
                        diagnostics: list[dict]) -> dict:
    from .sampler import resolve_articulation_detail, select_regions

    layer_name = _layer_name(layer, layer_index)
    instrument = layer["instrument"]
    requested_art = ev.get("art", layer.get("articulation", "sustain"))
    detail = resolve_articulation_detail(lib, instrument, requested_art)
    regions = detail["regions"]
    midi = _midi_for_event(ev)
    midi_i = int(round(midi))
    kreg = [r for r in regions if r.lokey <= midi_i <= r.hikey]
    if not kreg:
        raise SpecError(
            f"layers[{layer_index}].notes[{note_index}]: instrument "
            f"'{instrument}' has no SFZ region covering midi {midi_i} "
            f"for articulation '{requested_art}'")
    vel = float(ev.get("vel", 1.0))
    note_path = f"layers[{layer_index}].notes[{note_index}]"
    fallback = detail.get("fallback")
    if fallback and policy["fallbacks"] == "forbid":
        raise SpecError(
            f"{note_path}: render_plan_policy_fallback_forbid: "
            f"articulation '{requested_art}' would use fallback "
            f"'{fallback['base_articulation']}'")
    route = ROUTE_SYNTHETIC_FALLBACK if fallback else ROUTE_SAMPLE
    segment_diags: list[dict] = []
    if fallback:
        sev = "warning" if policy["fallbacks"] == "warn" else "info"
        code = ("render_plan_policy_fallback_warn"
                if policy["fallbacks"] == "warn" else "synthetic_fallback")
        segment_diags.append(_diag(
            sev,
            code,
            f"'{requested_art}' -> {fallback['description']}",
            note_path,
        ))
    keycenter_distance = min(
        abs(float(midi_i) - float(r.pitch_keycenter)) for r in kreg
    )
    stretch_threshold = policy.get("stretch_warn_semitones")
    if stretch_threshold is not None and keycenter_distance > stretch_threshold:
        segment_diags.append(_diag(
            "warning",
            "render_plan_stretch_warn",
            f"selected region is {keycenter_distance:.3g} semitones from "
            f"nearest keycenter, above threshold {stretch_threshold}",
            note_path,
        ))
    dynamic_mode = bool(ev.get("curves")) or bool(layer.get("dynamic"))
    if dynamic_mode:
        bands = {}
        for r in kreg:
            bands.setdefault((r.lovel, r.hivel), []).append(r)
        rng = _rng_for_note(
            spec_hash_value,
            layer_index,
            layer_name,
            layer["type"],
            note_index,
            section=bool(layer.get("section")),
        )
        selected = [
            {
                "velocity_range": [lo, hi],
                "center": (lo + hi) / 2.0,
                "regions": [_region_identity(r) for r in regs],
                "selected_regions": [
                    _region_identity(r)
                    for r in select_regions(regs, midi_i, int((lo + hi) / 2.0), rng)
                ],
            }
            for (lo, hi), regs in sorted(
                bands.items(), key=lambda item: (item[0][0] + item[0][1]) / 2.0
            )
        ]
        velocity = {
            "mode": "dynamic_crossfade",
            "source": "note_or_layer_dynamic_curve",
            "bands": selected,
        }
    else:
        v127 = _velocity127(vel)
        rng = _rng_for_note(
            spec_hash_value,
            layer_index,
            layer_name,
            layer["type"],
            note_index,
            section=bool(layer.get("section")),
        )
        picked = select_regions(kreg, midi_i, v127, rng)
        velocity = {
            "mode": "static_velocity",
            "vel": vel,
            "vel127": v127,
            "selected_regions": [_region_identity(r) for r in picked],
        }
    diagnostics.extend(d for d in segment_diags if d["severity"] == "warning")
    return {
        "id": _note_id(layer_name, note_index),
        "layer": layer_name,
        "layer_type": "instrument",
        "note_index": note_index,
        "span": {
            "start_beat": float(ev["start_beat"]),
            "dur_beats": float(ev["dur_beats"]),
        },
        "route": route,
        "decision": {
            "instrument": instrument,
            "requested_articulation": requested_art,
            "resolved_articulation": detail["resolved_articulation"],
            "fallback": fallback,
            "mods": dict(detail.get("mods", {})),
            "midi": midi,
            "midi_rounded": midi_i,
            "velocity": velocity,
        },
        "evidence": {
            "library": _library_entry(lib, layer["_library"]),
            "available_articulations": sorted(
                lib.manifest["instruments"][instrument].get(
                    "articulations", {})
            ),
            "candidate_region_count": len(kreg),
            "keycenter_distance_semitones": keycenter_distance,
        },
        "diagnostics": segment_diags,
        "cost": {"estimated_ms": None},
    }


def _synth_native_segment(layer: dict, layer_index: int,
                          note_index: int, ev: dict) -> dict:
    layer_name = _layer_name(layer, layer_index)
    osc = layer.get("osc", "sine")
    return {
        "id": _note_id(layer_name, note_index),
        "layer": layer_name,
        "layer_type": layer.get("type", "notes"),
        "note_index": note_index,
        "span": {
            "start_beat": float(ev["start_beat"]),
            "dur_beats": float(ev["dur_beats"]),
        },
        "route": ROUTE_SYNTH_NATIVE,
        "decision": {
            "voice": osc,
            "oscillator": osc,
            "curve_support": {
                "pitch_cents": "declared_by_validator",
                "dynamic": "declared_by_validator",
            },
        },
        "evidence": {
            "layer_type": layer.get("type", "notes"),
            "note_has_curves": bool(ev.get("curves")),
            "layer_has_automation": bool(layer.get("automation")),
        },
        "diagnostics": [],
        "cost": {"estimated_ms": None},
    }


def build_render_plan(spec: dict) -> RenderPlanResult:
    from .library import load_library

    resolved = validate_spec(copy.deepcopy(spec))
    root = spec_hash(resolved)
    policy = normalize_routing_policy(resolved)
    diagnostics: list[dict] = []
    segments: list[dict] = []
    libraries: dict[str, dict] = {}
    library_cache: dict[tuple[str, str], Any] = {}
    for layer_index, layer0 in enumerate(resolved.get("layers", [])):
        layer = layer0
        if layer.get("type") == "instrument":
            ref = resolved["library"]
            layer = {**layer, "_library": ref}
            key = (ref["name"], ref["manifest_sha256"])
            lib = library_cache.get(key)
            if lib is None:
                lib = load_library(ref)
                library_cache[key] = lib
            libraries[ref["name"]] = _library_entry(lib, ref)
            for note_index, ev in enumerate(layer.get("notes", [])):
                segments.append(_instrument_segment(
                    root, layer, layer_index, note_index, ev, lib, policy,
                    diagnostics))
        elif layer.get("type") == "notes":
            for note_index, ev in enumerate(layer.get("notes", [])):
                segments.append(_synth_native_segment(
                    layer, layer_index, note_index, ev))

    plan = {
        "schema": RENDER_PLAN_SCHEMA_VERSION,
        "spec_hash": root,
        "engine_version": ENGINE_VERSION,
        "catalog_pin": None,
        "libraries": [libraries[k] for k in sorted(libraries)],
        "policy_effective": policy,
        "segments": segments,
        "diagnostics": diagnostics,
    }
    validate_render_plan(plan)
    return RenderPlanResult(plan=plan, plan_hash=plan_hash(plan),
                            diagnostics=diagnostics)


def validate_render_plan(plan: dict) -> dict:
    if not isinstance(plan, dict):
        raise SpecError("render plan: must be an object")
    if plan.get("schema") != RENDER_PLAN_SCHEMA_VERSION:
        raise SpecError(
            "render plan: schema must be "
            f"{RENDER_PLAN_SCHEMA_VERSION!r}")
    required = {
        "spec_hash",
        "engine_version",
        "catalog_pin",
        "libraries",
        "policy_effective",
        "segments",
    }
    missing = sorted(required - set(plan))
    if missing:
        raise SpecError(f"render plan: missing fields {missing}")
    stored = plan.get("plan_hash")
    if stored is not None and stored != plan_hash(plan):
        raise SpecError("render plan: plan_hash does not match canonical JSON")
    if plan.get("engine_version") != ENGINE_VERSION:
        raise SpecError(
            "render_plan_stale: engine_version differs "
            f"(plan={plan.get('engine_version')} current={ENGINE_VERSION})")
    for i, seg in enumerate(plan.get("segments", [])):
        path = f"segments[{i}]"
        route = seg.get("route")
        if route not in RENDER_PLAN_ROUTES:
            raise SpecError(f"render plan {path}.route: unknown {route!r}")
        if route == ROUTE_INPAINT:
            raise SpecError(
                f"render plan {path}: render_plan_inpaint_unavailable")
        for key in ("id", "layer", "layer_type", "decision", "evidence",
                    "diagnostics", "cost"):
            if key not in seg:
                raise SpecError(f"render plan {path}: missing {key}")
        if route in {ROUTE_SAMPLE, ROUTE_SYNTHETIC_FALLBACK} \
                and not seg["evidence"]:
            raise SpecError(
                f"render plan {path}: render_plan_missing_evidence")
        if "estimated_ms" not in seg["cost"]:
            raise SpecError(f"render plan {path}.cost: missing estimated_ms")
    return plan


def verify_plan_for_spec(spec: dict, plan: dict) -> RenderPlanResult:
    validate_render_plan(plan)
    current = build_render_plan(spec)
    expected_hash = current.plan_hash
    actual_hash = plan_hash(plan)
    if actual_hash != expected_hash:
        reasons = []
        if plan.get("spec_hash") != current.plan.get("spec_hash"):
            reasons.append("spec_hash")
        if plan.get("engine_version") != current.plan.get("engine_version"):
            reasons.append("engine_version")
        if plan.get("libraries") != current.plan.get("libraries"):
            reasons.append("library pin")
        if plan.get("catalog_pin") != current.plan.get("catalog_pin"):
            reasons.append("catalog pin")
        if plan.get("policy_effective") != current.plan.get("policy_effective"):
            reasons.append("policy")
        if not reasons:
            reasons.append("routing decisions")
        raise SpecError(
            "render_plan_stale: plan_hash does not match current inputs "
            f"({', '.join(reasons)} drifted)")
    return current


def explain_plan(plan: dict) -> str:
    validate_render_plan(plan)
    lines = [
        f"render plan {plan_hash(plan)[:16]}",
        "segment layer route decision",
    ]
    for seg in plan.get("segments", []):
        decision = seg.get("decision", {})
        if seg["route"] in {ROUTE_SAMPLE, ROUTE_SYNTHETIC_FALLBACK}:
            detail = (
                f"{decision.get('instrument')} "
                f"{decision.get('requested_articulation')}"
            )
            if decision.get("fallback"):
                detail += f" -> {decision['fallback']['base_articulation']}"
        else:
            detail = str(decision.get("voice", "native"))
        lines.append(
            f"{seg['id']} {seg['layer']} {seg['route']} {detail}".rstrip()
        )
    return "\n".join(lines)
