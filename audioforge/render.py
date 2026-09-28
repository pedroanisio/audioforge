"""Deterministic renderer.

Pipeline: validate -> hash spec -> render each layer (seeded per layer path)
-> per-layer fx -> pan/mix to stereo -> master fx -> fades -> mastering
-> seeded TPDF dither -> quantize -> WAV + manifest (with output SHA-256).

Determinism contract:
  * no wall-clock, no global RNG, no os.urandom anywhere in the pipeline;
  * every random draw comes from a Generator seeded by
    SHA-256(performance_seed + variant)[component_path];
  * float64 throughout; quantization happens exactly once, at the end;
  * the manifest records spec_hash and output sha256 so CI can verify
    byte-identical reproduction.
"""
from __future__ import annotations

import hashlib
import json
import struct
import wave
from pathlib import Path

import numpy as np

from . import synth, sequencer
from .determinism import ENGINE_VERSION, performance_hash, rng_for, spec_hash
from .fx import apply_fx_chain, gain_fx
from .dynamics import master_loudness
from .schema import validate_spec


class _SampledCurve:
    """A per-sample automation envelope evaluated only where it is read.

    Cutoff automation is consumed at one index per filter block, so building
    the full-length array (and its exp) wasted a pass over every sample.
    Indexing yields exactly what the full array would hold at those indices."""

    def __init__(self, fn, size: int):
        self._fn = fn
        self.size = size

    def __getitem__(self, idx):
        return self._fn(np.asarray(idx))


_AUTOMATION_TARGETS = frozenset({"gain_db", "cutoff_hz", "scan"})
_DB_TO_LN = float(np.log(10.0) / 20.0)


def _automation_envs(layer: dict, total_n: int, sr: int, tm=None,
                     targets=_AUTOMATION_TARGETS):
    """Split a layer/master automation list into (gain_env | None,
    {fx_index: cutoff_env}, scan_env | None), computing only ``targets``."""
    gain_env = None
    cutoff_envs: dict[int, "np.ndarray"] = {}
    scan_env = None
    wanted = [au for au in layer.get("automation", [])
              if au["target"] in targets]
    if not wanted:
        return gain_env, cutoff_envs, scan_env
    from .curves import curve_points, evaluate_curve
    offset = layer.get("start_s", 0)

    def times_at(idx, au):
        seconds = idx / sr
        if au.get("time_basis") != "layer_beats":
            return seconds
        if tm is None:
            raise ValueError("beat-based automation requires the render timeline")
        return tm.beats_at(seconds + offset) - tm.beat_at(offset)

    full = {}                                  # time basis -> all-sample times

    def all_times(au):
        key = au.get("time_basis") == "layer_beats"
        if key not in full:
            full[key] = times_at(np.arange(total_n, dtype=float), au)
        return full[key]

    from ._native import curve_seconds

    def fused(au, mode):                       # seconds timeline: one native
        if au.get("time_basis") == "layer_beats":  # pass, no time array
            return None
        return curve_seconds(au, total_n, sr, mode, _DB_TO_LN)

    for au in wanted:
        if au["target"] == "gain_db":
            env = fused(au, 1)                         # 10^(dB/20) fused
            if env is None:
                env = evaluate_curve(au, all_times(au))    # dB -> linear, in
                np.multiply(env, _DB_TO_LN, out=env)       # place: 10^(dB/20)
                np.exp(env, out=env)                       # = e^(dB ln10/20)
            gain_env = env if gain_env is None else gain_env * env
        elif au["target"] == "cutoff_hz":
            logarithmic = {k: v for k, v in au.items() if k not in {"t0", "rate_hz", "values"}}
            logarithmic["points"] = [[p[0], float(np.log(max(p[1], 1e-9))), *p[2:]]
                                      for p in curve_points(au)]
            cutoff_envs[au.get("fx_index", 0)] = _SampledCurve(
                lambda idx, _c=logarithmic, _au=au: np.exp(evaluate_curve(
                    _c, times_at(idx.astype(float), _au))), total_n)
        elif au["target"] == "scan":
            scan_env = fused(au, 2)
            if scan_env is None:
                scan_env = np.clip(evaluate_curve(au, all_times(au)), 0.0, 1.0)
    return gain_env, cutoff_envs, scan_env


VOICE_KEYS = ("unison", "spread_cents", "bandwidth_cents", "harmonics",
              "damping", "brightness", "pluck_pos", "material",
              "mode_decay_s", "modes", "scan", "_scan_env", "pressure",
              "bow_position")


def _voice_params(layer: dict) -> dict:
    return {k: layer[k] for k in VOICE_KEYS if k in layer}


_layer_library_cache: dict = {}   # (name, manifest_sha256) -> Library
_premaster_reports: dict = {}     # transient: id(spec) -> render report


def _layer_signal(layer: dict, total_n: int, sr: int, tm, swing: float,
                  root: str, idx: int,
                  groove: dict | None = None,
                  report: dict | None = None,
                  render_plan: dict | None = None,
                  placed: bool = False) -> np.ndarray:
    """The layer's full-length signal, or with ``placed=True`` the tuple
    (start_sample, signal[:active]) without the zero padding around it."""
    layer = {**layer, "_performance_root": root}
    t = layer["type"]
    name = layer.get("name", f"layer{idx}")
    rng = lambda sub="": rng_for(root, name, t, sub)  # noqa: E731
    dur_n = int(layer.get("duration_s", total_n / sr) * sr)
    dur_n = min(dur_n, total_n)
    if layer.get("clip_map"):
        source = layer["clip_source"]
        original = {key: value for key, value in layer.items()
                    if key not in {"clip_map", "clip_source", "fx", "automation"}}
        original["start_s"] = source.get("start_s", 0)
        original["duration_s"] = source["layer_duration_s"]
        original["automation"] = [a for a in source.get("automation", []) if a["target"] == "scan"]
        original["_score"] = source.get("score", {})
        source_tm = sequencer.TimelineMap(sequencer.TempoMap(source["tempo_map"]), source.get("holds"))
        dry = _layer_signal(original, int(round(source["duration_s"] * sr)), sr,
                            source_tm, swing, root, idx, groove, report)
        sig = np.zeros((total_n, dry.shape[1]) if dry.ndim == 2 else total_n)
        for index, (a, b, dest) in enumerate(layer["clip_map"]):
            piece = dry[int(round(a * sr)):int(round(b * sr))].copy()
            start = int(round(dest * sr))
            count = min(piece.shape[0], total_n - start)
            fade = min(int(.005 * sr), count // 2)
            # Fixed-length edits: tapered discontinuous edges, no tempo drift.
            if fade and index:
                ramp = np.linspace(0, 1, fade)
                piece[:fade] *= ramp[:, None] if piece.ndim == 2 else ramp
            if fade and index + 1 < len(layer["clip_map"]):
                ramp = np.linspace(1, 0, fade)
                piece[-fade:] *= ramp[:, None] if piece.ndim == 2 else ramp
            sig[start:start + count] = piece[:count]
        # The source layer already applied its gain; effects follow assembly.
        layer = {**layer, "gain_db": 0}
    _, _, scan_env = _automation_envs(layer, dur_n, sr, tm, targets={"scan"})
    if scan_env is not None:
        layer = {**layer, "_scan_env": scan_env}   # reaches osc via voice

    if layer.get("clip_map"):
        pass
    elif t == "tone":
        freq = layer.get("freq_hz") or synth.note_to_freq(layer["note"])
        sig = synth.osc(layer.get("osc", "sine"), freq, dur_n, sr,
                        detune_cents=layer.get("detune_cents", 0.0),
                        fm_ratio=layer.get("fm_ratio", 2.0),
                        fm_index=layer.get("fm_index", 0.0),
                        rng=rng("osc"), voice=_voice_params(layer))
        e = layer["env"]
        sig *= synth.adsr(dur_n, sr, e["attack"], e["decay"],
                          e["sustain"], e["release"])
    elif t == "sweep":
        sig = synth.pitch_sweep(layer.get("shape", "sine"),
                                layer["f_start_hz"], layer["f_end_hz"],
                                dur_n, sr, layer.get("curve", "exp"))
        e = layer["env"]
        sig *= synth.adsr(dur_n, sr, e["attack"], e["decay"],
                          e["sustain"], e["release"])
    elif t == "noise":
        sig = synth.noise(layer["color"], dur_n, rng("noise"))
        e = layer["env"]
        sig *= synth.adsr(dur_n, sr, e["attack"], e["decay"],
                          e["sustain"], e["release"])
    elif t == "drums":
        sig = sequencer.render_drum_track(layer, dur_n, sr, tm, swing,
                                          rng("voice"), groove=groove,
                                          rng_humanize=rng("humanize"), rng_factory=rng)
    elif t == "notes":
        sig = sequencer.render_note_track(layer, dur_n, sr, tm,
                                          rng_factory=rng, groove=groove)
    elif t == "grain":
        srcname = layer.get("source", "pad")
        src_n = int(float(layer.get("source_dur_s", 2.0)) * sr)
        if srcname in ("white", "pink", "brown"):
            src_buf = synth.noise(srcname, src_n, rng("grain_src"))
        else:
            freq = (layer.get("freq_hz")
                    or synth.note_to_freq(layer.get("note", "A3")))
            src_buf = synth.osc(srcname, freq, src_n, sr,
                                rng=rng("grain_src"),
                                voice=_voice_params(layer))
        sig = synth.granular(
            src_buf, dur_n, sr, rng("grains"),
            grain_s=float(layer.get("grain_s", 0.09)),
            density=float(layer.get("density", 35.0)),
            pitch_spread_cents=float(layer.get("pitch_spread_cents", 30.0)),
            scatter=float(layer.get("scatter", 0.5)))
        e = layer["env"]
        sig *= synth.adsr(dur_n, sr, e["attack"], e["decay"],
                          e["sustain"], e["release"])
    elif t == "instrument":
        from .library import load_library
        from .sampler import render_instrument_track
        ref = layer["_library"]
        key = (ref["name"], ref["manifest_sha256"])
        lib = _layer_library_cache.get(key)
        if lib is None:
            lib = load_library(ref)
            _layer_library_cache[key] = lib
        sec = layer.get("section")
        plan_segments = None
        if render_plan is not None:
            lname = layer.get("name", f"layer{idx}")
            plan_segments = [
                seg for seg in render_plan.get("segments", [])
                if seg.get("layer") == lname
            ]
        if sec:
            from .sampler import render_section
            sig = render_section(layer, dur_n, sr, tm, rng, lib,
                                 groove=groove, report=report,
                                 plan_segments=plan_segments)
        else:
            sig = render_instrument_track(layer, dur_n, sr, tm,
                                          lambda sub: rng(sub), lib,
                                          groove=groove, report=report,
                                          plan_segments=plan_segments)
        if lib.ignored_opcodes and report is not None:
            report["sampler_ignored_opcodes"] = sorted(lib.ignored_opcodes)
    elif t == "foley":
        from .foley import FOLEY_MODELS
        sig = FOLEY_MODELS[layer["model"]](
            dur_n, sr, rng("foley"),
            intensity=float(layer.get("intensity", 0.5)),
            brightness=float(layer.get("brightness", 0.5)))
        e = layer.get("env", {"attack": 0.5, "decay": 0.5,
                              "sustain": 0.85, "release": 1.0})
        sig *= synth.adsr(dur_n, sr, e["attack"], e["decay"],
                          e["sustain"], e["release"])
    elif t == "sample":
        from . import samples as smod
        preserve_channels = bool(layer.get("preserve_channels")) \
            and "pattern" not in layer
        if preserve_channels:
            hit = smod.load_sample_multi(layer["file"], layer["sha256"], sr)
            if hit.ndim == 2 and hit.shape[1] > 2:
                hit = hit[:, :2]
            elif hit.ndim == 2 and hit.shape[1] == 1:
                hit = hit[:, 0]
        else:
            hit = smod.load_sample(layer["file"], layer["sha256"], sr,
                                   pitch_st=float(layer.get("pitch_st", 0.0)))
        if "pattern" in layer:
            sig = sequencer.render_drum_track(
                layer, dur_n, sr, tm, swing, rng("voice"), groove=groove,
                rng_humanize=rng("humanize"), hit_override=hit, rng_factory=rng)
        elif hit.ndim == 2:
            sig = np.zeros((dur_n, hit.shape[1]))
            seg = min(hit.shape[0], dur_n)
            sig[:seg, :hit.shape[1]] = hit[:seg]
        else:
            sig = np.zeros(dur_n)
            seg = min(hit.size, dur_n)
            sig[:seg] = hit[:seg]
    else:  # unreachable after validation
        raise ValueError(t)

    if "gain_db" in layer and t not in ("drums", "notes", "instrument") \
            and not (t == "sample" and "pattern" in layer):
        sig = gain_fx(sig, layer["gain_db"])
    gain_env, cutoff_envs, _scan = _automation_envs(
        layer, sig.shape[0], sr, tm, targets={"gain_db", "cutoff_hz"})
    if "fx" in layer:
        if sig.ndim == 2:                # section layers: fx per channel
            sig = np.stack([
                apply_fx_chain(sig[:, c], sr, layer["fx"],
                               lambda sub, _c=c: rng_for(
                                   root, name, f"ch{_c}", sub),
                               automation_envs=cutoff_envs)
                for c in (0, 1)], axis=1)
        else:
            sig = apply_fx_chain(sig, sr, layer["fx"],
                                 lambda sub: rng_for(root, name,
                                                     sub),
                                 automation_envs=cutoff_envs)
    if gain_env is not None:
        sig = sig * (gain_env[:, None] if sig.ndim == 2 else gain_env)

    start = int(layer.get("start_s", 0.0) * sr)
    seg = max(0, min(sig.shape[0], total_n - start))
    if placed:
        return start, sig[:seg]
    return _expand(start, sig[:seg], total_n)


def _expand(start: int, part: np.ndarray, total_n: int) -> np.ndarray:
    """Zero-padded full-length copy of a placed layer signal."""
    out = np.zeros((total_n, 2) if part.ndim == 2 else total_n)
    if part.shape[0]:
        out[start:start + part.shape[0]] = part
    return out


def _resolve_jobs(jobs: int | None) -> int:
    """Worker count for layer-parallel rendering. ``None`` -> the
    ``AUDIOFORGE_JOBS`` env var (default 1 = serial). Always >= 1.

    Parallelism is deterministic by construction: each layer's signal is a
    pure function of (layer, name, performance identity) with per-layer seeded RNG, and
    results are summed back in layer order — so any job count yields
    byte-identical audio. See ``_layer_signals``.
    """
    if jobs is None:
        import os
        try:
            jobs = int(os.environ.get("AUDIOFORGE_JOBS", "1"))
        except ValueError:
            jobs = 1
    return max(1, int(jobs))


def _layer_signals(spec: dict, total_n: int, sr: int, tm, swing: float,
                   root: str, groove, report: dict, jobs: int,
                   render_plan: dict | None = None):
    """Render every layer's full-length signal, optionally across threads.

    Returns ``(prepped_layers, signals)`` in spec order, each signal placed
    as ``(start_sample, active_samples)`` (see ``_expand``). Layer signals are
    order-independent (seeded per-layer RNG keyed by name); the caller sums
    them back in order, so the result is identical for any ``jobs``. The hot
    work (synthesis, sampling, FX) is largely in GIL-releasing numpy/scipy C,
    so threads give real speedup without breaking determinism or needing the
    libraries re-loaded per process. ``report`` is write-only metadata and is
    shared across threads (it never feeds back into the audio)."""
    layers = spec["layers"]
    prepped = [{**ly, "_score": spec.get("score", {}),
                **({"_library": spec["library"]} if ly.get("type") == "instrument" else {})}
               for ly in layers]
    n = len(prepped)
    parallel = jobs > 1 and n > 1
    if parallel:
        # Pre-load libraries serially so concurrent load_library() (disk read
        # + manifest re-hash) cannot race on the shared cache.
        from .library import load_library
        for ly in prepped:
            if ly.get("type") == "instrument":
                ref = ly["_library"]
                key = (ref["name"], ref["manifest_sha256"])
                if key not in _layer_library_cache:
                    _layer_library_cache[key] = load_library(ref)

    def _one(i):
        return _layer_signal(prepped[i], total_n, sr, tm, swing, root, i,
                             groove=groove, report=report,
                             render_plan=render_plan, placed=True)

    if parallel:
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=min(jobs, n)) as ex:
            sigs = list(ex.map(_one, range(n)))
    else:
        sigs = [_one(i) for i in range(n)]
    return prepped, sigs


def _premaster(spec: dict, root: str, sr: int, master: dict,
               return_stems: bool, jobs: int = 1,
               render_plan: dict | None = None):
    """Layers -> buses -> master fx/automation/width/DC; no loudness yet."""
    root = performance_hash(spec)
    total_n = int(spec["duration_s"] * sr)
    bpm = float(spec.get("bpm", 120.0))
    tm = sequencer.TempoMap(spec.get("tempo_map") or [[0.0, bpm]])
    if spec.get("holds"):
        tm = sequencer.TimelineMap(tm, spec["holds"])
    swing = float(spec.get("swing", 0.0))

    buses = spec.get("buses", [])
    duck_sources = {b["duck"]["source"] for b in buses if "duck" in b}
    # bus accumulators as contiguous (left, right) channel arrays: every
    # later stage works per channel, so no strided column passes or restacking
    acc = {None: (np.zeros(total_n), np.zeros(total_n))}

    def _bus(bus):                          # lazy: unrouted declared
        if bus not in acc:                  # buses cost nothing
            acc[bus] = (np.zeros(total_n), np.zeros(total_n))
        return acc[bus]

    def _acc_add(bus, st):
        bl, br = _bus(bus)
        bl += st[:, 0]
        br += st[:, 1]
    kept: dict[str, np.ndarray] = {}        # duck-source signals (mono mix)
    stems: dict[str, np.ndarray] = {}
    report: dict = {}
    _premaster_reports[id(spec)] = report
    stage_tail_in = np.zeros(total_n)
    groove = spec.get("groove")
    # Layer signals computed first (optionally in parallel); the seat/stage/bus
    # accumulation below stays serial and in spec order, so the mix sum is
    # byte-identical regardless of `jobs`.
    prepped, sigs = _layer_signals(spec, total_n, sr, tm, swing, root,
                                   groove, report, jobs, render_plan)
    for i, layer in enumerate(prepped):
        start, part = sigs[i]
        sigs[i] = None                       # release as we go
        seat = layer.get("seat")
        lname = layer.get("name", f"layer{i}")
        if (part.ndim == 1 and not return_stems and lname not in duck_sources
                and (seat is None or spec.get("stage") is None)):
            # mono layer: constant-power pan straight into its bus over the
            # active span only (outside it the full-length path adds zeros)
            pan = float(layer.get("pan", 0.0))  # -1 L..+1 R, const power
            theta = (pan + 1.0) * np.pi / 4.0
            bl, br = _bus(layer.get("bus"))
            if part.size:
                end = start + part.size
                bl[start:end] += np.cos(theta) * part
                br[start:end] += np.sin(theta) * part
            continue
        sig = _expand(start, part, total_n)
        del part
        if seat is not None and spec.get("stage") is not None:
            from .stage import direct_tap, early_tap
            stg = spec["stage"]
            mics = stg.get("mics", {})
            az, dist = seat["az_deg"], seat["dist_m"]
            if sig.ndim == 2 and layer.get('type') == 'instrument' and not layer.get('section'):
                from .sampler import pan_signal
                from .stage import seat_pan_itd
                sig = pan_signal(sig, seat_pan_itd(az)[0])
            mono = sig.mean(axis=1) if sig.ndim == 2 else sig
            st = np.zeros((total_n, 2))
            cw = float(mics.get("close", 0.2))
            tw = float(mics.get("tree", 0.7))
            if cw > 0:                       # spot mic: distance clamped
                st += cw * direct_tap(sig, sr, az, min(dist, 1.5))
            if tw > 0:                       # main pair: direct-at-distance
                st += tw * direct_tap(sig, sr, az, dist)   # + early image
                st += tw * early_tap(mono, sr, az, dist,
                                     stg.get("dims", [18.0, 26.0, 10.0]))
            stage_tail_in += mono            # shared hall feed (unit gain:
        elif sig.ndim == 2:                  # tail level ~ distance-flat
            if layer.get("type") == "instrument" and not layer.get("section"):
                from .sampler import pan_signal
                st = pan_signal(sig, float(layer.get("pan", 0)))
            else:
                st = sig                    # section players already seated
        else:
            pan = float(layer.get("pan", 0.0))  # -1 L..+1 R, const power
            theta = (pan + 1.0) * np.pi / 4.0
            st = np.stack([np.cos(theta) * sig, np.sin(theta) * sig],
                          axis=1)
        _acc_add(layer.get("bus"), st)
        if lname in duck_sources:
            kept[lname] = st.mean(axis=1)
        if return_stems:
            stems[lname] = st

    for lib in _layer_library_cache.values():     # notes all rendered:
        lib._audio_cache.clear()                   # drop decoded float64
        lib._region_cache.clear()                  # audio before the
    import gc                                      # memory-peak tail conv
    gc.collect()
    mix_l, mix_r = acc[None]
    stg = spec.get("stage")
    if stg is not None and np.any(stage_tail_in):
        from .stage import hall_tail
        tail = float(stg.get("mics", {}).get("ambient", 0.3)) \
            * hall_tail(stage_tail_in, sr, stg["hall_file"],
                        stg["hall_sha256"])
        mix_l = mix_l + tail[:, 0]
        mix_r = mix_r + tail[:, 1]
        del tail
    del stage_tail_in
    from .fx import apply_master_chain, duck_envelope
    for b in buses:                          # declared order; ducks resolve
        bn = b["name"]
        if bn not in acc:                    # nothing routed here (lazy acc)
            continue
        st_l, st_r = acc[bn]
        if "duck" in b:
            d = b["duck"]
            src_sig = kept.get(d["source"])
            if src_sig is None:              # an earlier bus's output
                src_sig = kept[f"bus:{d['source']}"]
            g = duck_envelope(src_sig, sr,
                              amount_db=d.get("amount_db", 6.0),
                              threshold_db=d.get("threshold_db", -35.0),
                              attack_s=d.get("attack_s", 0.012),
                              release_s=d.get("release_s", 0.18))
            st_l, st_r = st_l * g, st_r * g
        b_gain_env, b_cutoff_envs, _ = _automation_envs(b, total_n, sr, tm)
        if "fx" in b:
            st_l, st_r = apply_master_chain(
                st_l, st_r, sr, b["fx"],
                lambda ch, sub, _bn=bn: rng_for(root, f"bus:{_bn}", ch, sub),
                automation_envs=b_cutoff_envs)
        if "gain_db" in b:
            k = 10.0 ** (b["gain_db"] / 20.0)
            st_l, st_r = st_l * k, st_r * k
        if b_gain_env is not None:
            st_l, st_r = st_l * b_gain_env, st_r * b_gain_env
        if f"bus:{bn}" in duck_sources:     # later buses may duck off this one
            kept[f"bus:{bn}"] = (st_l + st_r) / 2.0    # == mean over L/R
        mix_l += st_l
        mix_r += st_r
    del acc, kept
    left, right = mix_l, mix_r

    m_gain_env, m_cutoff_envs, _mscan = _automation_envs(master, total_n, sr, tm)
    if "fx" in master:
        from .fx import apply_master_chain
        left, right = apply_master_chain(
            left, right, sr, master["fx"],
            lambda ch, sub: rng_for(root, "master", ch, sub),
            automation_envs=m_cutoff_envs)
    if m_gain_env is not None:
        left = left * m_gain_env
        right = right * m_gain_env

    # stereo width: 0 = mono, 1 = as mixed
    width = float(master.get("stereo_width", 1.0))
    mid = 0.5 * (left + right)
    side = 0.5 * (left - right) * width
    left, right = mid + side, mid - side

    # DC safety: synthesis offset eats headroom and biases the limiter
    from .dynamics import dc_block_lr
    left, right = dc_block_lr(left, right, sr)
    return left, right, stems


def _finish(left, right, sr, master, spec, root, stems, return_stems,
            render_plan_hash: str | None = None):
    loop_report = None
    if spec.get("loop_safe"):
        from .analysis import LOOP_BOUNDARY_CODE, loop_boundary_report
        from .schema import SpecError
        loop_report = loop_boundary_report(np.stack([left, right], axis=1), sr, spec)
        if not loop_report["passed"]:
            _premaster_reports.pop(id(spec), None)
            raise SpecError(f"{LOOP_BOUNDARY_CODE}: unsafe loop seam or truncated tail: "
                            + json.dumps(loop_report, sort_keys=True))
    # Measure and normalize the delivered fade envelope, not an earlier buffer.
    fi = min(left.size, int(master.get("fade_in_s", 0.0) * sr))
    fo = min(left.size, int(master.get("fade_out_s", 0.0 if spec.get("loop_safe") else 0.01) * sr))
    if fi:
        ramp = np.linspace(0, 1, fi)
        left[:fi] *= ramp
        right[:fi] *= ramp
    if fo:
        ramp = np.linspace(1, 0, fo)
        left[-fo:] *= ramp
        right[-fo:] *= ramp
    # Preserve deliberate levels; normalization requires an explicit request.
    loudness_report = None
    if "target_lufs" in master:
        st = np.stack([left, right], axis=1)
        del left, right                      # memory: one stereo copy only
        st, loudness_report = master_loudness(
            st, sr, float(master["target_lufs"]),
            float(master.get("target_peak_dbfs", -1.0)))
        left, right = st[:, 0], st[:, 1]
    elif master.get("normalization", "none") == "peak":
        target = float(master.get("target_peak_dbfs", -1.0))
        peak = max(np.max(np.abs(left)), np.max(np.abs(right)), 1e-12)
        g = (10.0 ** (target / 20.0)) / peak
        left *= g
        right *= g
    else:
        from .dynamics import true_peak_limit
        st, limiter = true_peak_limit(
            np.stack([left, right], axis=1), sr,
            float(master.get("target_peak_dbfs", -1.0)))
        left, right = st[:, 0], st[:, 1]
        if limiter["limited"]:
            loudness_report = {"limiter": limiter}

    # Peak normalization also promises a true-peak ceiling.
    if master.get("normalization") == "peak":
        from .dynamics import true_peak_limit
        st, limiter = true_peak_limit(np.stack([left, right], axis=1), sr,
                                      float(master.get("target_peak_dbfs", -1)))
        left, right = st[:, 0], st[:, 1]
        if limiter["limited"]:
            loudness_report = {"limiter": limiter}

    if left.base is not None and left.base is right.base:
        stereo = left.base                   # already one [n,2] array:
    else:                                    # no third stereo copy
        stereo = np.stack([left, right], axis=1)
        del left, right
    if loop_report is not None:
        delivered = loop_boundary_report(stereo, sr, spec)
        if not delivered["passed"]:
            _premaster_reports.pop(id(spec), None)
            raise SpecError(f"{LOOP_BOUNDARY_CODE}: unsafe delivered loop seam: "
                            + json.dumps(delivered, sort_keys=True))
        delivered["premaster"] = loop_report
        loop_report = delivered
    meta = {
        "id": spec["id"], "kind": spec["kind"], "engine_version": ENGINE_VERSION,
        "spec_hash": root, "sample_rate": sr,
        "bit_depth": int(spec.get("bit_depth", 24)),
        "duration_s": spec["duration_s"], "channels": 2,
        "markers": spec.get("markers", []),
        "emotion": spec.get("emotion", {}),
        "performance_hash": performance_hash(spec),
        "performance_seed": spec.get("performance_seed", 0),
    }
    if loop_report is not None:
        meta["loop_boundary"] = loop_report
    if render_plan_hash is not None:
        meta["plan_hash"] = render_plan_hash
    if loudness_report:
        meta["loudness"] = loudness_report
    rep = _premaster_reports.pop(id(spec), None)
    if rep:
        meta.update(rep)
    if "variant" in spec:
        meta["variant"] = spec["variant"]
    if "intensity_scale" in spec:
        meta["intensity_scale"] = spec["intensity_scale"]
    if return_stems:
        return stereo, sr, meta, stems
    return stereo, sr, meta


def _plan_for_render(spec: dict, render_plan: dict | None = None):
    from .plan import build_render_plan, verify_plan_for_spec

    if render_plan is not None:
        return verify_plan_for_spec(spec, render_plan)
    return build_render_plan(spec)


def render(spec: dict, return_stems: bool = False, jobs: int | None = None,
           render_plan: dict | None = None):
    """Returns (stereo float64 array [n,2] in -1..1, sample_rate, meta)
    or, with return_stems=True, (..., stems).

    ``jobs`` renders layers across that many threads (``None`` -> the
    ``AUDIOFORGE_JOBS`` env var, default 1). Output is byte-identical for any
    ``jobs`` — the determinism contract is preserved."""
    from ._memory import render_heap
    jobs = _resolve_jobs(jobs)
    spec = validate_spec(spec)
    plan_result = _plan_for_render(spec, render_plan)
    root = spec_hash(spec)
    sr = int(spec.get("sample_rate", 48000))
    master = _master_with_intensity(spec)
    with render_heap():
        left, right, stems = _premaster(spec, root, sr, master, return_stems,
                                        jobs, plan_result.plan)
        return _finish(left, right, sr, master, spec, root, stems,
                       return_stems, plan_result.plan_hash)


def _master_with_intensity(spec: dict) -> dict:
    """Master dict with intensity-derived automation scaled by
    spec.intensity_scale (the same cue at 0.3 / 0.6 / 1.0)."""
    master = spec.get("master", {})
    isc = float(spec.get("intensity_scale", 1.0))
    if isc == 1.0 or "automation" not in master:
        return master
    return {**master, "automation": [
        {**au, "points": [[t, v * isc] for t, v in au["points"]]}
        if au.get("from_intensity") else au
        for au in master["automation"]]}


def render_cutdowns(spec: dict):
    """Campaign matrix: render the premaster once, splice each declared
    cutdown's keep-windows with equal-power crossfades, then run the full
    loudness/fade finish per cutdown. Yields (length_s, stereo, sr, meta)."""
    spec = validate_spec(spec)
    root = spec_hash(spec)
    sr = int(spec.get("sample_rate", 48000))
    master = _master_with_intensity(spec)
    left, right, _ = _premaster(spec, root, sr, master, False)
    for cd in spec.get("cutdowns", []):
        fade_n = max(8, int(cd.get("fade_s", 0.5) * sr))
        segs = [(int(a * sr), int(b * sr)) for a, b in cd["segments"]]
        out_l = left[segs[0][0]:segs[0][1]].copy()
        out_r = right[segs[0][0]:segs[0][1]].copy()
        for a, b in segs[1:]:
            nl, nr = left[a:b].copy(), right[a:b].copy()
            f = min(fade_n, out_l.size, nl.size)
            theta = np.linspace(0, np.pi / 2, f)
            down, up = np.cos(theta), np.sin(theta)
            out_l[-f:] = out_l[-f:] * down + nl[:f] * up
            out_r[-f:] = out_r[-f:] * down + nr[:f] * up
            out_l = np.concatenate([out_l, nl[f:]])
            out_r = np.concatenate([out_r, nr[f:]])
        sub = dict(spec)
        sub["duration_s"] = round(out_l.size / sr, 3)
        sub.pop("loop_safe", None)   # a cutdown is a delivery, not a loop: no seam/tail gate
        st, _, meta = _finish(out_l, out_r, sr, master, sub, root, {}, False)
        meta["cutdown"] = {"length_s": cd["length_s"],
                           "segments": cd["segments"],
                           "parent_spec_hash": root,
                           "parent_duration_s": spec["duration_s"]}
        yield cd["length_s"], st, sr, meta


def _quantize_seeded(stereo: np.ndarray, bits: int, root: str,
                     path: str) -> bytes:
    """Seeded dither + quantize. 16-bit uses high-pass TPDF (first-difference
    of uniform noise) which pushes dither energy toward high frequencies —
    audibly cleaner than flat TPDF at 16-bit, still fully vectorized and
    deterministic. 24-bit keeps flat TPDF. Deterministic byte output."""
    rng = rng_for(root, path)
    full = float(2 ** (bits - 1) - 1)
    dither = (rng.random(stereo.shape) - rng.random(stereo.shape))  # TPDF
    if bits == 16:  # high-pass the dither: d[n] - d[n-1], per channel
        dither = np.diff(dither, axis=0, prepend=dither[:1] * 0.0)
    q = np.clip(np.round(stereo * full + dither), -full - 1, full).astype(np.int64)
    inter = q.reshape(-1)  # frame-interleaved L R L R ...
    if bits == 16:
        return inter.astype("<i2").tobytes()
    # 24-bit little-endian packing, vectorized: int32 LE -> drop the MSB byte
    as32 = inter.astype("<i4").tobytes()
    arr = np.frombuffer(as32, dtype=np.uint8).reshape(-1, 4)
    return arr[:, :3].tobytes()


def _write_wav(path: Path, stereo: np.ndarray, sr: int, bits: int, root: str,
               dither_path: str) -> str:
    pcm = _quantize_seeded(stereo, bits, root, dither_path)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(bits // 8)
        w.setframerate(sr)
        w.writeframes(pcm)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def render_to_wav(spec: dict, out_dir: str | Path, stems: bool = False,
                  jobs: int | None = None,
                  render_plan: dict | None = None) -> dict:
    from .plan import dumps_plan

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    plan_result = _plan_for_render(spec, render_plan)
    if stems:
        stereo, sr, meta, stem_map = render(
            spec, return_stems=True, jobs=jobs, render_plan=plan_result.plan)
    else:
        stereo, sr, meta = render(
            spec, jobs=jobs, render_plan=plan_result.plan)
    bits = meta["bit_depth"]
    root = performance_hash(spec)

    wav_path = out_dir / f"{spec['id']}.wav"
    meta["output_sha256"] = _write_wav(wav_path, stereo, sr, bits, root, "dither")
    meta["file"] = wav_path.name

    if plan_result.diagnostics:
        meta["plan_diagnostics"] = plan_result.diagnostics

    plan_path = out_dir / f"{spec['id']}.plan.json"
    plan_text = dumps_plan(plan_result.plan)
    plan_path.write_text(plan_text)
    meta["plan_file"] = plan_path.name
    meta["plan_sha256"] = hashlib.sha256(plan_text.encode("utf-8")).hexdigest()

    if stems:
        stem_dir = out_dir / f"{spec['id']}_stems"
        stem_dir.mkdir(exist_ok=True)
        meta["stems"] = {}
        peak = max(np.max(np.abs(stereo)), 1e-12)
        for name, sig in stem_map.items():
            sp = max(np.max(np.abs(sig)), 1e-12)
            norm = sig * min(1.0, (10 ** (-1.0 / 20.0)) / sp)
            p = stem_dir / f"{name}.wav"
            meta["stems"][name] = _write_wav(p, norm, sr, bits, root,
                                             f"dither:stem:{name}")

    if spec.get("markers"):
        (out_dir / f"{spec['id']}.markers.json").write_text(
            json.dumps({"id": spec["id"], "markers": spec["markers"]},
                       indent=2))

    manifest_path = out_dir / f"{spec['id']}.manifest.json"
    manifest_path.write_text(json.dumps(meta, indent=2, sort_keys=True))
    return meta


def verify(spec: dict, expected_sha256: str, tmp_dir: str | Path) -> bool:
    """Re-render and compare output hash — the CI reproducibility gate."""
    meta = render_to_wav(spec, tmp_dir)
    return meta["output_sha256"] == expected_sha256
