"""Beat & note sequencing on a deterministic tempo grid.

A pattern is a string of 16th-note steps: 'x' = hit, '.' = rest,
'X' = accented hit. Swing shifts every off-8th step by a fraction of a step.
"""
from __future__ import annotations

import numpy as np

from . import synth
from .curves import evaluate_curve
from .determinism import rng_for
from .performance import groove_slot, timing_deviation
from .fx import filter_auto_fx, filter_fx


# ---------------------------------------------------------------- drum voices
def _vp(params, key, default):
    return float((params or {}).get(key, default))


def _kick(sr: int, rng, params: dict | None = None) -> np.ndarray:
    """tune_st: pitch; decay: length scale; snap: click amount;
    bend: sweep depth (0 = flat 808-ish, 1 = hard punch)."""
    tune = 2.0 ** (_vp(params, "tune_st", 0.0) / 12.0)
    dec = _vp(params, "decay", 1.0)
    snap = _vp(params, "snap", 0.5)
    bend = _vp(params, "bend", 1.0)
    n = int(0.25 * dec * sr)
    f0 = 45.0 * tune
    f_start = f0 * (1.0 + bend * (120.0 / 45.0 - 1.0))
    body = synth.pitch_sweep("sine", f_start, f0, n, sr, curve="exp")
    env = synth.adsr(n, sr, 0.001, 0.18 * dec, 0.0, 0.05 * dec)
    click = synth.noise("white", int(0.005 * sr), rng) * 0.8 * snap
    out = body * env
    out[:click.size] += click * np.linspace(1, 0, click.size)
    return out


def _snare(sr: int, rng, params: dict | None = None) -> np.ndarray:
    """tune_st: shell tone; decay: length; snap: noise/tone balance."""
    tune = 2.0 ** (_vp(params, "tune_st", 0.0) / 12.0)
    dec = _vp(params, "decay", 1.0)
    snap = _vp(params, "snap", 0.5)
    n = int(0.2 * dec * sr)
    tone = synth.osc("sine", 190.0 * tune, n, sr) * (0.8 * (1.0 - snap))
    nz = synth.noise("white", n, rng) * (0.4 + 1.2 * snap)
    nz = filter_fx(nz, sr, "highpass", 1500.0)
    env = synth.adsr(n, sr, 0.001, 0.12 * dec, 0.0, 0.05 * dec)
    return (tone + nz) * env


def _hat(sr: int, rng, open_: bool = False,
         params: dict | None = None) -> np.ndarray:
    """tune_st: metallic brightness; decay: length."""
    tune = 2.0 ** (_vp(params, "tune_st", 0.0) / 12.0)
    dec = _vp(params, "decay", 1.0)
    n = int((0.35 if open_ else 0.06) * dec * sr)
    nz = synth.noise("white", n, rng)
    nz = filter_fx(nz, sr, "highpass", min(7000.0 * tune, sr * 0.45))
    env = synth.adsr(n, sr, 0.0005, n / sr * 0.9, 0.0, 0.02)
    return nz * env


def _clap(sr: int, rng, params: dict | None = None) -> np.ndarray:
    dec = _vp(params, "decay", 1.0)
    tune = 2.0 ** (_vp(params, "tune_st", 0.0) / 12.0)
    n = int(0.25 * dec * sr)
    nz = filter_fx(synth.noise("white", n, rng), sr, "bandpass",
                   1800.0 * tune, 1.2)
    env = np.zeros(n)
    for i, off in enumerate((0.0, 0.012, 0.024)):
        s = int(off * sr)
        seg = synth.adsr(n - s, sr, 0.001, 0.09 * dec, 0.0, 0.03 * dec)
        env[s:] = np.maximum(env[s:], seg * (0.8 + 0.1 * i))
    return nz * env


def _tom(sr: int, rng, params: dict | None = None) -> np.ndarray:
    tune = 2.0 ** (_vp(params, "tune_st", 0.0) / 12.0)
    dec = _vp(params, "decay", 1.0)
    bend = _vp(params, "bend", 1.0)
    n = int(0.3 * dec * sr)
    f0 = 110.0 * tune
    body = synth.pitch_sweep("sine", f0 * (1.0 + bend), f0, n, sr)
    env = synth.adsr(n, sr, 0.001, 0.22 * dec, 0.0, 0.05 * dec)
    return body * env


DRUM_VOICES = {
    "kick": _kick, "snare": _snare, "clap": _clap, "tom": _tom,
    "hat": lambda sr, rng, params=None: _hat(sr, rng, False, params),
    "open_hat": lambda sr, rng, params=None: _hat(sr, rng, True, params),
}


class TempoMap:
    """Piecewise-linear BPM over beats; beat->seconds is the analytic
    integral of 60/bpm (logarithmic per ramp segment), so accelerandi and
    ritardandi are exact, not stepped. A single point = constant tempo."""

    def __init__(self, points):
        pts = [[float(b), float(v)] for b, v in points] or [[0.0, 120.0]]
        if pts[0][0] != 0.0:
            pts.insert(0, [0.0, pts[0][1]])
        self.pts = pts
        self.t0 = [0.0]
        for i in range(1, len(pts)):
            self.t0.append(self.t0[-1] + self._seg(i - 1, pts[i][0]))

    def _seg(self, i, beat):
        b0, v0 = self.pts[i]
        if i + 1 < len(self.pts):
            b1, v1 = self.pts[i + 1]
        else:
            b1, v1 = b0 + 1.0, v0
        if b1 == b0 or v1 == v0:
            return (beat - b0) * 60.0 / v0
        k = (v1 - v0) / (b1 - b0)
        return (60.0 / k) * np.log((v0 + k * (beat - b0)) / v0)

    def sec(self, beat: float) -> float:
        i = 0
        for j in range(len(self.pts) - 1, -1, -1):
            if self.pts[j][0] <= beat:
                i = j
                break
        return self.t0[i] + self._seg(i, beat)

    def beat_at(self, t: float) -> float:
        i = 0
        for j in range(len(self.t0) - 1, -1, -1):
            if self.t0[j] <= t:
                i = j
                break
        b0, v0 = self.pts[i]
        dt = t - self.t0[i]
        if i + 1 < len(self.pts):
            b1, v1 = self.pts[i + 1]
            if b1 != b0 and v1 != v0:
                k = (v1 - v0) / (b1 - b0)
                return b0 + (v0 / k) * (np.exp(dt * k / 60.0) - 1.0)
        return b0 + dt * v0 / 60.0


class TimelineMap:
    """Beat timeline wrapper that inserts absolute-time holds.

    ``TempoMap`` remains the austere [beat, bpm] integrator. Holds are separate
    IR events with trivial semantics: a hold at beat B inserts N seconds before
    events at B and shifts all later beats by N seconds.
    """

    def __init__(self, tempo_map: TempoMap, holds: list[dict] | None = None):
        self.tempo_map = tempo_map
        merged: dict[float, float] = {}
        for hold in holds or []:
            beat = float(hold["beat"])
            duration = float(hold["duration_s"])
            if duration <= 0.0:
                continue
            merged[beat] = merged.get(beat, 0.0) + duration
        self.holds = [
            {"beat": beat, "duration_s": duration,
             "base_time_s": self.tempo_map.sec(beat)}
            for beat, duration in sorted(merged.items())
        ]

    def sec(self, beat: float) -> float:
        base = self.tempo_map.sec(beat)
        offset = sum(h["duration_s"] for h in self.holds
                     if h["beat"] <= beat)
        return base + offset

    def beat_at(self, t: float) -> float:
        offset = 0.0
        for hold in self.holds:
            start = hold["base_time_s"] + offset
            end = start + hold["duration_s"]
            if t < start:
                return self.tempo_map.beat_at(t - offset)
            if t <= end:
                return hold["beat"]
            offset += hold["duration_s"]
        return self.tempo_map.beat_at(t - offset)


def dyn_env(points, tm, start_n: int, n: int, sr: int) -> np.ndarray:
    """Per-sample dynamic value over [start_n, start_n+n): the layer's
    [beat, 0..1] breakpoints, linearly interpolated in beat space, sampled
    on a 1 ms block grid then expanded (the curve is slow by nature)."""
    pts = np.asarray(points, dtype=np.float64)
    step = max(1, sr // 1000)
    grid_n = np.arange(start_n, start_n + n + step, step)
    beats = np.array([tm.beat_at(t) for t in grid_n / sr])
    v = np.interp(beats, pts[:, 0], pts[:, 1])
    full = np.repeat(v, step)[: n]
    if full.size < n:
        full = np.pad(full, (0, n - full.size), mode="edge")
    return full


def dyn_gain(v: np.ndarray | float):
    """The level share of dynamics: -9 dB at niente to 0 dB at fff.
    Timbre (layer crossfade / brightness) carries the rest."""
    return 10.0 ** ((np.asarray(v) - 1.0) * 9.0 / 20.0)


def _note_curve_times(curve: dict, tm: "TempoMap", start_beat: float,
                      start_time_s: float, n: int, sr: int) -> np.ndarray:
    samples = np.arange(n, dtype=float) / sr
    basis = curve.get("time_basis", "note_beats")
    if basis == "note_beats":
        return np.array([
            tm.beat_at(start_time_s + float(t)) - start_beat
            for t in samples
        ], dtype=float)
    return samples


def _sum_note_curve(ev: dict, target: str, tm: "TempoMap",
                    start_beat: float, start_time_s: float, n: int,
                    sr: int) -> np.ndarray | None:
    curves = [
        curve for curve in ev.get("curves", [])
        if isinstance(curve, dict) and curve.get("target") == target
    ]
    if not curves:
        return None
    out = np.zeros(n, dtype=float)
    for curve in curves:
        times = _note_curve_times(curve, tm, start_beat, start_time_s, n, sr)
        out += evaluate_curve(curve, times)
    return out


def render_drum_track(track: dict, total_n: int, sr: int, tm: "TempoMap",
                      swing: float, rng, groove: dict | None = None,
                      rng_humanize=None, hit_override=None, rng_factory=None) -> np.ndarray:
    """track = {voice, pattern, gain_db?, humanize?} ; pattern repeats.
    groove = {"timing": [16 x 16th-fractions], "accent": [16 x mult]}
    humanize = {"timing_s": ..., "vel": ...} with per-hit seeded jitter."""
    from .plugins import DRUM_VOICES as PLUGIN_VOICES
    voice = DRUM_VOICES.get(track["voice"])
    dp = {k: track[k] for k in ("tune_st", "decay", "snap", "bend") if k in track}
    if hit_override is not None:
        hit = hit_override                 # content-addressed sample as the hit
    elif rng_factory is not None:
        hit = None                         # synthesized per hit below from its own seeded stream
    elif voice is not None:
        hit = voice(sr, rng, dp if dp else None)
    else:
        hit = PLUGIN_VOICES[track["voice"]](sr, rng)
    pattern = track["pattern"].replace(" ", "")
    gain = 10.0 ** (track.get("gain_db", 0.0) / 20.0)
    hum = track.get("humanize")
    g_t = (groove or {}).get("timing")
    g_a = (groove or {}).get("accent")
    out = np.zeros(total_n)
    n_steps = int(np.ceil(tm.beat_at(total_n / sr) * 4.0))
    for i in range(n_steps):
        ch = pattern[i % len(pattern)]
        if ch == ".":
            continue
        grid_beat = i * 0.25
        beat = grid_beat
        if swing and i % 2 == 1:
            beat += swing * 0.25
        amp = gain * (1.25 if ch == "X" else 1.0)
        # The groove slot is a property of the notated step, not of the swung onset:
        # round(1.5) is 2 under banker's rounding, so swing 0.5 would shift every odd step.
        slot = groove_slot(grid_beat, track.get("name", ""), track.get("_score", {}), len(g_t or g_a or [0] * 16))
        if g_t:
            beat += g_t[slot] * 0.25
        if g_a:
            amp *= g_a[slot]
        t = tm.sec(beat)
        if rng_factory is not None:
            event_rng = rng_factory(f"hit:{float(i * .25):.12g}")
            if hum:
                t += timing_deviation(track, beat, rng_factory) * hum.get("timing_s", 0)
                amp *= 1 + (event_rng.random() * 2 - 1) * hum.get("vel", 0)
            if hit_override is None:
                hit = (voice(sr, event_rng, dp if dp else None) if voice is not None
                       else PLUGIN_VOICES[track["voice"]](sr, event_rng))
        elif hum and rng_humanize is not None:
            t += (rng_humanize.random() * 2.0 - 1.0) * hum.get("timing_s", 0.0)
            amp *= 1.0 + (rng_humanize.random() * 2.0 - 1.0) * hum.get("vel", 0.0)
        start = int(round(max(t, 0.0) * sr))
        if start >= total_n:
            break
        seg = min(hit.size, total_n - start)
        out[start:start + seg] += amp * hit[:seg]
    return out


def render_note_track(track: dict, total_n: int, sr: int, tm: "TempoMap",
                      rng_factory=None, groove: dict | None = None) -> np.ndarray:
    """Melodic/harmonic sequence with performance realism:
    groove templates (timing/accent per 16th slot), seeded humanization,
    portamento (glide_s, monophonic-line semantics), per-note vibrato, and
    velocity->brightness. All deviation is drawn from per-note seeded RNG
    paths: 'imperfect' and byte-reproducible at once."""
    from .fx import filter_fx
    from .render import _voice_params
    env_p = track.get("env", {"attack": 0.01, "decay": 0.1,
                              "sustain": 0.7, "release": 0.1})
    gain = 10.0 ** (track.get("gain_db", 0.0) / 20.0)
    vib = track.get("vibrato")
    glide_s = float(track.get("glide_s", 0.0))
    vb_amount = float(track.get("vel_brightness", 0.0))
    dyn_pts = track.get("dynamic")
    if dyn_pts and vb_amount == 0.0:
        vb_amount = 1.0                  # dynamics imply full timbre coupling
    out = np.zeros(total_n)
    from .performance import schedule_notes
    factory = rng_factory or (lambda path: rng_for("default_take", path))
    scheduled = schedule_notes(track, total_n, sr, tm, factory, groove)
    prev_freq = None
    prev_start = None
    for note in scheduled:
        ev = note["event"]
        freq = ev.get("freq_hz") or synth.note_to_freq(ev["note"])
        vel, start, gate_n = note["vel"], note["start"], note["dur_n"]
        start_beat, t, ev_rng = note["start_beat"], note["start_time_s"], note["rng"]
        release_s = env_p["release"] + float(ev.get("release_s_add", 0.0))
        env = synth.note_adsr(gate_n, sr, env_p["attack"] * ev.get("attack_scale", 1), env_p["decay"],
                              env_p["sustain"], release_s)
        n = min(env.size, total_n - start)
        env = env[:n]
        shape = track.get("osc", "sine")
        # Explicit note curves are the render contract. Legacy glide/vibrato
        # remain as a fallback for pre-curve IR during the migration window.
        pitch_cents = _sum_note_curve(ev, "pitch_cents", tm, start_beat, t,
                                      n, sr)
        ratio = None
        if pitch_cents is not None:
            ratio = 2.0 ** (pitch_cents / 1200.0)
        else:
            if glide_s > 0 and prev_freq and prev_start is not None                 and prev_start < start_beat:
                ratio = synth.glide_ratio_env(prev_freq, freq, n, sr, glide_s)
            if vib:
                v_env = synth.vibrato_ratio_env(
                    n, sr, float(vib.get("rate_hz", 5.0)),
                    float(vib.get("depth_cents", 12.0)),
                    float(vib.get("delay_s", 0.25)))
                ratio = v_env if ratio is None else ratio * v_env
        voice = _voice_params(track)
        note_scan = _sum_note_curve(ev, "scan", tm, start_beat, t, n, sr)
        if note_scan is not None:
            voice = dict(voice)
            voice["_scan_env"] = np.clip(note_scan, 0.0, 1.0)
        elif "_scan_env" in voice:           # per-note slice of the scan ride
            voice = dict(voice)
            voice["_scan_env"] = voice["_scan_env"][start:start + n]
        if ratio is not None and shape not in ("pluck", "modal"):
            det = 2.0 ** (track.get("detune_cents", 0.0) / 1200.0)
            sig = synth.osc_dynamic(shape, freq * det * ratio, n, sr,
                                    f_nominal=freq * det,
                                    fm_ratio=track.get("fm_ratio", 2.0),
                                    fm_index=track.get("fm_index", 0.0),
                                    rng=ev_rng, voice=voice)
        else:
            sig = synth.osc(shape, freq, n, sr,
                            rng=ev_rng, voice=voice,
                            detune_cents=track.get("detune_cents", 0.0),
                            fm_ratio=track.get("fm_ratio", 2.0),
                            fm_index=track.get("fm_index", 0.0))
        dyn_v = None
        note_dyn = _sum_note_curve(ev, "dynamic", tm, start_beat, t, n, sr)
        if note_dyn is not None:
            dyn_v = np.clip(note_dyn, 0.0, 1.0)
        elif dyn_pts:
            dyn_v = dyn_env(dyn_pts, tm, start, n, sr)
        bright_vel = float(dyn_v[0]) if dyn_v is not None else vel
        cutoff = synth.vel_brightness_cutoff(bright_vel, freq, sr, vb_amount)
        if cutoff is not None:
            sig = filter_fx(sig, sr, "lowpass", cutoff, 0.7071)
        note_cutoff = _sum_note_curve(ev, "cutoff_hz", tm, start_beat, t,
                                      n, sr)
        if note_cutoff is not None:
            sig = filter_auto_fx(sig, sr, "lowpass",
                                 np.clip(note_cutoff, 10.0, sr / 2.0 - 1.0),
                                 0.7071)
        contrib = gain * vel * sig * env
        if dyn_v is not None:
            contrib = contrib * dyn_gain(dyn_v)
        note_gain_db = _sum_note_curve(ev, "gain_db", tm, start_beat, t, n, sr)
        if note_gain_db is not None:
            contrib = contrib * (10.0 ** (note_gain_db / 20.0))
        out[start:start + n] += contrib
        prev_freq, prev_start = freq, start_beat
    return out
