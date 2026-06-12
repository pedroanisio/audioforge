"""Tier S: deterministic SFZ-subset sampler (P1) + dynamics & articulation
engine (P2).

An offline interpreter for a documented subset of the SFZ sample-mapping
format. AudioForge implements its own NumPy interpreter rather than binding
a real-time engine: real-time samplers make voice-stealing and
buffer-ordering decisions that are hostile to byte-reproducibility, and the
IR being fully explicit means the exact region set is computable up front.

Supported opcodes (v1):
  <control> default_path
  <global>/<group>/<region> inheritance
  sample key lokey hikey pitch_keycenter lovel hivel
  seq_length seq_position                  (round-robins — seeded, not
                                            sequential: the pick derives
                                            from the per-note RNG path,
                                            which includes the variant tag)
  ampeg_attack ampeg_decay ampeg_sustain ampeg_release
  loop_mode loop_start loop_end loop_crossfade
  tune transpose volume

Anything else is collected and reported as ignored — loud, not silent.
Resampling uses a fixed 32-tap Hann-windowed-sinc kernel so pitch shifting
is bit-stable across versions.

P2 adds:
- a per-layer `dynamic` curve driving equal-power, *time-varying* velocity-
  layer crossfades (a crescendo on one held note moves through the recorded
  layers like a player leaning in) plus a small level term (-9 dB..0 —
  real dynamics are mostly timbre, only partly level);
- per-note articulations with documented synthetic fallbacks, recorded in
  the render manifest when applied.
Without a dynamic curve, velocity maps linearly to amplitude and selects
layers on the standard 1..127 scale (the P1 behavior, unchanged).
"""
from __future__ import annotations

import dataclasses
import re
from dataclasses import dataclass, field

import numpy as np

from . import synth

_HEADER_RE = re.compile(r"<(control|global|master|group|region)>")
_NOTE_NAME_RE = re.compile(r"^([a-gA-G])([#b]?)(-?\d+)$")
_NOTE_OFFSETS = {"c": 0, "d": 2, "e": 4, "f": 5, "g": 7, "a": 9, "b": 11}

_INT_OPS = {"key", "lokey", "hikey", "pitch_keycenter", "lovel", "hivel",
            "seq_length", "seq_position", "loop_start", "loop_end",
            "transpose"}
_FLOAT_OPS = {"ampeg_attack", "ampeg_decay", "ampeg_sustain",
              "ampeg_release", "loop_crossfade", "tune", "volume"}
_STR_OPS = {"sample", "loop_mode", "default_path"}
_KNOWN = _INT_OPS | _FLOAT_OPS | _STR_OPS


def _note_or_int(v: str) -> int:
    """SFZ key opcodes accept either MIDI numbers or note names (c4)."""
    m = _NOTE_NAME_RE.match(v)
    if not m:
        return int(v)
    letter, acc, octave = m.groups()
    n = _NOTE_OFFSETS[letter.lower()] + {"#": 1, "b": -1, "": 0}[acc]
    return n + (int(octave) + 1) * 12


@dataclass
class Region:
    sample: str = ""
    lokey: int = 0
    hikey: int = 127
    pitch_keycenter: int = 60
    lovel: int = 1
    hivel: int = 127
    seq_length: int = 1
    seq_position: int = 1
    ampeg_attack: float = 0.001
    ampeg_decay: float = 0.0
    ampeg_sustain: float = 100.0      # SFZ: percent
    ampeg_release: float = 0.05
    loop_mode: str = "no_loop"
    loop_start: int = 0
    loop_end: int = 0
    loop_crossfade: float = 0.0
    tune: float = 0.0                 # cents
    transpose: int = 0
    volume: float = 0.0               # dB
    extras: dict = field(default_factory=dict)


def parse_sfz(text: str) -> tuple[list[Region], set[str]]:
    """SFZ text -> (regions with inheritance resolved, ignored opcode names).

    Comments (// to end of line) are stripped. <global> and <group> opcodes
    are inherited by following <region> headers, per the format.
    """
    text = re.sub(r"//[^\n]*", "", text)
    tokens = _HEADER_RE.split(text)
    # tokens: [pre, header1, body1, header2, body2, ...]
    scopes = {"control": {}, "global": {}, "master": {}, "group": {}}
    regions: list[Region] = []
    ignored: set[str] = set()
    pairs_re = re.compile(r"(\w+)=([^\s=]+(?:\s+[^\s=]+)*?)(?=\s+\w+=|\s*$)")

    def parse_body(body: str) -> dict:
        out = {}
        for m in pairs_re.finditer(body):
            k, v = m.group(1), m.group(2).strip()
            if k not in _KNOWN:
                ignored.add(k)
                continue
            if k in _INT_OPS:
                out[k] = _note_or_int(v) if k.endswith("key") \
                    or k == "pitch_keycenter" else int(float(v))
            elif k in _FLOAT_OPS:
                out[k] = float(v)
            else:
                out[k] = v.replace("\\", "/")
        return out

    i = 1
    while i < len(tokens):
        header, body = tokens[i], tokens[i + 1]
        ops = parse_body(body)
        if header == "region":
            merged = {**scopes["global"], **scopes["master"],
                      **scopes["group"], **ops}
            if "key" in merged:
                k = merged.pop("key")
                merged.setdefault("lokey", k)
                merged.setdefault("hikey", k)
                merged.setdefault("pitch_keycenter", k)
            default_path = scopes["control"].get("default_path", "")
            r = Region(**{k: v for k, v in merged.items()
                          if k in Region.__dataclass_fields__})
            if r.sample:
                r.sample = (default_path + r.sample).replace("\\", "/")
            regions.append(r)
        elif header == "group":
            scopes["group"] = ops          # a new group resets group scope
        else:
            scopes[header].update(ops)
        i += 2
    return regions, ignored


def select_regions(regions: list[Region], midi: int, vel127: int,
                   rng) -> list[Region]:
    """All regions matching key+velocity; round-robin sets collapse to one
    seeded pick. The rng is the per-note RNG (root includes the variant
    tag), so repeated notes vary, re-renders are identical, and pack
    variants re-realize — the v2.8 lesson, applied from day one."""
    hits = [r for r in regions
            if r.lokey <= midi <= r.hikey and r.lovel <= vel127 <= r.hivel]
    if not hits:
        return []
    out, rr_sets = [], {}
    for r in hits:
        if r.seq_length > 1:
            rr_sets.setdefault((r.lokey, r.hikey, r.lovel, r.hivel,
                                r.seq_length), []).append(r)
        else:
            out.append(r)
    for key, pool in sorted(rr_sets.items()):
        pool.sort(key=lambda r: r.seq_position)
        pick = 1 + int(rng.integers(0, key[4]))
        chosen = [r for r in pool if r.seq_position == pick]
        out.extend(chosen if chosen else pool[:1])
    return out


# fixed resampling kernel: 32-tap Hann-windowed sinc, documented and frozen
_SINC_HALF = 16


def _sinc_read(src: np.ndarray, positions: np.ndarray) -> np.ndarray:
    """Read fractional positions from src with the fixed windowed-sinc
    kernel. Positions beyond the source are zero."""
    n_src = src.size
    padded = np.concatenate([np.zeros(_SINC_HALF), src,
                             np.zeros(_SINC_HALF + 1)])
    base = np.floor(positions).astype(np.int64)
    frac = positions - base
    valid = (base >= 0) & (base < n_src)
    base_c = np.clip(base, 0, n_src - 1)
    offsets = np.arange(-_SINC_HALF + 1, _SINC_HALF + 1)
    # x = distance from sample tap to read position
    x = offsets[None, :] - frac[:, None]
    window = 0.5 + 0.5 * np.cos(np.pi * x / _SINC_HALF)
    kern = np.sinc(x) * window
    idx = base_c[:, None] + offsets[None, :] + _SINC_HALF
    out = np.einsum("ij,ij->i", padded[idx], kern)
    return np.where(valid, out, 0.0)


def render_region(region: Region, src: np.ndarray, src_sr: int,
                  midi_float: float, dur_n: int, sr: int,
                  src_offset_s: float = 0.0,
                  ramp_from_midi: float | None = None,
                  ramp_s: float = 0.025,
                  pitch_cents: np.ndarray | None = None) -> np.ndarray:
    """One region playing one note: pitch via fixed-kernel resampling, loop
    extension with equal-power overlap-add seam crossfades, ampeg envelope,
    volume. Output length = dur_n + release tail.

    Legato support: `src_offset_s` skips into the recording past its attack
    transient; `ramp_from_midi` reads at the previous note's rate first and
    glides to this note's over `ramp_s` (variable-rate read — a real pitch
    smear, not a crossfade artifact)."""
    semis = (midi_float - region.pitch_keycenter + region.transpose
             + region.tune / 100.0)
    ratio = (2.0 ** (semis / 12.0)) * (src_sr / sr)
    rel_n = int(region.ampeg_release * sr)
    total_n = dur_n + rel_n
    if ramp_from_midi is not None and ramp_from_midi != midi_float:
        semis0 = (ramp_from_midi - region.pitch_keycenter + region.transpose
                  + region.tune / 100.0)
        r0 = (2.0 ** (semis0 / 12.0)) * (src_sr / sr)
        k = max(2, int(ramp_s * sr))
        rate = np.full(total_n, ratio)
        rate[:k] = r0 + (ratio - r0) * np.linspace(0.0, 1.0, k)
    else:
        rate = np.full(total_n, ratio)
    if pitch_cents is not None:
        cents = np.asarray(pitch_cents, dtype=np.float64)
        if cents.size == 0:
            cents = np.zeros(total_n, dtype=np.float64)
        elif cents.size < total_n:
            cents = np.pad(cents, (0, total_n - cents.size), mode="edge")
        else:
            cents = cents[:total_n]
        rate = rate * (2.0 ** (cents / 1200.0))
    if ((ramp_from_midi is not None and ramp_from_midi != midi_float)
            or pitch_cents is not None):
        positions = np.cumsum(rate) - rate[0]
    else:
        positions = np.arange(total_n) * ratio
    positions = positions + src_offset_s * src_sr

    if region.loop_mode in ("loop_continuous", "loop_sustain") \
            and region.loop_end > region.loop_start:
        ls, le = region.loop_start, min(region.loop_end, src.size - 1)
        body = src[ls:le]
        xf = int(min(region.loop_crossfade * src_sr, body.size * 0.5))
        stride = body.size - xf
        need = (positions[-1] if positions.size else 0.0) + 2
        reps = max(1, int(np.ceil((need - ls) / max(stride, 1))) + 1)
        ext = np.zeros(int(ls + stride * reps + body.size))
        ext[:le] = src[:le]              # original up to loop end
        theta = np.linspace(0, np.pi / 2, xf) if xf else None
        for k in range(1, reps + 1):     # overlap-add each pass
            pos = ls + k * stride
            if xf:
                ext[pos:pos + xf] = (ext[pos:pos + xf] * np.cos(theta)
                                     + body[:xf] * np.sin(theta))
                ext[pos + xf:pos + body.size] = body[xf:]
            else:
                ext[pos:pos + body.size] = body
        src = ext
    out = _sinc_read(src, positions)

    env = synth.adsr(total_n, sr, region.ampeg_attack, region.ampeg_decay,
                     region.ampeg_sustain / 100.0, region.ampeg_release)
    out *= env * (10.0 ** (region.volume / 20.0))
    return out


def freq_to_midi(freq: float) -> float:
    return 69.0 + 12.0 * np.log2(freq / 440.0)


# --- articulation engine (P2) ----------------------------------------------
# Synthetic fallbacks, applied when the library lacks a sampled articulation
# and recorded in the render manifest — loud, not silent. Each entry:
# (base articulation preference order, modifications, description).
_FALLBACKS = {
    "staccato": (("sustain",), {"dur_clamp_s": 0.18, "release_s": 0.08},
                 "sustain regions with a 0.18 s clamp"),
    "spiccato": (("sustain",), {"dur_clamp_s": 0.12, "release_s": 0.06},
                 "sustain regions with a 0.12 s clamp"),
    "pizzicato": (("spiccato", "sustain"),
                  {"dur_clamp_s": 0.10, "release_s": 0.06},
                  "short-articulation regions with a 0.10 s clamp"),
    "marcato": (("sustain",), {"gain_db": 2.5, "attack_s": 0.001},
                "sustain regions, +2.5 dB, hard attack"),
    "tremolo": (("spiccato", "sustain"),
                {"dur_clamp_s": 0.14, "release_s": 0.06, "retrigger": True},
                "seeded re-trigger train (~12 Hz) of short regions"),
    "legato": (("sustain",), {},
               "sustain regions (true legato joins arrive with P3)"),
}


def resolve_articulation(lib, instrument: str, art: str):
    """-> (regions, mods, fallback_description|None). Loud failure if even
    the fallback chain finds nothing."""
    inst = lib.manifest["instruments"].get(instrument, {})
    available = set(inst.get("articulations", {}))
    if art in available:
        return lib.regions(instrument, art), {}, None
    if art not in _FALLBACKS:
        raise ValueError(f"instrument '{instrument}': articulation '{art}' "
                         f"is not sampled and has no fallback "
                         f"(sampled: {sorted(available)})")
    bases, mods, desc = _FALLBACKS[art]
    for base in bases:
        if base in available:
            return (lib.regions(instrument, base), dict(mods),
                    f"'{art}' -> {desc} (base: '{base}')")
    raise ValueError(
        f"instrument '{instrument}': articulation '{art}' unavailable and "
        f"no fallback base exists (sampled: {sorted(available)})")


# --- dynamics: velocity-band crossfade (P2) ---------------------------------
def _vel_bands(regions: list[Region]):
    """Key-matched regions grouped by velocity band, sorted by center."""
    bands: dict[tuple, list] = {}
    for r in regions:
        bands.setdefault((r.lovel, r.hivel), []).append(r)
    out = [((lo + hi) / 2.0, lo, hi, regs)
           for (lo, hi), regs in bands.items()]
    out.sort(key=lambda b: b[0])
    return out


def _band_weight_envs(centers: list[float], p_env: np.ndarray):
    """Equal-power crossfade weights per band for a per-sample velocity
    position p (1..127). Below the first center the first band owns the
    note; between adjacent centers the two bands blend; above the last,
    the last owns it."""
    K = len(centers)
    if K == 1:
        return [np.ones_like(p_env)]
    envs = []
    for k in range(K):
        if k == 0:
            up = np.ones_like(p_env)
        else:
            t = np.clip((p_env - centers[k - 1])
                        / (centers[k] - centers[k - 1]), 0.0, 1.0)
            up = np.sin(t * np.pi / 2.0)
        if k == K - 1:
            down = np.ones_like(p_env)
        else:
            t = np.clip((p_env - centers[k])
                        / (centers[k + 1] - centers[k]), 0.0, 1.0)
            down = np.cos(t * np.pi / 2.0)
        envs.append(up * down)
    return envs


def render_instrument_track(track: dict, total_n: int, sr: int, tm,
                            rng_factory, lib, groove: dict | None = None,
                            report: dict | None = None,
                            time_offset_s: float = 0.0,
                            midi_offset: float = 0.0) -> np.ndarray:
    """Instrument layer: the same scheduling semantics as note tracks
    (groove slots, tempo map, seeded humanize, velocity clip), each note
    rendered through the library's SFZ regions instead of a synth voice.

    P3 performance model:
    - slur groups render with legato joins — the outgoing note holds
      through an equal-power crossfade window (default 50 ms, `legato_s`),
      the incoming note skips its recorded attack and glides its read rate
      from the previous pitch (a real smear, not a crossfade artifact);
    - an opt-in `phrasing` arch shapes slur groups: velocities rise toward
      the group's pitch peak and ease after, and the last note lifts
      slightly (documented constants, fully deterministic);
    - `time_offset_s`/`midi_offset` are the per-player handles used by
      section multiplication."""
    from .sequencer import _sum_note_curve, dyn_env, dyn_gain
    instrument = track["instrument"]
    default_art = track.get("articulation", "sustain")
    dyn_pts = track.get("dynamic")
    join_w = float(track.get("legato_s", 0.05))
    phrasing = float(track.get("phrasing", 0.0))
    art_cache: dict[str, tuple] = {}

    def articulation(name):
        if name not in art_cache:
            regs, mods, fb = resolve_articulation(lib, instrument, name)
            if fb and report is not None:
                report.setdefault("articulation_fallbacks", {}).setdefault(
                    f"{track.get('name', '?')}/{instrument}", {})[name] = fb
            art_cache[name] = (regs, mods)
        return art_cache[name]

    env_gain = 10.0 ** (track.get("gain_db", 0.0) / 20.0)
    hum = track.get("humanize")
    g_t = (groove or {}).get("timing")
    g_a = (groove or {}).get("accent")
    out = np.zeros(total_n)
    events = list(track["notes"])
    loop_beats = track.get("loop_beats")
    if loop_beats:
        reps = int(np.ceil(tm.beat_at(total_n / sr) / loop_beats))
        events = [{**e, "start_beat": e["start_beat"] + r * loop_beats}
                  for r in range(reps) for e in track["notes"]]
    events.sort(key=lambda e: (e["start_beat"], e.get("note", ""),
                               e.get("freq_hz", 0.0)))

    # ---- pass 1: schedule -------------------------------------------------
    sched = []
    for j, ev in enumerate(events):
        freq = ev.get("freq_hz") or synth.note_to_freq(ev["note"])
        vel = float(ev.get("vel", 1.0))
        b = ev["start_beat"]
        slot = int(round(b * 4.0)) % 16
        if g_t:
            b += g_t[slot] * 0.25
        if g_a:
            vel *= g_a[slot]
        t = tm.sec(b) + time_offset_s
        ev_rng = rng_factory(f"note{j}")
        if hum:
            t += (ev_rng.random() * 2.0 - 1.0) * hum.get("timing_s", 0.0)
            vel *= 1.0 + (ev_rng.random() * 2.0 - 1.0) * hum.get("vel", 0.0)
        start = int(round(max(t, 0.0) * sr))
        dur_n = int(round((tm.sec(ev["start_beat"] + ev["dur_beats"])
                           - tm.sec(ev["start_beat"])) * sr))
        if start >= total_n or dur_n <= 0:
            continue
        sched.append({
            "midi": freq_to_midi(freq) + midi_offset, "vel": vel,
            "start": start, "dur_n": dur_n, "rng": ev_rng,
            "art": ev.get("art", default_art), "slur": ev.get("slur"),
            "event": ev, "start_beat": ev["start_beat"],
            "start_time_s": t})

    # ---- phrasing arch over slur groups (documented constants) ------------
    if phrasing > 0.0:
        groups: dict[int, list[int]] = {}
        for k, s in enumerate(sched):
            if s["slur"]:
                groups.setdefault(s["slur"], []).append(k)
        for idxs in groups.values():
            if len(idxs) < 2:
                continue
            midis = [sched[k]["midi"] for k in idxs]
            peak = len(midis) - 1 - midis[::-1].index(max(midis))
            last = len(idxs) - 1
            for i2, k in enumerate(idxs):
                if i2 <= peak:
                    x = i2 / peak if peak else 1.0
                else:
                    x = 1.0 - 1.3 * (i2 - peak) / max(last - peak, 1)
                sched[k]["vel"] *= 1.0 + 0.18 * phrasing * (x - 0.5) * 2.0
            last_k = idxs[last]
            sched[last_k]["dur_n"] = int(
                sched[last_k]["dur_n"] * (1.0 - 0.05 * phrasing))
            sched[last_k]["vel"] *= 1.0 - 0.07 * phrasing

    # ---- pass 2: render with join awareness --------------------------------
    join_n = int(join_w * sr)
    for k, s in enumerate(sched):
        s["vel"] = float(np.clip(s["vel"], 0.05, 1.3))
        prev = sched[k - 1] if k > 0 else None
        nxt = sched[k + 1] if k + 1 < len(sched) else None
        join_in = (prev is not None and s["slur"]
                   and prev["slur"] == s["slur"])
        join_out = (nxt is not None and s["slur"]
                    and nxt["slur"] == s["slur"])
        regions, mods = articulation(s["art"])
        clamp_n = (int(mods["dur_clamp_s"] * sr)
                   if mods.get("dur_clamp_s") else None)
        dur_n = s["dur_n"]
        if clamp_n and not mods.get("retrigger"):
            dur_n = min(dur_n, clamp_n)
        midi_i = int(round(s["midi"]))
        kreg = [r for r in regions if r.lokey <= midi_i <= r.hikey]
        if not kreg:
            raise ValueError(
                f"instrument '{instrument}': no SFZ region covers midi "
                f"{midi_i} (articulation '{s['art']}')")
        extra_g = 10.0 ** (mods.get("gain_db", 0.0) / 20.0)

        def shaped(r):
            if mods.get("release_s") or mods.get("attack_s"):
                return dataclasses.replace(
                    r, ampeg_release=mods.get("release_s", r.ampeg_release),
                    ampeg_attack=mods.get("attack_s", r.ampeg_attack))
            return r

        rr_kwargs = {}
        if join_in:
            rr_kwargs = {"src_offset_s": 0.06,
                         "ramp_from_midi": prev["midi"]}
        held_n = dur_n + (join_n if join_out else 0)

        def note_curve(target: str, n: int, offset_n: int = 0):
            env = _sum_note_curve(
                s["event"], target, tm, s["start_beat"],
                s["start_time_s"], offset_n + n, sr)
            if env is None:
                return None
            return env[offset_n:offset_n + n]

        def render_hit(h_start, h_dur_n, h_vel, h_rng):
            note_offset_n = max(0, h_start - s["start"])
            max_rel = max(shaped(r).ampeg_release for r in kreg)
            full_n = h_dur_n + int(max_rel * sr)
            note_dyn = note_curve("dynamic", full_n, note_offset_n)
            if note_dyn is not None or dyn_pts:
                bands = _vel_bands(kreg)
                if note_dyn is not None:
                    v_env = np.clip(note_dyn, 0.0, 1.0)
                else:
                    v_env = np.clip(dyn_env(dyn_pts, tm, h_start, full_n, sr),
                                    0.0, 1.0)
                weights = _band_weight_envs([bb[0] for bb in bands],
                                            1.0 + v_env * 126.0)
                sig = np.zeros(full_n)
                for (c, lo, hi, regs), w in zip(bands, weights):
                    if w.max() < 1e-3:
                        continue
                    chosen = select_regions(regs, midi_i, int(c), h_rng)
                    for r in chosen:
                        srcb, src_sr = lib.audio(r.sample)
                        pitch = note_curve(
                            "pitch_cents",
                            h_dur_n + int(shaped(r).ampeg_release * sr),
                            note_offset_n)
                        part = render_region(shaped(r), srcb, src_sr,
                                             s["midi"], h_dur_n, sr,
                                             pitch_cents=pitch, **rr_kwargs)
                        m = min(part.size, full_n)
                        sig[:m] += part[:m] * w[:m]
                sig *= dyn_gain(v_env) * h_vel * extra_g
            else:
                v127 = int(np.clip(round(h_vel * 127), 1, 127))
                chosen = select_regions(kreg, midi_i, v127, h_rng)
                if not chosen:
                    raise ValueError(
                        f"instrument '{instrument}': no region at velocity "
                        f"{v127} for midi {midi_i}")
                sig = np.zeros(
                    max(int(shaped(r).ampeg_release * sr) for r in chosen)
                    + h_dur_n)
                for r in chosen:
                    srcb, src_sr = lib.audio(r.sample)
                    pitch = note_curve(
                        "pitch_cents",
                        h_dur_n + int(shaped(r).ampeg_release * sr),
                        note_offset_n)
                    part = render_region(shaped(r), srcb, src_sr,
                                         s["midi"], h_dur_n, sr,
                                         pitch_cents=pitch, **rr_kwargs)
                    sig[:part.size] += part
                sig = sig * h_vel * extra_g
            if join_in:                       # suppressed attack fades in
                f = min(join_n, sig.size)
                sig[:f] *= np.sin(np.linspace(0, np.pi / 2, f))
            if join_out:                      # hold, then hand over
                cut = min(h_dur_n, sig.size)
                f = min(join_n, sig.size - (cut - join_n))                     if cut > join_n else cut
                sig[cut - f:cut] *= np.cos(np.linspace(0, np.pi / 2, f))
                sig = sig[:cut]               # the join replaces the release
            seg = min(sig.size, total_n - h_start)
            if seg > 0:
                out[h_start:h_start + seg] += sig[:seg] * env_gain

        if mods.get("retrigger"):        # tremolo fallback: seeded train
            t_off = 0
            while t_off < dur_n and s["start"] + t_off < total_n:
                interval = int(sr * 0.085
                               * (1.0 + 0.25 * (s["rng"].random() - 0.5)))
                hit_n = min(clamp_n or int(0.14 * sr),
                            dur_n - t_off + int(0.06 * sr))
                render_hit(s["start"] + t_off, hit_n, s["vel"] * 0.85,
                           s["rng"])
                t_off += max(interval, 1)
        else:
            render_hit(s["start"], held_n, s["vel"], s["rng"])
    return out


def render_section(layer: dict, total_n: int, sr: int, tm, rng, lib,
                   groove: dict | None = None,
                   report: dict | None = None) -> np.ndarray:
    """Ensemble multiplication: N seeded virtual players from one part —
    independent timing offsets, micro-detune, round-robin pools, and a
    stereo position across the spread. All jitter derives from the spec
    hash via player-namespaced RNG paths (variant-aware by construction).

    Honest disclosure (also in the docs): N copies of one recorded player
    is a chorus of soloists, not a true section. VSCO's violin recordings
    are already section recordings; multiplication here thickens and
    spatializes — prefer genuinely-sampled sections where they exist."""
    sec = layer["section"]
    n_players = int(sec["size"])
    spread = float(sec.get("spread", 0.6))
    det_c = float(sec.get("detune_c", 7.0))
    tim_s = float(sec.get("timing_s", 0.009))
    base_pan = float(layer.get("pan", 0.0))
    out = np.zeros((total_n, 2))
    scale = 1.0 / np.sqrt(n_players)
    for p in range(n_players):
        prng = rng(f"player{p}:static")
        dt = (prng.random() * 2.0 - 1.0) * tim_s
        dmidi = (prng.random() * 2.0 - 1.0) * det_c / 100.0
        pos = base_pan + spread * (
            -1.0 + 2.0 * p / (n_players - 1) if n_players > 1 else 0.0)
        pos = float(np.clip(pos, -1.0, 1.0))
        mono = render_instrument_track(
            layer, total_n, sr, tm,
            lambda sub, _p=p: rng(f"player{_p}:{sub}"), lib,
            groove=groove, report=report if p == 0 else None,
            time_offset_s=dt, midi_offset=dmidi)
        theta = (pos + 1.0) * np.pi / 4.0
        out[:, 0] += np.cos(theta) * mono * scale
        out[:, 1] += np.sin(theta) * mono * scale
    return out
