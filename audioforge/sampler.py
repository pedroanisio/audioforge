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
Resampling uses a rate-adaptive Hann-windowed-sinc lowpass to suppress
aliasing when transposition or source-rate conversion skips samples.

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
import time
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
              "ampeg_release", "loop_crossfade", "tune", "volume",
              "lorand", "hirand"}
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
    lorand: float = 0.0               # random round-robin range [lorand, hirand)
    hirand: float = 1.0
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
    seeded pick. Two SFZ round-robin mechanisms are honoured: positional
    `seq_length`/`seq_position`, and random `lorand`/`hirand` (a region wins
    when a seeded uniform draw falls in its [lorand, hirand) sub-range). The
    rng is the per-note RNG (root includes the variant tag), so repeated
    notes vary, re-renders are identical, and pack variants re-realize — the
    v2.8 lesson, applied from day one. Regions with neither mechanism stack
    (true layering, e.g. multiple mics)."""
    hits = [r for r in regions
            if r.lokey <= midi <= r.hikey and r.lovel <= vel127 <= r.hivel]
    if not hits:
        return []
    out, seq_sets, rand_sets = [], {}, {}
    for r in hits:
        if r.seq_length > 1:
            seq_sets.setdefault((r.lokey, r.hikey, r.lovel, r.hivel,
                                 r.seq_length), []).append(r)
        elif r.lorand > 0.0 or r.hirand < 1.0:
            rand_sets.setdefault((r.lokey, r.hikey, r.lovel, r.hivel),
                                 []).append(r)
        else:
            out.append(r)
    # Positional round-robins: rotate by a seeded index.
    for key, pool in sorted(seq_sets.items()):
        pool.sort(key=lambda r: r.seq_position)
        pick = 1 + int(rng.integers(0, key[4]))
        chosen = [r for r in pool if r.seq_position == pick]
        out.extend(chosen if chosen else pool[:1])
    # Random round-robins: one seeded uniform draw per slot selects the region
    # whose [lorand, hirand) contains it (first match wins on overlap; the
    # last region covers any gap so a note is never dropped).
    for key, pool in sorted(rand_sets.items()):
        pool.sort(key=lambda r: (r.lorand, r.sample))
        u = float(rng.random())
        chosen = next((r for r in pool if r.lorand <= u < r.hirand), pool[-1])
        out.append(chosen)
    return out


# fixed resampling kernel: 32-tap Hann-windowed sinc, documented and frozen
_SINC_HALF = 16


def _sinc_read(src: np.ndarray, positions: np.ndarray,
               rates: np.ndarray | None = None) -> np.ndarray:
    """Bandlimited fractional reads with a playback-rate-dependent cutoff.

    Playback faster than one source sample per output sample is downsampling.
    Widening the kernel and reducing its cutoff removes frequencies that would
    fold into the output band. Each read uses its local rate, including glides.
    Chunks bound working memory without changing any sample's calculation.
    """
    out = np.zeros(positions.size, dtype=np.float64)
    if not src.size or not positions.size:
        return out
    if rates is None:
        rates = np.gradient(positions) if positions.size > 1 else np.ones(1)
    rates = np.broadcast_to(rates, positions.shape)
    cutoffs = 0.94 / np.maximum(1.0, np.abs(rates))
    radius = int(np.ceil(_SINC_HALF / float(np.min(cutoffs))))
    offsets = np.arange(-radius + 1, radius + 1)
    chunk = max(1, min(4096, 1_000_000 // offsets.size))
    for start in range(0, positions.size, chunk):
        end = min(start + chunk, positions.size)
        pos = positions[start:end]
        base = np.floor(pos).astype(np.int64)
        x = offsets[None, :] - (pos - base)[:, None]
        cutoff = cutoffs[start:end, None]
        scaled = x * cutoff
        window = np.where(
            np.abs(scaled) < _SINC_HALF,
            0.5 + 0.5 * np.cos(np.pi * scaled / _SINC_HALF), 0.0)
        kernel = cutoff * np.sinc(scaled) * window
        kernel /= np.sum(kernel, axis=1, keepdims=True)
        indices = base[:, None] + offsets[None, :]
        values = src[np.clip(indices, 0, src.size - 1)]
        values = np.where((indices >= 0) & (indices < src.size), values, 0.0)
        out[start:end] = np.einsum("ij,ij->i", values, kernel)
        out[start:end] *= (pos >= 0) & (pos < src.size)
    return out


def transition_offset(region: Region, source_rate: int) -> dict:
    """Use a library's sustain-loop start, or its declared attack endpoint.

    These are approximate joins between stationary notes; an SFZ sustain loop
    is evidence for a usable steady portion, not a recorded transition.
    """
    if region.loop_mode in ("loop_continuous", "loop_sustain") and region.loop_end > region.loop_start:
        return {"seconds": region.loop_start / source_rate, "evidence": "sfz_loop_start"}
    return {"seconds": region.ampeg_attack, "evidence": "sfz_envelope_attack"}


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
    rel_n = int(round(region.ampeg_release * sr))
    total_n = dur_n + rel_n
    if ramp_from_midi is not None and ramp_from_midi != midi_float:
        semis0 = (ramp_from_midi - region.pitch_keycenter + region.transpose
                  + region.tune / 100.0)
        r0 = (2.0 ** (semis0 / 12.0)) * (src_sr / sr)
        k = min(total_n, max(2, int(ramp_s * sr)))
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
    original_source = src
    sustain_release_positions = None

    if region.loop_mode in ("loop_continuous", "loop_sustain") \
            and region.loop_end > region.loop_start:
        ls, le = region.loop_start, min(region.loop_end, src.size - 1)
        body = src[ls:le]
        xf = int(min(region.loop_crossfade * src_sr, body.size * 0.5))
        stride = body.size - xf
        if region.loop_mode == "loop_sustain" and dur_n < total_n:
            at_release = positions[dur_n]
            phase = ls + (at_release - ls) % max(stride, 1) if at_release >= le else at_release
            sustain_release_positions = phase + positions[dur_n:] - at_release
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
    out = _sinc_read(src, positions, rate)
    if sustain_release_positions is not None:
        tail = _sinc_read(original_source, sustain_release_positions, rate[dur_n:])
        blend = min(int(.002 * sr), tail.size)
        if blend:
            weight = np.linspace(0, 1, blend)
            tail[:blend] = out[dur_n:dur_n + blend] * (1 - weight) + tail[:blend] * weight
        out[dur_n:] = tail

    env = synth.note_adsr(dur_n, sr, region.ampeg_attack, region.ampeg_decay,
                          region.ampeg_sustain / 100.0, region.ampeg_release)
    out *= env * (10.0 ** (region.volume / 20.0))
    return out


freq_to_midi = synth.freq_to_midi   # single definition lives in synth


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
               "sustain regions; joined slurs use approximate sample-aware crossfades"),
}


def resolve_articulation_detail(lib, instrument: str, art: str) -> dict:
    """Resolve sampled or synthetic-fallback articulation with evidence."""
    inst = lib.manifest["instruments"].get(instrument, {})
    available = set(inst.get("articulations", {}))
    if art in available:
        return {
            "regions": lib.regions(instrument, art),
            "mods": {},
            "resolved_articulation": art,
            "fallback": None,
        }
    if art not in _FALLBACKS:
        raise ValueError(f"instrument '{instrument}': articulation '{art}' "
                         f"is not sampled and has no fallback "
                         f"(sampled: {sorted(available)})")
    bases, mods, desc = _FALLBACKS[art]
    for base in bases:
        if base in available:
            return {
                "regions": lib.regions(instrument, base),
                "mods": dict(mods),
                "resolved_articulation": base,
                "fallback": {
                    "requested_articulation": art,
                    "base_articulation": base,
                    "description": desc,
                    "family": "synthetic_articulation_fallback",
                    "mods": dict(mods),
                },
            }
    raise ValueError(
        f"instrument '{instrument}': articulation '{art}' unavailable and "
        f"no fallback base exists (sampled: {sorted(available)})")


def resolve_articulation(lib, instrument: str, art: str):
    """-> (regions, mods, fallback_description|None). Loud failure if even
    the fallback chain finds nothing."""
    detail = resolve_articulation_detail(lib, instrument, art)
    fallback = detail["fallback"]
    fb = None
    if fallback:
        fb = (f"'{art}' -> {fallback['description']} "
              f"(base: '{fallback['base_articulation']}')")
    return detail["regions"], detail["mods"], fb


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
                            midi_offset: float = 0.0,
                            plan_segments: list[dict] | None = None) -> np.ndarray:
    """Instrument layer: the same scheduling semantics as note tracks
    (groove slots, tempo map, seeded humanize, velocity clip), each note
    rendered through the library's SFZ regions instead of a synth voice.

    P3 performance model:
    - slur groups render with legato joins — the outgoing note holds
      through an equal-power crossfade window (default 50 ms, `legato_s`),
      the incoming note skips its recorded attack and glides its read rate
      from the previous pitch (a real smear, not a crossfade artifact);
    - an opt-in `phrasing` arch shapes slur groups: velocities rise toward
      the group's temporal midpoint and ease after; authored gates remain
      unchanged (documented constants, fully deterministic);
    - `time_offset_s`/`midi_offset` are the per-player handles used by
      section multiplication."""
    from .sequencer import _sum_note_curve, dyn_env, dyn_gain
    instrument = track["instrument"]
    default_art = track.get("articulation", "sustain")
    dyn_pts = track.get("dynamic")
    join_w = float(track.get("legato_s", 0.05))
    art_cache: dict[str, tuple] = {}
    plan_by_note = {
        int(seg["note_index"]): seg
        for seg in (plan_segments or [])
        if seg.get("layer") == track.get("name", "?")
        and seg.get("layer_type") == "instrument"
        and "note_index" in seg
    }

    def planned_regions(segment: dict | None, identities: list[dict] | None,
                        candidates: list[Region]) -> list[Region] | None:
        if segment is None or identities is None:
            return None
        by_identity = {
            (r.sample, r.lokey, r.hikey, r.lovel, r.hivel,
             r.seq_length, r.seq_position): r
            for r in candidates
        }
        out = []
        for item in identities:
            key = (
                item["sample"],
                item["key_range"][0],
                item["key_range"][1],
                item["velocity_range"][0],
                item["velocity_range"][1],
                item["seq_length"],
                item["seq_position"],
            )
            region = by_identity.get(key)
            if region is None:
                raise ValueError(
                    f"render plan segment {segment.get('id')}: selected region "
                    f"{item.get('sample')} is not available in current library")
            out.append(region)
        return out

    def replay_planned_selection_rng(candidates: list[Region], midi: int,
                                     vel127: int, rng) -> None:
        """Preserve legacy RNG stream while selection comes from the plan."""
        rr_sets = set()
        for r in candidates:
            if (r.lokey <= midi <= r.hikey and r.lovel <= vel127 <= r.hivel
                    and r.seq_length > 1):
                rr_sets.add((r.lokey, r.hikey, r.lovel, r.hivel,
                             r.seq_length))
        for key in sorted(rr_sets):
            rng.integers(0, key[4])

    def articulation(name):
        if name not in art_cache:
            regs, mods, fb = resolve_articulation(lib, instrument, name)
            if fb and report is not None:
                report.setdefault("articulation_fallbacks", {}).setdefault(
                    f"{track.get('name', '?')}/{instrument}", {})[name] = fb
            art_cache[name] = (regs, mods)
        return art_cache[name]

    def articulation_from_plan(segment: dict | None, name: str):
        if segment is None:
            return articulation(name)
        decision = segment.get("decision", {})
        if decision.get("requested_articulation") != name:
            raise ValueError(
                f"render plan segment {segment.get('id')}: requested "
                "articulation drifted")
        resolved = decision.get("resolved_articulation")
        if not resolved:
            raise ValueError(
                f"render plan segment {segment.get('id')}: missing "
                "resolved_articulation")
        return lib.regions(instrument, resolved), dict(decision.get("mods", {}))

    env_gain = 10.0 ** (track.get("gain_db", 0.0) / 20.0)
    from .performance import legato_links, schedule_notes
    out = np.zeros(total_n)
    sched = schedule_notes(track, total_n, sr, tm, rng_factory, groove,
                           time_offset_s, midi_offset)

    # ---- pass 2: render with join awareness --------------------------------
    join_n = int(join_w * sr)
    links = legato_links(sched)
    for k, s in enumerate(sched):
        seg_t0 = time.perf_counter_ns()
        s["vel"] = float(np.clip(s["vel"], 0.0, 1.3))
        previous, following = links[k]
        prev = sched[previous] if previous is not None else None
        nxt = sched[following] if following is not None else None
        join_in, join_out = prev is not None, nxt is not None
        plan_segment = plan_by_note.get(int(s["note_index"]))
        regions, mods = articulation_from_plan(plan_segment, s["art"])
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
            return dataclasses.replace(
                r, ampeg_release=mods.get("release_s", r.ampeg_release)
                + float(s["event"].get("release_s_add", 0)),
                ampeg_attack=mods.get("attack_s", r.ampeg_attack)
                * float(s["event"].get("attack_scale", 1)))

        def transition_kwargs(region, source_rate):
            if not join_in:
                return {}
            offset = transition_offset(region, source_rate)
            return {"src_offset_s": offset["seconds"],
                    "ramp_from_midi": prev["midi"], "ramp_s": join_w}
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
            full_n = h_dur_n + int(round(max_rel * sr))
            note_gain_db = note_curve("gain_db", full_n, note_offset_n)
            note_gain = (10.0 ** (note_gain_db / 20.0)
                         if note_gain_db is not None else None)
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
                planned_bands = {}
                if plan_segment is not None:
                    for item in plan_segment["decision"]["velocity"].get("bands", []):
                        planned_bands[tuple(item["velocity_range"])] = item
                for (c, lo, hi, regs), w in zip(bands, weights):
                    if w.max() < 1e-3:
                        continue
                    planned = planned_bands.get((lo, hi))
                    chosen = planned_regions(
                        plan_segment,
                        planned.get("selected_regions") if planned else None,
                        regs,
                    )
                    if chosen is None:
                        chosen = select_regions(regs, midi_i, int(c), h_rng)
                    else:
                        replay_planned_selection_rng(regs, midi_i, int(c),
                                                     h_rng)
                    for r in chosen:
                        srcb, src_sr = lib.audio(r.sample)
                        pitch = note_curve(
                            "pitch_cents",
                            h_dur_n + int(round(shaped(r).ampeg_release * sr)),
                            note_offset_n)
                        part = render_region(shaped(r), srcb, src_sr,
                                             s["midi"], h_dur_n, sr,
                                             pitch_cents=pitch, **transition_kwargs(r, src_sr))
                        m = min(part.size, full_n)
                        sig[:m] += part[:m] * w[:m]
                sig *= dyn_gain(v_env) * h_vel * extra_g
                if note_gain is not None:
                    sig *= note_gain
            else:
                v127 = int(np.clip(round(h_vel * 127), 1, 127))
                chosen = None
                if plan_segment is not None:
                    velocity = plan_segment["decision"]["velocity"]
                    chosen = planned_regions(
                        plan_segment,
                        velocity.get("selected_regions"),
                        kreg,
                    )
                if chosen is None:
                    chosen = select_regions(kreg, midi_i, v127, h_rng)
                else:
                    replay_planned_selection_rng(kreg, midi_i, v127, h_rng)
                if not chosen:
                    raise ValueError(
                        f"instrument '{instrument}': no region at velocity "
                        f"{v127} for midi {midi_i}")
                sig = np.zeros(
                    max(int(round(shaped(r).ampeg_release * sr)) for r in chosen)
                    + h_dur_n)
                for r in chosen:
                    srcb, src_sr = lib.audio(r.sample)
                    pitch = note_curve(
                        "pitch_cents",
                        h_dur_n + int(round(shaped(r).ampeg_release * sr)),
                        note_offset_n)
                    part = render_region(shaped(r), srcb, src_sr,
                                         s["midi"], h_dur_n, sr,
                                         pitch_cents=pitch, **transition_kwargs(r, src_sr))
                    sig[:part.size] += part
                sig = sig * h_vel * extra_g
                if note_gain is not None:
                    sig *= note_gain
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
        if report is not None and plan_segment is not None:
            elapsed_ms = (time.perf_counter_ns() - seg_t0) / 1_000_000.0
            report.setdefault("plan_segment_actual_ms", {})[
                plan_segment["id"]
            ] = round(elapsed_ms, 6)
    return out


def render_section(layer: dict, total_n: int, sr: int, tm, rng, lib,
                   groove: dict | None = None,
                   report: dict | None = None,
                   plan_segments: list[dict] | None = None) -> np.ndarray:
    """Ensemble multiplication: N seeded virtual players from one part —
    independent timing offsets, micro-detune, round-robin pools, and a
    stereo position across the spread. All jitter derives from the take
    identity via player-namespaced RNG paths (variant-aware by construction).

    Honest disclosure (also in the docs): N copies of one recorded player
    is a chorus of soloists, not a true section. VSCO's violin recordings
    are already section recordings; multiplication here thickens and
    spatializes — prefer genuinely-sampled sections where they exist."""
    sec = layer["section"]
    n_players = int(sec["size"])
    from .performance import section_player
    out = np.zeros((total_n, 2))
    scale = 1.0 / np.sqrt(n_players)
    for p in range(n_players):
        dt, dmidi, pos = section_player(layer, p, rng)
        mono = render_instrument_track(
            layer, total_n, sr, tm,
            lambda sub, _p=p: rng(f"player{_p}:{sub}"), lib,
            groove=groove, report=report if p == 0 else None,
            time_offset_s=dt, midi_offset=dmidi,
            plan_segments=[seg for seg in (plan_segments or []) if seg.get("player_index", 0) == p])
        theta = (pos + 1.0) * np.pi / 4.0
        out[:, 0] += np.cos(theta) * mono * scale
        out[:, 1] += np.sin(theta) * mono * scale
    return out
