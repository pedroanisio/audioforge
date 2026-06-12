import json
from pathlib import Path

import numpy as np
import pytest

from audioforge.agent_tools import run_tool, tool_schemas
from audioforge.capabilities import capability_manifest
from audioforge.interop import export_session_bundle
from audioforge.ir_schema import ir_json_schema
from audioforge.plan import (
    RENDER_PLAN_SCHEMA_VERSION,
    build_render_plan,
    dumps_plan,
    explain_plan,
    load_plan_json,
    plan_hash,
    plan_sha256_file_payload,
    validate_render_plan,
    verify_plan_for_spec,
)
from audioforge.render import render_to_wav
from audioforge.sdk import AudioAsset
from audioforge.schema import SpecError, validate_spec
from audioforge.determinism import rng_for, spec_hash
from audioforge.library import load_library
from audioforge.sequencer import TempoMap
from test_sampler import build_library


def _instrument_spec(pin: str, *, art: str = "sustain") -> dict:
    return {
        "id": "plan_inst",
        "kind": "cue",
        "duration_s": 2.0,
        "bpm": 120,
        "library": {"name": "minilib", "manifest_sha256": pin},
        "layers": [{
            "name": "vln",
            "type": "instrument",
            "instrument": "testviolin",
            "articulation": art,
            "notes": [{"note": "C4", "start_beat": 0.0,
                       "dur_beats": 1.0, "vel": 0.9}],
        }],
        "master": {"target_peak_dbfs": -1.0},
    }


def _mixed_spec(pin: str) -> dict:
    spec = _instrument_spec(pin, art="staccato")
    spec["id"] = "plan_mixed"
    spec["layers"].append({
        "name": "lead",
        "type": "notes",
        "osc": "sine",
        "env": {"attack": 0.01, "decay": 0.1,
                "sustain": 0.8, "release": 0.1},
        "notes": [{"note": "E4", "start_beat": 0.5, "dur_beats": 1.0}],
    })
    return spec


@pytest.fixture
def pin(tmp_path: Path) -> str:
    return build_library(tmp_path / "minilib")


def test_render_plan_is_canonical_deterministic_and_hashable(pin):
    spec = _mixed_spec(pin)
    first = build_render_plan(spec)
    second = build_render_plan(json.loads(json.dumps(spec)))

    assert first.plan["schema"] == RENDER_PLAN_SCHEMA_VERSION
    assert first.plan_hash == second.plan_hash
    assert dumps_plan(first.plan) == dumps_plan(second.plan)
    loaded = load_plan_json(dumps_plan(first.plan))
    assert loaded["plan_hash"] == first.plan_hash
    assert plan_hash(loaded) == first.plan_hash


def test_render_plan_records_sample_fallback_and_synth_native_routes(pin):
    result = build_render_plan(_mixed_spec(pin))
    routes = {seg["id"]: seg["route"] for seg in result.plan["segments"]}

    assert routes["seg:vln:0"] == "synthetic_fallback"
    assert routes["seg:lead:0"] == "synth_native"

    fallback = result.plan["segments"][0]
    assert fallback["decision"]["fallback"]["requested_articulation"] == "staccato"
    assert fallback["decision"]["fallback"]["base_articulation"] == "sustain"
    assert fallback["evidence"]["library"]["manifest_sha256"] == pin
    assert fallback["decision"]["velocity"]["selected_regions"]
    assert fallback["cost"] == {"estimated_ms": None}

    native = result.plan["segments"][1]
    assert native["decision"]["voice"] == "sine"
    assert native["evidence"]["layer_type"] == "notes"


def test_render_plan_policy_forbid_fails_before_render(pin):
    spec = _instrument_spec(pin, art="staccato")
    spec["routing"] = {"fallbacks": "forbid"}

    with pytest.raises(SpecError, match="render_plan_policy_fallback_forbid"):
        build_render_plan(spec)


def test_routing_policy_validates_in_spec_schema(pin):
    spec = _instrument_spec(pin)
    spec["routing"] = {"fallbacks": "maybe"}
    with pytest.raises(SpecError, match="spec.routing.fallbacks"):
        validate_spec(spec)


def test_routing_policy_helper_rejects_bad_thresholds(pin):
    from audioforge.plan import normalize_routing_policy

    spec = _instrument_spec(pin)
    spec["routing"] = {"fallbacks": "allow", "stretch_warn_semitones": "wide"}
    with pytest.raises(SpecError, match="stretch_warn_semitones"):
        normalize_routing_policy(spec)

    spec["routing"] = {"fallbacks": "allow", "stretch_warn_semitones": -1}
    with pytest.raises(SpecError, match="must be >= 0"):
        normalize_routing_policy(spec)


def test_render_plan_verify_refuses_stale_policy(pin):
    spec = _instrument_spec(pin)
    result = build_render_plan(spec)
    changed = json.loads(json.dumps(spec))
    changed["routing"] = {"fallbacks": "warn"}

    with pytest.raises(SpecError, match="policy"):
        verify_plan_for_spec(changed, result.plan)


def test_render_plan_warn_policy_records_diagnostics(pin):
    spec = _instrument_spec(pin, art="staccato")
    spec["layers"][0]["notes"][0]["note"] = "D4"
    spec["routing"] = {"fallbacks": "warn", "stretch_warn_semitones": 0}
    result = build_render_plan(spec)
    segment = result.plan["segments"][0]
    codes = {d["code"] for d in segment["diagnostics"]}
    assert "render_plan_policy_fallback_warn" in codes
    assert "render_plan_stretch_warn" in codes
    assert any(d["code"] == "render_plan_policy_fallback_warn"
               for d in result.diagnostics)


def test_render_plan_dynamic_crossfade_and_section_rng_path(pin):
    spec = _instrument_spec(pin)
    spec["layers"][0]["section"] = {"size": 2}
    spec["layers"][0]["dynamic"] = [[0.0, 0.0], [1.0, 1.0]]
    result = build_render_plan(spec)
    velocity = result.plan["segments"][0]["decision"]["velocity"]
    assert velocity["mode"] == "dynamic_crossfade"
    assert velocity["bands"]


def test_render_plan_no_region_covering_note_fails(pin):
    spec = _instrument_spec(pin)
    spec["layers"][0]["notes"][0]["note"] = "C8"
    with pytest.raises(SpecError, match="no SFZ region covering"):
        build_render_plan(spec)


def test_render_plan_explain_is_stable_table(pin):
    text = explain_plan(build_render_plan(_mixed_spec(pin)).plan)
    assert "segment layer route decision" in text
    assert "seg:vln:0 vln synthetic_fallback testviolin staccato -> sustain" in text


def test_render_plan_file_payload_hash(pin):
    plan = build_render_plan(_instrument_spec(pin)).plan
    text = dumps_plan(plan)
    assert plan_sha256_file_payload(plan) == __import__("hashlib").sha256(
        text.encode("utf-8")
    ).hexdigest()


def test_render_plan_schema_validation_errors(pin):
    plan = build_render_plan(_instrument_spec(pin)).plan

    with pytest.raises(SpecError, match="must be an object"):
        validate_render_plan([])

    bad = dict(plan)
    bad["schema"] = "bad"
    with pytest.raises(SpecError, match="schema"):
        validate_render_plan(bad)

    bad = dict(plan)
    bad.pop("segments")
    with pytest.raises(SpecError, match="missing fields"):
        validate_render_plan(bad)

    bad = json.loads(dumps_plan(plan))
    bad["segments"][0]["route"] = "unknown"
    bad["plan_hash"] = plan_hash(bad)
    with pytest.raises(SpecError, match="unknown"):
        validate_render_plan(bad)

    bad = json.loads(dumps_plan(plan))
    bad["segments"][0]["route"] = "inpaint"
    bad["plan_hash"] = plan_hash(bad)
    with pytest.raises(SpecError, match="inpaint"):
        validate_render_plan(bad)

    bad = json.loads(dumps_plan(plan))
    bad["segments"][0].pop("decision")
    bad["plan_hash"] = plan_hash(bad)
    with pytest.raises(SpecError, match="missing decision"):
        validate_render_plan(bad)

    bad = json.loads(dumps_plan(plan))
    bad["segments"][0]["evidence"] = {}
    bad["plan_hash"] = plan_hash(bad)
    with pytest.raises(SpecError, match="missing_evidence"):
        validate_render_plan(bad)

    bad = json.loads(dumps_plan(plan))
    bad["segments"][0]["cost"] = {}
    bad["plan_hash"] = plan_hash(bad)
    with pytest.raises(SpecError, match="estimated_ms"):
        validate_render_plan(bad)

    bad = json.loads(dumps_plan(plan))
    bad["plan_hash"] = "0" * 64
    with pytest.raises(SpecError, match="plan_hash"):
        validate_render_plan(bad)


def test_render_manifest_and_plan_file_are_written(pin, tmp_path):
    spec = _instrument_spec(pin)
    meta = render_to_wav(spec, tmp_path)

    plan_path = tmp_path / "plan_inst.plan.json"
    manifest_path = tmp_path / "plan_inst.manifest.json"
    assert plan_path.exists()
    assert manifest_path.exists()

    plan = json.loads(plan_path.read_text())
    manifest = json.loads(manifest_path.read_text())
    assert manifest["plan_hash"] == plan["plan_hash"] == meta["plan_hash"]
    assert manifest["plan_file"] == "plan_inst.plan.json"
    assert manifest["plan_sha256"]
    assert set(manifest["plan_segment_actual_ms"]) == {"seg:vln:0"}
    assert manifest["plan_segment_actual_ms"]["seg:vln:0"] >= 0


def test_render_from_plan_refuses_stale_spec(pin, tmp_path):
    spec = _instrument_spec(pin)
    plan_path = tmp_path / "fresh.plan.json"
    plan_path.write_text(dumps_plan(build_render_plan(spec).plan))
    stale = json.loads(json.dumps(spec))
    stale["routing"] = {"fallbacks": "warn"}

    with pytest.raises(SpecError, match="policy"):
        render_to_wav(stale, tmp_path, render_plan=load_plan_json(plan_path.read_text()))


def test_sampler_consumes_planned_static_region_selection(pin, monkeypatch):
    from audioforge import sampler

    spec = _instrument_spec(pin)
    result = build_render_plan(spec)
    lib = load_library(spec["library"])

    def fail_select(*args, **kwargs):
        raise AssertionError("sampler tried to reselect regions after planning")

    monkeypatch.setattr(sampler, "select_regions", fail_select)
    track = spec["layers"][0]
    root = spec_hash(spec)
    out = sampler.render_instrument_track(
        track,
        total_n=48000,
        sr=48000,
        tm=TempoMap([[0.0, 120.0]]),
        rng_factory=lambda sub: rng_for(root, "0:vln", "instrument", sub),
        lib=lib,
        plan_segments=result.plan["segments"],
    )
    assert np.sqrt(np.mean(out ** 2)) > 0.001


def test_sampler_consumes_planned_fallback_without_re_resolving(pin, monkeypatch):
    from audioforge import sampler

    spec = _instrument_spec(pin, art="staccato")
    result = build_render_plan(spec)
    lib = load_library(spec["library"])

    def fail_resolve(*args, **kwargs):
        raise AssertionError("sampler recomputed fallback after planning")

    monkeypatch.setattr(sampler, "resolve_articulation", fail_resolve)
    root = spec_hash(spec)
    report = {}
    out = sampler.render_instrument_track(
        spec["layers"][0],
        total_n=48000,
        sr=48000,
        tm=TempoMap([[0.0, 120.0]]),
        rng_factory=lambda sub: rng_for(root, "0:vln", "instrument", sub),
        lib=lib,
        report=report,
        plan_segments=result.plan["segments"],
    )
    assert np.sqrt(np.mean(out ** 2)) > 0.001
    assert set(report["plan_segment_actual_ms"]) == {"seg:vln:0"}


def test_sampler_plan_authority_matches_legacy_rng_stream(pin):
    from audioforge import sampler

    spec = _instrument_spec(pin, art="staccato")
    result = build_render_plan(spec)
    lib = load_library(spec["library"])
    root = spec_hash(spec)

    def rng(sub: str):
        return rng_for(root, "0:vln", "instrument", sub)

    legacy = sampler.render_instrument_track(
        spec["layers"][0],
        total_n=48000,
        sr=48000,
        tm=TempoMap([[0.0, 120.0]]),
        rng_factory=rng,
        lib=lib,
    )
    planned = sampler.render_instrument_track(
        spec["layers"][0],
        total_n=48000,
        sr=48000,
        tm=TempoMap([[0.0, 120.0]]),
        rng_factory=rng,
        lib=lib,
        plan_segments=result.plan["segments"],
    )

    assert np.array_equal(planned, legacy)


def test_audioasset_plan_matches_core_planner(pin):
    spec = _instrument_spec(pin)
    result = AudioAsset(spec).plan()
    assert result["plan_hash"] == build_render_plan(spec).plan_hash
    assert result["plan"]["schema"] == RENDER_PLAN_SCHEMA_VERSION


def test_agent_tool_plan_operation_returns_artifact(pin):
    spec = _instrument_spec(pin)
    assert "plan" in tool_schemas()
    response = run_tool("plan", {"spec": spec})
    assert response["ok"] is True
    assert response["artifacts"][0]["plan"]["schema"] == RENDER_PLAN_SCHEMA_VERSION
    assert response["artifacts"][0]["plan_hash"]


def test_session_bundle_includes_plan_artifact(pin, tmp_path):
    spec = _instrument_spec(pin)
    manifest = export_session_bundle(spec, tmp_path)
    assert manifest["plan_hash"] == build_render_plan(spec).plan_hash
    assert Path(manifest["files"]["plan"]).is_file()
    assert manifest["sha256"]["plan"]
    assert json.loads((tmp_path / "session.manifest.json").read_text()) == manifest


def test_capability_manifest_and_ir_schema_publish_render_plan_contract():
    cap = capability_manifest()
    assert cap["render_plan"]["schema"] == RENDER_PLAN_SCHEMA_VERSION
    assert set(cap["render_plan"]["routes"]) >= {
        "sample", "synthetic_fallback", "synth_native", "inpaint",
    }
    assert cap["render_plan"]["policy"]["fallbacks"]["enum"] == [
        "allow", "forbid", "warn",
    ]
    assert "plan" in cap["cli"]["commands"]
    assert "render_plan_stale" in cap["diagnostic_codes"]

    schema = ir_json_schema()
    routing = schema["properties"]["routing"]
    assert routing["properties"]["fallbacks"]["enum"] == [
        "allow", "forbid", "warn",
    ]
