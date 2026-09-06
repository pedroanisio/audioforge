"""Deterministic render analysis for AI feedback loops."""
from __future__ import annotations

import math

import numpy as np


# Codes emitted by analysis and loop-safety checks. Registered in
# capabilities.capability_manifest()["diagnostic_codes"] (RM-E-001 / HARNESS-CON-001).
ANALYSIS_DIAGNOSTIC_CODES = frozenset({
    "low_foundation_weak", "mono_image", "very_bright", "high_crest", "near_ceiling", "dead_air",
})
LOOP_BOUNDARY_CODE = "loop_boundary_tail"

def _db(x: float) -> float:
    return 20.0 * math.log10(max(float(x), 1e-12))


def _silence_metrics(mono: np.ndarray, sample_rate: int,
                     hop_s: float = 0.25, expected: np.ndarray | None = None) -> dict:
    """Windowed dead-air detection.

    A render can be technically valid yet mostly silent — a lane that failed to
    sound, an accidental mute, or (as happens) a filter automated into removing
    all signal. Global RMS hides this when a few loud passages lift the average,
    so we scan a short-window envelope and report the longest continuous dead
    run and the dead share of the interior (fade in/out excluded). "Dead" is
    both near-absolute-silent and far below the track's own loud level, so a
    uniformly quiet-but-audible piece is not flagged.
    """
    n = max(1, int(hop_s * sample_rate))
    usable = mono.size - (mono.size % n)
    if usable < n * 4:
        return {"silence_share": 0.0, "longest_silence_s": 0.0}
    frames = mono[:usable].reshape(-1, n)
    wdb = 10.0 * np.log10(np.maximum(np.mean(frames * frames, axis=1), 1e-24))
    sounding = wdb[wdb > -120.0]
    loud_ref = float(np.percentile(sounding, 90)) if sounding.size else -48.0
    floor = min(-48.0, loud_ref - 30.0)
    dead = wdb < floor
    if expected is not None:
        dead &= expected[:dead.size]
    edge = int(round(1.0 / hop_s))              # ignore ~1 s fade edges
    if dead.size > 2 * edge:
        dead[:edge] = False
        dead[-edge:] = False
    longest = cur = 0
    for d in dead:
        cur = cur + 1 if d else 0
        longest = max(longest, cur)
    return {
        "silence_share": round(float(np.mean(dead)), 4),
        "longest_silence_s": round(longest * hop_s, 3),
    }


def analyze_audio(stereo: np.ndarray, sample_rate: int,
                  context: dict | None = None) -> dict:
    """Return structured, deterministic features for an already-rendered buffer.

    Analysis lives outside the render path: it observes audio and annotates the
    manifest/agent loop, but it never feeds hidden state back into synthesis.
    """
    arr = np.asarray(stereo, dtype=np.float64)
    if arr.ndim == 1:
        arr = np.stack([arr, arr], axis=1)
    if arr.size == 0:
        raise ValueError("cannot analyze empty audio")
    if arr.ndim != 2 or arr.shape[1] not in (1, 2):
        raise ValueError("audio must be mono or stereo")
    if not np.isfinite(arr).all() or not np.isfinite(sample_rate) or sample_rate <= 0:
        raise ValueError("audio and sample rate must be finite; sample rate must be positive")
    mono = arr.mean(axis=1)
    peak = float(np.max(np.abs(arr)))
    rms = float(np.sqrt(np.mean(arr * arr)))
    crest = _db(peak / max(rms, 1e-12))
    win = np.hanning(mono.size) if mono.size > 1 else np.ones(mono.size)
    spec = np.sqrt(np.mean(np.abs(np.fft.rfft(arr * win[:, None], axis=0)) ** 2, axis=1))
    freqs = np.fft.rfftfreq(mono.size, 1.0 / sample_rate)
    mag_sum = float(np.sum(spec))
    centroid = float(np.sum(freqs * spec) / mag_sum) if mag_sum else 0.0
    cumulative = np.cumsum(spec)
    roll_idx = int(np.searchsorted(cumulative, 0.85 * mag_sum)) if mag_sum else 0
    rolloff = float(freqs[min(roll_idx, freqs.size - 1)]) if freqs.size else 0.0
    low = float(np.sum(spec[freqs < 250.0]) / mag_sum) if mag_sum else 0.0
    if arr.shape[1] >= 2 and np.std(arr[:, 0]) > 1e-12 and np.std(arr[:, 1]) > 1e-12:
        corr = float(np.corrcoef(arr[:, 0], arr[:, 1])[0, 1])
    else:
        corr = 1.0
    width = float(max(0.0, min(2.0, 1.0 - corr)))
    report = {
        "duration_s": round(arr.shape[0] / float(sample_rate), 6),
        "peak_dbfs": round(_db(peak), 3),
        "rms_dbfs": round(_db(rms), 3),
        "crest_db": round(crest, 3),
        "spectral_centroid_hz": round(centroid, 3),
        "spectral_rolloff85_hz": round(rolloff, 3),
        "low_band_share": round(low, 6),
        "stereo_width": round(width, 6),
    }
    energy = np.sqrt(np.mean(arr * arr, axis=1))
    report.update(_silence_metrics(energy, sample_rate))
    expectations = _analysis_context(context or {})
    expected = _expected_activity(context or {}, arr.shape[0] / sample_rate)
    if expected is not None:
        missing = _silence_metrics(energy, sample_rate, expected=expected)
        report["unexpected_silence_share"] = missing["silence_share"]
        report["longest_unexpected_silence_s"] = missing["longest_silence_s"]
    else:
        missing = report
    observations = _recommend(report)
    report["observations"] = [{"code": item["code"], "message": item["message"]}
                              for item in observations]
    recs = []
    for item in observations:
        code = item["code"]
        relevant = {
            "low_foundation_weak": expectations.get("expect_bass") is True,
            "mono_image": expectations.get("stereo") == "stereo",
            "very_bright": expectations.get("brightness") == "warm",
            "high_crest": expectations.get("dynamics") == "controlled",
            "dead_air": not expectations.get("allow_silence", False) and (
                expected is not None or expectations.get("continuous") is True) and (
                missing.get("longest_silence_s", 0) >= 4 or missing.get("silence_share", 0) >= .2),
        }.get(code, True)
        if relevant:
            recs.append({**item, "basis": "declared_context" if code != "near_ceiling" else "measured_headroom"})
    report["context"] = expectations
    report["recommendations"] = recs
    report["assessment_scope"] = "signal_and_declared_expectations; musical merit requires listening"
    return report


def _analysis_context(context: dict) -> dict:
    if "layers" not in context:
        return dict(context)
    explicit = context.get("intent", {}).get("analysis_context", {})
    bass = any(layer.get("role") == "bass" for layer in context["layers"])
    return {"role": "solo" if len(context["layers"]) == 1 else "mix",
            "expect_bass": bass, **explicit}


def _expected_activity(context: dict, duration_s: float) -> np.ndarray | None:
    """Compare silence with written activity instead of assuming continuous music."""
    if "layers" not in context:
        return None
    from .performance import note_events
    from .sequencer import TempoMap, TimelineMap
    timeline = TimelineMap(TempoMap(context.get("tempo_map") or [[0, context.get("bpm", 120)]]),
                           context.get("holds"))
    centers = np.arange(.125, duration_s, .25)
    mask = np.zeros(centers.size, dtype=bool)
    for layer in context["layers"]:
        offset = layer.get("start_s", 0)
        if layer.get("clip_map"):
            # A repeated continuous layer sounds where its source windows carried sound,
            # mapped to their destinations; compile_repeats pops start_s/duration_s.
            source = layer.get("clip_source", {})
            src_start = float(source.get("start_s", 0))
            src_end = src_start + float(source.get("layer_duration_s", source.get("duration_s", duration_s)))
            for window in layer["clip_map"]:
                ta, tb, dest = (float(v) for v in window[:3])
                lo, hi = max(ta, src_start), min(tb, src_end)
                if hi > lo:
                    mask |= (centers >= dest + (lo - ta)) & (centers < dest + (hi - ta))
            continue
        if layer.get("notes"):
            for event in note_events(layer, timeline.beat_at(duration_s)):
                start = timeline.sec(event["start_beat"]) + offset
                end = timeline.sec(event["start_beat"] + event["dur_beats"]) + offset
                if event.get("vel", 1) > 0:
                    mask |= (centers >= start) & (centers < end)
        else:
            mask |= (centers >= offset) & (centers < offset + layer.get("duration_s", duration_s))
    return mask


def _recommend(r: dict) -> list[dict]:
    recs = []
    if r["low_band_share"] < 0.04:
        recs.append({
            "code": "low_foundation_weak",
            "severity": "warning",
            "message": "Little energy is below 250 Hz.",
            "suggestion": "Check the declared bass part, its register, gain and filtering.",
        })
    if r["stereo_width"] < 0.08:
        recs.append({
            "code": "mono_image",
            "severity": "info",
            "message": "Stereo image is very narrow.",
            "suggestion": "Increase space depth, width, unison spread, or pan layers.",
        })
    if r["spectral_centroid_hz"] > 5500:
        recs.append({
            "code": "very_bright",
            "severity": "warning",
            "message": "Spectral centroid is high; the render may read as bright.",
            "suggestion": "Lower oscillator brightness, add lowpass automation, or rebalance low layers.",
        })
    if r["crest_db"] > 22:
        recs.append({
            "code": "high_crest",
            "severity": "info",
            "message": "Transient crest factor is high.",
            "suggestion": "Use bus compression, saturation, or lower transient layers.",
        })
    if r["peak_dbfs"] > -0.2:
        recs.append({
            "code": "near_ceiling",
            "severity": "info",
            "message": "Peak is very close to 0 dBFS.",
            "suggestion": "Use a lower master peak target for delivery headroom.",
        })
    if r.get("longest_silence_s", 0.0) >= 4.0 or r.get("silence_share", 0.0) >= 0.2:
        recs.append({
            "code": "dead_air",
            "severity": "warning",
            "message": (
                f"Observed silence: longest quiet run "
                f"{r.get('longest_silence_s', 0.0):.1f}s, "
                f"{r.get('silence_share', 0.0) * 100:.0f}% of the interior is "
                f"near-silent."),
            "suggestion": (
                "A lane may be muted or filtered out — check gain automation "
                "and that 'auto cutoff' targets the intended filter (it drives "
                "the first filter in the chain)."),
        })
    return recs


def loop_boundary_report(stereo: np.ndarray, sample_rate: int, spec: dict) -> dict:
    """Measure the cyclic seam and identify note tails cut by the container.

    A whole-beat length is only a grid condition. This check runs before master
    fades so a fade cannot hide a clipped written release. It is a signal check,
    not a claim that the composition makes a satisfying musical loop.
    """
    arr = np.asarray(stereo)
    window = min(arr.shape[0] // 2, max(8, int(.005 * sample_rate)))
    first, last = arr[:window], arr[-window:]
    jump = float(np.max(np.abs(arr[0] - arr[-1])))
    derivatives = np.concatenate([np.diff(first, axis=0).ravel(), np.diff(last, axis=0).ravel()])
    typical_step = float(np.percentile(np.abs(derivatives), 95))
    click = jump > max(1e-4, 3 * typical_step)
    tail_rms = float(np.sqrt(np.mean(last * last)))
    head_rms = float(np.sqrt(np.mean(first * first)))
    from .performance import note_events
    from .sequencer import TempoMap, TimelineMap
    timeline = TimelineMap(TempoMap(spec.get("tempo_map") or [[0, spec.get("bpm", 120)]]), spec.get("holds"))
    duration = arr.shape[0] / sample_rate
    clipped = []
    for layer in spec.get("layers", []):
        for note in note_events(layer, timeline.beat_at(duration)) if layer.get("notes") else []:
            release = layer.get("env", {}).get("release", .1 if layer.get("type") == "notes" else .05)
            release += note.get("release_s_add", 0)
            end = timeline.sec(note["start_beat"] + note["dur_beats"]) + layer.get("start_s", 0)
            if (note.get("vel", 1) and end + release > duration + 1 / sample_rate
                    and tail_rms > 1e-4):
                clipped.append(layer.get("name", "?"))
    decaying_tail = tail_rms > max(1e-4, head_rms * 8)
    return {"passed": not (click or clipped or decaying_tail),
            "jump_dbfs": round(_db(jump), 3), "local_step_dbfs": round(_db(typical_step), 3),
            "tail_rms_dbfs": round(_db(tail_rms), 3),
            "head_rms_dbfs": round(_db(head_rms), 3),
            "discontinuous_seam": bool(click), "clipped_note_tails": sorted(set(clipped)),
            "unmatched_tail_energy": bool(decaying_tail)}
