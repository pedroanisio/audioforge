#!/usr/bin/env python3
"""Generate compositions/last_24h.af — a 10-minute techno arc charting the last
24 hours in the codebase: boot → first groove → build → the bug (breakdown) →
the fix ships (drop) → the joy (uplift) → the tools & the cover (breakdown 2) →
the concept paper (climax) → committed (outro).

128 BPM, A minor. Four-on-the-floor with a sidechained rolling bass (the pump),
acid squelch on a ladder filter, chord stabs, a supersaw lead motif, and
master filter sweeps at the transitions. All synth + drums, fully deterministic.
"""
from pathlib import Path

BPM = 128
DUR = 600                      # 320 bars, bar = 1.875s
LIB = None

# section boundaries in seconds
S = dict(boot=0, groove1=60, build1=150, break1=210, drop1=270,
         uplift=330, break2=420, climax=480, outro=570, end=600)


def env(pairs):
    """'auto <t>: 0s=v, ...' breakpoint string body."""
    return ", ".join(f"{int(round(t))}s={v}" for t, v in pairs)


# arrangement gain envelopes (seconds -> dB), shaping who plays when
KICK = [(0, -45), (16, -20), (40, -4), (150, -4), (206, -30), (210, -55),
        (266, -55), (270, -3), (330, -3.5), (416, -30), (420, -55),
        (476, -55), (480, -3), (566, -5), (588, -22), (600, -48)]
CLAP = [(0, -60), (60, -60), (74, -16), (150, -12), (208, -55), (270, -11),
        (330, -11), (418, -55), (480, -10), (566, -14), (594, -50)]
CHAT = [(0, -60), (30, -30), (60, -20), (90, -15), (150, -14), (210, -26),
        (240, -19), (270, -14), (330, -14), (420, -30), (480, -13),
        (566, -18), (596, -46)]
OHAT = [(0, -60), (150, -60), (152, -22), (210, -55), (270, -20), (330, -20),
        (420, -55), (480, -19), (566, -24), (596, -50)]
BASS = [(0, -55), (56, -55), (60, -8), (150, -7), (210, -55), (268, -55),
        (270, -6), (330, -6), (420, -55), (478, -55), (480, -6),
        (566, -9), (594, -40)]
PAD = [(0, -22), (40, -16), (60, -30), (150, -40), (210, -13), (250, -11),
       (270, -34), (330, -34), (420, -12), (460, -12), (480, -34),
       (560, -30), (570, -16), (600, -30)]
STAB = [(0, -60), (150, -60), (156, -16), (206, -40), (270, -13), (330, -13),
        (420, -40), (480, -11), (560, -13), (596, -46)]
ACID = [(0, -60), (150, -60), (168, -20), (206, -34), (210, -60), (270, -14),
        (312, -14), (330, -60), (480, -14), (556, -14), (596, -48)]
LEAD = [(0, -60), (330, -60), (338, -12), (360, -9), (418, -20), (420, -60),
        (480, -60), (496, -11), (540, -8), (566, -12), (592, -40)]


def gain_auto(pairs):
    return f"    auto gain: {env(pairs)}\n"


# --- lead motif: an 8-bar arpeggio that climbs — the "progress" theme -------
LEAD_NOTES = []
_seq = ["A3", "E4", "A4", "C5", "B4", "E4", "G4", "D5",
        "A3", "E4", "A4", "D5", "C5", "G4", "E4", "A4"]
for i, n in enumerate(_seq):
    LEAD_NOTES.append(f"{n} @ {i*0.5:g}b for 0.5b vel {0.7 + 0.02*(i%4)}")

AF = f"""# last_24h — a 10-minute techno arc of the last day in the codebase.
# 128 BPM · A minor · four-on-the-floor, sidechained bass, acid, stabs, lead.
# boot → groove → build → the bug (breakdown) → the fix (drop) → the joy
# (uplift) → tools & cover (breakdown) → the concept paper (climax) → committed.

asset last_24h {{
  kind: soundtrack
  duration: {DUR}s
  tempo: {BPM}bpm
  key: A minor
  groove: swing16 0.18
  emotion: urgency=0.5, triumph=0.45, cinematic_intensity=0.5, wonder=0.3

  marker boot       @ {S['boot']}s
  marker groove     @ {S['groove1']}s
  marker build      @ {S['build1']}s
  marker the_bug    @ {S['break1']}s
  marker the_fix    @ {S['drop1']}s
  marker the_joy    @ {S['uplift']}s
  marker the_tools  @ {S['break2']}s
  marker the_paper  @ {S['climax']}s
  marker committed  @ {S['outro']}s

  # sidechain bus — the techno pump: bass, stabs and pad ducked by the kick
  bus pump {{
    duck: source=kick amount=7db attack=0.006s release=0.15s threshold=-42db
    fx: saturate(amount=0.12, warmth=0.2)
  }}
  # shared space for stabs and lead
  bus air {{
    fx: delay(time=0.234, feedback=0.28, mix=0.16), hall(rt60=1.8, mix=0.12)
  }}

  # --- drums ---------------------------------------------------------------
  layer kick : drums {{
    voice: kick
    pattern: X...X...X...X...
    tune: -5st
    decay: 0.55
    snap: 0.55
    bend: 0.4
    gain: -3db
    humanize: 0.04
{gain_auto(KICK)}  }}

  layer clap : drums {{
    voice: clap
    pattern: ....X.......X...
    gain: -11db
    humanize: 0.06
    fx: reverb(decay=1.1s, mix=0.18)
{gain_auto(CLAP)}  }}

  layer chats : drums {{
    voice: hat
    pattern: ..x.x.x.x.x.x.x.
    tune: 2st
    decay: 0.3
    gain: -15db
    humanize: 0.05
{gain_auto(CHAT)}  }}

  layer ohat : drums {{
    voice: open_hat
    pattern: ....x.......x...
    decay: 0.6
    gain: -19db
{gain_auto(OHAT)}  }}

  # --- rolling sidechained bass (offbeat) ----------------------------------
  layer bass : notes {{
    osc: saw
    bus: pump
    gain: -6db
    env: a=0.004s d=0.11s s=0.35 r=0.06s
    velbright: 0.5
    notes: A1 @ 0.5b for 0.45b, A1 @ 1.5b for 0.45b, A1 @ 2.5b for 0.45b, A1 @ 3.5b for 0.45b, G1 @ 3b for 0.4b vel 0.8
    loop: 4b
    fx: lowpass(700hz), drive(amount=0.25)
    auto cutoff: 0s=260, 60s=520, 150s=1100, 210s=300, 270s=900, 330s=1300, 420s=320, 480s=1500, 570s=520, 600s=280
  }}

  # --- atmospheric pad (breakdowns), sidechained ---------------------------
  layer pad : notes {{
    osc: pad
    bus: pump
    bandwidth: 60c
    gain: -14db
    env: a=1.6s d=1.2s s=0.85 r=3s
    notes: A2 @ 0b for 16b, C3 @ 0b for 16b, E3 @ 0b for 16b, A3 @ 0b for 16b, G3 @ 8b for 8b
    loop: 16b
    fx: lowpass(2200hz), reverb(decay=4s, mix=0.4)
    auto cutoff: 0s=700, 210s=1900, 270s=800, 420s=2200, 480s=800, 570s=1600, 600s=900
{gain_auto(PAD)}  }}

  # --- chord stabs (syncopated), through air + pump ------------------------
  layer stab : notes {{
    osc: square
    unison: 3
    spread: 18c
    bus: pump
    gain: -13db
    env: a=0.004s d=0.16s s=0.0 r=0.14s
    velbright: 0.6
    notes: A3min7 @ 1b for 0.2b, A3min7 @ 2.5b for 0.2b, F3maj7 @ 3b for 0.2b vel 0.9, A3min7 @ 3.75b for 0.2b
    loop: 4b
    fx: bandpass(1400hz), delay(time=0.351, feedback=0.24, mix=0.2)
{gain_auto(STAB)}  }}

  # --- acid line (ladder filter squelch) -----------------------------------
  layer acid : notes {{
    osc: saw
    gain: -13db
    env: a=0.003s d=0.09s s=0.25 r=0.04s
    notes: A2 @ 0b for 0.24b, A2 @ 0.5b for 0.24b vel 0.9, A3 @ 1b for 0.24b, C3 @ 1.5b for 0.24b, A2 @ 2b for 0.24b, E3 @ 2.5b for 0.24b, A2 @ 3b for 0.24b vel 1.0, G2 @ 3.5b for 0.24b
    loop: 4b
    fx: ladder(cutoff=350, resonance=0.82, drive=0.5)
    auto cutoff: 150s=280, 206s=3200, 270s=500, 300s=3600, 312s=600, 480s=600, 520s=4200, 556s=700
{gain_auto(ACID)}  }}

  # --- supersaw lead motif — the progress theme (uplift + climax) ----------
  layer lead : notes {{
    osc: saw
    unison: 6
    spread: 22c
    bus: air
    gain: -13db
    env: a=0.01s d=0.2s s=0.6 r=0.3s
    velbright: 0.5
    notes: {", ".join(LEAD_NOTES)}
    loop: 8b
    fx: lowpass(3200hz)
    auto cutoff: 330s=1400, 360s=3600, 420s=1200, 480s=1600, 520s=4200, 566s=2000
{gain_auto(LEAD)}  }}

  # --- transition risers into the drops ------------------------------------
  layer riser_fix : sweep {{
    shape: saw
    from: 120hz
    to: 5000hz
    start: 262s
    duration: 8s
    gain: -18db
    env: a=7s d=0.1s s=0.95 r=0.8s
    curve: exp
  }}
  layer riser_paper : sweep {{
    shape: saw
    from: 140hz
    to: 6000hz
    start: 472s
    duration: 8s
    gain: -17db
    env: a=7.5s d=0.1s s=0.95 r=0.5s
    curve: exp
  }}
  layer noise_lift : noise {{
    color: white
    start: 200s
    duration: 12s
    gain: -30db
    env: a=9s d=0.1s s=0.9 r=2s
    fx: bandpass(3000hz), highpass(1200hz)
  }}

  master {{
    width: 0.92
    lufs: -9
    peak: -1db
    fadein: 0.5s
    fadeout: 6s
    fx: lowpass(19000hz), highpass(28hz), fdn(rt60=1.5, rt60_high=0.9, mix=0.07), comp(threshold=-14, ratio=2.2, attack=0.01, release=0.12, knee=5), saturate(amount=0.12, warmth=0.25)
    auto cutoff: 0s=1400, 40s=19000, 200s=19000, 235s=650, 270s=19000, 410s=19000, 445s=700, 480s=19000, 570s=19000, 596s=2200
  }}
}}
"""

Path("compositions/last_24h.af").write_text(AF)
print("wrote compositions/last_24h.af",
      f"({DUR}s · {BPM}bpm · {int(DUR/(240/BPM))} bars)")
