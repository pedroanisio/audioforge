#!/usr/bin/env python3
"""Generate `docs/examples/jazz/blue-in-five/blue_in_five.af` — a ~5 minute medium-swing jazz quartet.

A 16-bar form in F major, looped by the rhythm section, with *composed*
solos (idiomatic chord-relative licks with rests and phrasing — not
arpeggiators).  Voices: tenor = `blown` reed, vibes = `modal` bell, comp =
`fm` Rhodes, walking bass = `pluck`, plus a brushed swing kit.  Harmony of
the bass walk and the solo licks is realised through `audioforge.theory`,
so every note lands on a real chord/scale tone.

Map (132 bpm, 16-bar/64-beat form):
  intro 0-7 · head 8-23 · tenor solo 24-71 (3 chr) · vibes solo 72-135
  (4 chr) · head out 136-151 · outro/ritard 152+
"""
from pathlib import Path

from audioforge import theory

OUT = "docs/examples/jazz/blue-in-five/blue_in_five.af"
SN = theory.semis_to_note


def pc_of(name):
    return theory.note_to_semis(name + "3") % 12


def near(pc, center):
    best = None
    for k in range(-3, 4):
        val = pc + 12 * ((center // 12) + k)
        if best is None or abs(val - center) < abs(best - center):
            best = val
    return best


# ---- 16-bar changes.  Each bar -> [(root, quality, start_beat, dur), ...] ----
CHANGES = [
    [("F", "maj7", 0, 4)], [("D", "min7", 0, 4)],
    [("G", "min7", 0, 4)], [("C", "7", 0, 4)],
    [("A", "min7", 0, 4)], [("D", "7", 0, 4)],
    [("G", "min7", 0, 4)], [("C", "7", 0, 4)],
    [("F", "maj7", 0, 4)], [("A", "7", 0, 4)],
    [("D", "min7", 0, 4)], [("G", "7", 0, 4)],
    [("G", "min7", 0, 4)], [("C", "7", 0, 4)],
    [("A", "min7", 0, 2), ("D", "7", 2, 2)],
    [("G", "min7", 0, 2), ("C", "7", 2, 2)],
]


def family(q):
    if q in ("maj", "maj7", "maj9", "6", "add9"):
        return "maj7"
    if q in ("7", "9"):
        return "dom7"
    return "min7"


# ---- Idiomatic licks: (semitone-offset-from-root, start-in-bar, dur, vel) ----
# Every offset is a chord/scale tone (or a named chromatic passing/enclosure
# tone), so a lick is correct over any chord of its family.
LICKS = {
    "maj7": [
        [(7, 0, .5, .66), (9, .5, .5, .64), (11, 1, .5, .70),
         (12, 1.5, .5, .68), (14, 2, 1, .72)],                      # 5-6-7-1-9, rest
        [(0, 0, 1, .66), (4, 1, .5, .64), (7, 1.5, .5, .68),
         (11, 2, 1, .72), (9, 3, 1, .64)],                          # 1-3-5-7-6
        [(12, 0, 1, .70), (11, 1, .5, .64), (9, 1.5, .5, .66),
         (7, 2, 2, .68)],                                           # 8-7-6-5, hold
    ],
    "min7": [
        [(0, 0, .5, .66), (2, .5, .5, .64), (3, 1, .5, .68),
         (5, 1.5, .5, .66), (7, 2, .5, .72), (9, 2.5, .5, .68),
         (10, 3, 1, .70)],                                          # dorian run up
        [(10, 0, .5, .68), (9, .5, .5, .64), (7, 1, .5, .70),
         (5, 1.5, .5, .66), (3, 2, 1, .72)],                        # b7-6-5-4-b3, rest
        [(2, 0, .5, .62), (4, .5, .5, .62), (3, 1, 1, .72),
         (7, 2, .5, .66), (10, 2.5, .5, .68), (12, 3, 1, .70)],     # enclose b3, 5-b7-1
    ],
    "dom7": [
        [(4, 0, .5, .68), (5, .5, .5, .64), (7, 1, .5, .68),
         (9, 1.5, .5, .66), (10, 2, .5, .72), (11, 2.5, .5, .60),
         (12, 3, .5, .70), (14, 3.5, .5, .66)],                     # bebop 3-4-5-6-b7-7-1-9
        [(5, 0, .5, .62), (3, .5, .5, .62), (4, 1, 1, .72),
         (10, 2, .5, .66), (7, 2.5, .5, .64), (4, 3, 1, .68)],      # enclose 3, b7-5-3
        [(14, 0, .5, .70), (12, .5, .5, .66), (11, 1, .5, .64),
         (10, 1.5, .5, .66), (9, 2, .5, .68), (7, 2.5, .5, .64),
         (4, 3, 1, .70)],                                           # 9-1-7-b7-6-5-3
    ],
}

BASS_C = theory.note_to_semis("F2")
TEN_C = theory.note_to_semis("F4")
VIB_C = theory.note_to_semis("C5")


def ev(p, b, d, v):
    return f"{p} @ {round(b, 3)}b for {d}b vel {round(min(0.95, v), 3)}"


def slur(notes):
    return "slur(" + ", ".join(ev(*n) for n in notes) + ")"


# ---- Walking bass: chord tones + chromatic approach to the next root --------
def bass_notes():
    out = []
    for bar in range(16):
        base = bar * 4
        segs = CHANGES[bar]
        nxt = pc_of(CHANGES[(bar + 1) % 16][0][0])
        appr = near(nxt, BASS_C) - 1
        if len(segs) == 1:
            root, q, _, _ = segs[0]
            r = near(pc_of(root), BASS_C)
            ints = theory.CHORD_QUALITIES[q]
            seq = [(r, 0, .6), (r + ints[1], 1, .52),
                   (r + ints[2], 2, .6), (appr, 3, .5)]
        else:
            (r0n, q0, _, _), (r1n, _, _, _) = segs
            r0 = near(pc_of(r0n), BASS_C)
            r1 = near(pc_of(r1n), BASS_C)
            seq = [(r0, 0, .6), (r0 + theory.CHORD_QUALITIES[q0][2], 1, .52),
                   (r1, 2, .6), (appr, 3, .5)]
        for semi, bt, v in seq:
            out.append(ev(SN(semi), base + bt, 0.92, v))
    return out


# ---- Comp: syncopated drop-2 stabs -----------------------------------------
def comp_notes():
    out = []
    for bar in range(16):
        base = bar * 4
        segs = CHANGES[bar]
        if len(segs) == 1:
            root, q, _, _ = segs[0]
            tok = f"{root}3{q}"
            out.append(f"{tok} @ {base}b for 1.4b vel 0.42 voicing drop2")
            out.append(f"{tok} @ {base + 2.5}b for 1.0b vel 0.34 voicing drop2")
        else:
            for root, q, sb, _ in segs:
                out.append(f"{root}3{q} @ {base + sb}b for 1.5b vel 0.4 voicing drop2")
    return out


# ---- Composed solo from the lick bank, with rests for phrasing --------------
def solo(start, choruses, dens, center, velscales, pick=0):
    out = []
    for c in range(choruses):
        for bar in range(16):
            if not dens[c][bar]:
                continue
            root, q = CHANGES[bar][0][0], CHANGES[bar][0][1]
            variants = LICKS[family(q)]
            lk = variants[(c * 16 + bar + pick) % len(variants)]
            r = near(pc_of(root), center)
            bstart = start + (c * 16 + bar) * 4
            vs = velscales[c]
            out.append(slur([(SN(r + off), bstart + sb, d, v * vs)
                             for off, sb, d, v in lk]))
    return out


TEN_DENS = [
    [1, 1, 0, 1, 0, 1, 1, 0, 1, 1, 0, 1, 1, 0, 1, 1],
    [1, 1, 1, 0, 1, 1, 0, 1, 1, 0, 1, 1, 1, 1, 0, 1],
    [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
]
VIB_DENS = [
    [1, 0, 0, 1, 0, 0, 1, 0, 1, 0, 0, 1, 0, 0, 1, 0],
    [1, 0, 1, 0, 1, 0, 1, 0, 0, 1, 0, 1, 0, 1, 0, 1],
    [1, 1, 0, 1, 0, 1, 1, 0, 1, 1, 0, 1, 1, 0, 1, 0],
    [1, 0, 1, 1, 0, 1, 0, 1, 1, 1, 0, 1, 0, 1, 1, 1],
]

# ---- The head: a composed 16-bar tune, four 4-bar phrases -------------------
HEAD = [
    [("A4", 0, 1, .70), ("C5", 1, 1, .72), ("F5", 2, 2, .80),
     ("E5", 4, 1, .72), ("D5", 5, 1, .70), ("A4", 6, 2, .68),
     ("Bb4", 8, 1, .70), ("D5", 9, 1, .72), ("G5", 10, 1, .76), ("F5", 11, 1, .70),
     ("E5", 12, 1.5, .74), ("D5", 13.5, .5, .66), ("C5", 14, 2, .70)],
    [("C5", 16, 1, .72), ("E5", 17, 1, .76), ("A5", 18, 2, .84),
     ("F#5", 20, 1, .78), ("A5", 21, 1, .74), ("G5", 22, 1, .72), ("E5", 23, 1, .70),
     ("D5", 24, 1, .72), ("Bb4", 25, 1, .70), ("G4", 26, 2, .66),
     ("G4", 28, 1, .66), ("A4", 29, 1, .68), ("C5", 30, 1, .72), ("E5", 31, 1, .74)],
    [("F5", 32, 1, .74), ("A5", 33, 1, .80), ("C6", 34, 2, .86),
     ("C#6", 36, 1, .78), ("B5", 37, 1, .74), ("A5", 38, 2, .74),
     ("D6", 40, 1, .78), ("A5", 41, 1, .72), ("F5", 42, 1, .70), ("D5", 43, 1, .70),
     ("B5", 44, 1, .74), ("A5", 45, 1, .72), ("G5", 46, 1, .70), ("F5", 47, 1, .68)],
    [("Bb5", 48, 1, .74), ("A5", 49, 1, .72), ("G5", 50, 1, .70), ("D5", 51, 1, .68),
     ("E5", 52, 1.5, .74), ("G5", 53.5, .5, .70), ("Bb5", 54, 2, .76),
     ("A5", 56, 1, .74), ("G5", 57, 1, .70), ("F#5", 58, 1, .70), ("A5", 59, 1, .72),
     ("G5", 60, 1, .70), ("F5", 61, 1, .68), ("E5", 62, 1, .66), ("C5", 63, 1, .66)],
]


def head_notes(offset, vs=1.0):
    return [slur([(p, b + offset, d, v * vs) for p, b, d, v in ph]) for ph in HEAD]


HEAD_IN, SOLO_T, SOLO_V, HEAD_OUT = 32, 96, 288, 544

tenor = (head_notes(HEAD_IN)
         + solo(SOLO_T, 3, TEN_DENS, TEN_C, [0.92, 0.99, 1.06])
         + head_notes(HEAD_OUT)
         + [ev("F4", 624, 8, 0.42), ev("A4", 624, 8, 0.40), ev("C5", 624, 8, 0.40)])
vibes = solo(SOLO_V, 4, VIB_DENS, VIB_C, [0.85, 0.9, 0.98, 1.03], pick=1)


def fmt(items, indent=11):
    pad = " " * indent
    return (",\n" + pad).join(items)


AF = f"""# "Blue in Five" — a ~5 minute medium-swing jazz quartet (AudioForge DSL).
# 16-bar form in F major; the rhythm section loops it while a *composed* tenor
# and vibraphone trade choruses.  Solos are idiomatic chord-relative licks with
# rests and phrasing (no arpeggiators).  Arrangement is `auto gain`-driven.
# Generated by scripts/gen_jazz.py — edit the script, not this file.
asset blue_in_five {{
  kind: soundtrack
  duration: 300s
  samplerate: 48000
  bitdepth: 24
  tempo: 132bpm, 600b=132bpm, 616b=122bpm, 640b=104bpm, 660b=92bpm
  key: F major
  groove: shuffle 0.6
  emotion: awe=0.3, wonder=0.5, calm=0.4, intimacy=0.4
  intensity: 0s=0.22, 14s=0.42, 44s=0.6, 120s=0.85, 175s=0.8, 240s=0.7, 276s=0.5, 300s=0.12

  marker intro      @ 0s
  marker head_in    @ 14s
  marker tenor_solo @ 44s
  marker vibes_solo @ 131s
  marker head_out   @ 247s
  marker outro      @ 276s

  # shared club room — fdn is true-stereo on a bus, so it widens the image
  bus club {{
    gain: -1db
    fx: fdn(rt60=2.0, rt60_high=1.3, crossover=2600, size=1.05, mix=0.16),
        peak(2600hz, gain=0.6, q=0.7),
        lowshelf(160hz, gain=-1.0)
  }}

  # ---- WALKING BASS: upright-ish pluck, quarter notes, whole track ----
  layer bass : notes {{
    osc: pluck
    damping: 0.6
    brightness: 0.34
    pluckpos: 0.14
    gain: -6db
    pan: -0.06
    bus: club
    env: a=0.005s d=0.4s s=0.35 r=0.3s
    humanize: time=0.015s vel=0.07
    notes: {fmt(bass_notes())}
    loop: 64b
    fx: lowpass(2000hz)
    auto gain: 0s=-11db, 12s=-7db, 250s=-7db, 285s=-8db, 300s=-15db
  }}

  # ---- PIANO COMP: FM Rhodes (real modulation index), drop-2 stabs ----
  layer comp : notes {{
    osc: fm
    fmratio: 1
    fmindex: 1.4
    gain: -13db
    pan: 0.28
    bus: club
    env: a=0.005s d=0.6s s=0.35 r=0.5s
    velbright: 0.5
    humanize: time=0.018s vel=0.08
    notes: {fmt(comp_notes())}
    loop: 64b
    fx: lowpass(3800hz), delay(time=0.27s, feedback=0.18, mix=0.1)
    auto gain: 0s=-60db, 8s=-15db, 30s=-13db, 250s=-13db, 276s=-14db, 300s=-22db
  }}

  # ---- RIDE: spang-a-lang swung pattern, whole track ----
  layer ride : drums {{
    voice: hat
    pattern: X...X.X.X...X.X.
    tune: 2st
    decay: 0.6
    gain: -16db
    pan: 0.34
    humanize: 0.4
    fx: highpass(1500hz)
    auto gain: 0s=-19db, 12s=-15db, 44s=-13db, 250s=-14db, 300s=-22db
  }}

  # ---- BRUSHES: soft backbeat on 2 and 4 ----
  layer snare : drums {{
    voice: snare
    pattern: ....X.......X...
    decay: 0.5
    gain: -17db
    pan: -0.26
    humanize: 0.45
    fx: highpass(320hz), reverb(decay=0.9, mix=0.14)
    auto gain: 0s=-60db, 16s=-18db, 44s=-15db, 130s=-14db, 250s=-15db, 300s=-26db
  }}

  # ---- KICK: feathered four-on-the-floor, very low ----
  layer kick : drums {{
    voice: kick
    pattern: X...X...X...X...
    tune: -2st
    decay: 0.9
    gain: -22db
    humanize: 0.3
    auto gain: 0s=-30db, 30s=-24db, 130s=-22db, 300s=-30db
  }}

  # ---- TENOR: states the head, takes 3 choruses, restates, tags the end ----
  layer tenor : notes {{
    osc: blown
    pressure: 0.7
    brightness: 0.62
    gain: -5db
    pan: -0.12
    bus: club
    env: a=0.035s d=0.2s s=0.85 r=0.3s
    velbright: 0.55
    phrasing: 0.6
    humanize: time=0.017s vel=0.08
    notes: {fmt(tenor)}
    fx: reverb(decay=1.6, mix=0.16)
    auto gain: 0s=-60db, 13s=-5db, 44s=-7db, 80s=-5db, 125s=-4db, 131s=-7db, 140s=-60db, 245s=-60db, 247s=-5db, 276s=-6db, 281s=-60db, 283s=-9db, 300s=-16db
  }}

  # ---- VIBES: 4-chorus solo, sparser and longer-lined ----
  layer vibes : notes {{
    osc: modal
    material: bell
    modedecay: 1.6s
    gain: -11db
    pan: 0.22
    bus: club
    velbright: 0.5
    phrasing: 0.5
    humanize: time=0.02s vel=0.1
    notes: {fmt(vibes)}
    fx: delay(time=0.36s, feedback=0.2, mix=0.16)
    auto gain: 0s=-60db, 128s=-60db, 132s=-13db, 175s=-10db, 240s=-12db, 247s=-60db
  }}

  master {{
    width: 0.95
    lufs: -15
    peak: -1db
    fadein: 1.0s
    fadeout: 7s
    fx: highpass(26hz),
        lowshelf(120hz, gain=2.2),
        peak(300hz, gain=-0.8, q=1.0),
        comp(threshold=-17, ratio=1.6, attack=0.03, release=0.28, knee=10, makeup=1),
        highshelf(9000hz, gain=0.6),
        saturate(amount=0.06, warmth=0.6)
  }}
}}
"""

Path(OUT).parent.mkdir(parents=True, exist_ok=True)
with open(OUT, "w") as f:
    f.write(AF)
print(f"wrote {OUT} ({len(AF)} bytes)")
