#!/usr/bin/env python3
"""Generate compositions/road_trip/*.af — "Five Seats, One Horizon", an
80-minute family road-trip electronic journey for a mixed-age audience
(M46, F49, M21, M17, F10): cinematic, melodic, warm, driving — never dark,
sexual, aggressive, or repetitive.

Nine movements, ten files (movement 5, "Road Game / Momentum", is 12 minutes
and is split across the engine's 600s-per-asset cap into two parts that play
back to back). Home key A major (warm I-vi-IV-V7: Amaj7-F#min7-Dmaj7-E7),
lifting to D major at the emotional peak ("Big View"), returning home for the
drive back. A single four-note "road" motif is restated in different voices,
tempos, and registers throughout so the ten-year-old listener can recognize it
returning every time.

Energy is authored the same way as scripts/gen_techno_24h.py: explicit
per-layer `auto gain:`/`auto cutoff:` breakpoint envelopes. Because nearly
every layer's arrangement dynamics track the same movement-level energy curve
(the 0-10 contour named in the creative brief), `energy_env`/`hz_env` below
turn one curve plus a layer's (gain_min, gain_max) or (hz_min, hz_max) range
into breakpoints, instead of hand-tuning ten unrelated arrays per movement.
Layers whose shape genuinely differs (a kick that must vanish early, a motif
that only swells in at the reveal) just get their own explicit pairs list.
"""
from pathlib import Path

OUT = Path("compositions/road_trip")
OUT.mkdir(parents=True, exist_ok=True)


def energy_env(dur, curve, gmin, gmax, dp=1):
    """curve: [(frac_of_dur 0..1, energy 0..10), ...] -> [(seconds, value), ...]"""
    pts = []
    for frac, e in curve:
        t = round(frac * dur, 2)
        v = gmin + (gmax - gmin) * (e / 10.0)
        pts.append((t, round(v, dp)))
    return pts


def fmt_pairs(pairs):
    return ", ".join(f"{t:g}s={v:g}" for t, v in pairs)


def auto_gain(pairs, indent=4):
    return " " * indent + f"auto gain: {fmt_pairs(pairs)}\n"


def auto_cutoff(pairs, indent=4):
    return " " * indent + f"auto cutoff: {fmt_pairs(pairs)}\n"


# --- the road motif: a four-note arch, restated (transposed/diminished/
# augmented) in every movement so it stays recognizable across 80 minutes ---
ROAD_MOTIF_A = """  motif road {
    A4  @ 0b   for 1b   vel 0.7
    C#5 @ 1b   for 1b   vel 0.75
    E5  @ 2b   for 1b   vel 0.8
    D5  @ 3b   for 1.5b vel 0.78
    C#5 @ 4.5b for 0.5b vel 0.7
    A4  @ 5b   for 3b   vel 0.65
  }
"""
ROAD_MOTIF_D = """  motif road {
    D5  @ 0b   for 1b   vel 0.7
    F#5 @ 1b   for 1b   vel 0.75
    A5  @ 2b   for 1b   vel 0.8
    G5  @ 3b   for 1.5b vel 0.78
    F#5 @ 4.5b for 0.5b vel 0.7
    D5  @ 5b   for 3b   vel 0.65
  }
"""


def play_calls(motif, start_beat, every_beats, count, indent=4, transposes=None):
    """A periodic restatement of `motif`, e.g. every 32 beats, with an optional
    per-repeat transpose/diatonic list for gentle variation."""
    lines = []
    sp = " " * indent
    for i in range(count):
        b = start_beat + i * every_beats
        mod = ""
        if transposes:
            mod = transposes[i % len(transposes)]
        lines.append(f"{sp}play road @ {b:g}b{mod}")
    return "\n".join(lines) + "\n"


# =============================================================================
# 01 — Departure / Everyone Gets In  (0:00-8:00, 480s)
# =============================================================================

def section_01():
    dur = 480
    energy = [(0, 1), (0.3, 2), (0.7, 2.5), (1.0, 3)]
    heartbeat = energy_env(dur, energy, -55, -30)
    clicks = energy_env(dur, energy, -55, -34)
    pad = energy_env(dur, energy, -30, -18)
    motif_g = [(0, -60), (0.55, -60), (0.62, -26), (0.85, -24), (1.0, -30)]
    motif_g = [(round(f * dur, 1), g) for f, g in motif_g]

    return f"""# 01 — Departure / Everyone Gets In. Bags in the trunk, seatbelts, morning
# anticipation. No real beat yet — a warm sub heartbeat and dashboard clicks.
asset s01_departure {{
  kind: soundtrack
  duration: {dur}s
  tempo: 84bpm
  key: A major
  emotion: calm=0.55, intimacy=0.45, wonder=0.35
  intensity: 0s=0.1, 480s=0.3

  marker ignition      @ 0s
  marker doors_close    @ 18s
  marker pulling_away   @ 240s
  marker gentle_hum     @ 420s

{ROAD_MOTIF_A}
  layer heartbeat : drums {{
    voice: kick
    pattern: X...............
    tune: -6st
    decay: 0.7
    snap: 0.15
    bend: 0.1
    gain: -30db
    humanize: 0.1
{auto_gain(heartbeat)}  }}

  layer clicks : drums {{
    voice: hat
    pattern: ....x.......x...
    tune: 4st
    decay: 0.25
    gain: -34db
    humanize: 0.15
{auto_gain(clicks)}  }}

  layer door_thunk : noise {{
    color: brown
    start: 17s
    duration: 1.4s
    gain: -22db
    env: a=0.01s d=0.3s s=0.1 r=0.9s
    fx: lowpass(500hz), highpass(90hz)
  }}

  layer pad : notes {{
    osc: pad
    bandwidth: 45c
    gain: -20db
    env: a=3s d=2s s=0.85 r=4s
    notes: A2maj7 @ 0b for 16b, F#2min7 @ 16b for 16b, D3maj7 @ 32b for 16b, E3maj7 @ 48b for 16b
    loop: 64b
    fx: lowpass(1200hz), reverb(decay=4.5s, mix=0.4)
    auto cutoff: 0s=500, 480s=900
{auto_gain(pad)}  }}

  layer motif_hint : notes {{
    osc: pluck
    damping: 0.55
    brightness: 0.4
    gain: -26db
    env: a=0.01s d=0.3s s=0.2 r=0.6s
{play_calls("road", 168, 16, 4)}    loop: 0b
    fx: lowpass(2200hz), reverb(decay=3s, mix=0.35)
{auto_gain(motif_g)}    pan: 0.15
  }}

  master {{
    width: 0.85
    lufs: -20
    peak: -1.5db
    fadein: 2s
    fadeout: 3s
    fx: lowpass(9000hz), highpass(32hz), fdn(rt60=2.2, rt60_high=1.0, mix=0.18), saturate(amount=0.05, warmth=0.2)
  }}
}}
"""


# =============================================================================
# 02 — Leaving Town  (8:00-17:00, 540s)
# =============================================================================

def section_02():
    dur = 540
    energy = [(0, 3), (1.0, 5)]
    kick = energy_env(dur, energy, -45, -11)
    clap = energy_env(dur, energy, -45, -17)
    hat = energy_env(dur, energy, -40, -19)
    bass = energy_env(dur, energy, -40, -12)
    pad = energy_env(dur, energy, -26, -15)
    motif_g = energy_env(dur, energy, -40, -14)
    cutoff_bass = energy_env(dur, energy, 260, 620, dp=0)
    cutoff_pad = energy_env(dur, energy, 500, 1300, dp=0)

    return f"""# 02 — Leaving Town. Neighborhood roads, first jokes in the car, the road
# motif is introduced plainly. Relaxed 98 BPM groove, bouncy warm bass.
asset s02_leaving_town {{
  kind: soundtrack
  duration: {dur}s
  tempo: 98bpm
  key: A major
  groove: swing16 0.12
  emotion: wonder=0.5, calm=0.3, triumph=0.2

  marker neighborhood     @ 0s
  marker first_laugh      @ 60s
  marker road_motif_intro @ 180s
  marker edge_of_town     @ 480s

{ROAD_MOTIF_A}
  bus pump {{
    duck: source=kick amount=4.5db attack=0.01s release=0.18s threshold=-40db
    fx: saturate(amount=0.08, warmth=0.2)
  }}

  layer kick : drums {{
    voice: kick
    pattern: X.......X.......
    tune: -4st
    decay: 0.5
    snap: 0.35
    bend: 0.2
    gain: -11db
    humanize: 0.05
{auto_gain(kick)}  }}

  layer clap : drums {{
    voice: clap
    pattern: ....x.......x...
    gain: -17db
    humanize: 0.08
    fx: reverb(decay=0.9s, mix=0.16)
{auto_gain(clap)}  }}

  layer hat : drums {{
    voice: hat
    pattern: ..x.x.x.x.x.x.x.
    tune: 1st
    decay: 0.28
    gain: -19db
    humanize: 0.07
{auto_gain(hat)}  }}

  layer bass : notes {{
    osc: saw
    bus: pump
    gain: -12db
    env: a=0.01s d=0.14s s=0.4 r=0.1s
    velbright: 0.4
    notes: A1 @ 0b for 0.9b vel 0.75, A1 @ 2b for 0.9b vel 0.6, F#1 @ 4b for 0.9b vel 0.75, F#1 @ 6b for 0.9b vel 0.6, D2 @ 8b for 0.9b vel 0.75, D2 @ 10b for 0.9b vel 0.6, E1 @ 12b for 0.9b vel 0.75, E1 @ 14b for 0.9b vel 0.65
    loop: 16b
    fx: lowpass(500hz), saturate(amount=0.1, warmth=0.3)
{auto_cutoff(cutoff_bass)}{auto_gain(bass)}  }}

  layer pad : notes {{
    osc: pad
    bandwidth: 40c
    bus: pump
    gain: -18db
    env: a=1s d=1s s=0.8 r=1.5s
    notes: A2maj7 @ 0b for 8b, F#2min7 @ 8b for 8b, D3maj7 @ 16b for 8b, E3maj7 @ 24b for 8b
    loop: 32b
    fx: lowpass(1400hz), reverb(decay=2.5s, mix=0.25)
{auto_cutoff(cutoff_pad)}{auto_gain(pad)}  }}

  layer motif_lead : notes {{
    osc: pluck
    damping: 0.4
    brightness: 0.65
    gain: -14db
    env: a=0.005s d=0.25s s=0.3 r=0.3s
{play_calls("road", 32, 32, 14, transposes=[""] * 3 + [" vel 0.85"] + [""] * 3 + [" diatonic 1"])}    loop: 0b
    fx: lowpass(2600hz), delay(time=0.28, feedback=0.2, mix=0.15)
{auto_gain(motif_g)}    pan: 0.2
  }}

  master {{
    width: 0.9
    lufs: -14
    peak: -1db
    fadein: 1s
    fadeout: 2s
    fx: lowpass(13000hz), highpass(30hz), fdn(rt60=1.8, rt60_high=0.9, mix=0.12), comp(threshold=-16, ratio=1.8, attack=0.02, release=0.18, knee=6), saturate(amount=0.08, warmth=0.22)
  }}
}}
"""


# =============================================================================
# 03 — Highway Opens  (17:00-27:00, 600s)
# =============================================================================

def section_03():
    dur = 600
    energy = [(0, 5), (1.0, 6)]
    kick = energy_env(dur, energy, -40, -8)
    clap = energy_env(dur, energy, -40, -15)
    hat = energy_env(dur, energy, -36, -17)
    ohat = energy_env(dur, energy, -40, -21)
    bass = energy_env(dur, energy, -35, -9)
    pad = energy_env(dur, energy, -24, -14)
    lead = energy_env(dur, energy, -40, -11)
    hum = energy_env(dur, energy, -50, -36)
    cutoff_bass = energy_env(dur, energy, 320, 780, dp=0)
    cutoff_lead = energy_env(dur, energy, 900, 2400, dp=0)

    return f"""# 03 — Highway Opens. The city drops behind, the car finds its rhythm.
# Steady 110 BPM melodic house — the first "everyone can nod along" section.
asset s03_highway_opens {{
  kind: soundtrack
  duration: {dur}s
  tempo: 110bpm
  key: A major
  groove: swing16 0.08
  emotion: wonder=0.6, triumph=0.3, cinematic_intensity=0.3

  marker merge          @ 0s
  marker open_road       @ 120s
  marker everyone_nods    @ 360s
  marker miles_ahead      @ 540s

{ROAD_MOTIF_A}
  bus pump {{
    duck: source=kick amount=5db attack=0.008s release=0.16s threshold=-40db
    fx: saturate(amount=0.1, warmth=0.22)
  }}
  bus air {{
    fx: delay(time=0.234, feedback=0.22, mix=0.14), hall(rt60=1.6, mix=0.12)
  }}

  layer kick : drums {{
    voice: kick
    pattern: X...X...X...X...
    tune: -4st
    decay: 0.5
    snap: 0.45
    bend: 0.3
    gain: -8db
    humanize: 0.04
{auto_gain(kick)}  }}

  layer clap : drums {{
    voice: clap
    pattern: ....X.......x...
    gain: -15db
    humanize: 0.06
    fx: reverb(decay=1.0s, mix=0.16)
{auto_gain(clap)}  }}

  layer hat : drums {{
    voice: hat
    pattern: x.x.x.x.x.x.x.x.
    tune: 2st
    decay: 0.25
    gain: -17db
    humanize: 0.05
{auto_gain(hat)}  }}

  layer ohat : drums {{
    voice: open_hat
    pattern: ....x.......x...
    decay: 0.5
    gain: -21db
{auto_gain(ohat)}  }}

  layer road_hum : noise {{
    color: brown
    start: 0s
    duration: {dur}s
    gain: -40db
    env: a=4s d=0.1s s=0.9 r=4s
    fx: bandpass(220hz), lowpass(700hz)
{auto_gain(hum)}  }}

  layer bass : notes {{
    osc: saw
    bus: pump
    gain: -9db
    env: a=0.006s d=0.12s s=0.4 r=0.08s
    velbright: 0.4
    notes: A1 @ 0.5b for 0.45b, A1 @ 1.5b for 0.45b, A1 @ 2.5b for 0.45b, F#1 @ 3.5b for 0.45b vel 0.85, F#1 @ 4.5b for 0.45b, D2 @ 5.5b for 0.45b, D2 @ 6.5b for 0.45b, E1 @ 7.5b for 0.45b vel 0.85
    loop: 8b
    fx: lowpass(600hz), drive(amount=0.15)
{auto_cutoff(cutoff_bass)}{auto_gain(bass)}  }}

  layer pad : notes {{
    osc: pad
    bandwidth: 40c
    bus: pump
    gain: -16db
    env: a=1.2s d=1s s=0.8 r=1.8s
    notes: A2maj7 @ 0b for 8b, F#2min7 @ 8b for 8b, D3maj7 @ 16b for 8b, E3maj7 @ 24b for 8b
    loop: 32b
    fx: lowpass(1600hz), reverb(decay=2.8s, mix=0.26)
{auto_gain(pad)}  }}

  layer lead : notes {{
    osc: saw
    unison: 3
    spread: 14c
    bus: air
    gain: -11db
    env: a=0.01s d=0.2s s=0.6 r=0.3s
    velbright: 0.4
{play_calls("road", 40, 16, 24, transposes=[""] * 3 + [" diatonic 1"] + [""] * 3 + [" vel 0.85"])}    loop: 0b
    fx: lowpass(2200hz)
{auto_cutoff(cutoff_lead)}{auto_gain(lead)}    pan: -0.1
  }}

  master {{
    width: 0.92
    lufs: -13
    peak: -1db
    fadein: 1s
    fadeout: 3s
    fx: lowpass(15000hz), highpass(28hz), fdn(rt60=1.9, rt60_high=1.0, mix=0.14), comp(threshold=-15, ratio=2.0, attack=0.015, release=0.16, knee=5), saturate(amount=0.1, warmth=0.24)
  }}
}}
"""


# =============================================================================
# 04 — Window Seat Daydream  (27:00-36:00, 540s)
# =============================================================================

def section_04():
    dur = 540
    energy = [(0, 6), (0.35, 4), (0.65, 4), (1.0, 6)]
    kick = energy_env(dur, energy, -50, -24)
    shaker = energy_env(dur, energy, -40, -22)
    ohat = energy_env(dur, energy, -45, -27)
    bass = energy_env(dur, energy, -40, -20)
    pad = energy_env(dur, energy, -26, -15)
    bell = energy_env(dur, energy, -40, -18)
    cutoff_pad = energy_env(dur, energy, 600, 2200, dp=0)

    return f"""# 04 — Window Seat Daydream. Clouds, fields, distant hills. Drums lighten;
# bell synths and a childlike (not childish) melody carry the section.
asset s04_daydream {{
  kind: soundtrack
  duration: {dur}s
  tempo: 100bpm
  key: A major
  groove: laidback 0.25
  emotion: wonder=0.7, calm=0.4, intimacy=0.3

  marker window_gaze    @ 0s
  marker clouds_drift    @ 180s
  marker distant_hills   @ 360s
  marker second_thought  @ 480s

{ROAD_MOTIF_A}
  layer kick : drums {{
    voice: kick
    pattern: X.......x.......
    tune: -3st
    decay: 0.55
    snap: 0.2
    bend: 0.1
    gain: -24db
    humanize: 0.07
{auto_gain(kick)}  }}

  layer shaker : drums {{
    voice: hat
    pattern: x.x.x.x.x.x.x.x.
    tune: 3st
    decay: 0.25
    gain: -22db
    humanize: 0.12
{auto_gain(shaker)}  }}

  layer ohat : drums {{
    voice: open_hat
    pattern: ..x...x...x...x.
    decay: 0.4
    gain: -27db
    humanize: 0.1
{auto_gain(ohat)}  }}

  layer bass : notes {{
    osc: triangle
    gain: -20db
    env: a=0.02s d=0.3s s=0.5 r=0.5s
    notes: A2 @ 0b for 3.5b vel 0.6, F#2 @ 4b for 3.5b vel 0.55, D2 @ 8b for 3.5b vel 0.6, E2 @ 12b for 3.5b vel 0.55
    loop: 16b
    fx: lowpass(500hz)
{auto_gain(bass)}  }}

  layer pad : notes {{
    osc: pad
    bandwidth: 55c
    gain: -18db
    env: a=2s d=1.5s s=0.85 r=3s
    notes: A2maj7 @ 0b for 16b, F#2min7 @ 16b for 16b, D3maj7 @ 32b for 16b, E3maj7 @ 48b for 16b
    loop: 64b
    fx: lowpass(1000hz), reverb(decay=4s, mix=0.38)
{auto_cutoff(cutoff_pad)}{auto_gain(pad)}  }}

  layer bell_arp : notes {{
    osc: pluck
    damping: 0.35
    brightness: 0.7
    gain: -18db
    env: a=0.004s d=0.5s s=0.0 r=0.5s
    notes: A4maj7 @ 0b for 8b, F#4min7 @ 8b for 8b, D5maj7 @ 16b for 8b, E5maj7 @ 24b for 8b
    arp: up rate=0.5b octaves=1 gate=0.7
    loop: 32b
    fx: bandpass(2400hz), reverb(decay=3.5s, mix=0.4), delay(time=0.375, feedback=0.3, mix=0.22)
{auto_gain(bell)}    pan: 0.22
  }}

  layer motif_far : notes {{
    osc: pluck
    damping: 0.6
    brightness: 0.45
    gain: -20db
{play_calls("road", 64, 64, 4, transposes=[" transpose +12st", " diatonic 1 transpose +12st"])}    loop: 0b
    fx: lowpass(2400hz), reverb(decay=3s, mix=0.3)
{auto_gain(bell)}    pan: -0.18
  }}

  master {{
    width: 0.9
    lufs: -16
    peak: -1.2db
    fadein: 1.5s
    fadeout: 2.5s
    fx: lowpass(11000hz), highpass(30hz), fdn(rt60=2.6, rt60_high=1.1, mix=0.2), saturate(amount=0.06, warmth=0.25)
  }}
}}
"""


# =============================================================================
# 05a / 05b — Road Game / Momentum (36:00-48:00, 720s split into two 360s halves)
# =============================================================================

def section_05a():
    dur = 360
    energy = [(0, 6), (1.0, 7)]
    kick = energy_env(dur, energy, -35, -8)
    clap = energy_env(dur, energy, -35, -13)
    hat = energy_env(dur, energy, -32, -16)
    bass = energy_env(dur, energy, -32, -9)
    stab = energy_env(dur, energy, -35, -13)
    lead = energy_env(dur, energy, -40, -13)
    cutoff_bass = energy_env(dur, energy, 350, 900, dp=0)

    return f"""# 05a — Road Game / Momentum, part I. Playful, syncopated, family energy —
# the "fun" section, not the "rave" section. 120 BPM nu-disco bounce.
asset s05a_road_game_pt1 {{
  kind: soundtrack
  duration: {dur}s
  tempo: 120bpm
  key: A major
  groove: pushed 0.15
  emotion: triumph=0.4, wonder=0.3, cinematic_intensity=0.3

  marker game_starts  @ 0s
  marker first_round   @ 120s
  marker second_round  @ 240s

{ROAD_MOTIF_A}
  bus pump {{
    duck: source=kick amount=6db attack=0.006s release=0.13s threshold=-38db
    fx: saturate(amount=0.1, warmth=0.2)
  }}

  layer kick : drums {{
    voice: kick
    pattern: X...X...X...X...
    tune: -3st
    decay: 0.45
    snap: 0.5
    bend: 0.3
    gain: -8db
    humanize: 0.03
{auto_gain(kick)}  }}

  layer clap : drums {{
    voice: clap
    pattern: ....X.......X.x.
    gain: -13db
    humanize: 0.05
    fx: reverb(decay=0.8s, mix=0.14)
{auto_gain(clap)}  }}

  layer hat : drums {{
    voice: hat
    pattern: x.xxx.x.x.xxx.x.
    tune: 2st
    decay: 0.25
    gain: -16db
    humanize: 0.05
{auto_gain(hat)}  }}

  layer bass : notes {{
    osc: square
    bus: pump
    gain: -9db
    env: a=0.003s d=0.1s s=0.3 r=0.06s
    velbright: 0.5
    notes: A1 @ 0b for 0.4b vel 0.85, A1 @ 0.75b for 0.3b vel 0.6, A2 @ 1.5b for 0.4b vel 0.75, F#1 @ 2b for 0.4b vel 0.85, F#1 @ 2.75b for 0.3b vel 0.6, F#2 @ 3.5b for 0.4b vel 0.75
    loop: 4b
    fx: lowpass(600hz), drive(amount=0.15)
{auto_cutoff(cutoff_bass)}{auto_gain(bass)}  }}

  layer stab : notes {{
    osc: square
    unison: 2
    spread: 10c
    bus: pump
    gain: -13db
    env: a=0.004s d=0.14s s=0.0 r=0.1s
    velbright: 0.5
    notes: A3maj7 @ 1b for 0.2b, D3maj7 @ 2.5b for 0.2b, E3maj7 @ 3.75b for 0.2b vel 0.9
    loop: 4b
    fx: bandpass(1600hz), delay(time=0.234, feedback=0.2, mix=0.18)
{auto_gain(stab)}  }}

  layer motif_bounce : notes {{
    osc: pluck
    damping: 0.35
    brightness: 0.65
    gain: -13db
    env: a=0.004s d=0.2s s=0.2 r=0.2s
{play_calls("road", 24, 24, 15, transposes=["", " vel 0.85", " diatonic 1"])}    loop: 0b
    fx: lowpass(2600hz), delay(time=0.187, feedback=0.22, mix=0.16)
{auto_gain(lead)}    pan: 0.15
  }}

  master {{
    width: 0.92
    lufs: -12.5
    peak: -1db
    fadein: 0.5s
    fadeout: 1s
    fx: lowpass(15000hz), highpass(28hz), fdn(rt60=1.5, rt60_high=0.8, mix=0.12), comp(threshold=-14, ratio=2.2, attack=0.012, release=0.14, knee=5), saturate(amount=0.12, warmth=0.24)
  }}
}}
"""


def section_05b():
    dur = 360
    energy = [(0, 7), (1.0, 8)]
    kick = energy_env(dur, energy, -30, -7)
    clap = energy_env(dur, energy, -30, -12)
    hat = energy_env(dur, energy, -28, -14)
    bass = energy_env(dur, energy, -28, -8)
    stab = energy_env(dur, energy, -32, -11)
    arp = energy_env(dur, energy, -35, -14)
    lead = energy_env(dur, energy, -35, -11)
    cutoff_bass = energy_env(dur, energy, 400, 1000, dp=0)

    return f"""# 05b — Road Game / Momentum, part II. The trip becomes active again;
# same game continues, denser and brighter, still tasteful — not a rave.
asset s05b_road_game_pt2 {{
  kind: soundtrack
  duration: {dur}s
  tempo: 121bpm
  key: A major
  groove: pushed 0.18
  emotion: triumph=0.5, wonder=0.3, cinematic_intensity=0.35

  marker bonus_round      @ 0s
  marker momentum_builds  @ 180s
  marker crest            @ 320s

{ROAD_MOTIF_A}
  bus pump {{
    duck: source=kick amount=6.5db attack=0.006s release=0.12s threshold=-37db
    fx: saturate(amount=0.12, warmth=0.22)
  }}

  layer kick : drums {{
    voice: kick
    pattern: X...X...X...X...
    tune: -3st
    decay: 0.45
    snap: 0.55
    bend: 0.3
    gain: -7db
    humanize: 0.03
{auto_gain(kick)}  }}

  layer clap : drums {{
    voice: clap
    pattern: ....X.x.....X.x.
    gain: -12db
    humanize: 0.05
    fx: reverb(decay=0.8s, mix=0.16)
{auto_gain(clap)}  }}

  layer hat : drums {{
    voice: hat
    pattern: x.xxx.x.x.xxx.xx
    tune: 2st
    decay: 0.25
    gain: -14db
    humanize: 0.05
{auto_gain(hat)}  }}

  layer bass : notes {{
    osc: square
    bus: pump
    gain: -8db
    env: a=0.003s d=0.1s s=0.3 r=0.06s
    velbright: 0.5
    notes: A1 @ 0b for 0.4b vel 0.9, A1 @ 0.75b for 0.3b vel 0.65, A2 @ 1.5b for 0.4b vel 0.8, D2 @ 2b for 0.4b vel 0.85, D2 @ 2.75b for 0.3b vel 0.6, E1 @ 3.5b for 0.4b vel 0.8
    loop: 4b
    fx: lowpass(650hz), drive(amount=0.18)
{auto_cutoff(cutoff_bass)}{auto_gain(bass)}  }}

  layer stab : notes {{
    osc: square
    unison: 3
    spread: 12c
    bus: pump
    gain: -11db
    env: a=0.004s d=0.16s s=0.0 r=0.12s
    velbright: 0.55
    notes: A3maj7 @ 1b for 0.2b, F#3min7 @ 2b for 0.2b, D3maj7 @ 2.75b for 0.2b, E3maj7 @ 3.5b for 0.2b vel 0.9
    loop: 4b
    fx: bandpass(1800hz), delay(time=0.234, feedback=0.22, mix=0.2)
{auto_gain(stab)}  }}

  layer arp : notes {{
    osc: pluck
    damping: 0.3
    brightness: 0.7
    gain: -14db
    env: a=0.004s d=0.3s s=0.0 r=0.2s
    notes: A3maj7 @ 0b for 4b, F#3min7 @ 4b for 4b, D3maj7 @ 8b for 4b, E3maj7 @ 12b for 4b
    arp: up rate=0.25b octaves=1 gate=0.75
    loop: 16b
    fx: bandpass(2600hz), delay(time=0.187, feedback=0.2, mix=0.15)
{auto_gain(arp)}    pan: -0.15
  }}

  layer motif_bounce : notes {{
    osc: pluck
    damping: 0.3
    brightness: 0.7
    gain: -11db
    env: a=0.004s d=0.2s s=0.25 r=0.2s
{play_calls("road", 8, 16, 22, transposes=["", " vel 0.9", " diatonic 1", " transpose +12st vel 0.85"])}    loop: 0b
    fx: lowpass(2800hz), delay(time=0.187, feedback=0.24, mix=0.18)
{auto_gain(lead)}    pan: 0.18
  }}

  master {{
    width: 0.94
    lufs: -12
    peak: -1db
    fadein: 0.3s
    fadeout: 1.5s
    fx: lowpass(16000hz), highpass(28hz), fdn(rt60=1.6, rt60_high=0.85, mix=0.13), comp(threshold=-13, ratio=2.3, attack=0.01, release=0.13, knee=5), saturate(amount=0.14, warmth=0.24)
  }}
}}
"""


# =============================================================================
# 06 — Big View / Mountain or Ocean Reveal  (48:00-57:00, 540s) — D major lift
# =============================================================================

def section_06():
    dur = 540
    energy = [(0, 8), (1.0, 9)]
    kick = energy_env(dur, energy, -22, -6)
    clap = energy_env(dur, energy, -22, -10)
    hat = energy_env(dur, energy, -20, -13)
    ohat = energy_env(dur, energy, -24, -16)
    bass = energy_env(dur, energy, -20, -8)
    pad = energy_env(dur, energy, -16, -9)
    lead = energy_env(dur, energy, -26, -8)
    cutoff_bass = energy_env(dur, energy, 500, 1100, dp=0)
    cutoff_lead = energy_env(dur, energy, 1400, 3000, dp=0)
    riser_g = [(0, -60), (dur - 10, -60), (dur - 8, -14), (dur - 1, -60)]

    return f"""# 06 — Big View / Mountain or Ocean Reveal. Everyone sees something
# beautiful outside. D major (the album's emotional lift). The road motif
# returns as the main theme, wide and bright but never harsh. 124 BPM.
asset s06_big_view {{
  kind: soundtrack
  duration: {dur}s
  tempo: 124bpm
  key: D major
  groove: pushed 0.12
  emotion: awe=0.7, triumph=0.6, wonder=0.5, cinematic_intensity=0.5

  marker the_reveal  @ 0s
  marker breath_taken @ 60s
  marker full_view    @ 300s
  marker held_gaze     @ 480s

{ROAD_MOTIF_D}
  bus pump {{
    duck: source=kick amount=5db attack=0.008s release=0.16s threshold=-36db
    fx: saturate(amount=0.1, warmth=0.24)
  }}
  bus air {{
    fx: delay(time=0.234, feedback=0.26, mix=0.18), hall(rt60=2.4, mix=0.2)
  }}

  layer intro_riser : sweep {{
    shape: saw
    from: 100hz
    to: 3000hz
    start: 0s
    duration: 6s
    gain: -20db
    env: a=5.5s d=0.1s s=0.9 r=0.5s
    curve: exp
  }}

  layer kick : drums {{
    voice: kick
    pattern: X...X...X...X...
    tune: -2st
    decay: 0.55
    snap: 0.5
    bend: 0.35
    gain: -6db
    humanize: 0.03
{auto_gain(kick)}  }}

  layer clap : drums {{
    voice: clap
    pattern: ....X.......X...
    gain: -10db
    humanize: 0.05
    fx: reverb(decay=1.4s, mix=0.22)
{auto_gain(clap)}  }}

  layer hat : drums {{
    voice: hat
    pattern: x.x.x.x.x.x.x.x.
    tune: 2st
    decay: 0.28
    gain: -13db
    humanize: 0.04
{auto_gain(hat)}  }}

  layer ohat : drums {{
    voice: open_hat
    pattern: ....x.......x...
    decay: 0.55
    gain: -16db
{auto_gain(ohat)}  }}

  layer bass : notes {{
    osc: saw
    bus: pump
    gain: -8db
    env: a=0.006s d=0.12s s=0.42 r=0.1s
    velbright: 0.4
    notes: D1 @ 0.5b for 0.45b, D1 @ 1.5b for 0.45b, D1 @ 2.5b for 0.45b, B1 @ 3.5b for 0.45b vel 0.85, B1 @ 4.5b for 0.45b, G1 @ 5.5b for 0.45b, G1 @ 6.5b for 0.45b, A1 @ 7.5b for 0.45b vel 0.9
    loop: 8b
    fx: lowpass(700hz), drive(amount=0.12)
{auto_cutoff(cutoff_bass)}{auto_gain(bass)}  }}

  layer pad : notes {{
    osc: pad
    bandwidth: 45c
    bus: pump
    gain: -12db
    env: a=1.2s d=1s s=0.85 r=2.2s
    notes: D3maj7 @ 0b for 8b voicing spread, B2min7 @ 8b for 8b voicing spread, G3maj7 @ 16b for 8b voicing spread, A3maj7 @ 24b for 8b voicing spread
    loop: 32b
    fx: lowpass(2200hz), reverb(decay=3.2s, mix=0.3)
{auto_gain(pad)}  }}

  layer lead : notes {{
    osc: saw
    unison: 5
    spread: 20c
    bus: air
    gain: -10db
    env: a=0.015s d=0.25s s=0.65 r=0.4s
    velbright: 0.4
{play_calls("road", 32, 16, 30, transposes=[""] * 2 + [" transpose +12st"] + [""] * 2 + [" vel 0.9"] + [" diatonic 1"])}    loop: 0b
    fx: lowpass(2600hz)
{auto_cutoff(cutoff_lead)}{auto_gain(lead)}    pan: 0.0
  }}

  layer outro_riser : sweep {{
    shape: triangle
    from: 3000hz
    to: 120hz
    start: {dur - 9}s
    duration: 8s
    gain: -22db
    env: a=6s d=0.2s s=0.85 r=1s
    curve: exp
  }}

  master {{
    width: 1.0
    lufs: -11
    peak: -1db
    fadein: 0.5s
    fadeout: 2s
    fx: lowpass(17000hz), highpass(26hz), fdn(rt60=2.6, rt60_high=1.2, mix=0.2), comp(threshold=-13, ratio=2.0, attack=0.015, release=0.18, knee=6), saturate(amount=0.1, warmth=0.28)
{auto_gain(riser_g)}  }}
}}
"""


# =============================================================================
# 07 — Rest Stop / Night Air  (57:00-64:00, 420s)
# =============================================================================

def section_07():
    dur = 420
    energy = [(0, 9), (0.12, 3), (1.0, 3)]
    pad = energy_env(dur, energy, -22, -13)
    shimmer = energy_env(dur, energy, -40, -20)
    noise_bed = energy_env(dur, energy, -50, -34)
    motif_g = [(0, -60), (60, -60), (75, -22), (140, -50), (220, -60), (240, -24),
               (300, -50), (380, -60), (400, -22), (dur, -50)]

    return f"""# 07 — Rest Stop / Night Air. Gas station lights, snacks, a quiet reset.
# No kick. Ambient, reflective — a rest, not a mystery. D major, sparse.
asset s07_rest_stop {{
  kind: soundtrack
  duration: {dur}s
  tempo: 80bpm
  key: D major
  emotion: calm=0.6, intimacy=0.5, wonder=0.3

  marker pulling_in   @ 0s
  marker snacks         @ 60s
  marker stretch_legs  @ 120s
  marker quiet_stars   @ 300s

{ROAD_MOTIF_D}
  layer night_air : noise {{
    color: pink
    start: 0s
    duration: {dur}s
    gain: -40db
    env: a=6s d=0.2s s=0.9 r=6s
    fx: bandpass(1200hz), highpass(300hz)
{auto_gain(noise_bed)}  }}

  layer pad : notes {{
    osc: pad
    bandwidth: 60c
    gain: -18db
    env: a=3s d=2s s=0.85 r=5s
    notes: D3maj7 @ 0b for 16b, B2min7 @ 16b for 16b, G3maj7 @ 32b for 16b, D3maj7 @ 48b for 16b
    loop: 64b
    fx: lowpass(900hz), reverb(decay=5s, mix=0.42)
{auto_gain(pad)}  }}

  layer shimmer : notes {{
    osc: triangle
    unison: 2
    spread: 8c
    gain: -22db
    env: a=1.5s d=1s s=0.7 r=2s
    notes: F#5 @ 0b for 8b vel 0.4, A5 @ 16b for 8b vel 0.4, D5 @ 32b for 8b vel 0.4, F#5 @ 48b for 8b vel 0.4
    loop: 64b
    fx: lowpass(4000hz), reverb(decay=4s, mix=0.4)
{auto_gain(shimmer)}    pan: 0.2
  }}

  layer motif_echo : notes {{
    osc: pluck
    damping: 0.65
    brightness: 0.4
    gain: -22db
{play_calls("road", 80, 160, 3, transposes=[" transpose -12st vel 0.55", " stretch 1.5"])}    loop: 0b
    fx: lowpass(1800hz), reverb(decay=4.5s, mix=0.45), delay(time=0.6, feedback=0.35, mix=0.25)
{auto_gain(motif_g)}    pan: -0.12
  }}

  master {{
    width: 0.88
    lufs: -20
    peak: -1.5db
    fadein: 2s
    fadeout: 3s
    fx: lowpass(8000hz), highpass(35hz), fdn(rt60=3.2, rt60_high=1.3, mix=0.24), saturate(amount=0.05, warmth=0.3)
  }}
}}
"""


# =============================================================================
# 08 — Golden Hour Drive  (64:00-73:00, 540s)
# =============================================================================

def section_08():
    dur = 540
    energy = [(0, 3), (1.0, 6)]
    kick = energy_env(dur, energy, -45, -13)
    perc = energy_env(dur, energy, -40, -20)
    bass = energy_env(dur, energy, -38, -12)
    pad = energy_env(dur, energy, -24, -14)
    lead = energy_env(dur, energy, -40, -13)
    cutoff_pad = energy_env(dur, energy, 500, 1600, dp=0)

    return f"""# 08 — Golden Hour Drive. Warm light, second wind, less machine more human.
# Home key returns (A major). Organic-feeling percussion, warm bass, 112 BPM.
asset s08_golden_hour {{
  kind: soundtrack
  duration: {dur}s
  tempo: 112bpm
  key: A major
  groove: swing16 0.1
  emotion: calm=0.4, intimacy=0.4, wonder=0.5, triumph=0.3

  marker engine_restarts @ 0s
  marker second_wind      @ 120s
  marker warm_light       @ 360s
  marker long_shadows     @ 480s

{ROAD_MOTIF_A}
  bus pump {{
    duck: source=kick amount=4db attack=0.012s release=0.2s threshold=-42db
    fx: saturate(amount=0.08, warmth=0.26)
  }}

  layer kick : drums {{
    voice: kick
    pattern: X.......X.......
    tune: -3st
    decay: 0.55
    snap: 0.3
    bend: 0.2
    gain: -13db
    humanize: 0.08
{auto_gain(kick)}  }}

  layer perc : drums {{
    voice: tom
    pattern: ..x...x...x...x.
    tune: -2st
    decay: 0.3
    gain: -20db
    humanize: 0.12
{auto_gain(perc)}  }}

  layer shaker : drums {{
    voice: hat
    pattern: x.x.x.x.x.x.x.x.
    tune: 1st
    decay: 0.25
    gain: -21db
    humanize: 0.1
{auto_gain(perc)}  }}

  layer bass : notes {{
    osc: saw
    bus: pump
    gain: -12db
    env: a=0.015s d=0.16s s=0.45 r=0.2s
    velbright: 0.35
    notes: A1 @ 0b for 1.8b vel 0.7, A1 @ 2b for 1.8b vel 0.55, F#1 @ 4b for 1.8b vel 0.7, F#1 @ 6b for 1.8b vel 0.55, D2 @ 8b for 1.8b vel 0.7, D2 @ 10b for 1.8b vel 0.55, E1 @ 12b for 1.8b vel 0.7, E1 @ 14b for 1.8b vel 0.6
    loop: 16b
    fx: lowpass(550hz), saturate(amount=0.1, warmth=0.32)
{auto_gain(bass)}  }}

  layer pad : notes {{
    osc: pad
    bandwidth: 45c
    gain: -18db
    env: a=1.5s d=1.2s s=0.82 r=2.2s
    notes: A2maj7 @ 0b for 16b, F#2min7 @ 16b for 16b, D3maj7 @ 32b for 16b, E3maj7 @ 48b for 16b
    loop: 64b
    fx: lowpass(1300hz), reverb(decay=3.4s, mix=0.32)
{auto_cutoff(cutoff_pad)}{auto_gain(pad)}  }}

  layer motif_return : notes {{
    osc: pluck
    damping: 0.45
    brightness: 0.55
    gain: -13db
    env: a=0.008s d=0.3s s=0.3 r=0.4s
{play_calls("road", 32, 32, 15, transposes=[""] * 2 + [" vel 0.85"] + [""] * 2 + [" diatonic 1"])}    loop: 0b
    fx: lowpass(2400hz), delay(time=0.31, feedback=0.24, mix=0.2), reverb(decay=2.6s, mix=0.24)
{auto_gain(lead)}    pan: 0.15
  }}

  master {{
    width: 0.9
    lufs: -14.5
    peak: -1db
    fadein: 1.5s
    fadeout: 2.5s
    fx: lowpass(13000hz), highpass(30hz), fdn(rt60=2.2, rt60_high=1.0, mix=0.18), comp(threshold=-16, ratio=1.8, attack=0.02, release=0.2, knee=6), saturate(amount=0.09, warmth=0.3)
  }}
}}
"""


# =============================================================================
# 09 — Arrival / One Last Look Back  (73:00-80:00, 420s)
# =============================================================================

def section_09():
    dur = 420
    pad = [(0, -18), (0.55 * dur, -14), (0.85 * dur, -20), (dur, -60)]
    kick_g = [(0, -13), (0.2 * dur, -13), (0.3 * dur, -50), (dur, -50)]
    motif_g = [(0, -60), (30, -14), (0.5 * dur, -12), (0.8 * dur, -18), (dur - 8, -50)]
    struck_g = [(0, -60), (0.6 * dur, -60), (0.65 * dur, -16), (dur - 6, -30), (dur, -55)]

    return f"""# 09 — Arrival / One Last Look Back. Tired but happy; the trip becomes a
# memory. Drums strip away, the road motif returns slower and warmer, then
# a soft struck/synth hybrid carries it to silence. Not "the party ended" —
# "we shared something."
asset s09_arrival {{
  kind: soundtrack
  duration: {dur}s
  tempo: 90bpm
  key: A major
  emotion: calm=0.55, intimacy=0.5, wonder=0.4, triumph=0.2

  marker last_stretch  @ 0s
  marker one_more_look  @ 180s
  marker home           @ 390s

{ROAD_MOTIF_A}
  layer kick : drums {{
    voice: kick
    pattern: X.......X.......
    tune: -4st
    decay: 0.5
    snap: 0.25
    bend: 0.15
    gain: -13db
    humanize: 0.09
{auto_gain(kick_g)}  }}

  layer pad : notes {{
    osc: pad
    bandwidth: 50c
    gain: -16db
    env: a=2.5s d=1.5s s=0.85 r=6s
    notes: A2maj7 @ 0b for 16b, F#2min7 @ 16b for 16b, D3maj7 @ 32b for 16b, A2maj7 @ 48b for 16b
    loop: 64b
    fx: lowpass(1200hz), reverb(decay=5s, mix=0.4)
    auto cutoff: 0s=1200, {round(0.7 * dur)}s=1400, {dur}s=500
{auto_gain(pad)}  }}

  layer motif_slow : notes {{
    osc: pluck
    damping: 0.5
    brightness: 0.5
    gain: -12db
    env: a=0.02s d=0.4s s=0.35 r=1.2s
{play_calls("road", 0, 16, 4)}
{play_calls("road", 96, 16, 3, transposes=[" stretch 1.5"])}
    loop: 0b
    fx: lowpass(2200hz), reverb(decay=3.5s, mix=0.32), delay(time=0.4, feedback=0.22, mix=0.2)
{auto_gain(motif_g)}    pan: 0.1
  }}

  layer struck_farewell : notes {{
    osc: struck
    tension: 0.15
    strike: 0.4
    damping: 0.5
    brightness: 0.45
    gain: -14db
    env: a=0.01s d=0.6s s=0.2 r=2s
    play road @ 152b stretch 2
    play road @ 168b stretch 2 diatonic -1
    loop: 0b
    fx: lowpass(2000hz), reverb(decay=6s, mix=0.45)
{auto_gain(struck_g)}    pan: -0.1
  }}

  master {{
    width: 0.9
    lufs: -18
    peak: -1.5db
    fadein: 1.5s
    fadeout: 10s
    fx: lowpass(9000hz), highpass(32hz), fdn(rt60=3.5, rt60_high=1.4, mix=0.26), saturate(amount=0.06, warmth=0.3)
  }}
}}
"""


SECTIONS = [
    ("s01_departure.af", section_01),
    ("s02_leaving_town.af", section_02),
    ("s03_highway_opens.af", section_03),
    ("s04_daydream.af", section_04),
    ("s05a_road_game_pt1.af", section_05a),
    ("s05b_road_game_pt2.af", section_05b),
    ("s06_big_view.af", section_06),
    ("s07_rest_stop.af", section_07),
    ("s08_golden_hour.af", section_08),
    ("s09_arrival.af", section_09),
]

if __name__ == "__main__":
    total = 0
    for fname, fn in SECTIONS:
        text = fn()
        path = OUT / fname
        path.write_text(text)
        print(f"wrote {path}")
        total += 1
    print(f"{total} files written to {OUT}/")
