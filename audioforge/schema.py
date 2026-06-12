"""Spec validation. Fail fast, with paths, before any rendering happens.

Top-level spec shape (JSON):
{
  "id": "brand_signature_v1",          # stable asset identity
  "kind": "signature|sfx|loop|jingle|transition|cue|bed",
  "duration_s": 2.5,
  "sample_rate": 48000,                # optional, default 48000
  "bit_depth": 16 | 24,                # optional, default 24
  "bpm": 120,                          # required if any track uses the grid
  "swing": 0.0,                        # 0..0.5 fraction of a 16th step
  "layers": [ { ...layer... } ],
  "master": { "fx": [...], "target_peak_dbfs": -1.0,
               "fade_in_s": 0, "fade_out_s": 0.05, "stereo_width": 0.4 }
}

Layer shapes (discriminated by "type"):
  tone     – {type, osc, note|freq_hz, duration_s?, env, detune_cents?,
              fm_ratio?, fm_index?, gain_db?, pan?, start_s?, fx?}
  sweep    – {type, shape, f_start_hz, f_end_hz, curve?, env, ...}
  noise    – {type, color, env, ...}
  drums    – {type, voice, pattern, gain_db?, pan?, fx?}
  notes    – {type, osc, notes[], env?, loop_beats?, gain_db?, pan?, fx?}
"""
from __future__ import annotations

import re

from .curves import (
    CURVE_UNSUPPORTED_VOICE_CODE,
    LAYER_TIME_BASES,
    NOTE_TIME_BASES,
    PERFORMANCE_CURVE_TARGETS,
    PHYSICAL_MODEL_OSCILLATORS,
    CurveError,
    validate_curve,
)
from . import theory

KINDS = {"signature", "sfx", "loop", "jingle", "transition", "cue", "bed",
         "soundtrack"}
LAYER_TYPES = {"tone", "sweep", "noise", "drums", "notes",
               "grain", "sample", "foley", "instrument"}
NOISE_COLORS = {"white", "pink", "brown"}
# Voices whose render path is the native C kernel — sequential nonlinear /
# time-varying DSP that NumPy can't express. Single source of truth: the
# readiness gate in resolve.py keys off this set (not a private literal), so
# adding a kernel voice here can't silently bypass the fail-loud "no compiler"
# check. The matching dispatch in synth.osc() and binding in _native.py are
# guarded by tests/test_contract so the three can't drift apart.
NATIVE_OSC_SHAPES = {"bowed", "blown", "brass", "struck", "sympathetic"}
OSC_SHAPES = {"sine", "saw", "square", "triangle", "fm", "organ",
              "pad", "pluck", "modal", "morph"} | NATIVE_OSC_SHAPES
# Effects whose render path is the native C kernel — same rationale and
# single-source discipline as NATIVE_OSC_SHAPES. `fx_needs_native()` below is
# the one predicate the resolve readiness gate calls, so a native effect can't
# silently bypass the fail-loud "no compiler" check.
NATIVE_FX_TYPES = {"ladder", "tape"}
FX_TYPES = {"filter", "delay", "reverb", "hall", "plate", "fdn",
            "comp", "mbcomp", "drive", "tremolo", "gain",
            "peak", "lowshelf", "highshelf", "transient", "saturate",
            "convolve"} | NATIVE_FX_TYPES


def fx_needs_native(fx: dict) -> bool:
    """Whether an fx dict can only be rendered by the native kernel. The plate
    is LTI (a cached impulse response) unless its swept-allpass modulation is
    engaged (mod > 0); everything in NATIVE_FX_TYPES is native unconditionally."""
    t = fx.get("type")
    if t in NATIVE_FX_TYPES:
        return True
    return t == "plate" and float(fx.get("mod", 0.0)) > 0.0
BIT_DEPTHS = {16, 24}
BASE_AUTOMATION_TARGETS = {"gain_db", "cutoff_hz", "scan"}
AUTO_TARGETS = BASE_AUTOMATION_TARGETS | PERFORMANCE_CURVE_TARGETS

# Single source of truth for tempo bounds (audit finding F3). The base `bpm` is
# the asset's nominal tempo; a `tempo_map` carries time-varying tempo and is
# deliberately allowed to exceed the base ceiling (e.g. an accelerando), so it
# has its own, looser maximum.
BPM_MIN, BPM_MAX = 20, 300
TEMPO_MAP_BPM_MIN, TEMPO_MAP_BPM_MAX = 20.0, 400.0

# Fx targets whose `cutoff_hz` automation is meaningful (audit finding F12).
CUTOFF_CAPABLE_FX = {"filter", "ladder"}

# Articulations the IR validator accepts. `trill` is authoring-only — it compiles
# away in the DSL — so the DSL set is a structural superset (see dsl.ARTICULATIONS,
# audit finding F6); keeping the relationship structural prevents silent drift.
IR_ARTICULATIONS = {"sustain", "staccato", "spiccato", "pizzicato",
                    "tremolo", "marcato", "legato"}


def _osc_ok(name: str) -> bool:
    from .plugins import OSCILLATORS
    return name in OSC_SHAPES or name in OSCILLATORS


def _fx_ok(name: str) -> bool:
    from .plugins import FX
    return name in FX_TYPES or name in FX


def _voice_ok(name: str) -> bool:
    from .plugins import DRUM_VOICES as PLUGIN_VOICES
    from .sequencer import DRUM_VOICES
    return name in DRUM_VOICES or name in PLUGIN_VOICES


class SpecError(ValueError):
    pass


def _req(d: dict, key: str, path: str):
    if key not in d:
        raise SpecError(f"{path}: missing required field '{key}'")
    return d[key]


def _num(d: dict, key: str, path: str, lo=None, hi=None, required=True, default=None):
    if key not in d:
        if required:
            raise SpecError(f"{path}: missing required field '{key}'")
        return default
    v = d[key]
    if not isinstance(v, (int, float)) or isinstance(v, bool):
        raise SpecError(f"{path}.{key}: expected a number, got {type(v).__name__}")
    if lo is not None and v < lo:
        raise SpecError(f"{path}.{key}: {v} below minimum {lo}")
    if hi is not None and v > hi:
        raise SpecError(f"{path}.{key}: {v} above maximum {hi}")
    return v


def _validate_fx(chain, path):
    if not isinstance(chain, list):
        raise SpecError(f"{path}: fx must be a list")
    for i, fx in enumerate(chain):
        p = f"{path}[{i}]"
        t = _req(fx, "type", p)
        if not _fx_ok(t):
            raise SpecError(f"{p}: unknown fx type '{t}' "
                            f"(built-in: {sorted(FX_TYPES)}; or a registered plugin)")
        if t == "filter":
            mode = _req(fx, "mode", p)
            if mode not in {"lowpass", "highpass", "bandpass"}:
                raise SpecError(f"{p}.mode: '{mode}' invalid")
            _num(fx, "cutoff_hz", p, 10, 24000)
        if t == "delay":
            _num(fx, "time_s", p, 0.001, 5.0)
            _num(fx, "feedback", p, 0.0, 0.95, required=False)
            _num(fx, "mix", p, 0.0, 1.0, required=False)
        if t == "reverb":
            _num(fx, "decay_s", p, 0.05, 15.0, required=False)
            _num(fx, "mix", p, 0.0, 1.0, required=False)
        if t == "ladder":
            _num(fx, "cutoff_hz", p, 20, 20000)
            _num(fx, "resonance", p, 0.0, 1.1, required=False)
            _num(fx, "drive", p, 0.0, 1.0, required=False)
            _num(fx, "mix", p, 0.0, 1.0, required=False)
        if t == "tape":
            _num(fx, "drive", p, 0.0, 1.0, required=False)
            _num(fx, "flutter", p, 0.0, 1.0, required=False)
            _num(fx, "tone", p, 0.0, 1.0, required=False)
            _num(fx, "mix", p, 0.0, 1.0, required=False)


def _validate_env(env, path):
    # attack/decay/release are times in seconds; sustain is a level in 0..1
    # (the DSL `s=0.7`, style packs and synth all treat it that way) — bounding
    # it like a time let nonsense such as `sustain: 37` through (audit F4).
    for k in ("attack", "decay", "release"):
        _num(env, k, path, 0.0, 60.0)
    _num(env, "sustain", path, 0.0, 1.0)


def _validate_automation(autos, path, fx_chain, *, scope="layer",
                         layer_type=None, osc=None):
    if not isinstance(autos, list):
        raise SpecError(f"{path}: automation must be a list")
    fx_chain = fx_chain if isinstance(fx_chain, list) else []
    allowed_targets = set(BASE_AUTOMATION_TARGETS)
    if scope == "layer":
        allowed_targets |= PERFORMANCE_CURVE_TARGETS
    for i, au in enumerate(autos):
        p = f"{path}[{i}]"
        tgt = _req(au, "target", p)
        try:
            validate_curve(
                au,
                p,
                allowed_targets=allowed_targets,
                allowed_time_bases=LAYER_TIME_BASES,
                min_points=2 if tgt in BASE_AUTOMATION_TARGETS else 1,
            )
        except CurveError as exc:
            raise SpecError(str(exc)) from exc
        if tgt == "pitch_cents" and osc in PHYSICAL_MODEL_OSCILLATORS:
            raise SpecError(
                f"{p}: {CURVE_UNSUPPORTED_VOICE_CODE}: pitch_cents curves "
                f"are not yet supported for '{osc}'")
        if tgt == "cutoff_hz":
            # Must point at a real, cutoff-capable fx — not merely "some fx
            # chain exists" (audit F12).
            idx = au.get("fx_index", 0)
            if not (isinstance(idx, int) and 0 <= idx < len(fx_chain)):
                raise SpecError(
                    f"{p}: cutoff_hz automation fx_index {idx} is out of range "
                    f"for an fx chain of length {len(fx_chain)}")
            ftype = fx_chain[idx].get("type")
            if ftype not in CUTOFF_CAPABLE_FX:
                raise SpecError(
                    f"{p}: cutoff_hz automation targets fx_index {idx} of type "
                    f"'{ftype}', which has no cutoff (need one of "
                    f"{sorted(CUTOFF_CAPABLE_FX)})")


_VOICE_RANGES = {
    "unison": (1, 16), "spread_cents": (0.0, 200.0),
    "bandwidth_cents": (1.0, 300.0), "harmonics": (1, 256),
    "damping": (0.0, 1.0), "brightness": (0.0, 1.0),
    "pluck_pos": (0.02, 0.5), "mode_decay_s": (0.01, 30.0),
    "tension": (0.0, 1.0), "strike": (0.0, 1.0), "lip": (0.0, 1.0),
    "coupling": (0.0, 1.0), "buzz": (0.0, 1.0),
}


def _validate_new_voices(layer: dict, p: str):
    modes = layer.get("modes")
    if modes is not None:
        if (not isinstance(modes, list) or not 1 <= len(modes) <= 32
                or not all(isinstance(m, list) and len(m) == 3
                           for m in modes)):
            raise SpecError(f"{p}.modes: needs 1..32 [ratio, amp, t60_share]"
                            f" triplets")
        for j, (r, a, t) in enumerate(modes):
            if not (0.05 <= r <= 40.0):
                raise SpecError(f"{p}.modes[{j}]: ratio {r} outside 0.05..40")
            if not (0.0 <= a <= 2.0):
                raise SpecError(f"{p}.modes[{j}]: amp {a} outside 0..2")
            if not (0.01 <= t <= 3.0):
                raise SpecError(f"{p}.modes[{j}]: t60 share {t} outside "
                                f"0.01..3")
    _num(layer, "scan", p, 0.0, 1.0, required=False)
    _num(layer, "pressure", p, 0.2, 1.0, required=False)
    _num(layer, "bow_position", p, 0.05, 0.45, required=False)


def _validate_note_events(layer: dict, p: str):
    notes = _req(layer, "notes", p)
    if not isinstance(notes, list) or not notes:
        raise SpecError(f"{p}.notes: must be a non-empty list")
    osc = layer.get("osc")
    for j, ev in enumerate(notes):
        ep = f"{p}.notes[{j}]"
        if "note" not in ev and "freq_hz" not in ev:
            raise SpecError(f"{ep}: needs 'note' or 'freq_hz'")
        _num(ev, "start_beat", ep, 0.0)
        _num(ev, "dur_beats", ep, 1e-3)
        art = ev.get("art")
        if art is not None and art not in IR_ARTICULATIONS:
            raise SpecError(f"{ep}.art: '{art}' is not one of "
                            f"{sorted(IR_ARTICULATIONS)}")
        s = ev.get("slur")
        if s is not None and (not isinstance(s, int) or s < 1):
            raise SpecError(f"{ep}.slur: positive integer group id")
        curves = ev.get("curves")
        if curves is not None:
            if not isinstance(curves, list) or not curves:
                raise SpecError(f"{ep}.curves: non-empty list")
            dynamic_seen = False
            for k, curve in enumerate(curves):
                cp = f"{ep}.curves[{k}]"
                target = curve.get("target") if isinstance(curve, dict) else None
                if target == "dynamic":
                    if dynamic_seen:
                        raise SpecError(f"{cp}: duplicate dynamic curve in note scope")
                    dynamic_seen = True
                try:
                    validate_curve(
                        curve,
                        cp,
                        allowed_targets=PERFORMANCE_CURVE_TARGETS,
                        allowed_time_bases=NOTE_TIME_BASES,
                    )
                except CurveError as exc:
                    raise SpecError(str(exc)) from exc
                if target == "pitch_cents" and osc in PHYSICAL_MODEL_OSCILLATORS:
                    raise SpecError(
                        f"{cp}: {CURVE_UNSUPPORTED_VOICE_CODE}: pitch_cents "
                        f"curves are not yet supported for '{osc}'")
    dyn = layer.get("dynamic")
    if dyn is not None:
        if not isinstance(dyn, list) or not dyn:
            raise SpecError(f"{p}.dynamic: non-empty [beat, 0..1] list")
        prev = -1.0
        for k, pt in enumerate(dyn):
            if (not isinstance(pt, list) or len(pt) != 2
                    or pt[0] < prev or not 0.0 <= pt[1] <= 1.0):
                raise SpecError(f"{p}.dynamic[{k}]: ascending beats, "
                                f"values 0..1")
            prev = pt[0]


def _validate_orchestration(layer: dict, p: str):
    orch = layer.get("orchestration")
    if orch is None:
        return
    if not isinstance(orch, dict):
        raise SpecError(f"{p}.orchestration: object")
    hard = orch.get("hard_range", {})
    arts = set(orch.get("articulations", []))
    art = layer.get("articulation", "sustain")
    if arts and art not in arts:
        raise SpecError(
            f"{p}.articulation: unavailable articulation '{art}' "
            f"(available: {sorted(arts)})"
        )
    if hard:
        from .theory import note_to_semis
        low = int(hard["low_midi"])
        high = int(hard["high_midi"])
        for idx, ev in enumerate(layer.get("notes", [])):
            if "note" not in ev:
                continue
            midi = note_to_semis(ev["note"]) + 12
            if midi < low or midi > high:
                raise SpecError(
                    f"{p}.notes[{idx}].note: {ev['note']} outside hard range "
                    f"{hard.get('low_note', low)}..{hard.get('high_note', high)}"
                )


def _validate_performance(layer: dict, p: str):
    hum = layer.get("humanize")
    if hum is not None:
        if not isinstance(hum, dict):
            raise SpecError(f"{p}.humanize: must be an object")
        _num(hum, "timing_s", f"{p}.humanize", 0.0, 0.06, required=False)
        _num(hum, "vel", f"{p}.humanize", 0.0, 0.5, required=False)
    vib = layer.get("vibrato")
    if vib is not None:
        if not isinstance(vib, dict):
            raise SpecError(f"{p}.vibrato: must be an object")
        _num(vib, "rate_hz", f"{p}.vibrato", 0.1, 12.0, required=False)
        _num(vib, "depth_cents", f"{p}.vibrato", 0.0, 100.0, required=False)
        _num(vib, "delay_s", f"{p}.vibrato", 0.0, 5.0, required=False)
    _num(layer, "glide_s", p, 0.0, 1.0, required=False)
    _num(layer, "vel_brightness", p, 0.0, 1.0, required=False)


def _validate_voice(layer: dict, p: str):
    from .synth import MODAL_MATERIALS
    for k, (lo, hi) in _VOICE_RANGES.items():
        if k in layer:
            v = layer[k]
            if not isinstance(v, (int, float)) or not (lo <= v <= hi):
                raise SpecError(f"{p}.{k}: must be a number in {lo}..{hi}")
    if "material" in layer and layer["material"] not in MODAL_MATERIALS:
        raise SpecError(f"{p}.material: unknown "
                        f"(allowed: {sorted(MODAL_MATERIALS)})")


def validate_spec(spec: dict) -> dict:
    if not isinstance(spec, dict):
        raise SpecError("spec: must be a JSON object")
    sid = _req(spec, "id", "spec")
    if not isinstance(sid, str) or not sid:
        raise SpecError("spec.id: must be a non-empty string")
    kind = _req(spec, "kind", "spec")
    if kind not in KINDS:
        raise SpecError(f"spec.kind: '{kind}' invalid (allowed: {sorted(KINDS)})")
    _num(spec, "duration_s", "spec", 0.05, 600.0)
    sr = int(_num(spec, "sample_rate", "spec", 8000, 192000,
                  required=False, default=48000))
    bd = int(_num(spec, "bit_depth", "spec", required=False, default=24))
    if bd not in BIT_DEPTHS:
        raise SpecError(f"spec.bit_depth: {bd} invalid (allowed 16, 24)")
    _num(spec, "swing", "spec", 0.0, 0.5, required=False)

    layers = _req(spec, "layers", "spec")
    if not isinstance(layers, list) or not layers:
        raise SpecError("spec.layers: must be a non-empty list")

    # Compute grid usage once, up front — `instrument` layers are validated in a
    # second pass below, so deferring this let an instrument-only spec skip the
    # `bpm` requirement entirely (audit finding F1).
    GRID_LAYER_TYPES = {"drums", "notes", "instrument"}
    uses_grid = any(isinstance(l, dict) and l.get("type") in GRID_LAYER_TYPES
                    for l in layers)
    for i, layer in enumerate(layers):
        p = f"spec.layers[{i}]"
        t = _req(layer, "type", p)
        if t not in LAYER_TYPES:
            raise SpecError(f"{p}.type: '{t}' invalid (allowed: {sorted(LAYER_TYPES)})")
        _num(layer, "pan", p, -1.0, 1.0, required=False)
        _num(layer, "start_s", p, 0.0, 600.0, required=False)
        if "fx" in layer:
            _validate_fx(layer["fx"], f"{p}.fx")
        if t == "tone":
            nt = layer.get("note")
            # Shared single-octave-digit pitch grammar (audit F13): the local
            # multi-digit regex here once diverged from the DSL's NOTE_RE.
            if nt is not None and not theory.NOTE_RE.match(str(nt)):
                raise SpecError(
                    f"{p}.note: tone layers take a single pitch (e.g. Bb2)."
                    f" '{nt}' looks like a chord — use a notes layer with a"
                    f" chord event (e.g. Bb2maj @ 0b for 8b) instead")
            if not _osc_ok(layer.get("osc", "sine")):
                raise SpecError(f"{p}.osc: invalid shape")
            _validate_voice(layer, p)
            _validate_performance(layer, p)
            _validate_new_voices(layer, p)
            if "note" not in layer and "freq_hz" not in layer:
                raise SpecError(f"{p}: tone needs 'note' or 'freq_hz'")
            _validate_env(_req(layer, "env", p), f"{p}.env")
        elif t == "sweep":
            _num(layer, "f_start_hz", p, 1, 24000)
            _num(layer, "f_end_hz", p, 1, 24000)
            _validate_env(_req(layer, "env", p), f"{p}.env")
        elif t == "noise":
            if _req(layer, "color", p) not in NOISE_COLORS:
                raise SpecError(f"{p}.color: invalid")
            _validate_env(_req(layer, "env", p), f"{p}.env")
        elif t == "drums":
            if not _voice_ok(_req(layer, "voice", p)):
                raise SpecError(f"{p}.voice: invalid drum voice")
            _validate_performance(layer, p)
            _num(layer, "tune_st", p, -12.0, 12.0, required=False)
            _num(layer, "decay", p, 0.25, 4.0, required=False)
            _num(layer, "snap", p, 0.0, 1.0, required=False)
            _num(layer, "bend", p, 0.0, 1.5, required=False)
            pat = _req(layer, "pattern", p).replace(" ", "")
            if not pat or any(c not in "xX." for c in pat):
                raise SpecError(f"{p}.pattern: only 'x', 'X', '.' allowed")
        elif t == "notes":
            _num(layer, "phrasing", p, 0.0, 1.0, required=False)
            if not _osc_ok(layer.get("osc", "sine")):
                raise SpecError(f"{p}.osc: invalid shape")
            _validate_voice(layer, p)
            _validate_performance(layer, p)
            _validate_note_events(layer, p)
            if "env" in layer:
                _validate_env(layer["env"], f"{p}.env")

        seat = layer.get("seat")
        if seat is not None:
            if spec.get("stage") is None:
                raise SpecError(f"{p}.seat: needs a stage block on the "
                                f"asset")
            _num(seat, "az_deg", f"{p}.seat", -60.0, 60.0)
            _num(seat, "dist_m", f"{p}.seat", 1.0, 60.0)
            if "bus" in layer:
                raise SpecError(f"{p}: seat and bus are mutually exclusive "
                                f"— the stage is the staged layer's bus")
        if "automation" in layer:
            _validate_automation(layer["automation"], f"{p}.automation",
                                 layer.get("fx"), scope="layer",
                                 layer_type=t, osc=layer.get("osc"))

    for i, layer in enumerate(spec.get("layers", [])):
        p = f"layers[{i}]"
        t = layer.get("type")
        if t == "grain":
            srcname = layer.get("source", "pad")
            if srcname not in ("white", "pink", "brown") \
                    and not _osc_ok(srcname):
                raise SpecError(f"{p}.source: '{srcname}' is neither an "
                                f"oscillator nor a noise color")
            if srcname not in ("white", "pink", "brown") \
                    and "note" not in layer and "freq_hz" not in layer:
                raise SpecError(f"{p}: grain source '{srcname}' needs note "
                                f"or freq_hz")
            _num(layer, "grain_s", p, 0.005, 0.5, required=False)
            _num(layer, "density", p, 1.0, 200.0, required=False)
            _num(layer, "pitch_spread_cents", p, 0.0, 1200.0, required=False)
            _num(layer, "scatter", p, 0.0, 1.0, required=False)
            _num(layer, "source_dur_s", p, 0.25, 10.0, required=False)
            if "env" not in layer:
                raise SpecError(f"{p}: grain layer needs env")
            _validate_new_voices(layer, p)
        elif t == "instrument":
            if spec.get("library") is None:
                raise SpecError(
                    f"{p}: instrument layers need a spec-level library "
                    f"reference (library: \"name@manifest_hash\")")
            if not layer.get("instrument"):
                raise SpecError(f"{p}.instrument: required (name in the "
                                f"library manifest)")
            _validate_note_events(layer, p)
            _validate_performance(layer, p)
            art = layer.get("articulation", "sustain")
            if art not in IR_ARTICULATIONS:
                raise SpecError(f"{p}.articulation: '{art}' is not one of "
                                f"{sorted(IR_ARTICULATIONS)}")
            _validate_orchestration(layer, p)
            sec = layer.get("section")
            if sec is not None:
                if not isinstance(sec, dict):
                    raise SpecError(f"{p}.section: object")
                _num(sec, "size", f"{p}.section", 2, 24)
                _num(sec, "spread", f"{p}.section", 0.0, 1.0,
                     required=False)
                _num(sec, "detune_c", f"{p}.section", 0.0, 30.0,
                     required=False)
                _num(sec, "timing_s", f"{p}.section", 0.0, 0.04,
                     required=False)
            _num(layer, "legato_s", p, 0.02, 0.15, required=False)
            _num(layer, "phrasing", p, 0.0, 1.0, required=False)
        elif t == "foley":
            from .foley import FOLEY_MODELS
            if layer.get("model") not in FOLEY_MODELS:
                raise SpecError(f"{p}.model: needs one of "
                                f"{sorted(FOLEY_MODELS)}")
            _num(layer, "intensity", p, 0.0, 1.0, required=False)
            _num(layer, "brightness", p, 0.0, 1.0, required=False)
        elif t == "sample":
            f = layer.get("file")
            if not isinstance(f, str) or not f:
                raise SpecError(f"{p}.file: required string")
            h = layer.get("sha256", "")
            if not (isinstance(h, str) and len(h) == 64
                    and all(c in "0123456789abcdefABCDEF" for c in h)):
                raise SpecError(f"{p}.sha256: required 64-char hex hash — "
                                f"pin the sample's content identity")
            _num(layer, "pitch_st", p, -24.0, 24.0, required=False)
            if "pattern" in layer and not isinstance(layer["pattern"], str):
                raise SpecError(f"{p}.pattern: must be a string")

    buses = spec.get("buses", [])
    if not isinstance(buses, list):
        raise SpecError("spec.buses: must be a list")
    seen_buses: list[str] = []
    layer_names = {ly.get("name", f"layer{j}")
                   for j, ly in enumerate(spec.get("layers", []))}
    for i, b in enumerate(buses):
        p = f"buses[{i}]"
        name = b.get("name")
        if not isinstance(name, str) or not name:
            raise SpecError(f"{p}.name: required")
        if name in seen_buses:
            raise SpecError(f"{p}: duplicate bus name '{name}'")
        _num(b, "gain_db", p, -60.0, 12.0, required=False)
        d = b.get("duck")
        if d is not None:
            srcn = d.get("source", "")
            ok = srcn in layer_names or (
                srcn.startswith("bus:") and srcn[4:] in seen_buses)
            if not ok:
                raise SpecError(
                    f"{p}.duck.source: '{srcn}' must be a layer name or "
                    f"'bus:<name>' of a bus declared earlier (no cycles)")
            _num(d, "amount_db", f"{p}.duck", 0.0, 24.0, required=False)
            _num(d, "threshold_db", f"{p}.duck", -80.0, 0.0, required=False)
            _num(d, "attack_s", f"{p}.duck", 0.001, 0.5, required=False)
            _num(d, "release_s", f"{p}.duck", 0.01, 2.0, required=False)
        seen_buses.append(name)
    for j, ly in enumerate(spec.get("layers", [])):
        bref = ly.get("bus")
        if bref is not None and bref not in seen_buses:
            raise SpecError(f"layers[{j}].bus: unknown bus '{bref}' "
                            f"(declared: {seen_buses})")

    stg = spec.get("stage")
    if stg is not None:
        if not isinstance(stg, dict) or not stg.get("hall_file") \
                or not isinstance(stg.get("hall_sha256"), str) \
                or len(stg["hall_sha256"]) != 64:
            raise SpecError('spec.stage: needs hall_file + full 64-hex '
                            'hall_sha256 (content-addressed IR)')
        mics = stg.get("mics", {})
        for m, v in mics.items():
            if m not in ("tree", "close", "ambient") \
                    or not 0.0 <= float(v) <= 1.5:
                raise SpecError(f"spec.stage.mics.{m}: 0..1.5")
        dims = stg.get("dims", [18.0, 26.0, 10.0])
        if (not isinstance(dims, list) or len(dims) != 3
                or not all(3.0 <= float(d) <= 80.0 for d in dims)):
            raise SpecError("spec.stage.dims: [W, L, H] in 3..80 m")
    lib = spec.get("library")
    if lib is not None:
        if (not isinstance(lib, dict) or not lib.get("name")
                or not isinstance(lib.get("manifest_sha256"), str)
                or len(lib["manifest_sha256"]) < 12):
            raise SpecError(
                'spec.library: {"name": ..., "manifest_sha256": ...} — '
                'pin the orchestra manifest hash (full 64-hex preferred)')
    v = spec.get("variant")
    if v is not None and not isinstance(v, (str, int)):
        raise SpecError("spec.variant: string or integer tag")
    _num(spec, "intensity_scale", "spec", 0.0, 1.5, required=False)
    cds = spec.get("cutdowns")
    if cds is not None:
        if not isinstance(cds, list) or not cds:
            raise SpecError("spec.cutdowns: non-empty list")
        dur = spec["duration_s"]
        for i, cd in enumerate(cds):
            p = f"cutdowns[{i}]"
            _num(cd, "length_s", p, 1.0, 600.0)
            _num(cd, "fade_s", p, 0.05, 3.0, required=False)
            segs = cd.get("segments")
            if not isinstance(segs, list) or not segs:
                raise SpecError(f"{p}.segments: need at least one keep window")
            total = 0.0
            for s in segs:
                if (not isinstance(s, list) or len(s) != 2
                        or not 0 <= s[0] < s[1] <= dur):
                    raise SpecError(f"{p}: keep windows must satisfy "
                                    f"0 <= start < end <= duration ({dur}s)")
                total += s[1] - s[0]
            fade = cd.get("fade_s", 0.5)
            assembled = total - fade * (len(segs) - 1)
            if abs(assembled - cd["length_s"]) > 1.0:
                raise SpecError(
                    f"{p}: keep windows assemble to {assembled:.1f}s but the "
                    f"cutdown is declared {cd['length_s']}s — adjust windows "
                    f"or the declared length (tolerance 1s)")

    tmap = spec.get("tempo_map")
    if tmap is not None:
        if (not isinstance(tmap, list) or len(tmap) < 1
                or not all(isinstance(x, list) and len(x) == 2 for x in tmap)):
            raise SpecError("spec.tempo_map: list of [beat, bpm] pairs")
        last = -1.0
        for b, v in tmap:
            if b < last:
                raise SpecError("spec.tempo_map: beats must ascend")
            if not (TEMPO_MAP_BPM_MIN <= v <= TEMPO_MAP_BPM_MAX):
                raise SpecError(f"spec.tempo_map: bpm {v} outside "
                                f"{TEMPO_MAP_BPM_MIN:g}..{TEMPO_MAP_BPM_MAX:g}")
            last = b
        if tmap[0][0] != 0.0:
            raise SpecError("spec.tempo_map: first point must be at beat 0")

    holds = spec.get("holds")
    if holds is not None:
        if (not isinstance(holds, list)
                or not all(isinstance(x, dict) for x in holds)):
            raise SpecError("spec.holds: list of {beat, duration_s} events")
        last = -1.0
        for idx, hold in enumerate(holds):
            p = f"spec.holds[{idx}]"
            _num(hold, "beat", p, 0.0, required=True)
            _num(hold, "duration_s", p, 0.0, required=True)
            if hold["duration_s"] <= 0.0:
                raise SpecError(f"{p}.duration_s: must be > 0")
            if hold["beat"] < last:
                raise SpecError("spec.holds: beats must ascend")
            last = hold["beat"]

    groove = spec.get("groove")
    if groove is not None:
        if not isinstance(groove, dict):
            raise SpecError("spec.groove: must be an object")
        for key, lo, hi in (("timing", -0.5, 0.5), ("accent", 0.25, 2.0)):
            arr = groove.get(key)
            if arr is not None:
                if (not isinstance(arr, list) or len(arr) != 16
                        or not all(isinstance(x, (int, float))
                                   and lo <= x <= hi for x in arr)):
                    raise SpecError(f"spec.groove.{key}: needs 16 numbers "
                                    f"in {lo}..{hi}")

    for i, m in enumerate(spec.get("markers", [])):
        p = f"spec.markers[{i}]"
        if not isinstance(_req(m, "name", p), str):
            raise SpecError(f"{p}.name: must be a string")
        _num(m, "time_s", p, 0.0, spec["duration_s"])

    emotion = spec.get("emotion", {})
    if not isinstance(emotion, dict):
        raise SpecError("spec.emotion: must be an object of name -> 0..1")
    for k, v in emotion.items():
        if not isinstance(v, (int, float)) or not (0.0 <= v <= 1.0):
            raise SpecError(f"spec.emotion.{k}: must be a number in 0..1")

    master = spec.get("master", {})
    if "fx" in master:
        _validate_fx(master["fx"], "spec.master.fx")
    if "automation" in master:
        _validate_automation(master["automation"], "spec.master.automation",
                             master.get("fx"), scope="master")
    _num(master, "target_peak_dbfs", "spec.master", -40.0, 0.0, required=False)
    _num(master, "target_lufs", "spec.master", -40.0, -5.0, required=False)
    _num(master, "stereo_width", "spec.master", 0.0, 1.0, required=False)

    # Grid-using specs (drums/notes/instrument) require a base tempo. Checked at
    # the end so each layer's own diagnostics surface first, and so an
    # instrument-only spec — validated in the second layer pass above — can no
    # longer slip through without a bpm (audit finding F1).
    if uses_grid:
        _num(spec, "bpm", "spec", BPM_MIN, BPM_MAX)

    if spec.get("loop_safe"):
        if not spec.get("bpm"):
            raise SpecError("spec.loop_safe: requires bpm")
        beat_s = 60.0 / spec["bpm"]
        beats = spec["duration_s"] / beat_s
        if abs(beats - round(beats)) > 1e-6:
            raise SpecError(
                f"spec.loop_safe: duration_s={spec['duration_s']} is "
                f"{beats:.4f} beats at {spec['bpm']} bpm — must be a whole "
                f"number of beats for a seamless loop")
    return spec
